"""Tests for the workflow expression service (resolver)."""

from __future__ import annotations

import pytest

from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.service import (
    ExpressionResult,
    ResolvedPlaceholder,
    ResolvedTemplate,
    WorkflowExpressionService,
    _scan_placeholders,
)


@pytest.fixture
def service() -> WorkflowExpressionService:
    return WorkflowExpressionService()


@pytest.fixture
def context() -> ExpressionContext:
    return ExpressionContext(
        variables={
            "name": "Jorge",
            "iterator": 0,
            "languages": {
                "values": ["spanish", "french", "german", "portuguese"],
            },
            "translations": [],
        },
        parameters={"temperature": "1"},
        input="Hello world",
        last_output="Hola mundo",
    )


class TestScanPlaceholders:
    """Tests for the brace-depth placeholder scanner."""

    def test_simple_placeholder(self) -> None:
        matches = _scan_placeholders("Hello {{name}}")
        assert len(matches) == 1
        start, end, content, is_expr = matches[0]
        assert content == "name"
        assert is_expr is False

    def test_expression_placeholder(self) -> None:
        matches = _scan_placeholders("Result: ${{1 + 2}}")
        assert len(matches) == 1
        start, end, content, is_expr = matches[0]
        assert content == "1 + 2"
        assert is_expr is True

    def test_does_not_double_match_expression(self) -> None:
        """${{ X }} must not also match the inner {{ X }}.

        Regression: the old regex produced two overlapping matches, which
        caused the resolver to evaluate and emit the value twice.
        """
        matches = _scan_placeholders("A ${{var.x}} B")
        assert len(matches) == 1
        start, end, content, is_expr = matches[0]
        assert content == "var.x"
        assert is_expr is True

    def test_handles_json_object_literal(self) -> None:
        """${{ { "values": [...] } }} must be matched in full.

        Regression: the old regex ``[^}]+`` stopped at the first ``}``
        inside the JSON, so the literal never resolved.
        """
        template = '${{ { "values": ["a", "b"] } }}'
        matches = _scan_placeholders(template)
        assert len(matches) == 1
        start, end, content, is_expr = matches[0]
        assert content.strip() == '{ "values": ["a", "b"] }'
        assert is_expr is True

    def test_handles_json_array_literal(self) -> None:
        template = '${{ [1, 2, 3] }}'
        matches = _scan_placeholders(template)
        assert len(matches) == 1
        _, _, content, is_expr = matches[0]
        assert content.strip() == "[1, 2, 3]"
        assert is_expr is True

    def test_multiple_placeholders(self) -> None:
        template = "A {{x}} B ${{y}} C {{z}} D"
        matches = _scan_placeholders(template)
        assert len(matches) == 3
        contents = [m[2] for m in matches]
        assert contents == ["x", "y", "z"]

    def test_no_placeholders(self) -> None:
        assert _scan_placeholders("plain text") == []

    def test_skips_braces_inside_string_literals(self) -> None:
        """Braces inside string literals must not affect brace counting."""
        template = '${{"a { b } c"}}'
        matches = _scan_placeholders(template)
        assert len(matches) == 1
        _, _, content, _ = matches[0]
        assert content == '"a { b } c"'

    def test_ignores_orphan_braces(self) -> None:
        """A single ``{`` without a matching ``}}`` should not crash."""
        assert _scan_placeholders("no placeholders here { stray") == []


class TestEvaluate:
    """Tests for the evaluate method, including the JSON-literal fast path."""

    def test_expression_evaluation(self, service: WorkflowExpressionService) -> None:
        result = service.evaluate("1 + 2", ExpressionContext())
        assert isinstance(result, ExpressionResult)
        assert result.value == 3.0
        assert result.error is None

    def test_json_object_literal(self, service: WorkflowExpressionService) -> None:
        """Regression: expressions starting with ``{`` must short-circuit
        to ``json.loads`` instead of being sent to the expression parser,
        which doesn't understand JSON object syntax.
        """
        result = service.evaluate(
            '{ "values": ["a", "b"] }', ExpressionContext()
        )
        assert result.error is None
        assert result.value == {"values": ["a", "b"]}

    def test_json_array_literal(self, service: WorkflowExpressionService) -> None:
        result = service.evaluate("[1, 2, 3]", ExpressionContext())
        assert result.error is None
        assert result.value == [1, 2, 3]

    def test_invalid_json_records_error(
        self, service: WorkflowExpressionService
    ) -> None:
        result = service.evaluate("{ not: valid }", ExpressionContext())
        assert result.error is not None


class TestResolvePlaceholders:
    """Tests for the full template resolver."""

    def test_simple_placeholder(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders("Hi {{var.name}}!", context)
        assert result.resolved == "Hi Jorge!"
        assert len(result.placeholders) == 1
        assert result.placeholders[0].value == "Jorge"
        assert result.placeholders[0].error is None

    def test_expression_placeholder(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders("next=${{var.iterator + 1}}", context)
        # Binary + always returns float today; only the type of the literal
        # in the source matters. ``0 + 1`` is therefore ``1.0``.
        assert result.resolved == "next=1.0"
        assert result.placeholders[0].value == "1.0"

    def test_json_literal_value_is_emitted_once(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        """Regression: the same JSON object must not appear twice in the
        output. The old resolver emitted it once for the ``${{ ... }}``
        match and once for the inner ``{{ ... }}`` overlap.
        """
        result = service.resolve_placeholders(
            "Langs: ${{var.languages.values}}", context
        )
        assert result.resolved.count("spanish") == 1
        assert result.resolved.count("portuguese") == 1

    def test_array_access(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders(
            "First: ${{var.languages.values[var.iterator]}}", context
        )
        assert result.resolved == "First: spanish"

    def test_array_access_out_of_bounds(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        ctx = context.model_copy(update={"variables": {**context.variables, "iterator": 99}})
        result = service.resolve_placeholders(
            "${{var.languages.values[var.iterator]}}", ctx
        )
        # Out-of-bounds should resolve to empty string, not raise.
        assert result.resolved == ""

    def test_last_output_in_expression(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders("${{lastOutput}}", context)
        assert result.resolved == "Hola mundo"

    def test_unresolved_placeholder_falls_back_to_literal(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders(
            "${{var.nonexistent + 1}}", context
        )
        # Falls back to the original placeholder text on error.
        assert result.resolved == "${{var.nonexistent + 1}}"
        assert result.placeholders[0].error is not None

    def test_mixed_text_and_placeholders(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders(
            "Input: {{input}} | ${{var.iterator + 1}} | ${{lastOutput}}",
            context,
        )
        # ``+`` returns float, so ``var.iterator + 1`` is ``1.0``.
        assert result.resolved == "Input: Hello world | 1.0 | Hola mundo"

    def test_no_placeholders_returns_unchanged(
        self, service: WorkflowExpressionService, context: ExpressionContext
    ) -> None:
        result = service.resolve_placeholders("plain text only", context)
        assert result.resolved == "plain text only"
        assert result.placeholders == []
