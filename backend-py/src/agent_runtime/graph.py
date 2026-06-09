"""LangGraph state graph definition for agent execution."""

from __future__ import annotations

from functools import partial
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from src.agent_runtime.nodes.chat_node import chat_node
from src.agent_runtime.nodes.input_node import input_node
from src.agent_runtime.nodes.output_node import output_node
from src.agent_runtime.nodes.tool_node import tool_node
from src.agent_runtime.state import AgentState


def create_agent_graph(
    llm: Any,
    tools: list[Any] | None = None,
    system_prompt: str | None = None,
    max_iterations: int = 50,
) -> Any:
    """Create the agent state graph.

    The graph has the following structure:

        START -> input -> chat -> tools -> chat -> ... -> output -> END
                           ^        |
                           |________|

    The chat-tools cycle continues until:
    - The LLM produces a final response (no tool calls)
    - max_iterations is reached

    Args:
        llm: LLM chat model
        tools: Optional list of tools
        system_prompt: Optional system prompt
        max_iterations: Maximum iterations before forcing output

    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("input", input_node)
    graph.add_node("chat", partial(chat_node, llm=llm, tools=tools, system_prompt=system_prompt))
    graph.add_node("output", output_node)

    if tools:
        graph.add_node("tools", partial(tool_node, tools=tools))

    # Define edges
    graph.add_edge(START, "input")

    if tools:
        # With tools: input -> chat -> tools -> (chat or output)
        graph.add_edge("input", "chat")
        graph.add_edge("chat", "tools")

        # Conditional: if no tool calls, go to output
        def should_continue_with_tools(state: AgentState) -> Literal["chat", "output"]:
            messages = state.get("messages", [])
            if not messages:
                return "output"

            last = messages[-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "chat"
            return "output"

        graph.add_conditional_edges(
            "tools",
            should_continue_with_tools,
            {"chat": "chat", "output": "output"},
        )

        # Check iteration limit before going back to chat
        def should_continue_chat(state: AgentState) -> Literal["tools", "output"]:
            iteration = state.get("iteration", 0)
            max_iter = state.get("max_iterations", max_iterations)

            if iteration >= max_iter:
                return "output"

            messages = state.get("messages", [])
            if not messages:
                return "output"

            last = messages[-1]
            if hasattr(last, "tool_calls") and last.tool_calls:
                return "tools"
            return "output"

        graph.add_conditional_edges(
            "chat",
            should_continue_chat,
            {"tools": "tools", "output": "output"},
        )
    else:
        # Without tools: input -> chat -> output
        graph.add_edge("input", "chat")
        graph.add_edge("chat", "output")

    graph.add_edge("output", END)

    return graph.compile()


def create_simple_chat_graph(
    llm: Any,
    system_prompt: str | None = None,
) -> Any:
    """Create a simple chat-only graph (no tools).

    Args:
        llm: LLM chat model
        system_prompt: Optional system prompt

    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(AgentState)

    graph.add_node("input", input_node)
    graph.add_node("chat", partial(chat_node, llm=llm, tools=None, system_prompt=system_prompt))
    graph.add_node("output", output_node)

    graph.add_edge(START, "input")
    graph.add_edge("input", "chat")
    graph.add_edge("chat", "output")
    graph.add_edge("output", END)

    return graph.compile()


def should_continue(state: AgentState) -> Literal["chat", "end"]:
    """Determine if we should continue chatting or end.

    Args:
        state: Current agent state

    Returns:
        "chat" to continue or "end" to finish
    """
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 50)

    if iteration >= max_iterations:
        return "end"

    messages = state.get("messages", [])
    if not messages:
        return "end"

    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "chat"

    return "end"