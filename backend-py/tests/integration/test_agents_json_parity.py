"""End-to-end validation of the user's ``agents.json`` in Python.

These tests load ``configs/agents/agents.json`` directly and run
the ``qualify-pricing-production`` workflow with a stubbed LLM so
we can assert the streaming and JSON paths both produce the same
identifiers and outputs the .NET backend would.

The point is parity: any ``agents.json`` that runs on .NET must
run identically on Python, with ``lastOutput`` resolving to the
previous step's output at every iteration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.agent_runtime.progress_sink import NoOpProgressSink
from src.agent_runtime.workflow_executor import WorkflowExecutor


_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENTS_JSON = _REPO_ROOT / "configs" / "agents" / "agents.json"


def _load_qualify_pricing_agent() -> dict[str, Any]:
    assert _AGENTS_JSON.exists(), f"missing {_AGENTS_JSON}"
    with _AGENTS_JSON.open() as fh:
        document = json.load(fh)
    agents = document.get("agents") or []
    agent = next(
        (a for a in agents if a.get("id") == "qualify-pricing-production"),
        None,
    )
    assert agent is not None, "qualify-pricing-production not in agents.json"
    return agent


class _SequenceStub:
    """Stub LLM factory that returns the next canned response."""

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = list(outputs)
        self.index = 0

    def create_chat_model(self, **_kwargs: Any) -> Any:
        outer = self

        class _Chat:
            async def ainvoke(self, _messages: Any) -> Any:
                content = outer.outputs[outer.index % len(outer.outputs)]
                outer.index += 1

                class _Resp:
                    def __init__(self, content: str) -> None:
                        self.content = content

                return _Resp(content)

        return _Chat()


def _halt_after_first_iteration(agent_def: dict) -> None:
    """Patch the agent so the iterator step terminates the loop
    after one iteration, so the test doesn't have to provide four
    distinct LLM responses just to reach ``set-out-vars``.
    """
    for step in agent_def["steps"]:
        if step.get("name") == "increment-iterator":
            for outcome in step.get("outcomes", []):
                if outcome.get("name") == "continue":
                    outcome["condition"] = {"expression": "false"}


def _translations_of(step: Any) -> list:
    """Coerce the step's resolved ``translations`` to a list.

    The resolver may return the value as a JSON string (when the
    variable type is ``json`` and the result is a list literal) or
    as a Python list directly.
    """
    raw = step.resolved_parameters.get("translations") if step.resolved_parameters else None
    if raw is None:
        return []
    if isinstance(raw, str):
        return json.loads(raw)
    return list(raw)


class TestQualifyPricingAgent:
    """Run the user's real ``agents.json`` end-to-end."""

    @pytest.mark.asyncio
    async def test_streaming_path_picks_up_last_output(self) -> None:
        """The Python streaming executor must propagate ``lastOutput``
        across iterations the way the .NET backend does.

        The workflow's ``increment-iterator`` step uses
        ``${{ addToArray(var.translations, lastOutput) }}`` to push
        the chat step's output into a translations array. If the
        bug were back, that array would contain ``None`` or ``""``
        instead of the chat output.
        """
        agent_def = _load_qualify_pricing_agent()
        _halt_after_first_iteration(agent_def)

        executor = WorkflowExecutor(
            llm_factory=_SequenceStub(["Hola mundo (es)"])  # type: ignore[arg-type]
        )

        result = await executor.execute_stream(
            agent_definition=agent_def,  # type: ignore[arg-type]
            input_text="Hello world",
            progress_sink=NoOpProgressSink(),
        )

        step_names = [step.name for step in result.steps]
        assert "set-initial-vars" in step_names
        assert "general chat agent" in step_names
        assert "increment-iterator" in step_names

        # The chat step's output ("Hola mundo (es)") should have
        # been appended to translations via the ``lastOutput``
        # reference. If the bug were back, this would be ``[None]``
        # or ``[""]``.
        increment_step = next(
            step for step in result.steps if step.name == "increment-iterator"
        )
        translations = _translations_of(increment_step)
        assert any(
            isinstance(t, str) and "Hola" in t for t in translations
        ), (
            f"translations did not pick up lastOutput: {translations!r}"
        )