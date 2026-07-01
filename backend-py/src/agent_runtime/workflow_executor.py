"""Dynamic workflow executor - executes workflows based on workflow definition."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any

import structlog

from src.agent_runtime.state import AgentState, create_initial_state
from src.application.workflows.service import WorkflowExpressionService
from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.expressions.evaluator import evaluate as evaluate_expression
from src.application.agents.message import AgentMessage
from src.infrastructure.llm.factory import LLMFactory, get_llm_factory
from src.infrastructure.mcp.registry import McpToolRegistry, get_mcp_registry
from src.infrastructure.conversation.store import (
    ConversationContext,
    IAgentConversationStore,
    get_conversation_store,
)
from src.infrastructure.diagnostics.store import (
    IAgentDiagnosticsStore,
    get_diagnostics_store,
)
from src.application.agents.run_result import (
    AgentIterationTrace,
    AgentRunResult,
    AgentStepExecutionResult,
    AgentToolCall,
    LLMCallConfig,
    _fingerprint_api_key,
)

logger = structlog.get_logger(__name__)


class _NoOpSink:
    """Internal default sink used by ``execute_stream``.

    Lives next to the executor so the streaming path doesn't have to
    import the protocol module just to construct a no-op default.
    Externally, callers should import ``NoOpProgressSink`` from
    ``src.agent_runtime.progress_sink`` if they need one.
    """

    async def step_start(self, **_kwargs: Any) -> None:
        return None

    async def step_complete(self, **_kwargs: Any) -> None:
        return None

    async def run_complete(self, _run_result: Any) -> None:
        return None

    async def iteration(self, **_kwargs: Any) -> None:
        return None

    async def tool_call(self, **_kwargs: Any) -> None:
        return None


def _resolve_outcome_name(
    resolved_step: dict[str, Any],
    output: Any,
    next_step_name: str | None,
) -> str | None:
    """Return the name of the outcome that was selected for this step.

    Mirrors what ``DefaultAgentRunner`` does in the .NET backend: pick
    the first outcome whose ``nextStep`` matches the routing target
    (or whose ``endWorkflow`` flag is set). ``None`` if the step has
    no outcomes defined.
    """
    outcomes = resolved_step.get("outcomes") or []
    if not outcomes:
        return None

    end_workflow = next_step_name is None

    for raw in outcomes:
        outcome = raw if isinstance(raw, dict) else {}
        name = outcome.get("name")
        if not isinstance(name, str):
            continue
        candidate_next = outcome.get("nextStep")
        candidate_end = bool(outcome.get("endWorkflow"))
        if end_workflow and candidate_end:
            return name
        if not end_workflow and candidate_next == next_step_name:
            return name

    return None


def _with_step_error(
    step: AgentStepExecutionResult,
    message: str,
) -> AgentStepExecutionResult:
    """Return a copy of ``step`` annotated with an error message.

    The .NET ``AgentStepExecutionResult`` doesn't carry a free-form
    error field, so we surface the failure via the existing
    ``toolErrorDetected`` flag and a synthetic tool call. This keeps
    the JSON shape (and the SPA's expectations) stable while still
    letting the UI render a useful error message for the step.
    """
    from dataclasses import replace

    synthetic_tool = AgentToolCall(
        tool_name="__step_error__",
        invocation_id=None,
        result=None,
        arguments_json=None,
        error_message=message,
    )
    return replace(
        step,
        tool_invocations=[*step.tool_invocations, synthetic_tool],
        tool_error_detected=True,
    )


def _llm_config_to_snake_dict(config: LLMCallConfig) -> dict[str, Any]:
    """Return ``config`` as a plain dict with snake_case keys.

    ``LLMCallConfig.from_dict`` consumes snake_case (the dataclass
    field names) while ``to_dict`` emits camelCase for the wire.
    The workflow executor persists the snapshot into
    ``step_outputs`` (an internal dict) and rebuilds it after the
    loop, so we use snake_case here to keep the round-trip
    self-consistent with the surrounding fields (``resolved_parameters``
    / ``parameter_debug`` / ``variable_debug``).
    """
    from dataclasses import asdict

    return asdict(config)


class WorkflowExecutor:
    """Executes dynamic workflows based on agent step definitions.

    Handles:
    - Multi-step workflow execution with outcomes (branching/looping)
    - Expression resolution before each step
    - Step output chaining for lastOutput access
    - Progress event emission aligned with workflow steps
    - Variable management across steps
    - Step types: agent, setVariables, echo
    - MCP tool integration for agent steps
    - Conversation history for multi-turn interactions
    """

    def __init__(
        self,
        llm_factory: LLMFactory | None = None,
        expression_service: WorkflowExpressionService | None = None,
        mcp_registry: McpToolRegistry | None = None,
        conversation_store: IAgentConversationStore | None = None,
        diagnostics_store: IAgentDiagnosticsStore | None = None,
    ) -> None:
        self._llm_factory = llm_factory or get_llm_factory()
        self._expression_service = expression_service or WorkflowExpressionService()
        self._mcp_registry = mcp_registry or get_mcp_registry()
        self._conversation_store = conversation_store or get_conversation_store()
        self._diagnostics_store = diagnostics_store or get_diagnostics_store()

    async def execute(
        self,
        agent_definition: dict[str, Any],
        input_text: str,
        parameters: dict[str, Any] | None = None,
        progress_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Execute a workflow based on agent definition.

        Args:
            agent_definition: Full agent definition dict
            input_text: User input
            parameters: Runtime parameters
            progress_callback: Optional async callback for progress events

        Returns:
            Execution result with output and metadata
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()

        steps = agent_definition.get("steps", [])
        if not steps:
            raise ValueError("Agent has no steps defined")

        # Initialize MCP tools from agent definition
        mcp_tools = {}
        try:
            mcp_tools = await self._mcp_registry.initialize_from_agent(agent_definition)
        except Exception as e:
            logger.warning("mcp_init_skipped", error=str(e))

        # Find start step
        start_step_name = self._find_start_step(steps)
        if not start_step_name:
            start_step_name = steps[0].get("name")

        # Build step index
        step_index = {s.get("name"): s for s in steps}

        # Initialize variables
        variables: dict[str, Any] = {}
        context = self._build_expression_context(
            variables=variables,
            parameters=parameters or {},
            input=input_text,
            step_outputs={},
        )

        # Emit start event
        if progress_callback:
            await progress_callback({
                "event_type": "start",
                "run_id": run_id,
                "start_step": start_step_name,
            })

        # Execute workflow
        try:
            variables, step_outputs = await self._execute_workflow(
                steps=steps,
                step_index=step_index,
                start_step_name=start_step_name,
                input_text=input_text,
                parameters=parameters or {},
                context=context,
                progress_callback=progress_callback,
                run_id=run_id,
                agent_definition=agent_definition,
                mcp_tools=mcp_tools,
            )
        finally:
            # Cleanup MCP connections
            await self._mcp_registry.disconnect_all()

        # Get final output
        final_output = ""
        if step_outputs:
            last_step_id = list(step_outputs.keys())[-1]
            final_output = step_outputs[last_step_id].get("output", "")

        duration_ms = int((time.time() - start_time) * 1000)

        result = {
            "run_id": run_id,
            "status": "complete",
            "output": final_output,
            "duration_ms": duration_ms,
            "steps": step_outputs,
            "variables": variables,
        }

        if progress_callback:
            await progress_callback({
                "event_type": "complete",
                "run_id": run_id,
                "final_output": final_output,
                "total_duration_ms": duration_ms,
            })

        # Build and save run result to diagnostics store
        agent_id = agent_definition.get("id", agent_definition.get("name", "unknown"))
        step_results = []
        for step_name, step_data in step_outputs.items():
            step_result = AgentStepExecutionResult(
                name=step_name,
                type=step_data.get("type", "unknown"),
                output=step_data.get("output", ""),
            )
            step_results.append(step_result)

        run_result = AgentRunResult(
            agent_id=agent_id,
            status="completed",
            steps=step_results,
            conversation_id=None,  # Could be set from conversation context if available
        )

        # Save to diagnostics store if conversation_id is available
        if run_result.conversation_id:
            await self._diagnostics_store.save_run(run_result.conversation_id, run_result)

        return result

    async def execute_stream(
        self,
        agent_definition: dict[str, Any],
        input_text: str,
        parameters: dict[str, Any] | None = None,
        progress_sink: Any | None = None,
        conversation_id: str | None = None,
    ) -> AgentRunResult:
        """Execute a workflow while pushing progress events to a sink.

        The non-streaming ``execute()`` path also accepts a progress
        callback; this method is the streaming equivalent. Instead of
        yielding a stream of dicts (the old wire format), it calls
        ``step_start``/``step_complete``/``run_complete`` on the
        supplied ``progress_sink``. The .NET backend's
        ``StreamingAgentRunProgressSink`` is the canonical
        implementation; ``SseProgressSink`` is the Python equivalent.

        Args:
            agent_definition: Full agent definition dict.
            input_text: User input.
            parameters: Runtime parameters.
            progress_sink: Optional ``AgentRunProgressSink`` (any
                object with the three async methods). ``None`` is
                equivalent to ``NoOpProgressSink()`` and used for
                backward-compat callers that don't care about events.
            conversation_id: Optional conversation ID forwarded by the
                caller (typically the ``RunRequest.conversation_id``
                supplied by the SPA on a follow-up turn). When set it
                is reused by ``ConversationContext`` so the agent
                step sees the prior user/assistant messages instead
                of starting from scratch, and it is propagated onto
                the returned ``AgentRunResult`` so the diagnostics
                store records every round under the same key.

        Returns:
            The final ``AgentRunResult`` (same shape the
            ``/api/agents/{id}/runs/{conversationId}/debug`` endpoint
            serves from the diagnostics store).
        """
        if progress_sink is None:
            progress_sink = _NoOpSink()

        run_id = str(uuid.uuid4())
        start_time = time.time()
        agent_id = agent_definition.get(
            "id", agent_definition.get("name", "unknown")
        )

        steps = agent_definition.get("steps", [])
        if not steps:
            raise ValueError("Agent has no steps defined")

        # Initialize MCP tools from agent definition
        mcp_tools: dict[str, list[Any]] = {}
        try:
            mcp_tools = await self._mcp_registry.initialize_from_agent(agent_definition)
        except Exception as e:
            logger.warning("mcp_init_skipped", error=str(e))

        start_step_name = self._find_start_step(steps)
        if not start_step_name:
            start_step_name = steps[0].get("name")

        step_index = {s.get("name"): s for s in steps}

        variables: dict[str, Any] = {}
        # Latest-record-per-step view used by the expression
        # resolver (``step_outputs.X.output``). Mirrors the .NET
        # ``WorkflowExpressionContext`` semantics where each step
        # name maps to its most recent execution.
        step_outputs: dict[str, Any] = {}
        # Append-only history. The diagnostics endpoint and the SSE
        # ``run-complete`` payload need *every* execution of a step
        # so a workflow that loops (e.g. the multi-language
        # translator calling ``general chat agent`` once per
        # language) shows up once per iteration instead of just
        # the last call.
        step_history: list[tuple[str, dict[str, Any]]] = []
        max_iterations = parameters.get("max_iterations", 50) if parameters else 50
        iteration = 0
        current_step_name: str | None = start_step_name
        # Seed with the caller-supplied conversation id so multi-round
        # runs reuse the same conversation context. The agent step
        # will generate a new one if ``conversation.enabled`` is true
        # and no id was supplied; otherwise the caller's id is
        # preserved on the returned ``AgentRunResult`` so the
        # diagnostics store keeps grouping rounds together.
        conversation_id: str | None = conversation_id
        # Mirrors ``DefaultAgentRunner.lastStepOutput`` in the .NET
        # backend. ``None`` until the first step produces output; from
        # then on it's the previous step's output string, exposed as
        # ``lastOutput`` in expressions and used to build the
        # ``runtime_state.output`` for the next step.
        last_step_output: Any = None
        workflow_failed = False
        workflow_error: str | None = None

        try:
            while current_step_name and iteration < max_iterations:
                step = step_index.get(current_step_name)
                if not step:
                    logger.warning("step_not_found", step_name=current_step_name)
                    break

                step_name = step.get("name", current_step_name)
                step_type = step.get("type", "agent")
                resolved_step = step

                await progress_sink.step_start(
                    agent_id=agent_id,
                    step_name=step_name,
                    step_type=step_type,
                    iteration=iteration,
                )

                step_start_time = time.time()

                # Build a fresh expression context for this step.
                # ``last_output`` is None on the first iteration and
                # carries the previous step's output on subsequent
                # iterations; ``runtime_state`` mirrors the .NET
                # ``StepOutcomeResolver.BuildRuntimeState`` shape so
                # expressions like ``output`` / ``stepName`` /
                # ``stepType`` resolve to the current step's metadata.
                context = self._build_expression_context(
                    variables=variables,
                    parameters=parameters or {},
                    input=input_text,
                    step_outputs=step_outputs,
                    last_output=last_step_output,
                    runtime_state={
                        "output": last_step_output or "",
                        "stepName": step_name,
                        "stepType": step_type,
                    },
                )

                error_message: str | None = None
                output: Any = None
                outcome: str | None = None
                next_step: str | None = None
                end_workflow = False
                resolved_parameters: dict[str, str] | None = None
                parameter_debug: dict[str, Any] | None = None
                variable_debug: dict[str, Any] | None = None
                thread_context: dict[str, Any] | None = None
                tool_invocations: list = []
                # Per-LLM-turn trace collected from the agent loop.
                # ``agent`` steps populate it via ``_execute_step``;
                # ``echo``/``setVariables`` leave it empty. Attached
                # to the step record below so it reaches the
                # diagnostics endpoint and the ``run-complete``
                # SSE event.
                step_iterations: list[AgentIterationTrace] = []
                # Built upfront for ``agent`` steps so the diagnostics
                # endpoint can still see which backend was attempted
                # when the actual LLM call raises. Stays ``None`` for
                # non-agent steps (``setVariables``/``echo``).
                step_llm_config: LLMCallConfig | None = (
                    self._build_llm_call_config(agent_definition)
                    if step_type == "agent"
                    else None
                )

                try:
                    resolved_step = self._resolve_step(
                        step,
                        variables,
                        parameters or {},
                        input_text,
                        step_outputs,
                        last_output=context.last_output,
                    )
                    resolved_parameters = dict(resolved_step.get("parameters", {}))
                    parameter_debug = resolved_step.get("parameter_debug")
                    variable_debug = resolved_step.get("variable_debug")

                    output, new_conversation_id, step_iterations, step_tool_calls = (
                        await self._execute_step(
                            step=resolved_step,
                            step_type=step_type,
                            variables=variables,
                            agent_definition=agent_definition,
                            context=context,
                            mcp_tools=mcp_tools,
                            conversation_id=conversation_id,
                            progress_sink=progress_sink,
                            agent_id=agent_id,
                        )
                    )
                    if new_conversation_id:
                        conversation_id = new_conversation_id
                    # ``step_tool_calls`` is the per-step tool-call
                    # list returned by ``_execute_step``; replaces the
                    # empty initialiser so the diagnostics payload
                    # reflects the actual calls performed during the
                    # agent loop. ``agent`` steps populate it;
                    # ``echo``/``setVariables`` return an empty list.
                    if step_tool_calls:
                        tool_invocations = list(step_tool_calls)

                except Exception as e:
                    logger.error(
                        "step_execution_error",
                        step_id=step_name,
                        error=str(e),
                    )
                    error_message = str(e)

                elapsed_ms = int((time.time() - step_start_time) * 1000)

                # Determine the routing for this iteration *before*
                # building the step record so outcome / nextStep /
                # endWorkflow land in the persisted record (and the
                # ``/debug`` payload) — not just in the live SSE
                # ``step-complete`` event.
                try:
                    next_step_name = self._determine_next_step(
                        step=resolved_step,
                        output=output,
                        variables=variables,
                        context=context,
                    )
                except Exception as e:
                    logger.error(
                        "next_step_error", step_id=step_name, error=str(e)
                    )
                    next_step_name = None
                    if error_message is None:
                        error_message = str(e)

                outcome = _resolve_outcome_name(resolved_step, output, next_step_name)
                end_workflow = next_step_name is None
                next_step = next_step_name if next_step_name is not None else None

                step_record = {
                    "type": step_type,
                    "output": output,
                    "duration_ms": elapsed_ms,
                    # Persist the resolved parameters / debug info on
                    # the step record so the final ``AgentRunResult``
                    # (and the diagnostics payload) can surface the
                    # exact strings the resolver produced, including
                    # the ``${{ lastOutput }}`` substitution.
                    "resolved_parameters": resolved_parameters,
                    "parameter_debug": parameter_debug,
                    "variable_debug": variable_debug,
                    # Routing metadata. Captured here so the rebuilt
                    # ``AgentStepExecutionResult`` (the one the
                    # ``/debug`` endpoint serves) can show which
                    # outcome fired and which step ran next — not
                    # just the live ``step-complete`` SSE event.
                    "outcome": outcome,
                    "next_step": next_step,
                    "end_workflow": end_workflow,
                    # Per-LLM-turn reasoning trace collected from
                    # the agent loop. Stored in snake_case as a list
                    # of plain dicts so it round-trips through the
                    # diagnostics store; the typed dataclass is
                    # rebuilt when the step record is converted to
                    # an ``AgentStepExecutionResult`` below. Each
                    # entry has the iteration index, the assistant's
                    # text (when present), the names of the tools
                    # it requested, and the observation timestamp.
                    "iterations": [it.to_dict() for it in step_iterations],
                    # LLM config snapshot (provider/model/endpoint/etc.)
                    # must round-trip through the diagnostics store
                    # so the ``/debug`` endpoint and the SSE
                    # ``run-complete`` payload can both prove which
                    # backend actually handled the step. Stored in
                    # snake_case so ``LLMCallConfig.from_dict`` can
                    # rebuild it back into a typed dataclass after the
                    # workflow loop; the wire format (camelCase) is
                    # produced later by ``step.to_dict()``.
                    "llm_config": (
                        _llm_config_to_snake_dict(step_llm_config)
                        if step_llm_config is not None
                        else None
                    ),
                }
                if error_message is not None:
                    step_record["error"] = error_message
                # Latest execution: overwrite for expression resolution.
                step_outputs[step_name] = step_record
                # Append-only history: drives the ``/debug`` payload
                # and the ``run-complete`` SSE event so loops are
                # visible end-to-end.
                step_history.append((step_name, step_record))

                # Persist the step's output for the next iteration's
                # ``lastOutput`` and ``runtime_state.output`` lookups.
                # A failed step surfaces as the error message so the
                # subsequent step's expressions see something
                # meaningful instead of a silent ``None``.
                last_step_output = output if output is not None else error_message

                # Build the typed step result and forward to the sink.
                step_result = AgentStepExecutionResult(
                    name=step_name,
                    type=step_type,
                    output=output if output is not None else "",
                    resolved_parameters=resolved_parameters,
                    parameter_debug=parameter_debug,
                    variable_debug=variable_debug,
                    thread_context=thread_context,
                    outcome=outcome,
                    next_step=next_step,
                    end_workflow=end_workflow,
                    tool_invocations=tool_invocations,
                    iterations=list(step_iterations),
                    llm_config=step_llm_config,
                )
                if error_message is not None:
                    step_result = _with_step_error(step_result, error_message)

                await progress_sink.step_complete(
                    agent_id=agent_id,
                    step=step_result,
                    elapsed_ms=elapsed_ms,
                )

                current_step_name = next_step_name
                iteration += 1

            final_output = ""
            if step_history:
                _last_name, _last_record = step_history[-1]
                final_output = _last_record.get("output") or ""

            total_duration_ms = int((time.time() - start_time) * 1000)
            run_status = "completed"
        except Exception as e:
            logger.error(
                "workflow_execution_error", run_id=run_id, error=str(e)
            )
            workflow_failed = True
            workflow_error = str(e)
            run_status = "failed"
            total_duration_ms = int((time.time() - start_time) * 1000)
        finally:
            await self._mcp_registry.disconnect_all()

        step_results: list[AgentStepExecutionResult] = []
        # ``step_history`` is the append-only record of every
        # execution. Iterating it (instead of ``step_outputs``) keeps
        # loop iterations visible in the ``/debug`` payload and the
        # SSE ``run-complete`` event — a step that runs N times in a
        # loop produces N entries here, in execution order.
        for step_name, step_data in step_history:
            llm_config_data = step_data.get("llm_config")
            llm_config = (
                LLMCallConfig.from_dict(llm_config_data)
                if isinstance(llm_config_data, dict)
                else None
            )
            iterations_data = step_data.get("iterations") or []
            iterations = [
                AgentIterationTrace.from_dict(it) for it in iterations_data
            ]
            step_result = AgentStepExecutionResult(
                name=step_name,
                type=step_data.get("type", "unknown"),
                output=step_data.get("output") or "",
                resolved_parameters=step_data.get("resolved_parameters"),
                parameter_debug=step_data.get("parameter_debug"),
                variable_debug=step_data.get("variable_debug"),
                outcome=step_data.get("outcome"),
                next_step=step_data.get("next_step"),
                end_workflow=step_data.get("end_workflow", False),
                iterations=iterations,
                llm_config=llm_config,
            )
            if "error" in step_data:
                step_result = _with_step_error(
                    step_result, str(step_data["error"])
                )
            step_results.append(step_result)

        run_result = AgentRunResult(
            agent_id=agent_id,
            status=run_status,
            steps=step_results,
            conversation_id=conversation_id,
        )

        if run_result.conversation_id:
            await self._diagnostics_store.save_run(
                run_result.conversation_id, run_result
            )

        if not workflow_failed:
            await progress_sink.run_complete(run_result)
            return run_result

        # Re-raise after we've persisted the diagnostic record.
        raise RuntimeError(workflow_error or "Workflow execution failed")

    async def _execute_workflow(
        self,
        steps: list[dict[str, Any]],
        step_index: dict[str, dict[str, Any]],
        start_step_name: str,
        input_text: str,
        parameters: dict[str, Any],
        context: ExpressionContext,
        progress_callback: Any | None,
        run_id: str,
        agent_definition: dict[str, Any],
        mcp_tools: dict[str, list[Any]] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute the workflow starting from start_step.

        Args:
            steps: All workflow steps
            step_index: Map of step name to step definition
            start_step_name: Name of starting step
            input_text: User input
            parameters: Runtime parameters
            context: Expression context
            progress_callback: Progress callback
            run_id: Run identifier
            agent_definition: Agent definition
            mcp_tools: Dict of MCP tool ID to list of LangChain tools

        Returns:
            Tuple of (variables, step_outputs)
        """
        variables: dict[str, Any] = {}
        # Latest-record-per-step view for expression resolution
        # (``step_outputs.X.output``) — same semantics the streaming
        # path uses. ``step_history`` is the append-only record the
        # caller rebuilds into ``AgentStepExecutionResult`` entries;
        # without it, loop iterations overwrite each other and the
        # diagnostics payload only contains the last call.
        step_outputs: dict[str, Any] = {}
        step_history: list[tuple[str, dict[str, Any]]] = []
        current_step_name: str | None = start_step_name
        max_iterations = parameters.get("max_iterations", 50)
        iteration = 0
        conversation_id: str | None = None

        while current_step_name and iteration < max_iterations:
            step = step_index.get(current_step_name)
            if not step:
                logger.warning("step_not_found", step_name=current_step_name)
                break

            step_name = step.get("name", current_step_name)
            step_type = step.get("type", "agent")
            # Default to the raw step so _determine_next_step has a valid
            # input even when an exception short-circuits the try block
            # before resolved_step gets assigned.
            resolved_step = step

            # Emit step_start event
            if progress_callback:
                await progress_callback({
                    "event_type": "step_start",
                    "step_id": step_name,
                    "step_type": step_type,
                    "iteration": iteration,
                })

            step_start_time = time.time()

            try:
                # Resolve step configuration with current variables
                resolved_step = self._resolve_step(
                    step,
                    variables,
                    parameters,
                    input_text,
                    step_outputs,
                    last_output=context.last_output,
                )

                # Execute step
                output, new_conversation_id = await self._execute_step(
                    step=resolved_step,
                    step_type=step_type,
                    variables=variables,
                    agent_definition=agent_definition,
                    context=context,
                    mcp_tools=mcp_tools or {},
                    conversation_id=conversation_id,
                )
                # Update conversation_id for next iteration if a new one was created
                if new_conversation_id:
                    conversation_id = new_conversation_id

                # Store step output
                step_record = {
                    "type": step_type,
                    "output": output,
                    "duration_ms": int((time.time() - step_start_time) * 1000),
                }
                # Latest execution: overwrite for expression resolution.
                step_outputs[step_name] = step_record
                # Append-only history: drives the diagnostics payload
                # so loop iterations are visible.
                step_history.append((step_name, step_record))

                # Update context for expressions
                context = self._build_expression_context(
                    variables=variables,
                    parameters=parameters,
                    input=input_text,
                    step_outputs=step_outputs,
                    last_output=output,
                )

                # Emit step_complete event
                if progress_callback:
                    await progress_callback({
                        "event_type": "step_complete",
                        "step_id": step_name,
                        "output": output,
                        "duration_ms": step_outputs[step_name]["duration_ms"],
                    })

            except Exception as e:
                logger.error("step_execution_error", step_id=step_name, error=str(e))
                if progress_callback:
                    await progress_callback({
                        "event_type": "error",
                        "step_id": step_name,
                        "error": str(e),
                        "recoverable": True,
                    })
                error_record = {
                    "type": step_type,
                    "output": None,
                    "error": str(e),
                }
                step_outputs[step_name] = error_record
                step_history.append((step_name, error_record))

            # Determine next step based on outcomes - use resolved_step
            current_step_name = self._determine_next_step(
                step=resolved_step,
                output=step_outputs[step_name].get("output"),
                variables=variables,
                context=context,
            )

            iteration += 1

        return variables, step_outputs

    def _find_start_step(self, steps: list[dict[str, Any]]) -> str | None:
        """Find the start step of the workflow.

        Args:
            steps: List of step definitions

        Returns:
            Name of start step or None
        """
        for step in steps:
            if step.get("isStartStep"):
                return step.get("name")
        return None

    def _resolve_step(
        self,
        step: dict[str, Any],
        variables: dict[str, Any],
        parameters: dict[str, Any],
        input_text: str,
        step_outputs: dict[str, Any],
        last_output: Any = None,
    ) -> dict[str, Any]:
        """Resolve placeholders in step configuration.

        Args:
            step: Step definition
            variables: Current workflow variables
            parameters: Runtime parameters
            input_text: User input
            step_outputs: Previous step outputs
            last_output: Output from the previously executed step (exposed
                as ``lastOutput`` in expressions)

        Returns:
            Resolved step configuration
        """
        resolved = dict(step)

        # Build context for resolution
        context = self._build_expression_context(
            variables=variables,
            parameters=parameters,
            input=input_text,
            step_outputs=step_outputs,
            last_output=last_output,
        )

        # Resolve parameters
        if "parameters" in resolved:
            params = resolved["parameters"]
            resolved_params = {}
            for key, value in params.items():
                resolved_params[key] = self._resolve_value(value, context)
            resolved["parameters"] = resolved_params

        # Resolve system prompt in parameters
        if "systemPrompt" in resolved.get("parameters", {}):
            sp = resolved["parameters"]["systemPrompt"]
            resolved["parameters"]["systemPrompt"] = self._resolve_value(sp, context)

        return resolved

    def _resolve_value(self, value: Any, context: ExpressionContext) -> Any:
        """Resolve a value that may contain expressions.

        Args:
            value: Value to resolve
            context: Expression context

        Returns:
            Resolved value
        """
        if not isinstance(value, str):
            return value

        result = self._expression_service.resolve_placeholders(value, context)
        return result.resolved

    def _determine_next_step(
        self,
        step: dict[str, Any],
        output: Any,
        variables: dict[str, Any],
        context: ExpressionContext,
    ) -> str | None:
        """Determine the next step based on outcomes.

        Args:
            step: Current step definition
            output: Step output
            variables: Current variables
            context: Expression context

        Returns:
            Name of next step or None to end
        """
        outcomes = step.get("outcomes", [])
        if not outcomes:
            return None

        # Sort outcomes by order
        sorted_outcomes = sorted(outcomes, key=lambda x: x.get("order", 999))

        for outcome in sorted_outcomes:
            condition = outcome.get("condition")
            next_step: str | None = outcome.get("nextStep")
            end_workflow = outcome.get("endWorkflow", False)

            # Check condition
            if condition:
                expr = condition.get("expression")
                if expr:
                    try:
                        result = evaluate_expression(expr, context)
                        if not result:
                            continue
                    except Exception:
                        continue
            else:
                # Default outcome - take if no condition
                pass

            if end_workflow:
                return None

            return next_step

        return None

    def _build_expression_context(
        self,
        variables: dict[str, Any],
        parameters: dict[str, Any],
        input: str,
        step_outputs: dict[str, Any],
        last_output: Any = None,
        runtime_state: dict[str, Any] | None = None,
    ) -> ExpressionContext:
        """Build expression context.

        Args:
            variables: Workflow variables
            parameters: Runtime parameters
            input: User input
            step_outputs: Outputs from previous steps
            last_output: Output from most recent step
            runtime_state: Per-step runtime identifiers (``output``,
                ``stepName``, ``stepType``) that should be exposed as
                top-level identifiers in expressions. Mirrors the
                .NET ``WorkflowExpressionContext.RuntimeState``.

        Returns:
            ExpressionContext
        """
        return ExpressionContext(
            variables=variables,
            parameters=parameters,
            input=input,
            last_output=last_output,
            runtime_state=runtime_state or {},
            step_outputs=step_outputs,
        )

    def _resolve_llm_config(self, agent_definition: dict[str, Any]) -> dict[str, Any]:
        """Return the fully-resolved LLM config dict for the agent.

        Mirrors the precedence the factory uses: ``agent.llm.*``
        wins, with the same ``endpoint``/``baseUrl``/``deployment``/
        ``apiKey``/``apiVersion`` fallbacks lifted to the top of the
        agent, and ``defaultParameters.{temperature,max_tokens}``
        flowing through last.

        ``apiKey`` (and its ``defaultParameters`` alias) support
        ``${ENV_VAR}`` placeholders so the secret never has to live in
        ``agents.json``. When a placeholder resolves to nothing we
        drop the key entirely so the factory can fall back to its
        settings/env-var chain instead of substituting a sentinel that
        real servers (e.g. a local Qwen with auth enabled) would
        reject as ``Invalid API key``.

        Kept separate from the actual ``ChatOpenAI`` construction so
        the diagnostics snapshot can be captured **before** the LLM
        call — that way the ``/debug`` endpoint still tells
        operators which backend was attempted when the call itself
        raises.
        """
        llm_config = dict(agent_definition.get("llm", {}) or {})
        if not llm_config:
            llm_config = {
                "provider": agent_definition.get("provider", "azure-openai"),
                "model": agent_definition.get("model", "gpt-4o"),
            }

        llm_config.setdefault("endpoint", agent_definition.get("endpoint"))
        llm_config.setdefault("base_url", agent_definition.get("baseUrl"))
        llm_config.setdefault("deployment", agent_definition.get("deployment"))
        # Track whether the agent definition explicitly named an
        # ``apiKey`` so the ``defaultParameters`` fallback can
        # distinguish "no key declared" from "key declared as null".
        # ``setdefault`` already populates the key with ``None`` in
        # both cases, which is too coarse to drive the fallback.
        if agent_definition.get("apiKey"):
            llm_config["api_key"] = agent_definition["apiKey"]
        else:
            llm_config.setdefault("api_key", None)
        llm_config.setdefault("api_version", agent_definition.get("apiVersion"))

        default_params: dict[str, Any] = {
            **agent_definition.get("default_parameters", {}),
            **agent_definition.get("defaultParameters", {}),
        }
        for key in ("temperature", "max_tokens", "maxTokens"):
            if key in default_params and key not in llm_config:
                llm_config[key] = default_params[key]

        # ``apiKey`` is intentionally re-read from defaultParameters
        # (and the ``api_key`` snake_case alias) so workflow authors
        # can keep the secret out of the top-level agent definition
        # via ``"apiKey": "${OPENAI_API_KEY}"``. Resolved through the
        # shared env-var helper so the same ``$VAR``/``${VAR}`` syntax
        # used in MCP headers works here too. An unresolved
        # placeholder must NOT be passed through to the LLM factory —
        # it would either be rejected by a real auth layer or end up
        # in the resolved-parameter debug payload as a literal
        # ``${OPENAI_API_KEY}`` string.
        if not llm_config.get("api_key"):
            default_api_key = (
                default_params.get("apiKey") or default_params.get("api_key")
            )
            if default_api_key:
                from src.lib.security import resolve_env_vars

                resolved = resolve_env_vars(str(default_api_key))
                if not resolved or resolved == default_api_key:
                    # Either the placeholder didn't resolve or the
                    # value was already plain. Only accept the plain
                    # value as a hardcoded override; drop unresolved
                    # placeholders so the LLM factory can fall back
                    # to its own settings/env-var chain instead of
                    # shipping a literal ``${...}`` to the server.
                    if "${" in str(default_api_key) or "{" in str(default_api_key):
                        llm_config["api_key"] = None
                    else:
                        llm_config["api_key"] = resolved
                else:
                    llm_config["api_key"] = resolved

        return llm_config

    def _build_llm_call_config(
        self,
        agent_definition: dict[str, Any],
    ) -> LLMCallConfig:
        """Build an :class:`LLMCallConfig` snapshot for diagnostics.

        ``api_key`` is reduced to a last-4 fingerprint (or ``None``
        when the agent definition didn't supply one), so the
        diagnostics endpoint can tell which credential was used
        without leaking the secret.
        """
        llm_config = self._resolve_llm_config(agent_definition)
        explicit_api_key = llm_config.get("api_key")
        return LLMCallConfig(
            provider=llm_config.get("provider", "azure-openai"),
            model=llm_config.get("model"),
            endpoint=llm_config.get("endpoint"),
            base_url=llm_config.get("base_url"),
            deployment=llm_config.get("deployment"),
            api_version=llm_config.get("api_version"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=(
                llm_config.get("max_tokens") or llm_config.get("maxTokens")
            ),
            api_key_fingerprint=_fingerprint_api_key(explicit_api_key),
        )

    async def _execute_step(
        self,
        step: dict[str, Any],
        step_type: str,
        variables: dict[str, Any],
        agent_definition: dict[str, Any],
        context: ExpressionContext,
        mcp_tools: dict[str, list[Any]] | None = None,
        conversation_id: str | None = None,
        *,
        progress_sink: Any | None = None,
        agent_id: str = "",
    ) -> tuple[str, str | None, list[AgentIterationTrace], list[AgentToolCall]]:
        """Execute a single workflow step.

        Args:
            step: Resolved step definition
            step_type: Step type (agent, setVariables, echo)
            variables: Workflow variables (modified in place)
            agent_definition: Agent definition
            context: Expression context
            mcp_tools: Dict of MCP tool ID to list of LangChain tools
            conversation_id: Optional conversation ID for multi-turn conversations
            progress_sink: Optional sink used to emit per-iteration and
                per-tool-call ``agent-iteration`` / ``tool-call`` SSE
                events. ``None`` disables live emission but the
                returned lists are still populated.
            agent_id: Agent definition id, forwarded to the sink for
                event payloads.

        Returns:
            Tuple of ``(step output, conversation_id, iterations,
            tool_calls)``. ``iterations`` and ``tool_calls`` are
            populated for ``agent`` steps and empty for
            ``setVariables``/``echo``. The caller attaches them to
            the step result so they reach the diagnostics endpoint
            and the ``run-complete`` SSE event.
        """
        if step_type == "setVariables":
            result = await self._execute_set_variables(step, variables, context)
            return result, conversation_id, [], []

        elif step_type == "echo":
            result = await self._execute_echo(step, variables, context)
            return result, conversation_id, [], []

        elif step_type == "agent":
            output, new_conversation_id, _llm_config, iterations, tool_calls = (
                await self._execute_agent(
                    step,
                    variables,
                    agent_definition,
                    context,
                    mcp_tools or {},
                    conversation_id,
                    progress_sink=progress_sink,
                    agent_id=agent_id,
                )
            )
            return output, new_conversation_id, iterations, tool_calls

        else:
            logger.warning("unknown_step_type", step_type=step_type)
            return "", conversation_id, [], []

    async def _execute_set_variables(
        self,
        step: dict[str, Any],
        variables: dict[str, Any],
        context: ExpressionContext,
    ) -> str:
        """Execute a setVariables step.

        Args:
            step: Step definition
            variables: Workflow variables (modified in place)
            context: Expression context

        Returns:
            Completion message
        """
        parameters = step.get("parameters", {})
        variable_types = step.get("variableTypes", {})

        for var_name, var_value in parameters.items():
            # Resolve the value
            resolved = self._resolve_value(var_value, context)

            # Convert type if needed
            var_type = variable_types.get(var_name, "string")
            if var_type == "number" and isinstance(resolved, str):
                try:
                    resolved = float(resolved) if "." in resolved else int(resolved)
                except (ValueError, TypeError):
                    pass
            elif var_type == "json" and isinstance(resolved, str):
                import json
                try:
                    resolved = json.loads(resolved)
                except json.JSONDecodeError:
                    pass

            variables[var_name] = resolved

        return "Variables set"

    async def _execute_echo(
        self,
        step: dict[str, Any],
        variables: dict[str, Any],
        context: ExpressionContext,
    ) -> str:
        """Execute an echo step.

        Args:
            step: Step definition
            variables: Workflow variables
            context: Expression context

        Returns:
            Echo message
        """
        parameters = step.get("parameters", {})
        message = parameters.get("message", "")

        resolved = self._resolve_value(message, context)
        return str(resolved)

    async def _execute_agent(
        self,
        step: dict[str, Any],
        variables: dict[str, Any],
        agent_definition: dict[str, Any],
        context: ExpressionContext,
        mcp_tools: dict[str, list[Any]],
        conversation_id: str | None = None,
        *,
        progress_sink: Any | None = None,
        agent_id: str = "",
    ) -> tuple[str, str | None, dict[str, Any], list[AgentIterationTrace], list[AgentToolCall]]:
        """Execute an agent step (LLM chat).

        Args:
            step: Step definition
            variables: Workflow variables
            agent_definition: Agent definition
            context: Expression context
            mcp_tools: Dict of MCP tool ID to list of LangChain tools
            conversation_id: Optional conversation ID for multi-turn conversations
            progress_sink: Optional sink that receives ``agent-iteration``
                and ``tool-call`` events as the agent loop runs.
            agent_id: Agent definition id, forwarded to the sink for
                event payloads.

        Returns:
            Tuple of ``(agent response, conversation_id, resolved llm
            config dict, iterations, tool_calls)``. ``iterations``
            captures the assistant's text + tool-call requests per
            LLM turn; ``tool_calls`` lists each tool execution. Both
            are empty when the agent loop did not run. The ``llm_config``
            dict is currently unused by callers (the diagnostics
            snapshot is built upfront by ``execute_stream``) but is
            returned so tests can inspect the resolved values
            without rebuilding them.
        """
        parameters = step.get("parameters", {})
        system_prompt = parameters.get("systemPrompt", "")
        message = parameters.get("message", "")

        # Resolve message
        resolved_message = self._resolve_value(message, context)

        # Create conversation context if enabled
        conversation_context = await ConversationContext.create(
            store=self._conversation_store,
            step=step,
            conversation_id=conversation_id,
        )

        # Get LLM config from agent definition. The diagnostics
        # snapshot is built by the caller (``execute_stream``) so it
        # survives a failing LLM call; here we just consume the same
        # resolved dict to actually construct the chat model.
        llm_config = self._resolve_llm_config(agent_definition)
        explicit_api_key = llm_config.get("api_key")

        # Create LLM
        llm = self._llm_factory.create_chat_model(
            provider=llm_config.get("provider", "azure-openai"),
            model=llm_config.get("model"),
            api_key=explicit_api_key,
            endpoint=llm_config.get("endpoint"),
            base_url=llm_config.get("base_url"),
            deployment=llm_config.get("deployment"),
            api_version=llm_config.get("api_version"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens") or llm_config.get("maxTokens"),
        )

        # Collect tools for this step
        # Step can reference tools by ID in its tools array
        step_tool_ids = parameters.get("tools", [])
        if isinstance(step_tool_ids, str):
            step_tool_ids = [step_tool_ids]

        # Also check step-level tools array in step definition
        step_tools_list = step.get("tools", [])
        if isinstance(step_tools_list, list):
            for t in step_tools_list:
                if isinstance(t, str) and t not in step_tool_ids:
                    step_tool_ids.append(t)

        # Gather LangChain tools from MCP registry
        langchain_tools: list[Any] = []
        for tool_id in step_tool_ids:
            if tool_id in mcp_tools:
                langchain_tools.extend(mcp_tools[tool_id])

        # Build messages
        from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

        messages: list[BaseMessage] = []

        # Prepend system prompt if present
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        # If conversation is enabled, prepend existing messages
        if conversation_context.enabled:
            existing_messages = conversation_context.to_langchain_messages()
            messages.extend(existing_messages)

        # Add the current user message
        messages.append(HumanMessage(content=str(resolved_message)))

        # Invoke LLM with or without tools. The tool-calling path
        # runs a proper agent loop (see ``_run_agent_loop``) so the
        # LLM can make multiple rounds of tool calls and still land
        # on a text response — the previous implementation did
        # exactly one round of tool calls and then called the LLM
        # *without* tool bindings for the synthesis step, which made
        # smaller/quantised local models (e.g. Qwen3.6-35B-A3B) return
        # an empty ``content`` field and the workflow step produced
        # no output.
        step_name = step.get("name", "")
        iterations: list[AgentIterationTrace] = []
        tool_calls_out: list[AgentToolCall] = []
        if langchain_tools:
            response, iterations, tool_calls_out = await self._run_agent_loop(
                llm=llm,
                messages=messages,
                tools=langchain_tools,
                progress_sink=progress_sink,
                agent_id=agent_id,
                step_name=step_name,
            )
        else:
            response = await llm.ainvoke(messages)
            # Single-turn path: surface the assistant's text as one
            # iteration so the UI still shows a (no-tool) trace.
            response_content = getattr(response, "content", "") or ""
            iterations.append(
                AgentIterationTrace(
                    iteration=0,
                    content=response_content if response_content else None,
                    tool_call_names=[],
                    has_tool_calls=False,
                )
            )
            if progress_sink is not None:
                try:
                    await progress_sink.iteration(
                        agent_id=agent_id,
                        step_name=step_name,
                        trace=iterations[-1],
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("iteration_event_failed", error=str(exc))

        response_content = getattr(response, "content", str(response))
        if not response_content:
            # Surface the LLM's actual response so empty output is
            # diagnosable from the workflow logs (and the
            # ``/debug`` payload) — without this, the operator sees
            # an empty step output with no hint about whether the
            # LLM returned an empty string, a tool call that never
            # resolved, or a model that simply doesn't support the
            # tool-calling protocol being used.
            logger.warning(
                "agent_step_empty_response",
                step_name=step.get("name"),
                response_type=type(response).__name__,
                tool_calls=(
                    getattr(response, "tool_calls", None) or None
                ),
            )

        # Save conversation messages if enabled
        if conversation_context.enabled:
            # Add user message
            await conversation_context.add_user_message(str(resolved_message))
            # Add assistant response
            await conversation_context.add_assistant_message(response_content)
            # Save to store
            await conversation_context.save()

        return (
            response_content,
            conversation_context.conversation_id,
            llm_config,
            iterations,
            tool_calls_out,
        )

    async def _run_agent_loop(
        self,
        llm: Any,
        messages: list[Any],
        tools: list[Any],
        *,
        progress_sink: Any | None = None,
        agent_id: str = "",
        step_name: str = "",
        max_iterations: int = 8,
    ) -> tuple[Any, list[AgentIterationTrace], list[AgentToolCall]]:
        """Run the LLM in an agent loop until it returns text.

        Some local models (Qwen3.6-35B-A3B-OptiQ-4bit among them)
        make a tool call, run the tool, and then return *another*
        tool call on the synthesis turn — sometimes several in a row
        — before finally producing text. The previous single-round
        implementation called ``llm.ainvoke`` (without tool bindings!)
        for the synthesis turn, which both broke tool-aware models
        *and* dropped the response on the floor if the model still
        wanted to call a tool.

        This loop uses ``llm_with_tools`` for every turn so the
        model always sees the tool schema, and iterates until we
        either get a non-empty ``content`` or hit ``max_iterations``.
        Each iteration logs what the model did so the operator can
        see whether the LLM is making progress or stuck in a loop.

        When ``progress_sink`` is provided, each iteration is also
        emitted as an ``agent-iteration`` SSE event for the live UI;
        regardless of the sink, the function returns the captured
        ``iterations`` and ``tool_calls`` lists so the caller can
        attach them to the step record.
        """
        llm_with_tools = llm.bind_tools(tools)
        iterations: list[AgentIterationTrace] = []
        tool_calls_out: list[AgentToolCall] = []

        for iteration_index in range(max_iterations):
            response = await llm_with_tools.ainvoke(messages)

            tool_calls = getattr(response, "tool_calls", None) or []
            content = getattr(response, "content", "") or ""

            tool_call_names = [
                tc.get("name") for tc in tool_calls if tc.get("name")
            ]
            trace = AgentIterationTrace(
                iteration=iteration_index,
                content=content if content else None,
                tool_call_names=tool_call_names,
                has_tool_calls=bool(tool_calls),
            )
            iterations.append(trace)
            if progress_sink is not None:
                try:
                    await progress_sink.iteration(
                        agent_id=agent_id,
                        step_name=step_name,
                        trace=trace,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("iteration_event_failed", error=str(exc))

            logger.debug(
                "agent_loop_iteration",
                iteration=iteration_index,
                has_content=bool(content),
                content_preview=content[:200] if content else "",
                tool_call_names=tool_call_names,
            )

            if not tool_calls:
                # No tool calls: this is the final response.
                return response, iterations, tool_calls_out

            # Execute the tool calls and append the results, then
            # loop again so the model can either chain another tool
            # call or return a final text response.
            messages.append(response)
            await self._execute_tool_calls(
                tool_calls=tool_calls,
                tools=tools,
                messages=messages,
                tool_calls_out=tool_calls_out,
                progress_sink=progress_sink,
                agent_id=agent_id,
                step_name=step_name,
            )

        logger.warning(
            "agent_loop_exhausted",
            max_iterations=max_iterations,
            hint=(
                "LLM kept requesting tool calls without producing a "
                "final text response. Returning the last response "
                "(which may be empty) so the workflow can continue."
            ),
        )
        return response, iterations, tool_calls_out

    async def _execute_tool_calls(
        self,
        tool_calls: list[Any],
        tools: list[Any],
        messages: list[Any],
        *,
        tool_calls_out: list[AgentToolCall] | None = None,
        progress_sink: Any | None = None,
        agent_id: str = "",
        step_name: str = "",
    ) -> None:
        """Execute a batch of tool calls and append results to ``messages``.

        Mirrors the body of the previous ``_handle_tool_calls`` but
        factored out so the agent loop can call it multiple times
        and so the synthesis step isn't tangled up with execution.

        When ``tool_calls_out`` is provided, each executed call is
        appended so the caller can attach the full list to the step
        record. When ``progress_sink`` is provided, each call is
        also emitted as a ``tool-call`` SSE event for the live UI.
        """
        from langchain_core.messages import ToolMessage

        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {}) or {}
            tool_call_id = tool_call.get("id")

            tool = next((t for t in tools if t.name == tool_name), None)
            if not tool:
                logger.warning("tool_not_found", tool_name=tool_name)
                continue

            arguments_json = (
                json.dumps(tool_args) if tool_args else None
            )
            started_at = time.time()
            result_text: str
            error_message: str | None = None
            try:
                if hasattr(tool, "ainvoke"):
                    tool_result = await tool.ainvoke(tool_args)
                else:
                    tool_result = await tool.invoke(tool_args)
                result_text = (
                    str(tool_result) if tool_result is not None else ""
                )
            except Exception as e:
                logger.error(
                    "tool_call_failed", tool_name=tool_name, error=str(e)
                )
                error_message = str(e)
                result_text = f"Error: {error_message}"

            record = AgentToolCall(
                tool_name=tool_name,
                invocation_id=tool_call_id,
                result=result_text,
                arguments_json=arguments_json,
                error_message=error_message,
            )
            if tool_calls_out is not None:
                tool_calls_out.append(record)
            if progress_sink is not None:
                try:
                    await progress_sink.tool_call(
                        agent_id=agent_id,
                        step_name=step_name,
                        tool_call=record,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("tool_call_event_failed", error=str(exc))

            messages.append(
                ToolMessage(
                    content=result_text,
                    tool_call_id=tool_call_id,
                )
            )


# Singleton
_workflow_executor: WorkflowExecutor | None = None


def get_workflow_executor() -> WorkflowExecutor:
    """Get the workflow executor singleton."""
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = WorkflowExecutor()
    return _workflow_executor