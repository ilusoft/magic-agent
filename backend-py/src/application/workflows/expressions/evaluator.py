"""Workflow expression evaluator - evaluates AST nodes against a context."""

from __future__ import annotations

from typing import Any

from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.expressions.helpers import WorkflowHelperRegistry
from src.application.workflows.expressions.nodes import (
    ArrayAccessNode,
    ASTNode,
    BinaryOpNode,
    BooleanNode,
    FunctionCallNode,
    IdentifierNode,
    JsonNode,
    NullNode,
    NumberNode,
    PropertyAccessNode,
    StringNode,
    UnaryOpNode,
)


class EvaluationError(Exception):
    """Raised when expression evaluation fails."""

    def __init__(self, message: str, node: ASTNode | None = None) -> None:
        self.node = node
        super().__init__(message)


class WorkflowExpressionEvaluator:
    """Evaluates workflow expression AST nodes.

    Handles:
    - Literals (numbers, strings, booleans, null)
    - Identifiers with path access (var.name, param.items[0])
    - Binary operators (+, -, *, /, ^, %, =, !=, <, <=, >, >=, &&, ||)
    - Unary operators (+, -, !)
    - Function calls (via helper registry)
    - JSON object/array literals
    """

    def __init__(
        self,
        context: ExpressionContext,
        helper_registry: WorkflowHelperRegistry | None = None,
    ) -> None:
        self._context = context
        self._helpers = helper_registry or WorkflowHelperRegistry()

    def evaluate(self, node: ASTNode) -> Any:
        """Evaluate an AST node.

        Args:
            node: AST node to evaluate

        Returns:
            Evaluated value

        Raises:
            EvaluationError: If evaluation fails
        """
        try:
            return self._visit(node)
        except Exception as e:
            if isinstance(e, EvaluationError):
                raise
            raise EvaluationError(str(e), node) from e

    def _visit(self, node: ASTNode) -> Any:
        """Visit a node and return its value."""
        match node:
            case NumberNode():
                return node.value
            case StringNode():
                return node.value
            case BooleanNode():
                return node.value
            case NullNode():
                return None
            case JsonNode():
                return node.value
            case IdentifierNode():
                return self._evaluate_identifier(node)
            case PropertyAccessNode():
                return self._evaluate_property_access(node)
            case ArrayAccessNode():
                return self._evaluate_array_access(node)
            case BinaryOpNode():
                return self._evaluate_binary_op(node)
            case UnaryOpNode():
                return self._evaluate_unary_op(node)
            case FunctionCallNode():
                return self._evaluate_function_call(node)
            case _:
                raise EvaluationError(f"Unknown node type: {type(node)}", node)

    def _evaluate_identifier(self, node: IdentifierNode) -> Any:
        """Evaluate an identifier with optional path.

        Resolution order (matches the .NET ``WorkflowExpressionEvaluator``):

        1. ``input`` → step input (string, ``""`` when unset)
        2. ``lastOutput`` → previous step's output (string, ``""`` when unset)
        3. ``var.X`` / ``param.X`` / ``parameter.X`` → variables / params
        4. ``runtime_state`` (e.g. ``output``, ``stepName``, ``stepType``)
        5. Bare identifier → fallback to variables
        """
        root = node.root
        path = node.path

        # Get root value
        match root:
            case "var":
                value = self._context.get_variable(path[0] if path else "")
                remaining = path[1:] if path else []
            case "param" | "parameter":
                value = self._context.get_parameter(path[0] if path else "")
                remaining = path[1:] if path else []
            case "input":
                # .NET returns ``stepInput ?? string.Empty`` so the
                # placeholder resolves to ``""`` rather than the
                # literal ``input`` when no step input was supplied.
                value = (
                    "" if self._context.input is None
                    else self._context.input
                )
                remaining = path
            case "lastOutput":
                # .NET returns ``LastStepOutput ?? string.Empty``;
                # mirror that here so a placeholder like
                # ``${{ addToArray(var.translations, lastOutput) }}``
                # behaves the same on both backends when there is no
                # previous step.
                value = (
                    "" if self._context.last_output is None
                    else self._context.last_output
                )
                remaining = path
            case "step_outputs":
                # Access step_outputs.<step_id>.output
                value = self._context.step_outputs
                remaining = path
            case _:
                # Mirror the .NET ``RuntimeState`` lookup so a
                # placeholder like ``{{ output }}`` (used in outcome
                # conditions) resolves to the current step's output,
                # and ``{{ stepName }}`` / ``{{ stepType }}`` resolve
                # to the corresponding step attributes.
                if root in self._context.runtime_state:
                    value = self._context.runtime_state[root]
                    remaining = path
                else:
                    value = self._context.get_variable(root)
                    remaining = path

        # Traverse path
        for prop in remaining:
            if value is None:
                return None
            if isinstance(value, dict):
                value = value.get(prop)
            elif hasattr(value, prop):
                value = getattr(value, prop)
            else:
                raise EvaluationError(
                    f"Cannot access property '{prop}' on {type(value)}",
                    node,
                )

        return value

    def _evaluate_property_access(self, node: PropertyAccessNode) -> Any:
        """Evaluate property access on a base value."""
        base = self._visit(node.base)
        if base is None:
            return None
        if isinstance(base, dict):
            return base.get(node.property_name)
        if hasattr(base, node.property_name):
            return getattr(base, node.property_name)
        raise EvaluationError(
            f"Cannot access property '{node.property_name}' on {type(base)}",
            node,
        )

    def _evaluate_array_access(self, node: ArrayAccessNode) -> Any:
        """Evaluate array index access."""
        base = self._visit(node.base)
        index = self._visit(node.index)

        if base is None:
            return None

        # Coerce float indices that are whole numbers (e.g. 0.0 -> 0)
        if isinstance(index, float) and index.is_integer():
            index = int(index)

        if isinstance(index, int) and isinstance(base, (list, tuple, str)):
            if index < 0 or index >= len(base):
                return None
            return base[index]

        if isinstance(base, dict):
            return base.get(str(index))

        raise EvaluationError(
            f"Cannot index {type(base)} with {type(index)}",
            node,
        )

    def _evaluate_binary_op(self, node: BinaryOpNode) -> Any:
        """Evaluate a binary operation."""
        left = self._visit(node.left)
        right = self._visit(node.right)

        match node.operator:
            # Arithmetic
            case "+":
                if isinstance(left, str) or isinstance(right, str):
                    return str(left) + str(right)
                return float(left) + float(right)
            case "-":
                return float(left) - float(right)
            case "*":
                return float(left) * float(right)
            case "/":
                return float(left) / float(right)
            case "%":
                return float(left) % float(right)
            case "^":
                return float(left) ** float(right)

            # Comparison
            case "=":
                return left == right
            case "!=":
                return left != right
            case "<":
                return float(left) < float(right)
            case "<=":
                return float(left) <= float(right)
            case ">":
                return float(left) > float(right)
            case ">=":
                return float(left) >= float(right)

            # Logical
            case "&&":
                return bool(left) and bool(right)
            case "||":
                return bool(left) or bool(right)

            case _:
                raise EvaluationError(f"Unknown operator: {node.operator}", node)

    def _evaluate_unary_op(self, node: UnaryOpNode) -> Any:
        """Evaluate a unary operation."""
        operand = self._visit(node.operand)

        match node.operator:
            case "+":
                return float(operand)
            case "-":
                return -float(operand)
            case "!":
                return not operand
            case _:
                raise EvaluationError(f"Unknown unary operator: {node.operator}", node)

    def _evaluate_function_call(self, node: FunctionCallNode) -> Any:
        """Evaluate a function call via the helper registry."""
        args = [self._visit(arg) for arg in node.arguments]
        return self._helpers.invoke(node.name, args)


def evaluate(expression: str, context: ExpressionContext) -> Any:
    """Evaluate an expression string against a context.

    Args:
        expression: Expression string to evaluate
        context: Evaluation context

    Returns:
        Evaluated value
    """
    from src.application.workflows.expressions.parser import parse

    ast = parse(expression)
    evaluator = WorkflowExpressionEvaluator(context)
    return evaluator.evaluate(ast)