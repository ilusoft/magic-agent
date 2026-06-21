"""End-to-end-ish tests for ``WorkflowExecutor.execute_stream``.

These pin down the sink-based contract that the SSE route relies on.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.agent_runtime.progress_sink import NoOpProgressSink
from src.agent_runtime.workflow_executor import (
    _resolve_outcome_name,
    _with_step_error,
    WorkflowExecutor,
)
from src.application.agents.run_result import AgentStepExecutionResult


class _RecordingSink:
    """Collects every method call so tests can assert on them."""

    def __init__(self) -> None:
        self.step_starts: list[dict[str, Any]] = []
        self.step_completes: list[dict[str, Any]] = []
        self.run_completes: list[Any] = []

    async def step_start(
        self,
        agent_id: str,
        step_name: str,
        step_type: str,
        iteration: int,
    ) -> None:
        self.step_starts.append(
            {
                "agent_id": agent_id,
                "step_name": step_name,
                "step_type": step_type,
                "iteration": iteration,
            }
        )

    async def step_complete(
        self,
        agent_id: str,
        step: AgentStepExecutionResult,
        elapsed_ms: float,
    ) -> None:
        self.step_completes.append(
            {
                "agent_id": agent_id,
                "step_name": step.name,
                "step": step,
                "elapsed_ms": elapsed_ms,
            }
        )

    async def run_complete(self, run_result: Any) -> None:
        self.run_completes.append(run_result)


class _StubLLMFactory:
    """Returns a canned response for any chat invocation."""

    def __init__(self, response: str = "Bonjour le monde") -> None:
        self.response = response
        self.invocations: list[dict] = []

    def create_chat_model(self, **_kwargs: Any) -> Any:
        return self._ChatModel(self)

    class _ChatModel:
        def __init__(self, outer: "_StubLLMFactory") -> None:
            self.outer = outer

        async def ainvoke(self, messages: Any) -> Any:
            self.outer.invocations.append(
                {"messages": [m.content for m in messages]}
            )

            class _Resp:
                def __init__(self, content: str) -> None:
                    self.content = content

            return _Resp(self.outer.response)


class TestExecuteStreamSink:
    """``execute_stream`` should call the sink with the right events."""

    @pytest.mark.asyncio
    async def test_emits_step_start_complete_and_run_complete(self) -> None:
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "agent-stream",
            "name": "agent-stream",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "hello"},
                    "outcomes": [
                        {
                            "name": "next",
                            "nextStep": "finish",
                            "condition": None,
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                    "isStartStep": True,
                },
                {
                    "name": "finish",
                    "type": "setVariables",
                    "parameters": {"done": "yes"},
                    "variableTypes": {"done": "string"},
                    "outcomes": [
                        {
                            "name": "end",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 1,
                        }
                    ],
                    "isStartStep": False,
                },
            ],
        }

        run_result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        # One step_start + step_complete for each of the two steps.
        assert [s["step_name"] for s in sink.step_starts] == ["chat", "finish"]
        assert [s["step_name"] for s in sink.step_completes] == ["chat", "finish"]

        # chat step has next=finish, finish step has endWorkflow=True.
        chat_complete = sink.step_completes[0]
        finish_complete = sink.step_completes[1]
        assert chat_complete["step"].next_step == "finish"
        assert chat_complete["step"].end_workflow is False
        assert finish_complete["step"].end_workflow is True

        # run_complete fired exactly once with the full result.
        assert len(sink.run_completes) == 1
        assert sink.run_completes[0].agent_id == "agent-stream"
        assert run_result.status == "completed"

    @pytest.mark.asyncio
    async def test_sink_step_complete_uses_elapsed_ms(self) -> None:
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "agent-elapsed",
            "name": "agent-elapsed",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "x"},
                    "outcomes": [
                        {
                            "name": "end",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 1,
                        }
                    ],
                    "isStartStep": True,
                }
            ],
        }

        await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="x",
            progress_sink=sink,
        )

        # We don't pin an exact value, but it must be a positive number
        # and within a sane range (10 seconds upper bound).
        elapsed = sink.step_completes[0]["elapsed_ms"]
        assert 0 <= elapsed < 10_000

    @pytest.mark.asyncio
    async def test_noop_sink_default(self) -> None:
        """Calling ``execute_stream`` with no sink should not raise
        and should still return an ``AgentRunResult``."""
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        agent_def = {
            "id": "agent-default",
            "name": "agent-default",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "x"},
                    "outcomes": [
                        {
                            "name": "end",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 1,
                        }
                    ],
                    "isStartStep": True,
                }
            ],
        }

        result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="x",
        )
        assert result.status == "completed"
        assert result.agent_id == "agent-default"

    @pytest.mark.asyncio
    async def test_sink_step_error_when_step_raises(self) -> None:
        """A step that raises should still emit ``step_complete``
        with the error annotation, and the workflow should keep
        going (matching the .NET backend's behaviour)."""
        boom = RuntimeError("boom")

        class _RaisingStub:
            def create_chat_model(self, **_kwargs: Any) -> Any:
                class _Chat:
                    async def ainvoke(self, _messages: Any) -> Any:
                        raise boom

                return _Chat()

        executor = WorkflowExecutor(llm_factory=_RaisingStub())  # type: ignore[arg-type]
        sink = _RecordingSink()
        agent_def = {
            "id": "agent-boom",
            "name": "agent-boom",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "x"},
                    "outcomes": [
                        {
                            "name": "next",
                            "nextStep": "finish",
                            "condition": None,
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                    "isStartStep": True,
                },
                {
                    "name": "finish",
                    "type": "setVariables",
                    "parameters": {"done": "yes"},
                    "variableTypes": {"done": "string"},
                    "outcomes": [
                        {
                            "name": "end",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 1,
                        }
                    ],
                    "isStartStep": False,
                },
            ],
        }

        result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="x",
            progress_sink=sink,
        )

        # The chat step was marked with an error and a synthetic tool
        # invocation, but the workflow kept going.
        assert result.status == "completed"
        chat_step = sink.step_completes[0]["step"]
        assert chat_step.tool_error_detected is True
        assert any(
            t.tool_name == "__step_error__" and t.error_message == "boom"
            for t in chat_step.tool_invocations
        )
        # The finish step ran after the error and emitted a normal
        # completion.
        assert sink.step_completes[1]["step"].name == "finish"
        assert sink.step_completes[1]["step"].end_workflow is True

    @pytest.mark.asyncio
    async def test_last_output_propagates_between_iterations(self) -> None:
        """Regression: after my refactor, ``last_output`` was not
        updated between iterations of the streaming loop, so a step
        that referenced ``${{ lastOutput }}`` saw an empty string
        instead of the previous step's output.

        This test reproduces the exact pattern from the user's
        ``agents.json``:

        1. ``init`` step sets a ``var.seed`` variable
        2. ``chat`` step produces a known output
        3. ``capture`` step resolves ``${{ lastOutput }}`` and
           stores the result in ``var.captured`` so we can assert
           the value made it through.
        """
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        # Override the stub so we can return different output per call.
        class _SequenceStub:
            def __init__(self, outputs: list[str]) -> None:
                self.outputs = outputs
                self.index = 0

            def create_chat_model(self, **_kwargs: Any) -> Any:
                outer = self

                class _Chat:
                    async def ainvoke(self, _messages: Any) -> Any:
                        content = outer.outputs[outer.index]
                        outer.index += 1

                        class _Resp:
                            def __init__(self, content: str) -> None:
                                self.content = content

                        return _Resp(content)

                return _Chat()

        executor._llm_factory = _SequenceStub(["hola"])  # type: ignore[assignment]

        agent_def = {
            "id": "agent-last-output",
            "name": "agent-last-output",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "init",
                    "type": "setVariables",
                    "parameters": {"seed": "ready"},
                    "variableTypes": {"seed": "string"},
                    "outcomes": [
                        {
                            "name": "go",
                            "nextStep": "chat",
                            "condition": None,
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                    "isStartStep": True,
                },
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "translate", "message": "hi"},
                    "outcomes": [
                        {
                            "name": "next",
                            "nextStep": "capture",
                            "condition": None,
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                    "isStartStep": False,
                },
                {
                    "name": "capture",
                    "type": "setVariables",
                    "parameters": {
                        "captured": "${{ lastOutput }}",
                    },
                    "variableTypes": {"captured": "string"},
                    "outcomes": [
                        {
                            "name": "end",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 1,
                        }
                    ],
                    "isStartStep": False,
                },
            ],
        }

        result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hola",
            progress_sink=sink,
        )

        # The ``capture`` step's resolved parameters must have
        # ``captured = "hola"`` (the previous step's output), not
        # the empty string the old bug produced.
        capture_step = next(
            step for step in result.steps if step.name == "capture"
        )
        assert capture_step.resolved_parameters is not None
        assert capture_step.resolved_parameters["captured"] == "hola", (
            f"lastOutput did not propagate: got "
            f"{capture_step.resolved_parameters['captured']!r}"
        )


class TestResolveOutcomeName:
    """Pin down the helper that maps routing target → outcome name."""

    def test_returns_none_when_no_outcomes(self) -> None:
        assert _resolve_outcome_name(
            {"name": "x", "type": "agent"},
            output="ok",
            next_step_name=None,
        ) is None

    def test_matches_end_workflow(self) -> None:
        step = {
            "outcomes": [
                {"name": "next", "nextStep": "y", "endWorkflow": False},
                {"name": "stop", "nextStep": None, "endWorkflow": True},
            ]
        }
        assert (
            _resolve_outcome_name(step, output="ok", next_step_name=None)
            == "stop"
        )

    def test_matches_next_step_name(self) -> None:
        step = {
            "outcomes": [
                {"name": "loop", "nextStep": "y", "endWorkflow": False},
                {"name": "stop", "nextStep": "z", "endWorkflow": False},
            ]
        }
        assert (
            _resolve_outcome_name(step, output="ok", next_step_name="z")
            == "stop"
        )

    def test_returns_none_when_no_match(self) -> None:
        step = {
            "outcomes": [
                {"name": "loop", "nextStep": "y", "endWorkflow": False},
            ]
        }
        assert (
            _resolve_outcome_name(step, output="ok", next_step_name="z")
            is None
        )


class TestWithStepError:
    def test_adds_synthetic_tool_invocation(self) -> None:
        step = AgentStepExecutionResult(name="x", type="agent", output="o")
        updated = _with_step_error(step, "boom")
        assert updated.tool_error_detected is True
        assert len(updated.tool_invocations) == 1
        assert updated.tool_invocations[0].tool_name == "__step_error__"
        assert updated.tool_invocations[0].error_message == "boom"

    def test_preserves_existing_tool_invocations(self) -> None:
        from src.application.agents.run_result import AgentToolCall

        step = AgentStepExecutionResult(
            name="x",
            type="agent",
            output="o",
            tool_invocations=[AgentToolCall(tool_name="search")],
        )
        updated = _with_step_error(step, "boom")
        assert len(updated.tool_invocations) == 2
        assert updated.tool_invocations[0].tool_name == "search"
        assert updated.tool_invocations[1].tool_name == "__step_error__"


def test_noop_sink_importable() -> None:
    """Sanity check that the no-op sink is reachable from the
    progress_sink module (the service imports it from there)."""
    assert NoOpProgressSink is not None
