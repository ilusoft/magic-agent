"""Agent state definition for LangGraph."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class AgentState(TypedDict, total=False):
    """State for the agent graph.

    Attributes:
        messages: Conversation messages (appended via add_messages reducer)
        context: Workflow variables and parameters
        step_outputs: Outputs from completed steps by step ID
        current_step: ID of the current step being executed
        iteration: Current iteration number
        max_iterations: Maximum allowed iterations
        run_id: Unique identifier for this run
        input: Original user input
        final_output: Final agent output (set on completion)
    """

    messages: Annotated[list[Any], add_messages]
    context: dict[str, Any]
    step_outputs: dict[str, Any]
    current_step: str
    iteration: int
    max_iterations: int
    run_id: str
    input: str
    final_output: str | None


def create_initial_state(
    run_id: str,
    input_text: str,
    max_iterations: int = 50,
    initial_context: dict[str, Any] | None = None,
) -> AgentState:
    """Create initial agent state.

    Args:
        run_id: Unique run identifier
        input_text: User input
        max_iterations: Maximum iterations allowed
        initial_context: Initial context variables

    Returns:
        Initial agent state
    """
    return AgentState(
        messages=[],
        context=initial_context or {},
        step_outputs={},
        current_step="",
        iteration=0,
        max_iterations=max_iterations,
        run_id=run_id,
        input=input_text,
        final_output=None,
    )