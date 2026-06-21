"""Parity tests for the expression context / runtime state.

These pin the contract that lets a single ``agents.json`` file
work against both the .NET and the Python backends. The .NET
backend exposes a small set of per-step identifiers through
``WorkflowExpressionContext.RuntimeState`` (``output``,
``stepName``, ``stepType``) and the workflow orchestrator passes
the previous step's output as ``lastOutput``.

The Python backend must expose the same identifiers or any
``agents.json`` that references them (e.g. in outcome
conditions) will behave differently across backends.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.service import (
    ExpressionResult,
    WorkflowExpressionService,
)


@pytest.fixture
def service() -> WorkflowExpressionService:
    return WorkflowExpressionService()


def _evaluate(
    service: WorkflowExpressionService, expression: str, context: ExpressionContext
) -> Any:
    """Evaluate an expression and unwrap the ``ExpressionResult``."""
    result: ExpressionResult = service.evaluate(expression, context)
    assert result.error is None, f"unexpected error: {result.error}"
    return result.value


class TestLastOutputParity:
    """``lastOutput`` must resolve to the previous step's output."""

    def test_last_output_exposed_as_identifier(
        self, service: WorkflowExpressionService
    ) -> None:
        ctx = ExpressionContext(last_output="Bonjour le monde")
        assert _evaluate(service, "lastOutput", ctx) == "Bonjour le monde"

    def test_last_output_defaults_to_none(
        self, service: WorkflowExpressionService
    ) -> None:
        ctx = ExpressionContext()
        # No previous step → resolver's None-fallback is the empty
        # string (so the placeholder resolves to "" rather than the
        # literal "lastOutput").
        assert _evaluate(service, "lastOutput", ctx) == ""


class TestRuntimeStateParity:
    """Mirror the .NET ``RuntimeState`` identifiers.

    The .NET ``StepOutcomeResolver.BuildRuntimeState`` exposes
    ``output``, ``stepName`` and ``stepType`` as top-level
    identifiers in outcome-condition expressions. The Python
    expression engine has to do the same so a workflow that uses
    ``${{ output }}`` or ``${{ stepType }}`` in a condition runs
    identically on both backends.
    """

    def test_output_resolves_from_runtime_state(
        self, service: WorkflowExpressionService
    ) -> None:
        ctx = ExpressionContext(
            runtime_state={"output": "Hola", "stepName": "x", "stepType": "agent"}
        )
        assert _evaluate(service, "output", ctx) == "Hola"

    def test_step_name_resolves_from_runtime_state(
        self, service: WorkflowExpressionService
    ) -> None:
        ctx = ExpressionContext(
            runtime_state={"output": "", "stepName": "translate", "stepType": "agent"}
        )
        assert _evaluate(service, "stepName", ctx) == "translate"

    def test_step_type_resolves_from_runtime_state(
        self, service: WorkflowExpressionService
    ) -> None:
        ctx = ExpressionContext(
            runtime_state={
                "output": "",
                "stepName": "translate",
                "stepType": "setVariables",
            }
        )
        assert _evaluate(service, "stepType", ctx) == "setVariables"

    def test_runtime_state_does_not_shadow_variables(
        self, service: WorkflowExpressionService
    ) -> None:
        """``var.X`` and ``param.X`` still win over a same-named
        runtime state entry — variables/parameters are resolved
        first in both .NET and Python.
        """
        ctx = ExpressionContext(
            variables={"output": "from-variables"},
            runtime_state={"output": "from-runtime-state"},
        )
        # Bare ``output`` is a runtime-state lookup; ``var.output``
        # is the variable lookup.
        assert _evaluate(service, "output", ctx) == "from-runtime-state"
        assert _evaluate(service, "var.output", ctx) == "from-variables"

    def test_runtime_state_does_not_shadow_last_output(
        self, service: WorkflowExpressionService
    ) -> None:
        """``lastOutput`` is a special-cased identifier; it must
        always win over a runtime_state key called ``lastOutput``
        (which isn't a valid runtime-state name anyway, but the
        principle is that ``lastOutput`` is a first-class slot).
        """
        ctx = ExpressionContext(
            last_output="from-previous-step",
            runtime_state={"lastOutput": "from-runtime-state"},
        )
        assert _evaluate(service, "lastOutput", ctx) == "from-previous-step"

    def test_unknown_runtime_state_returns_none(
        self, service: WorkflowExpressionService
    ) -> None:
        """A bare identifier that isn't ``input`` / ``lastOutput``
        and isn't in variables, parameters, or runtime state must
        not leak a KeyError — it resolves to ``None`` (which the
        resolver's None-fallback turns into ``""`` for placeholders).
        """
        ctx = ExpressionContext()
        assert _evaluate(service, "nonexistent", ctx) is None


class TestCombinedParity:
    """Combined: the .NET workflow reference scenario."""

    def test_translation_loop_pattern(
        self, service: WorkflowExpressionService
    ) -> None:
        """Replicate the expression from the user's ``agents.json``
        where ``${{ addToArray(var.translations, lastOutput) }}``
        appends the previous step's output to a translations list.
        """
        ctx = ExpressionContext(
            variables={"translations": ["uno"]},
            last_output="dos",
        )
        result = _evaluate(
            service, "addToArray(var.translations, lastOutput)", ctx
        )
        # The helper should append ``dos`` to the existing list.
        assert result == ["uno", "dos"]
