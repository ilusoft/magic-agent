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


class TestLLMConfigCapture:
    """The diagnostics endpoint exposes which LLM actually handled a
    step so operators can confirm the expected backend (e.g. local
    qwen vs. Azure OpenAI) was called. These tests pin down the
    ``llm_config`` snapshot on ``AgentStepExecutionResult``.
    """

    class _StubLLMFactory:
        def __init__(self, response: str = "ok") -> None:
            self.response = response
            self.invocations: list[dict[str, Any]] = []

        def create_chat_model(self, **kwargs: Any) -> Any:
            return self._ChatModel(self, kwargs)

        class _ChatModel:
            def __init__(self, outer: "_StubLLMFactory", kwargs: dict[str, Any]) -> None:
                self.outer = outer
                self.kwargs = kwargs

            async def ainvoke(self, _messages: Any) -> Any:
                self.outer.invocations.append(self.kwargs)

                class _Resp:
                    def __init__(self, content: str) -> None:
                        self.content = content

                return _Resp(self.outer.response)

    @pytest.mark.asyncio
    async def test_azure_agent_step_records_provider_and_endpoint(self) -> None:
        """An Azure-backed agent step should surface
        ``provider=azure-openai`` and the resolved endpoint/deployment
        on the step result so the debug endpoint can prove the cloud
        LLM was actually called.
        """
        stub = self._StubLLMFactory()
        executor = WorkflowExecutor(llm_factory=stub)  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "azure-agent",
            "name": "azure-agent",
            "provider": "azure-openai",
            "endpoint": "https://example.openai.azure.com/",
            "deployment": "gpt-5-mini",
            "apiKey": "secret-1234abcd",
            "apiVersion": "2024-12-01-preview",
            "defaultParameters": {"temperature": "0.5"},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "hello"},
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
                },
            ],
        }

        await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        chat_step = sink.step_completes[0]["step"]
        assert chat_step.llm_config is not None
        assert chat_step.llm_config.provider == "azure-openai"
        assert chat_step.llm_config.model == "gpt-4o"  # default from agent def
        assert chat_step.llm_config.endpoint == "https://example.openai.azure.com/"
        assert chat_step.llm_config.deployment == "gpt-5-mini"
        assert chat_step.llm_config.api_version == "2024-12-01-preview"
        assert chat_step.llm_config.base_url is None
        # Fingerprint keeps the last 4 characters of the explicit key
        # so operators can tell two keys apart without seeing the secret.
        assert chat_step.llm_config.api_key_fingerprint == "***abcd"

        # Factory was invoked with the Azure endpoint, not a base_url.
        kwargs = stub.invocations[0]
        assert kwargs["provider"] == "azure-openai"
        assert kwargs["endpoint"] == "https://example.openai.azure.com/"
        assert kwargs["api_key"] == "secret-1234abcd"
        assert "base_url" not in kwargs or kwargs.get("base_url") is None

    @pytest.mark.asyncio
    async def test_openai_compatible_step_records_base_url(self) -> None:
        """An openai-compatible agent step should surface
        ``provider=openai-compatible`` and the ``base_url`` on the
        step result so the debug endpoint can prove the local qwen
        server (not Azure) was the one actually called.
        """
        stub = self._StubLLMFactory()
        executor = WorkflowExecutor(llm_factory=stub)  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "qwen-local",
            "name": "qwen-local",
            "provider": "openai-compatible",
            "baseUrl": "http://127.0.0.1:8000/v1",
            "model": "qwen-3.5",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "hello"},
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
                },
            ],
        }

        await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        chat_step = sink.step_completes[0]["step"]
        assert chat_step.llm_config is not None
        assert chat_step.llm_config.provider == "openai-compatible"
        assert chat_step.llm_config.base_url == "http://127.0.0.1:8000/v1"
        assert chat_step.llm_config.model == "qwen-3.5"
        # No Azure fields should leak into an openai-compatible config.
        assert chat_step.llm_config.endpoint is None
        assert chat_step.llm_config.deployment is None
        assert chat_step.llm_config.api_version is None
        # No explicit key on the agent → no fingerprint (so the
        # factory's ``not-needed`` placeholder is never reported back).
        assert chat_step.llm_config.api_key_fingerprint is None

        kwargs = stub.invocations[0]
        assert kwargs["provider"] == "openai-compatible"
        assert kwargs["base_url"] == "http://127.0.0.1:8000/v1"
        assert kwargs["model"] == "qwen-3.5"

    @pytest.mark.asyncio
    async def test_non_agent_step_has_no_llm_config(self) -> None:
        """``setVariables`` / ``echo`` steps never call an LLM, so
        ``llm_config`` must stay ``None`` on their step results.
        """
        stub = self._StubLLMFactory()
        executor = WorkflowExecutor(llm_factory=stub)  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "no-llm",
            "name": "no-llm",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "init",
                    "type": "setVariables",
                    "parameters": {"x": "1"},
                    "variableTypes": {"x": "string"},
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
                },
            ],
        }

        await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        step = sink.step_completes[0]["step"]
        assert step.llm_config is None
        # LLM factory must not be called for non-agent steps.
        assert stub.invocations == []

    @pytest.mark.asyncio
    async def test_failing_agent_step_still_emits_llm_config(self) -> None:
        """Even when the LLM call raises, the diagnostics payload
        should still surface the resolved ``llm_config`` so operators
        can see which backend was attempted (and whether the failure
        is in the expected provider, not a misrouted call).
        """
        class _RaisingFactory:
            def create_chat_model(self, **kwargs: Any) -> Any:  # type: ignore[no-untyped-def]
                self.kwargs = kwargs
                return self._ChatModel()

            class _ChatModel:
                async def ainvoke(self, _messages: Any) -> Any:  # type: ignore[no-untyped-def]
                    raise RuntimeError("boom")

        factory = _RaisingFactory()
        executor = WorkflowExecutor(llm_factory=factory)  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "qwen-failing",
            "name": "qwen-failing",
            "provider": "openai-compatible",
            "baseUrl": "http://127.0.0.1:8000/v1",
            "model": "qwen-3.5",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "hello"},
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
                },
            ],
        }

        await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        chat_step = sink.step_completes[0]["step"]
        assert chat_step.llm_config is not None
        assert chat_step.llm_config.provider == "openai-compatible"
        assert chat_step.llm_config.base_url == "http://127.0.0.1:8000/v1"
        # Error path still marks the step as failed.
        assert chat_step.tool_error_detected is True


class TestLLMConfigSurvivesRunResult:
    """Regression for the ``/debug`` endpoint and the SSE
    ``run-complete`` payload.

    The streaming sink's ``step_complete`` events already carry
    ``llm_config`` (set on the in-loop ``AgentStepExecutionResult``),
    but the final ``AgentRunResult`` that gets saved to the
    diagnostics store is rebuilt from a ``step_outputs`` dict at the
    end of ``execute_stream``. The rebuild must preserve ``llm_config``
    or the ``/debug`` endpoint — and the ``run-complete`` SSE event
    that the SPA listens to — both report ``llmConfig: null``.
    """

    @pytest.mark.asyncio
    async def test_run_result_carries_llm_config_per_step(self) -> None:
        """Both the ``run_result`` returned to the route layer and the
        one handed to ``run_complete`` must include the per-step
        ``llm_config`` so the diagnostics endpoint can render it.
        """
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "qwen-debug-roundtrip",
            "name": "qwen-debug-roundtrip",
            "provider": "openai-compatible",
            "baseUrl": "http://127.0.0.1:8000/v1",
            "model": "qwen-3.5",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {"systemPrompt": "hi", "message": "hello"},
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
                },
            ],
        }

        run_result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        # The ``run_complete`` sink event should also have the config.
        assert len(sink.run_completes) == 1
        assert sink.run_completes[0] is run_result
        assert len(run_result.steps) == 1
        chat = run_result.steps[0]
        assert chat.name == "chat"
        assert chat.llm_config is not None, (
            "llm_config must survive the final step rebuild so the "
            "/debug endpoint and the run-complete SSE payload can "
            "report which backend actually handled the step"
        )
        assert chat.llm_config.provider == "openai-compatible"
        assert chat.llm_config.base_url == "http://127.0.0.1:8000/v1"
        assert chat.llm_config.model == "qwen-3.5"

        # Wire format also has to keep the field for the SPA.
        wire = chat.to_dict()
        assert wire["llmConfig"] is not None
        assert wire["llmConfig"]["provider"] == "openai-compatible"
        assert wire["llmConfig"]["baseUrl"] == "http://127.0.0.1:8000/v1"

    @pytest.mark.asyncio
    async def test_diagnostics_store_returns_llm_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end check: persist the run, then read it back through
        the diagnostics store — the same path the
        ``/api/agents/{id}/runs/{cid}/debug`` endpoint follows.
        """
        from src.infrastructure.diagnostics.store import (
            InMemoryAgentDiagnosticsStore,
        )

        store = InMemoryAgentDiagnosticsStore()
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "qwen-store",
            "name": "qwen-store",
            "provider": "openai-compatible",
            "baseUrl": "http://127.0.0.1:8000/v1",
            "model": "qwen-3.5",
            "defaultParameters": {},
            "conversation": {"enabled": True},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {
                        "systemPrompt": "hi",
                        "message": "hello",
                    },
                    "conversation": {"enabled": True},
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
                },
            ],
        }

        run_result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )
        # ``execute_stream`` only saves to the diagnostics store when
        # the run produced a conversation_id (the agent above has
        # ``conversation.enabled = True`` so we get one).
        assert run_result.conversation_id is not None
        await store.save_run(run_result.conversation_id, run_result)

        loaded = await store.get_runs(run_result.conversation_id)
        assert len(loaded) == 1
        assert loaded[0].steps[0].llm_config is not None
        assert loaded[0].steps[0].llm_config.provider == "openai-compatible"
        assert loaded[0].steps[0].llm_config.base_url == (
            "http://127.0.0.1:8000/v1"
        )

    @pytest.mark.asyncio
    async def test_non_agent_step_rebuild_has_no_llm_config(self) -> None:
        """``setVariables``/``echo`` steps never call an LLM, so the
        rebuild must leave their ``llm_config`` as ``None``.
        """
        executor = WorkflowExecutor(llm_factory=_StubLLMFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "no-llm-roundtrip",
            "name": "no-llm-roundtrip",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "init",
                    "type": "setVariables",
                    "parameters": {"x": "1"},
                    "variableTypes": {"x": "string"},
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
                },
            ],
        }

        run_result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )
        assert run_result.steps[0].llm_config is None


class TestLoopExecutionHistory:
    """The diagnostics endpoint and the ``run-complete`` SSE event
    must surface *every* execution of a step — not just the last one.

    Regression: ``step_outputs[step_name] = step_record`` used to
    overwrite the previous iteration, so a workflow that loops
    (e.g. the multi-language-translator's per-language ``general
    chat agent`` call) only ever showed one entry in the debug
    panel.
    """

    @pytest.mark.asyncio
    async def test_loop_preserves_all_iterations_in_run_result(self) -> None:
        """A loop workflow should produce one ``chat`` entry per
        iteration plus the surrounding ``init`` / ``finish`` /
        ``echo`` entries — in execution order.

        ``max = 1`` keeps the iteration count predictable: the chat
        step fires twice (iter=0 loops, iter=1 finishes) so the
        assertion can pin down the exact outputs / outcomes.
        """

        class _CountingFactory:
            """Returns a different response per call so we can tell
            the iterations apart in the captured run result."""

            def __init__(self) -> None:
                self.call_count = 0

            def create_chat_model(self, **_kwargs: Any) -> Any:
                return self._ChatModel(self)

            class _ChatModel:
                def __init__(self, outer: "_CountingFactory") -> None:
                    self.outer = outer

                async def ainvoke(self, _messages: Any) -> Any:
                    self.outer.call_count += 1

                    class _Resp:
                        def __init__(self, content: str) -> None:
                            self.content = content

                    return _Resp(f"response-{self.outer.call_count}")

        executor = WorkflowExecutor(llm_factory=_CountingFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        # Mini version of the multi-language-translator: an init step
        # sets ``var.iterator = 0`` and ``var.max = 1``; chat emits a
        # different response per call; the increment step bumps the
        # iterator and loops back to ``chat`` while
        # ``var.iterator < var.max``.
        agent_def = {
            "id": "loop-agent",
            "name": "loop-agent",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "init",
                    "type": "setVariables",
                    "parameters": {"iterator": "0", "max": "1"},
                    "variableTypes": {"iterator": "number", "max": "number"},
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
                    "parameters": {
                        "systemPrompt": "hi",
                        "message": "iteration ${{ var.iterator }}",
                    },
                    "outcomes": [
                        {
                            "name": "loop",
                            "nextStep": "increment",
                            "condition": {
                                "expression": "var.iterator < var.max"
                            },
                            "endWorkflow": False,
                            "order": 1,
                        },
                        {
                            "name": "finish",
                            "nextStep": "echo",
                            "condition": None,
                            "endWorkflow": False,
                            "order": 2,
                        },
                    ],
                },
                {
                    "name": "increment",
                    "type": "setVariables",
                    "parameters": {"iterator": "${{ var.iterator + 1 }}"},
                    "variableTypes": {"iterator": "number"},
                    "outcomes": [
                        {
                            "name": "back",
                            "nextStep": "chat",
                            "condition": {"expression": "true"},
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                },
                {
                    "name": "echo",
                    "type": "echo",
                    "parameters": {"message": "done"},
                    "outcomes": [
                        {
                            "name": "end",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 1,
                        }
                    ],
                },
            ],
        }

        run_result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hello",
            progress_sink=sink,
        )

        # Build a per-name index so the assertion is robust to any
        # future reshuffling of the step list.
        by_name: dict[str, list[AgentStepExecutionResult]] = {}
        for step in run_result.steps:
            by_name.setdefault(step.name, []).append(step)

        assert list(by_name) == ["init", "chat", "increment", "echo"], (
            f"unexpected step order: {list(by_name)}"
        )
        assert len(by_name["chat"]) == 2, (
            "chat should have one entry per loop iteration; the /debug "
            "endpoint and the run-complete SSE event need every call so "
            "operators can audit each LLM invocation"
        )
        # Outputs must come from the actual chat invocations, in order.
        assert [s.output for s in by_name["chat"]] == [
            "response-1",
            "response-2",
        ]
        # Each chat iteration must carry its own outcome / nextStep
        # (pre-fix these were stripped on the rebuilt record).
        assert [s.outcome for s in by_name["chat"]] == ["loop", "finish"]
        assert [s.next_step for s in by_name["chat"]] == ["increment", "echo"]
        assert [s.end_workflow for s in by_name["chat"]] == [False, False]

        # The increment step also ran once (between the two chat
        # iterations).
        assert len(by_name["increment"]) == 1

        # The final ``echo`` step's output is what ``final_output``
        # surfaces, mirroring the ``lastOutput`` of the last record
        # in the history.
        assert run_result.steps[-1].name == "echo"
        assert run_result.steps[-1].output == "done"

        # The sink must have observed the same number of step_complete
        # events as ``run_result.steps`` entries (one per execution).
        assert len(sink.step_completes) == len(run_result.steps)
        assert len(sink.step_starts) == len(run_result.steps)
        # The run_complete event uses the same rebuilt run result.
        assert sink.run_completes == [run_result]

    @pytest.mark.asyncio
    async def test_loop_persists_all_iterations_in_diagnostics_store(
        self,
    ) -> None:
        """End-to-end: a loop workflow saved to the diagnostics store
        must read back with every iteration intact — that's exactly
        the path the ``/api/agents/{id}/runs/{cid}/debug`` endpoint
        serves.
        """
        from src.infrastructure.diagnostics.store import (
            InMemoryAgentDiagnosticsStore,
        )

        class _CountingFactory:
            def __init__(self) -> None:
                self.call_count = 0

            def create_chat_model(self, **_kwargs: Any) -> Any:
                return self._ChatModel(self)

            class _ChatModel:
                def __init__(self, outer: "_CountingFactory") -> None:
                    self.outer = outer

                async def ainvoke(self, _messages: Any) -> Any:
                    self.outer.call_count += 1

                    class _Resp:
                        def __init__(self, content: str) -> None:
                            self.content = content

                    return _Resp(f"response-{self.outer.call_count}")

        store = InMemoryAgentDiagnosticsStore()
        executor = WorkflowExecutor(llm_factory=_CountingFactory())  # type: ignore[arg-type]
        sink = _RecordingSink()

        agent_def = {
            "id": "loop-store",
            "name": "loop-store",
            "defaultParameters": {},
            "conversation": {"enabled": True},
            "steps": [
                {
                    "name": "init",
                    "type": "setVariables",
                    "parameters": {"iterator": "0", "max": "1"},
                    "variableTypes": {"iterator": "number", "max": "number"},
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
                    "parameters": {
                        "systemPrompt": "hi",
                        "message": "i ${{ var.iterator }}",
                    },
                    "conversation": {"enabled": True},
                    "outcomes": [
                        {
                            "name": "loop",
                            "nextStep": "increment",
                            "condition": {
                                "expression": "var.iterator < var.max"
                            },
                            "endWorkflow": False,
                            "order": 1,
                        },
                        {
                            "name": "finish",
                            "nextStep": None,
                            "condition": None,
                            "endWorkflow": True,
                            "order": 2,
                        },
                    ],
                },
                {
                    "name": "increment",
                    "type": "setVariables",
                    "parameters": {"iterator": "${{ var.iterator + 1 }}"},
                    "variableTypes": {"iterator": "number"},
                    "outcomes": [
                        {
                            "name": "back",
                            "nextStep": "chat",
                            "condition": {"expression": "true"},
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                },
            ],
        }

        run_result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hi",
            progress_sink=sink,
        )
        assert run_result.conversation_id is not None
        await store.save_run(run_result.conversation_id, run_result)

        loaded = await store.get_runs(run_result.conversation_id)
        assert len(loaded) == 1
        loaded_by_name: dict[str, list[AgentStepExecutionResult]] = {}
        for step in loaded[0].steps:
            loaded_by_name.setdefault(step.name, []).append(step)

        assert len(loaded_by_name["chat"]) == 2
        assert [s.output for s in loaded_by_name["chat"]] == [
            "response-1",
            "response-2",
        ]
        assert [s.outcome for s in loaded_by_name["chat"]] == ["loop", "finish"]
        assert [s.next_step for s in loaded_by_name["chat"]] == ["increment", None]
        assert [s.end_workflow for s in loaded_by_name["chat"]] == [False, True]
