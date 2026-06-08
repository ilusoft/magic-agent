"""Workflow helpers and expression evaluation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.service import WorkflowExpressionService

router = APIRouter()


class EvaluateRequest(BaseModel):
    """Request to evaluate a workflow expression."""

    expression: str
    variables: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    input: Any = None


class EvaluateResponse(BaseModel):
    """Response from expression evaluation."""

    value: Any
    error: str | None = None


@router.get("/helpers")
async def list_workflow_helpers() -> list[dict[str, Any]]:
    """List all available workflow expression helpers.

    Returns:
        List of helper descriptors with name, category, and parameters
    """
    service = WorkflowExpressionService()
    helpers = service.get_helpers()
    return helpers


@router.post("/evaluate")
async def evaluate_expression(request: EvaluateRequest) -> EvaluateResponse:
    """Evaluate a workflow expression.

    Args:
        request: Evaluation request with expression and context

    Returns:
        Evaluation result with value or error
    """
    context = ExpressionContext(
        variables=request.variables or {},
        parameters=request.parameters or {},
        input=request.input,
    )

    service = WorkflowExpressionService()
    result = service.evaluate(request.expression, context)

    return EvaluateResponse(
        value=result.value,
        error=result.error,
    )


@router.post("/resolve")
async def resolve_template(
    template: str,
    variables: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
    input: Any = None,
) -> dict[str, Any]:
    """Resolve placeholders in a template string.

    Args:
        template: Template with {{ }} or ${{ }} placeholders
        variables: Context variables
        parameters: Context parameters
        input: Input value

    Returns:
        Resolved template with placeholder details
    """
    context = ExpressionContext(
        variables=variables or {},
        parameters=parameters or {},
        input=input,
    )

    service = WorkflowExpressionService()
    result = service.resolve_placeholders(template, context)

    return {
        "resolved": result.resolved,
        "placeholders": [p.model_dump() for p in result.placeholders],
    }