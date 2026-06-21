"""Workflow expression service - orchestrates expression evaluation and placeholder resolution."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.expressions.evaluator import (
    EvaluationError,
    WorkflowExpressionEvaluator,
    evaluate as evaluate_expression,
)
from src.application.workflows.expressions.helpers import WorkflowHelperRegistry
from src.application.workflows.expressions.parser import ParseError, parse as parse_expression


class ResolvedPlaceholder(BaseModel):
    """Information about a resolved placeholder."""

    original: str
    value: Any = ""
    error: str | None = None


class ResolvedTemplate(BaseModel):
    """Result of resolving a template with placeholders."""

    resolved: str
    placeholders: list[ResolvedPlaceholder]


class ExpressionResult(BaseModel):
    """Result of an expression evaluation."""

    value: Any
    error: str | None = None


def _scan_placeholders(template: str) -> list[tuple[int, int, str, bool]]:
    """Find ``{{ ... }}`` and ``${{ ... }}`` placeholders in a template.

    Uses a brace-depth scanner so placeholders containing JSON literals
    with ``}`` (e.g. ``${{ { "key": "value" } }}``) are matched correctly.

    Returns:
        List of ``(start, end, content, is_expression)`` tuples, sorted by
        start position. Overlapping matches are not produced.
    """
    matches: list[tuple[int, int, str, bool]] = []
    i = 0
    n = len(template)

    while i < n - 1:
        ch = template[i]
        nxt = template[i + 1]

        if ch == "$" and nxt == "{" and i + 2 < n and template[i + 2] == "{":
            end = _find_closing(template, i + 3, open_char="{", close_char="}")
            if end != -1 and end + 1 < n and template[end + 1] == "}":
                content = template[i + 3 : end]
                matches.append((i, end + 2, content, True))
                i = end + 2
                continue
        elif ch == "{" and nxt == "{":
            end = _find_closing(template, i + 2, open_char="{", close_char="}")
            if end != -1 and end + 1 < n and template[end + 1] == "}":
                content = template[i + 2 : end]
                matches.append((i, end + 2, content, False))
                i = end + 2
                continue
        i += 1

    return matches


def _find_closing(template: str, start: int, open_char: str, close_char: str) -> int:
    """Return the index of the matching ``close_char`` accounting for nesting.

    Skips over string literals (``"..."`` and ``'...'``) so that braces
    inside strings don't affect depth counting.
    """
    depth = 1
    i = start
    n = len(template)
    while i < n:
        ch = template[i]
        if ch in ("'", '"'):
            quote = ch
            i += 1
            while i < n and template[i] != quote:
                if template[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            i += 1
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


class WorkflowExpressionService:
    """Service for workflow expression evaluation and placeholder resolution.

    Handles:
    - Simple placeholders: {{variable}}
    - Expression placeholders: ${{expression}}
    - Mixed content with multiple placeholders
    """

    def __init__(self, helper_registry: WorkflowHelperRegistry | None = None) -> None:
        self._helpers = helper_registry or WorkflowHelperRegistry()

    def evaluate(self, expression: str, context: ExpressionContext) -> ExpressionResult:
        """Evaluate a single expression.

        Args:
            expression: Expression string (without {{ }} wrappers)
            context: Evaluation context

        Returns:
            ExpressionResult with value or error
        """
        # Short-circuit JSON literals (objects/arrays) since the expression
        # parser doesn't know how to parse them.
        stripped = expression.strip()
        if stripped.startswith(("{", "[")):
            import json
            try:
                return ExpressionResult(value=json.loads(stripped))
            except json.JSONDecodeError as e:
                return ExpressionResult(value=None, error=str(e))

        try:
            value = evaluate_expression(expression, context)
            return ExpressionResult(value=value)
        except (ParseError, EvaluationError) as e:
            return ExpressionResult(value=None, error=str(e))

    def resolve_placeholders(
        self, template: str, context: ExpressionContext
    ) -> ResolvedTemplate:
        """Resolve all placeholders in a template string.

        Supports both ``{{simple}}`` and ``${{expression}}`` syntax.
        Non-placeholder text is preserved verbatim. Placeholder contents may
        include JSON literals with nested braces (e.g. ``${{ { "a": 1 } }}``).

        Args:
            template: Template string with placeholders
            context: Evaluation context

        Returns:
            ResolvedTemplate with resolved string and placeholder info
        """
        placeholders: list[ResolvedPlaceholder] = []
        result_parts: list[str] = []
        pos = 0

        matches = _scan_placeholders(template)

        # Process matches
        evaluator = WorkflowExpressionEvaluator(context, self._helpers)

        for start, end, content, is_expression in matches:
            # Add literal text before this placeholder
            if pos < start:
                result_parts.append(template[pos:start])

            # Evaluate placeholder
            ph = ResolvedPlaceholder(original=template[start:end])

            try:
                # Short-circuit JSON literals
                trimmed = content.strip()
                if trimmed.startswith(("{", "[")):
                    import json
                    value = json.loads(trimmed)
                else:
                    ast = parse_expression(trimmed)
                    value = evaluator.evaluate(ast)

                # Convert value to string
                if value is None:
                    ph.value = ""
                elif isinstance(value, bool):
                    ph.value = str(value).lower()
                elif isinstance(value, (int, float)):
                    ph.value = str(value)
                elif isinstance(value, (dict, list)):
                    import json
                    ph.value = json.dumps(value)
                else:
                    ph.value = str(value)

            except (ParseError, EvaluationError) as e:
                ph.error = str(e)
                ph.value = template[start:end]  # Fall back to original
            except Exception as e:  # JSONDecodeError and similar
                ph.error = str(e)
                ph.value = template[start:end]

            placeholders.append(ph)
            result_parts.append(str(ph.value))
            pos = end

        # Add remaining literal text
        if pos < len(template):
            result_parts.append(template[pos:])

        return ResolvedTemplate(
            resolved="".join(result_parts),
            placeholders=placeholders,
        )

    def get_helpers(self) -> list[dict[str, Any]]:
        """Get metadata for all available helpers.

        Returns:
            List of helper descriptors
        """
        return [
            h.model_dump() for h in self._helpers.get_helpers()
        ]


# Convenience function
def resolve_template(template: str, context: ExpressionContext) -> ResolvedTemplate:
    """Resolve placeholders in a template string.

    Args:
        template: Template with {{ }} or ${{ }} placeholders
        context: Evaluation context

    Returns:
        ResolvedTemplate with result
    """
    service = WorkflowExpressionService()
    return service.resolve_placeholders(template, context)