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


class TestDatePresets:
    """Regression tests for the date-preset keywords the resolver
    honours inside the legacy ``{{ … }}`` syntax.

    The preset layer exists so that workflow authors who reach
    for ``{{ today }}`` or ``{{ dd-mm-yyyy }}`` get a working
    current-date substitution even though the legacy syntax
    normally only handles variable lookups. Without the
    preset, an author who wrote ``{{ today }}`` would see
    an empty string and conclude (correctly!) that the
    feature doesn't work.
    """

    def test_today_keyword_resolves_to_local_date(
        self, service: WorkflowExpressionService
    ) -> None:
        from datetime import datetime, timezone

        result = service.resolve_placeholders(
            "{{ today }}", ExpressionContext()
        )
        expected = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        assert result.resolved == expected

    def test_today_keyword_is_case_insensitive(
        self, service: WorkflowExpressionService
    ) -> None:
        result = service.resolve_placeholders(
            "{{ TODAY }}", ExpressionContext()
        )
        # The exact date isn't asserted (clock may tick over
        # between this and the previous test) — only that the
        # preset *resolved* rather than returning empty.
        assert result.resolved
        assert "T" not in result.resolved  # a date, not a datetime

    def test_now_keyword_returns_iso_datetime(
        self, service: WorkflowExpressionService
    ) -> None:
        result = service.resolve_placeholders(
            "{{ now }}", ExpressionContext()
        )
        # ISO 8601 with timezone offset or Z.
        assert "T" in result.resolved
        assert "+" in result.resolved[10:] or "Z" in result.resolved

    def test_dd_mm_yyyy_placeholder_resolves(
        self, service: WorkflowExpressionService
    ) -> None:
        """The exact placeholder the user pasted into the
        web-search agent's system prompt. Without the preset
        layer this would have evaluated as a variable lookup,
        missed, and produced the literal string the LLM
        then hallucinated against.
        """
        from datetime import datetime, timezone

        result = service.resolve_placeholders(
            "{{ dd-mm-yyyy }}", ExpressionContext()
        )
        expected = datetime.now(timezone.utc).astimezone().strftime("%d-%m-%Y")
        assert result.resolved == expected

    @pytest.mark.parametrize(
        "placeholder, expected_format",
        [
            ("{{ yyyy-mm-dd }}", "%Y-%m-%d"),
            ("{{ dd-mm-yyyy }}", "%d-%m-%Y"),
            ("{{ mm/dd/yyyy }}", "%m/%d/%Y"),
            ("{{ dd/mm/yyyy }}", "%d/%m/%Y"),
            ("{{ yyyy/mm/dd }}", "%Y/%m/%d"),
        ],
    )
    def test_format_placeholder_resolves_to_today(
        self,
        service: WorkflowExpressionService,
        placeholder: str,
        expected_format: str,
    ) -> None:
        from datetime import datetime, timezone

        result = service.resolve_placeholders(placeholder, ExpressionContext())
        expected = datetime.now(timezone.utc).astimezone().strftime(expected_format)
        assert result.resolved == expected

    def test_unknown_preset_falls_through_to_normal_lookup(
        self, service: WorkflowExpressionService
    ) -> None:
        """A non-preset key (``foo``) must NOT be hijacked by
        the preset layer — it should still go through the
        normal variable lookup. The preset is purely
        additive.
        """
        context = ExpressionContext(variables={"foo": "bar"})
        result = service.resolve_placeholders("{{ foo }}", context)
        assert result.resolved == "bar"

    def test_mixed_preset_and_expression(
        self, service: WorkflowExpressionService
    ) -> None:
        """The preset and expression syntaxes can coexist in
        the same template — the preset handles the legacy
        ``{{ today }}`` placeholder while ``${{ now('…') }}``
        runs the full expression evaluator.
        """
        from datetime import datetime, timezone

        result = service.resolve_placeholders(
            "Today: {{ today }} (ISO: ${{ now() }})", ExpressionContext()
        )
        # ``Today: YYYY-MM-DD`` followed by an ISO datetime.
        expected_date = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        assert result.resolved.startswith(f"Today: {expected_date} (ISO: ")
        assert "T" in result.resolved


class TestNowHelperFormatAliases:
    """The ``now()`` / ``nowUtc()`` / ``nowLocal()`` helpers accept
    both Python ``strftime`` codes and the friendlier
    ``dd-mm-yyyy`` / ``yyyy-mm-dd`` tokens that humans actually
    write. The aliases are what the user's web-search agent
    relies on — without them, ``strftime("dd-mm-yyyy")``
    returns the literal string and the LLM hallucinates
    against it.
    """

    @pytest.mark.parametrize(
        "helper_name",
        ["now", "nowUtc", "nowLocal"],
    )
    def test_dd_mm_yyyy_alias_is_translated(
        self, helper_name: str
    ) -> None:
        from src.application.workflows.expressions.helpers import DateHelpers
        from datetime import datetime, timezone

        result = getattr(DateHelpers, helper_name)("dd-mm-yyyy")
        expected = datetime.now(timezone.utc).astimezone().strftime("%d-%m-%Y")
        assert result == expected

    @pytest.mark.parametrize(
        "helper_name",
        ["now", "nowUtc", "nowLocal"],
    )
    def test_yyyy_mm_dd_alias_is_translated(
        self, helper_name: str
    ) -> None:
        from src.application.workflows.expressions.helpers import DateHelpers
        from datetime import datetime, timezone

        result = getattr(DateHelpers, helper_name)("yyyy-mm-dd")
        expected = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        assert result == expected

    def test_strftime_passthrough_is_preserved(
        self,
    ) -> None:
        """Strings that already contain ``%`` are strftime
        templates and must be passed through unchanged — the
        alias only fires for bare tokens.
        """
        from src.application.workflows.expressions.helpers import DateHelpers
        from datetime import datetime, timezone

        result = DateHelpers.now("%d-%m-%Y")
        expected = datetime.now(timezone.utc).astimezone().strftime("%d-%m-%Y")
        assert result == expected

    def test_unknown_format_passes_through_unchanged(
        self,
    ) -> None:
        """A format string that isn't a recognised alias and
        isn't a strftime template is left to ``strftime`` to
        interpret (which may return it as a literal if no
        ``%`` codes are present). We don't want the alias
        layer to silently rewrite arbitrary strings.
        """
        from src.application.workflows.expressions.helpers import DateHelpers

        result = DateHelpers.now("not-a-real-format")
        assert result == "not-a-real-format"
