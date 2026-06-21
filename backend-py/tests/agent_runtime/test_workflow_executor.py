"""Tests for the workflow executor.

These tests focus on the regression cases we hit while debugging the
qualify-pricing-production agent: the resolver exposing ``lastOutput`` to
``setVariables`` steps that follow an ``agent`` step, and the
``resolved_step`` initialisation that keeps ``_determine_next_step`` safe
when a step raises before its parameters are resolved.
"""

from __future__ import annotations

import pytest

from src.agent_runtime.workflow_executor import WorkflowExecutor


class TestResolveStep:
    """Regression tests for ``WorkflowExecutor._resolve_step``."""

    def setup_method(self) -> None:
        self.executor = WorkflowExecutor()

    def test_last_output_resolved_in_set_variables_step(self) -> None:
        """``lastOutput`` must be available when resolving a
        ``setVariables`` step's parameters.

        Regression: the resolver built its own context without
        ``last_output``, so expressions like
        ``${{ addToArray(var.translations, lastOutput) }}`` evaluated
        with ``lastOutput = None`` and pushed ``None`` into the array.
        """
        step = {
            "name": "increment-iterator",
            "type": "setVariables",
            "parameters": {
                "lastSeen": "${{ lastOutput }}",
            },
            "variableTypes": {"lastSeen": "string"},
        }
        variables = {"translations": []}
        step_outputs = {
            "general chat agent": {
                "type": "agent",
                "output": "Hola mundo",
            }
        }

        resolved = self.executor._resolve_step(
            step=step,
            variables=variables,
            parameters={},
            input_text="Hello",
            step_outputs=step_outputs,
            last_output="Hola mundo",
        )

        assert resolved["parameters"]["lastSeen"] == "Hola mundo"

    def test_last_output_defaults_to_none(self) -> None:
        """When ``last_output`` is omitted, ``lastOutput`` resolves to an
        empty string (the resolver's None-fallback), not the previous
        step's actual output.
        """
        step = {
            "name": "echo-last",
            "type": "setVariables",
            "parameters": {"x": "${{ lastOutput }}"},
            "variableTypes": {"x": "string"},
        }
        resolved = self.executor._resolve_step(
            step=step,
            variables={},
            parameters={},
            input_text="hi",
            step_outputs={},
        )
        assert resolved["parameters"]["x"] == ""


class TestDetermineNextStep:
    """Regression tests for ``_determine_next_step`` resilience."""

    def setup_method(self) -> None:
        self.executor = WorkflowExecutor()

    def test_returns_none_when_no_outcomes(self) -> None:
        assert self.executor._determine_next_step(
            step={"name": "x", "type": "setVariables", "parameters": {}},
            output="ok",
            variables={},
            context=None,  # type: ignore[arg-type]
        ) is None

    def test_takes_default_outcome(self) -> None:
        result = self.executor._determine_next_step(
            step={
                "name": "x",
                "type": "setVariables",
                "parameters": {},
                "outcomes": [
                    {
                        "name": "next",
                        "nextStep": "next-step",
                        "condition": None,
                        "endWorkflow": False,
                        "order": 1,
                    }
                ],
            },
            output="ok",
            variables={},
            context=None,  # type: ignore[arg-type]
        )
        assert result == "next-step"

    def test_skips_falsy_condition_outcome(self) -> None:
        result = self.executor._determine_next_step(
            step={
                "name": "x",
                "type": "setVariables",
                "parameters": {},
                "outcomes": [
                    {
                        "name": "loop",
                        "nextStep": "loop-step",
                        "condition": {"expression": "false"},
                        "endWorkflow": False,
                        "order": 1,
                    },
                    {
                        "name": "stop",
                        "nextStep": "end",
                        "condition": None,
                        "endWorkflow": False,
                        "order": 2,
                    },
                ],
            },
            output="ok",
            variables={},
            context=None,  # type: ignore[arg-type]
        )
        assert result == "end"

    def test_returns_none_on_end_workflow(self) -> None:
        result = self.executor._determine_next_step(
            step={
                "name": "x",
                "type": "setVariables",
                "parameters": {},
                "outcomes": [
                    {
                        "name": "finish",
                        "nextStep": None,
                        "condition": None,
                        "endWorkflow": True,
                        "order": 1,
                    }
                ],
            },
            output="ok",
            variables={},
            context=None,  # type: ignore[arg-type]
        )
        assert result is None


@pytest.mark.asyncio
class TestExecuteWorkflowStepResolution:
    """End-to-end-ish tests for ``_execute_workflow`` using a stubbed
    LLM factory so we don't need real Azure OpenAI credentials.
    """

    class _StubLLMFactory:
        """Returns a canned response for any chat invocation."""

        def __init__(
            self,
            response: str = "Bonjour le monde",
            should_raise: Exception | None = None,
        ) -> None:
            self.response = response
            self.should_raise = should_raise
            self.invocations: list[dict] = []

        def create_chat_model(self, **_kwargs):  # type: ignore[no-untyped-def]
            return self._ChatModel(self)

        class _ChatModel:
            def __init__(self, outer) -> None:  # type: ignore[no-untyped-def]
                self.outer = outer

            async def ainvoke(self, messages):  # type: ignore[no-untyped-def]
                if self.outer.should_raise is not None:
                    raise self.outer.should_raise
                self.outer.invocations.append(
                    {"messages": [m.content for m in messages]}
                )

                class _Resp:
                    def __init__(self, content: str) -> None:
                        self.content = content

                return _Resp(self.outer.response)

    def _executor_with_stub(
        self,
        response: str = "Bonjour le monde",
        should_raise: Exception | None = None,
    ) -> tuple[WorkflowExecutor, "_StubLLMFactory"]:
        stub = self._StubLLMFactory(response=response, should_raise=should_raise)
        executor = WorkflowExecutor(llm_factory=stub)  # type: ignore[arg-type]
        return executor, stub

    async def test_resolved_step_defined_when_step_raises(self) -> None:
        """Regression: an exception inside ``_execute_step`` previously
        left ``resolved_step`` undefined, which made the next iteration's
        ``_determine_next_step`` raise ``UnboundLocalError``. The fix
        initialises ``resolved_step = step`` before the try block.

        We trigger the exception with a stub LLM that raises on the
        first chat call. The agent step records the error, the loop
        evaluates the next outcome (which falls through to the
        "next-step" outcome), and the workflow reaches the end.
        """
        executor, _stub = self._executor_with_stub(
            should_raise=RuntimeError("boom")
        )

        agent_def = {
            "id": "agent-with-failing-step",
            "name": "agent-with-failing-step",
            "defaultParameters": {},
            "steps": [
                {
                    "name": "chat",
                    "type": "agent",
                    "parameters": {
                        "systemPrompt": "say hi",
                        "message": "hello",
                    },
                    "outcomes": [
                        {
                            "name": "next",
                            "nextStep": "finish-step",
                            "condition": None,
                            "endWorkflow": False,
                            "order": 1,
                        }
                    ],
                    "isStartStep": True,
                },
                {
                    "name": "finish-step",
                    "type": "setVariables",
                    "parameters": {"done": "yes"},
                    "variableTypes": {"done": "string"},
                    "outcomes": [
                        {
                            "name": "finish",
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

        # Should NOT raise UnboundLocalError: the failing step is recorded
        # with an error, the loop moves on, and the workflow reaches the
        # end via the "next -> finish-step -> finish" chain.
        result = await executor.execute(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="hi",
        )
        assert result["status"] == "complete"
        assert "chat" in result["steps"]
        # The failing step has an error recorded and no output.
        assert result["steps"]["chat"].get("error")
        assert result["steps"]["chat"]["output"] is None
        # The follow-up step ran.
        assert "finish-step" in result["steps"]
