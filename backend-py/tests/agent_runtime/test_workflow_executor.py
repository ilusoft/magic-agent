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


class TestAgentLoop:
    """Regression tests for ``_run_agent_loop``.

    These cover the empty-output bug the user hit on the real
    Qwen3.6 model: the LLM made a tool call, the tool ran, then
    the synthesis call returned *another* tool call (or empty
    content). The single-round ``_handle_tool_calls`` path silently
    dropped those cases; the new loop iterates until the model
    produces a text response or the iteration cap is hit.
    """

    @pytest.mark.asyncio
    async def test_loop_terminates_on_first_text_response(self) -> None:
        """Baseline: the LLM returns text on the first call, the
        loop must not spin."""
        from langchain_core.messages import AIMessage
        from langchain_core.tools import Tool

        async def _search(query: str) -> str:
            return f"results for {query}"

        tool = Tool(name="web_search", description="search", func=_search)
        llm = _SequenceLLM([AIMessage(content="the capital is Paris")])
        executor = WorkflowExecutor()

        from langchain_core.messages import HumanMessage

        response = await executor._run_agent_loop(
            llm=llm,
            messages=[HumanMessage(content="What's the capital of France?")],
            tools=[tool],
        )
        assert response.content == "the capital is Paris"
        # Only one LLM call should have been made.
        assert llm.call_count == 1

    @pytest.mark.asyncio
    async def test_loop_handles_multiple_tool_call_rounds(self) -> None:
        """The LLM makes a tool call, then a *second* tool call on
        the synthesis turn, then finally text. This is the exact
        pattern observed with the real Qwen model."""
        from langchain_core.messages import AIMessage, ToolCall
        from langchain_core.tools import Tool

        async def _search(query: str) -> str:
            return f"results for {query}"

        tool = Tool(name="web_search", description="search", func=_search)
        llm = _SequenceLLM(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="web_search",
                            args={"query": "France capital"},
                            id="call_1",
                        )
                    ],
                ),
                # Second LLM call also returns a tool call (Qwen did
                # this with the real Tavily workflow).
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="web_search",
                            args={"query": "France population"},
                            id="call_2",
                        )
                    ],
                ),
                # Third LLM call finally returns text.
                AIMessage(content="the capital of France is Paris"),
            ]
        )
        executor = WorkflowExecutor()

        from langchain_core.messages import HumanMessage

        response = await executor._run_agent_loop(
            llm=llm,
            messages=[HumanMessage(content="What's the capital of France?")],
            tools=[tool],
        )
        assert response.content == "the capital of France is Paris"
        assert llm.call_count == 3

    @pytest.mark.asyncio
    async def test_loop_returns_last_response_on_iteration_cap(self) -> None:
        """If the LLM keeps requesting tool calls past the cap, the
        loop returns the last response (with a warning) instead of
        hanging or returning empty content silently."""
        from langchain_core.messages import AIMessage, ToolCall
        from langchain_core.tools import Tool

        async def _search(query: str) -> str:
            return f"results for {query}"

        tool = Tool(name="web_search", description="search", func=_search)
        # 10 tool calls in a row; default cap is 8.
        llm = _SequenceLLM(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="web_search",
                            args={"query": f"q{i}"},
                            id=f"call_{i}",
                        )
                    ],
                )
                for i in range(10)
            ]
        )
        executor = WorkflowExecutor()

        from langchain_core.messages import HumanMessage

        response = await executor._run_agent_loop(
            llm=llm,
            messages=[HumanMessage(content="hi")],
            tools=[tool],
        )
        # Should have stopped at the cap, not run all 10.
        assert llm.call_count == 8
        # Last response had a tool call (no text).
        assert not response.content
        assert response.tool_calls

    @pytest.mark.asyncio
    async def test_loop_passes_tool_args_intact(self) -> None:
        """The LLM's structured tool-call args must reach the tool
        unchanged — a regression of the LangChain Tool collapse bug
        would surface here as the tool receiving a string instead
        of a dict.

        Uses ``StructuredTool`` (the same class the MCP wrapper
        uses) so the structured ``{"query": ...}`` payload from
        the LLM survives the ``ainvoke`` round-trip; the legacy
        ``Tool`` class collapses a single-key dict to its first
        value, which is the original bug we're guarding against.
        """
        from typing import Any, Dict

        from langchain_core.messages import AIMessage, ToolCall
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, ConfigDict, Field

        captured: list[dict] = []

        class _Args(BaseModel):
            model_config = ConfigDict(extra="allow")
            mcp_call_args: Dict[str, Any] = Field(default_factory=dict)

        async def _coroutine(mcp_call_args: Dict[str, Any], **kwargs: Any) -> str:
            if kwargs:
                captured.append(dict(kwargs))
            elif mcp_call_args:
                captured.append(dict(mcp_call_args))
            return "results"

        tool = StructuredTool(
            name="web_search",
            description="search",
            args_schema=_Args,
            func=lambda mcp_call_args, **kw: "sync",
            coroutine=_coroutine,
        )
        llm = _SequenceLLM(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            name="web_search",
                            args={"query": "France capital"},
                            id="call_1",
                        )
                    ],
                ),
                AIMessage(content="Paris"),
            ]
        )
        executor = WorkflowExecutor()

        from langchain_core.messages import HumanMessage

        await executor._run_agent_loop(
            llm=llm,
            messages=[HumanMessage(content="hi")],
            tools=[tool],
        )
        assert captured == [{"query": "France capital"}]


class _SequenceLLM:
    """Stub LLM that returns the next ``AIMessage`` from ``responses``
    on each ``ainvoke`` call, recording how many calls were made.

    Used by the ``TestAgentLoop`` regression tests above.
    """

    def __init__(self, responses: list) -> None:  # type: ignore[no-untyped-def]
        self.responses = list(responses)
        self.call_count = 0

    def bind_tools(self, tools):  # type: ignore[no-untyped-def]
        # Return self so the executor's ``llm_with_tools.ainvoke`` path
        # still lands on our ``ainvoke`` below.
        return self

    async def ainvoke(self, messages):  # type: ignore[no-untyped-def]
        if self.call_count >= len(self.responses):
            # Past the planned sequence — return a no-op text response
            # so the test doesn't accidentally exercise the empty-
            # response path it wasn't written for.
            from langchain_core.messages import AIMessage

            return AIMessage(content="")
        response = self.responses[self.call_count]
        self.call_count += 1
        return response
