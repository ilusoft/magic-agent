"""Tool node for executing tools and processing tool results."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from src.agent_runtime.state import AgentState


async def tool_node(
    state: AgentState,
    tools: list[Any],
    tool_executor: Any | None = None,
) -> dict[str, Any]:
    """Execute tools based on the last LLM message.

    Args:
        state: Current agent state
        tools: List of available tools
        tool_executor: Optional custom tool executor

    Returns:
        Dictionary of state updates to apply
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]

    # Check if last message has tool calls
    if not isinstance(last_message, AIMessage):
        return {}

    tool_calls = last_message.tool_calls or []
    if not tool_calls:
        return {}

    # Execute each tool call
    tool_results = []
    for call in tool_calls:
        tool_name = call.get("name")
        tool_args = call.get("args", {})

        # Find the tool
        tool = None
        for t in tools:
            if t.name == tool_name:
                tool = t
                break

        if not tool:
            tool_results.append({
                "tool_call_id": call.get("id"),
                "error": f"Tool not found: {tool_name}",
            })
            continue

        # Execute the tool
        try:
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(tool_args)
            elif hasattr(tool, "invoke"):
                result = tool.invoke(tool_args)
            else:
                result = tool.func(**tool_args)

            tool_results.append({
                "tool_call_id": call.get("id"),
                "result": result,
            })
        except Exception as e:
            tool_results.append({
                "tool_call_id": call.get("id"),
                "error": str(e),
            })

    # Create tool messages
    tool_messages = []
    for result in tool_results:
        tool_messages.append(
            ToolMessage(
                content=str(result.get("result", result.get("error", ""))),
                tool_call_id=result["tool_call_id"],
            )
        )

    return {
        "messages": tool_messages,
        "current_step": "tools",
    }


async def sequential_tool_node(
    state: AgentState,
    tools: list[Any],
) -> dict[str, Any]:
    """Execute tools sequentially, collecting all results.

    Args:
        state: Current agent state
        tools: List of tools to execute in order

    Returns:
        Dictionary of state updates to apply
    """
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]
    if not isinstance(last_message, AIMessage):
        return {}

    tool_calls = last_message.tool_calls or []
    if not tool_calls:
        return {}

    tool_messages = []

    for call in tool_calls:
        tool_name = call.get("name")
        tool_args = call.get("args", {})

        tool = next((t for t in tools if t.name == tool_name), None)
        if not tool:
            continue

        try:
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(tool_args)
            else:
                result = tool.invoke(tool_args)

            tool_messages.append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=call.get("id"),
                )
            )
        except Exception as e:
            tool_messages.append(
                ToolMessage(
                    content=f"Error: {str(e)}",
                    tool_call_id=call.get("id"),
                )
            )

    return {
        "messages": tool_messages,
        "current_step": "tools",
    }