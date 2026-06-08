"""Workflow expression service - orchestrates expression evaluation and placeholder resolution."""

from __future__ import annotations

import re
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


class WorkflowExpressionService:
    """Service for workflow expression evaluation and placeholder resolution.

    Handles:
    - Simple placeholders: {{variable}}
    - Expression placeholders: ${{expression}}
    - Mixed content with multiple placeholders
    """

    SIMPLE_PATTERN = re.compile(r"\{\{([^}]+)\}\}")
    EXPRESSION_PATTERN = re.compile(r"\$\{\{([^}]+)\}\}")

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
        try:
            value = evaluate_expression(expression, context)
            return ExpressionResult(value=value)
        except (ParseError, EvaluationError) as e:
            return ExpressionResult(value=None, error=str(e))

    def resolve_placeholders(
        self, template: str, context: ExpressionContext
    ) -> ResolvedTemplate:
        """Resolve all placeholders in a template string.

        Supports both {{simple}} and ${{expression}} syntax.
        Non-placeholder text is preserved verbatim.

        Args:
            template: Template string with placeholders
            context: Evaluation context

        Returns:
            ResolvedTemplate with resolved string and placeholder info
        """
        placeholders: list[ResolvedPlaceholder] = []
        result_parts: list[str] = []
        pos = 0

        # Find all placeholders (both styles)
        matches: list[tuple[int, int, str, bool]] = []

        for match in self.SIMPLE_PATTERN.finditer(template):
            matches.append((match.start(), match.end(), match.group(1), False))

        for match in self.EXPRESSION_PATTERN.finditer(template):
            matches.append((match.start(), match.end(), match.group(1), True))

        # Sort by position
        matches.sort(key=lambda x: x[0])

        # Process matches
        evaluator = WorkflowExpressionEvaluator(context, self._helpers)

        for start, end, content, is_expression in matches:
            # Add literal text before this placeholder
            if pos < start:
                result_parts.append(template[pos:start])

            # Evaluate placeholder
            ph = ResolvedPlaceholder(original=template[start:end])

            try:
                if is_expression:
                    ast = parse_expression(content)
                    value = evaluator.evaluate(ast)
                else:
                    # Simple placeholder - treat as identifier
                    ast = parse_expression(content.strip())
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