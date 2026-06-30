"""Agent executor for running the LangGraph workflow."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, AsyncGenerator, Callable

import structlog

from src.agent_runtime.graph import create_agent_graph, create_simple_chat_graph
from src.agent_runtime.state import AgentState, create_initial_state
from src.infrastructure.llm.factory import LLMFactory, get_llm_factory

logger = structlog.get_logger(__name__)


class AgentExecutor:
    """Executes agent workflows using LangGraph.

    Provides both synchronous and streaming execution with progress callbacks.
    """

    def __init__(
        self,
        llm_factory: LLMFactory | None = None,
    ) -> None:
        self._llm_factory = llm_factory or get_llm_factory()

    async def execute(
        self,
        input_text: str,
        llm_config: dict[str, Any],
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 50,
        initial_context: dict[str, Any] | None = None,
        progress_callback: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an agent workflow.

        Args:
            input_text: User input
            llm_config: LLM configuration dict
            tools: Optional list of tools
            system_prompt: Optional system prompt
            max_iterations: Maximum iterations
            initial_context: Initial context variables
            progress_callback: Optional callback for progress events

        Returns:
            Final execution result with output and metadata
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()

        # Create LLM
        llm = self._llm_factory.create_chat_model(
            provider=llm_config.get("provider", "azure-openai"),
            model=llm_config.get("model"),
            api_key=llm_config.get("api_key"),
            endpoint=llm_config.get("endpoint"),
            base_url=llm_config.get("base_url"),
            deployment=llm_config.get("deployment"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens"),
        )

        # Create graph
        if tools:
            graph = create_agent_graph(
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                max_iterations=max_iterations,
            )
        else:
            graph = create_simple_chat_graph(
                llm=llm,
                system_prompt=system_prompt,
            )

        # Create initial state
        state = create_initial_state(
            run_id=run_id,
            input_text=input_text,
            max_iterations=max_iterations,
            initial_context=initial_context,
        )

        # Emit start event
        if progress_callback:
            await progress_callback({
                "event_type": "start",
                "run_id": run_id,
                "iteration": 0,
                "max_iterations": max_iterations,
            })

        # Run graph
        try:
            config = {"recursion_limit": max_iterations + 10}
            final_state = await graph.ainvoke(state, config=config)

            duration_ms = int((time.time() - start_time) * 1000)

            result = {
                "run_id": run_id,
                "status": "complete",
                "output": final_state.get("final_output", ""),
                "duration_ms": duration_ms,
                "iteration": final_state.get("iteration", 0),
            }

            if progress_callback:
                await progress_callback({
                    "event_type": "complete",
                    "run_id": run_id,
                    "final_output": result["output"],
                    "total_duration_ms": duration_ms,
                    "max_iterations": max_iterations,
                })

            return result

        except Exception as e:
            logger.error("agent_execution_error", run_id=run_id, error=str(e))
            duration_ms = int((time.time() - start_time) * 1000)

            if progress_callback:
                await progress_callback({
                    "event_type": "error",
                    "run_id": run_id,
                    "error": str(e),
                    "recoverable": False,
                    "duration_ms": duration_ms,
                })

            return {
                "run_id": run_id,
                "status": "error",
                "error": str(e),
                "duration_ms": duration_ms,
            }

    async def execute_stream(
        self,
        input_text: str,
        llm_config: dict[str, Any],
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 50,
        initial_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute an agent workflow with streaming progress events.

        Args:
            input_text: User input
            llm_config: LLM configuration dict
            tools: Optional list of tools
            system_prompt: Optional system prompt
            max_iterations: Maximum iterations
            initial_context: Initial context variables

        Yields:
            Progress events
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()

        # Create LLM
        llm = self._llm_factory.create_chat_model(
            provider=llm_config.get("provider", "azure-openai"),
            model=llm_config.get("model"),
            api_key=llm_config.get("api_key"),
            endpoint=llm_config.get("endpoint"),
            base_url=llm_config.get("base_url"),
            deployment=llm_config.get("deployment"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens"),
        )

        # Create graph
        if tools:
            graph = create_agent_graph(
                llm=llm,
                tools=tools,
                system_prompt=system_prompt,
                max_iterations=max_iterations,
            )
        else:
            graph = create_simple_chat_graph(
                llm=llm,
                system_prompt=system_prompt,
            )

        # Create initial state
        state = create_initial_state(
            run_id=run_id,
            input_text=input_text,
            max_iterations=max_iterations,
            initial_context=initial_context,
        )

        # Emit start
        yield {
            "event_type": "start",
            "run_id": run_id,
            "iteration": 0,
            "max_iterations": max_iterations,
        }

        try:
            config = {"recursion_limit": max_iterations + 10}

            # Stream through graph
            async for chunk in graph.astream(state, config=config):
                for node_name, node_state in chunk.items():
                    yield {
                        "event_type": "node_progress",
                        "node": node_name,
                        "state": node_state,
                        "run_id": run_id,
                    }

            # Get final output
            duration_ms = int((time.time() - start_time) * 1000)

            yield {
                "event_type": "complete",
                "run_id": run_id,
                "final_output": state.get("final_output", ""),
                "total_duration_ms": duration_ms,
                "max_iterations": max_iterations,
            }

        except Exception as e:
            logger.error("agent_stream_error", run_id=run_id, error=str(e))
            duration_ms = int((time.time() - start_time) * 1000)

            yield {
                "event_type": "error",
                "run_id": run_id,
                "error": str(e),
                "recoverable": False,
                "duration_ms": duration_ms,
            }


# Singleton executor
_executor: AgentExecutor | None = None


def get_agent_executor() -> AgentExecutor:
    """Get the agent executor singleton."""
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor