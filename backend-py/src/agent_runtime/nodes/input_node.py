"""Input node for processing user input."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from src.agent_runtime.state import AgentState


async def input_node(state: AgentState) -> dict[str, Any]:
    """Process user input and initialize the conversation.

    This node is typically called at the start of a workflow to
    process the initial user input.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates to apply
    """
    input_text = state.get("input", "")

    if not input_text:
        return {}

    return {
        "messages": [HumanMessage(content=input_text)],
        "current_step": "input",
    }