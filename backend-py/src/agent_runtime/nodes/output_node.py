"""Output node for formatting and returning final results."""

from __future__ import annotations

from typing import Any

from src.agent_runtime.state import AgentState


async def output_node(state: AgentState) -> dict[str, Any]:
    """Format and return the final output.

    This node is called when the workflow is complete and extracts
    the final response from the conversation messages.

    Args:
        state: Current agent state

    Returns:
        Dictionary of state updates to apply
    """
    messages = state.get("messages", [])

    if not messages:
        return {"final_output": ""}

    # Get the last message content
    last_message = messages[-1]

    if hasattr(last_message, "content"):
        final_output = last_message.content
    else:
        final_output = str(last_message)

    return {
        "final_output": final_output,
        "current_step": "output",
    }


async def structured_output_node(
    state: AgentState,
    output_schema: type | None = None,
) -> dict[str, Any]:
    """Format output according to a schema.

    Args:
        state: Current agent state
        output_schema: Optional Pydantic model for structured output

    Returns:
        Dictionary of state updates to apply
    """
    messages = state.get("messages", [])
    if not messages:
        return {"final_output": ""}

    last_message = messages[-1]
    content = getattr(last_message, "content", str(last_message))

    if output_schema:
        # Try to parse as structured output
        try:
            import json
            data = json.loads(content)
            if hasattr(output_schema, "model_validate"):
                parsed = output_schema.model_validate(data)
                return {"final_output": parsed.model_dump_json()}
            else:
                # Fall back for non-Pydantic schemas
                return {"final_output": content}
        except Exception:
            pass

    return {"final_output": content}