"""Chat node for LLM-based conversation with tools."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool

from src.agent_runtime.state import AgentState


async def chat_node(
    state: AgentState,
    llm: Any,
    tools: list[BaseTool] | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Execute a chat turn with the LLM.

    Args:
        state: Current agent state
        llm: LLM chat model
        tools: Optional list of tools available to the LLM
        system_prompt: Optional system prompt to prepend

    Returns:
        Dictionary of state updates to apply
    """
    messages = list(state.get("messages", []))

    # Build message list with optional system prompt
    chat_messages = []
    if system_prompt:
        from langchain_core.messages import SystemMessage
        chat_messages.append(SystemMessage(content=system_prompt))
    chat_messages.extend(messages)

    # Bind tools if provided
    if tools:
        llm_with_tools = llm.bind_tools(tools)
        response = await llm_with_tools.ainvoke(chat_messages)
    else:
        response = await llm.ainvoke(chat_messages)

    return {
        "messages": [response],
        "current_step": "chat",
    }


async def simple_chat_node(state: AgentState, llm: Any) -> dict[str, Any]:
    """Simple chat node without tools.

    Args:
        state: Current agent state
        llm: LLM chat model

    Returns:
        Dictionary of state updates to apply
    """
    return await chat_node(state, llm, tools=None, system_prompt=None)


async def tool_calling_chat_node(
    state: AgentState,
    llm: Any,
    tools: list[BaseTool],
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Chat node that always expects tool calls.

    Args:
        state: Current agent state
        llm: LLM chat model configured for tool calling
        tools: List of available tools
        system_prompt: Optional system prompt

    Returns:
        Dictionary of state updates to apply
    """
    return await chat_node(state, llm, tools=tools, system_prompt=system_prompt)