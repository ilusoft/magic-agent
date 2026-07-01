"""End-to-end-ish reproduction of the multi-round memory bug.

The user reported that the ``web-search-tavily-qwen-local`` agent
defined in ``configs/agents/agents.json`` starts from scratch on
follow-up rounds even though the SPA sends the same
``conversation_id`` back. This test loads that real config (no
synthetic agent), stubs the LLM and the MCP registry, and runs the
workflow twice with the same id to confirm whether the prior
user/assistant turns make it into the second prompt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.agent_runtime.progress_sink import NoOpProgressSink
from src.agent_runtime.workflow_executor import WorkflowExecutor
from src.infrastructure.conversation.store import InMemoryAgentConversationStore


_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENTS_JSON = _REPO_ROOT / "configs" / "agents" / "agents.json"


def _load_web_search_agent() -> dict[str, Any]:
    with _AGENTS_JSON.open() as fh:
        document = json.load(fh)
    agent = next(
        (a for a in document["agents"] if a.get("id") == "web-search-tavily-qwen-local"),
        None,
    )
    assert agent is not None, "web-search-tavily-qwen-local not in agents.json"
    return agent


class _RecordingLLMFactory:
    """Stub LLM that records every prompt and returns canned text."""

    def __init__(self) -> None:
        self.invocations: list[list[str]] = []

    def create_chat_model(self, **_kwargs: Any) -> Any:
        return self._ChatModel(self)

    class _ChatModel:
        def __init__(self, outer: "_RecordingLLMFactory") -> None:
            self.outer = outer

        async def ainvoke(self, messages: Any) -> Any:
            self.outer.invocations.append(
                [str(m.content) for m in messages]
            )

            class _Resp:
                def __init__(self, content: str) -> None:
                    self.content = content

            return _Resp(f"reply-{len(self.outer.invocations)}")


class _StubMcpRegistry:
    """No-op MCP registry so the test doesn't try to reach Tavily."""

    async def initialize_from_agent(self, _agent_definition: dict) -> dict:
        return {}

    async def disconnect_all(self) -> None:
        return None


@pytest.mark.asyncio
async def test_web_search_agent_reuses_conversation_across_rounds() -> None:
    """Run the real ``web-search-tavily-qwen-local`` agent twice with
    the same ``conversation_id`` and assert the round-2 prompt
    contains the round-1 user message and the round-1 assistant reply.
    """
    agent_def = _load_web_search_agent()
    factory = _RecordingLLMFactory()
    executor = WorkflowExecutor(  # type: ignore[arg-type]
        llm_factory=factory,
        mcp_registry=_StubMcpRegistry(),  # type: ignore[arg-type]
        conversation_store=InMemoryAgentConversationStore(),
    )

    # Round 1: no conversation_id, the agent mints one.
    round1 = await executor.execute_stream(
        agent_definition=agent_def,
        input_text="What is the capital of France?",
        progress_sink=NoOpProgressSink(),
    )
    assert round1.conversation_id is not None
    first_id = round1.conversation_id

    assert len(factory.invocations) == 1
    round1_prompt = factory.invocations[0]
    # Round 1 sees only the system prompt + the new user question.
    # ``set-initial-vars`` resolves ``{{input}}`` into
    # ``var.userQuestion`` and the chat step's ``message`` re-emits it
    # as the user turn.
    assert any("capital of France" in msg for msg in round1_prompt), round1_prompt

    # Round 2: same conversation_id, follow-up question.
    round2 = await executor.execute_stream(
        agent_definition=agent_def,
        input_text="And what is its population?",
        progress_sink=NoOpProgressSink(),
        conversation_id=first_id,
    )
    assert round2.conversation_id == first_id

    assert len(factory.invocations) == 2
    round2_prompt = factory.invocations[1]

    # The follow-up should be in the round-2 prompt.
    assert any("And what is its population?" in msg for msg in round2_prompt), round2_prompt
    # The round-1 assistant reply should also be present — that is
    # the whole point of conversation memory.
    assert any("reply-1" in msg for msg in round2_prompt), round2_prompt
    # And the round-1 user question should be there too.
    assert any("capital of France" in msg for msg in round2_prompt), round2_prompt
