"""Dynamic workflow executor - executes workflows based on workflow definition."""

from __future__ import annotations

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
    AgentRunResult,
    AgentStepExecutionResult,
    AgentToolCall,
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
        step_outputs: dict[str, Any] = {}
        max_iterations = parameters.get("max_iterations", 50) if parameters else 50
        iteration = 0
        current_step_name: str | None = start_step_name
        conversation_id: str | None = None
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

                    output, new_conversation_id = await self._execute_step(
                        step=resolved_step,
                        step_type=step_type,
                        variables=variables,
                        agent_definition=agent_definition,
                        context=context,
                        mcp_tools=mcp_tools,
                        conversation_id=conversation_id,
                    )
                    if new_conversation_id:
                        conversation_id = new_conversation_id

                except Exception as e:
                    logger.error(
                        "step_execution_error",
                        step_id=step_name,
                        error=str(e),
                    )
                    error_message = str(e)

                elapsed_ms = int((time.time() - step_start_time) * 1000)

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
                }
                if error_message is not None:
                    step_record["error"] = error_message
                step_outputs[step_name] = step_record

                # Persist the step's output for the next iteration's
                # ``lastOutput`` and ``runtime_state.output`` lookups.
                # A failed step surfaces as the error message so the
                # subsequent step's expressions see something
                # meaningful instead of a silent ``None``.
                last_step_output = output if output is not None else error_message

                # Determine next step before publishing the completion
                # event so the SSE payload can include outcome /
                # nextStep / endWorkflow.
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

                # Find which outcome fired, if any, by reading the
                # outcomes list off the resolved step.
                outcome = _resolve_outcome_name(resolved_step, output, next_step_name)
                end_workflow = next_step_name is None
                if next_step_name is not None:
                    next_step = next_step_name

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
            if step_outputs:
                last_step_id = list(step_outputs.keys())[-1]
                final_output = step_outputs[last_step_id].get("output") or ""

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
        for step_name, step_data in step_outputs.items():
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
        step_outputs: dict[str, Any] = {}
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
                step_outputs[step_name] = {
                    "type": step_type,
                    "output": output,
                    "duration_ms": int((time.time() - step_start_time) * 1000),
                }

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
                step_outputs[step_name] = {
                    "type": step_type,
                    "output": None,
                    "error": str(e),
                }

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

    async def _execute_step(
        self,
        step: dict[str, Any],
        step_type: str,
        variables: dict[str, Any],
        agent_definition: dict[str, Any],
        context: ExpressionContext,
        mcp_tools: dict[str, list[Any]] | None = None,
        conversation_id: str | None = None,
    ) -> tuple[str, str | None]:
        """Execute a single workflow step.

        Args:
            step: Resolved step definition
            step_type: Step type (agent, setVariables, echo)
            variables: Workflow variables (modified in place)
            agent_definition: Agent definition
            context: Expression context
            mcp_tools: Dict of MCP tool ID to list of LangChain tools
            conversation_id: Optional conversation ID for multi-turn conversations

        Returns:
            Tuple of (step output, conversation_id if applicable)
        """
        if step_type == "setVariables":
            result = await self._execute_set_variables(step, variables, context)
            return result, conversation_id

        elif step_type == "echo":
            result = await self._execute_echo(step, variables, context)
            return result, conversation_id

        elif step_type == "agent":
            return await self._execute_agent(
                step, variables, agent_definition, context, mcp_tools or {}, conversation_id
            )

        else:
            logger.warning("unknown_step_type", step_type=step_type)
            return "", conversation_id

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
    ) -> tuple[str, str | None]:
        """Execute an agent step (LLM chat).

        Args:
            step: Step definition
            variables: Workflow variables
            agent_definition: Agent definition
            context: Expression context
            mcp_tools: Dict of MCP tool ID to list of LangChain tools
            conversation_id: Optional conversation ID for multi-turn conversations

        Returns:
            Tuple of (agent response, conversation_id if created/used)
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

        # Get LLM config from agent definition
        llm_config = dict(agent_definition.get("llm", {}) or {})
        if not llm_config:
            llm_config = {
                "provider": agent_definition.get("provider", "azure-openai"),
                "model": agent_definition.get("model", "gpt-4o"),
            }

        # Backfill top-level fields used by the JSON format
        llm_config.setdefault("endpoint", agent_definition.get("endpoint"))
        llm_config.setdefault("deployment", agent_definition.get("deployment"))
        llm_config.setdefault("api_key", agent_definition.get("apiKey"))
        llm_config.setdefault("api_version", agent_definition.get("apiVersion"))

        # Allow defaultParameters (e.g. temperature, max_tokens) to flow into
        # the LLM client. Accept both the snake_case and camelCase keys for
        # compatibility with the JSON schema used by the agent definitions.
        default_params: dict[str, Any] = {
            **agent_definition.get("default_parameters", {}),
            **agent_definition.get("defaultParameters", {}),
        }
        for key in ("temperature", "max_tokens", "maxTokens"):
            if key in default_params and key not in llm_config:
                llm_config[key] = default_params[key]

        # Create LLM
        llm = self._llm_factory.create_chat_model(
            provider=llm_config.get("provider", "azure-openai"),
            model=llm_config.get("model"),
            api_key=llm_config.get("api_key"),
            endpoint=llm_config.get("endpoint"),
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

        # Invoke LLM with or without tools
        if langchain_tools:
            llm_with_tools = llm.bind_tools(langchain_tools)
            response = await llm_with_tools.ainvoke(messages)
            # Handle tool calls if present
            if hasattr(response, "tool_calls") and response.tool_calls:
                # Execute tool calls and continue conversation
                response = await self._handle_tool_calls(
                    response, messages, langchain_tools, llm
                )
        else:
            response = await llm.ainvoke(messages)

        response_content = getattr(response, "content", str(response))

        # Save conversation messages if enabled
        if conversation_context.enabled:
            # Add user message
            await conversation_context.add_user_message(str(resolved_message))
            # Add assistant response
            await conversation_context.add_assistant_message(response_content)
            # Save to store
            await conversation_context.save()

        return response_content, conversation_context.conversation_id

    async def _handle_tool_calls(
        self,
        response: Any,
        messages: list[Any],
        tools: list[Any],
        llm: Any,
    ) -> Any:
        """Handle tool calls from LLM response.

        Args:
            response: LLM response with tool_calls
            messages: Conversation messages (modified in place)
            tools: LangChain tools available
            llm: LLM instance

        Returns:
            Final response after tool execution
        """
        from langchain_core.messages import AIMessage, ToolMessage

        # Add the AI message with tool calls
        messages.append(response)

        # Execute each tool call
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args", {})

            # Find the tool
            tool = next((t for t in tools if t.name == tool_name), None)
            if not tool:
                logger.warning("tool_not_found", tool_name=tool_name)
                continue

            try:
                # Invoke the tool
                if hasattr(tool, "ainvoke"):
                    tool_result = await tool.ainvoke(tool_args)
                else:
                    tool_result = await tool.invoke(tool_args)

                # Add tool result as ToolMessage
                messages.append(
                    ToolMessage(
                        content=str(tool_result),
                        tool_call_id=tool_call.get("id"),
                    )
                )
            except Exception as e:
                logger.error("tool_call_failed", tool_name=tool_name, error=str(e))
                messages.append(
                    ToolMessage(
                        content=f"Error: {str(e)}",
                        tool_call_id=tool_call.get("id"),
                    )
                )

        # Continue conversation with tool results
        final_response = await llm.ainvoke(messages)
        return final_response


# Singleton
_workflow_executor: WorkflowExecutor | None = None


def get_workflow_executor() -> WorkflowExecutor:
    """Get the workflow executor singleton."""
    global _workflow_executor
    if _workflow_executor is None:
        _workflow_executor = WorkflowExecutor()
    return _workflow_executor