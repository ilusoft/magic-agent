"""Workflow graph builder - constructs LangGraph from workflow step definitions."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from src.agent_runtime.state import AgentState


class WorkflowGraphBuilder:
    """Builds a LangGraph from workflow step definitions.

    Supports dynamic graph construction based on workflow.steps[]:
    - input: Process user input
    - chat: LLM chat with optional tools
    - agent-step: Execute a referenced agent
    """

    def __init__(self) -> None:
        self._nodes: list[tuple[str, Any]] = []
        self._edges: list[tuple[str, str]] = []
        self._conditional_edges: list[tuple[str, Any, dict[Any, str]]] = []

    def add_node(self, name: str, node: Any) -> "WorkflowGraphBuilder":
        """Add a node to the graph.

        Args:
            name: Node name
            node: Node function

        Returns:
            Self for chaining
        """
        self._nodes.append((name, node))
        return self

    def add_edge(self, from_node: str, to_node: str) -> "WorkflowGraphBuilder":
        """Add a directed edge between nodes.

        Args:
            from_node: Source node
            to_node: Target node

        Returns:
            Self for chaining
        """
        self._edges.append((from_node, to_node))
        return self

    def add_conditional_edge(
        self, from_node: str, condition: Any, mapping: dict[Any, str]
    ) -> "WorkflowGraphBuilder":
        """Add a conditional edge.

        Args:
            from_node: Source node
            condition: Condition function
            mapping: Mapping of condition results to target nodes

        Returns:
            Self for chaining
        """
        self._conditional_edges.append((from_node, condition, mapping))
        return self

    def build(self) -> Any:
        """Build and compile the graph.

        Returns:
            Compiled StateGraph
        """
        graph = StateGraph(AgentState)

        # Add all nodes
        for name, node in self._nodes:
            graph.add_node(name, node)

        # Add start edge
        if self._nodes:
            graph.add_edge(START, self._nodes[0][0])

        # Add regular edges
        for from_node, to_node in self._edges:
            graph.add_edge(from_node, to_node)

        # Add conditional edges
        for from_node, condition, mapping in self._conditional_edges:
            graph.add_conditional_edges(from_node, condition, mapping)

        # Add end edge to last node if not already connected to END
        if self._nodes and not any(
            target == END for _, target in self._edges
        ):
            last_node = self._nodes[-1][0]
            if last_node not in [from_node for from_node, _ in self._edges]:
                pass  # Let the last node's conditional routing handle it
            else:
                # Check if last node already has an edge to END
                has_end_edge = any(
                    from_node == self._nodes[-1][0] and target == END
                    for from_node, target in self._edges
                )
                if not has_end_edge:
                    # Add conditional to END based on step completion
                    pass

        return graph.compile()

    @staticmethod
    def build_workflow_graph(
        steps: list[dict[str, Any]],
        llm_factory: Any,
        mcp_clients: dict[str, Any] | None = None,
    ) -> Any:
        """Build a workflow graph from step definitions.

        Args:
            steps: List of workflow step definitions
            llm_factory: LLM factory for creating chat models
            mcp_clients: Dict of MCP client instances by tool id

        Returns:
            Compiled StateGraph
        """
        builder = WorkflowGraphBuilder()
        mcp_clients = mcp_clients or {}

        for i, step in enumerate(steps):
            step_id = step.get("id", f"step_{i}")
            step_type = step.get("type", "chat")

            if step_type == "input":
                from src.agent_runtime.nodes.input_node import input_node
                builder.add_node(f"input_{step_id}", input_node)
                if i == 0:
                    pass  # Will be connected to START
                else:
                    builder.add_edge(f"step_{i-1}", f"input_{step_id}")

            elif step_type == "chat":
                from src.agent_runtime.nodes.chat_node import chat_node
                from functools import partial

                # Get step config
                parameters = step.get("parameters", {})
                system_prompt = parameters.get("systemPrompt")
                tools = parameters.get("tools", [])

                # Build tools list
                langchain_tools: list[Any] = []
                for tool_def in tools:
                    from src.infrastructure.mcp.tool_builder import ToolBuilder

                    tool_type = tool_def.get("type", "")
                    if tool_type == "http":
                        tool = ToolBuilder.from_http_definition(tool_def)
                        if tool:
                            langchain_tools.append(tool)
                    elif tool_type == "mcp":
                        tool_id = tool_def.get("id")
                        if tool_id and tool_id in mcp_clients:
                            tool = ToolBuilder.from_mcp_definition(
                                tool_def, mcp_clients[tool_id]
                            )
                            if tool:
                                langchain_tools.append(tool)

                # Create chat node with bound LLM
                # Note: LLM will be bound later when agent config is available
                chat_fn = partial(
                    chat_node,
                    tools=langchain_tools if langchain_tools else None,
                    system_prompt=system_prompt,
                )
                builder.add_node(f"chat_{step_id}", chat_fn)

                # Connect from previous step
                if i == 0:
                    builder.add_edge("__start__", f"chat_{step_id}")
                else:
                    prev_step = steps[i - 1]
                    prev_type = prev_step.get("type", "chat")
                    if prev_type == "input":
                        builder.add_edge(f"input_{prev_step.get('id', f'step_{i-1}')}", f"chat_{step_id}")
                    else:
                        builder.add_edge(f"chat_{prev_step.get('id', f'step_{i-1}')}", f"chat_{step_id}")

            elif step_type == "agent-step":
                from src.agent_runtime.nodes.chat_node import chat_node
                from functools import partial

                agent_id = step.get("agent")
                parameters = step.get("parameters", {})

                # Agent-step will be handled by loading the referenced agent
                # For now, create a placeholder that will be resolved at runtime
                chat_fn = partial(
                    chat_node,
                    tools=None,
                    system_prompt=parameters.get("systemPrompt"),
                )
                builder.add_node(f"agent_{step_id}", chat_fn)

                # Connect from previous step
                if i == 0:
                    builder.add_edge("__start__", f"agent_{step_id}")
                else:
                    prev_step = steps[i - 1]
                    prev_type = prev_step.get("type", "chat")
                    if prev_type == "input":
                        builder.add_edge(f"input_{prev_step.get('id', f'step_{i-1}')}", f"agent_{step_id}")
                    else:
                        builder.add_edge(f"chat_{prev_step.get('id', f'step_{i-1}')}", f"agent_{step_id}")

            elif step_type == "output":
                from src.agent_runtime.nodes.output_node import output_node
                builder.add_node(f"output_{step_id}", output_node)

                # Connect from previous step
                prev_step = steps[i - 1]
                prev_type = prev_step.get("type", "chat")
                if prev_type == "input":
                    builder.add_edge(f"input_{prev_step.get('id', f'step_{i-1}')}", f"output_{step_id}")
                else:
                    builder.add_edge(f"chat_{prev_step.get('id', f'step_{i-1}')}", f"output_{step_id}")

                builder.add_edge(f"output_{step_id}", END)

        # If no output step, connect last chat to END
        has_output = any(s.get("type") == "output" for s in steps)
        if not has_output and steps:
            last_step = steps[-1]
            if last_step.get("type") == "chat":
                builder.add_edge(f"chat_{last_step.get('id', 'final')}", END)
            elif last_step.get("type") == "input":
                builder.add_edge(f"input_{last_step.get('id', 'final')}", END)

        return builder.build()