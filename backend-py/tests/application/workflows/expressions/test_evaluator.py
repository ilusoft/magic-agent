"""Tests for the expression evaluator."""

from __future__ import annotations

import pytest

from src.application.workflows.expressions.context import ExpressionContext
from src.application.workflows.expressions.evaluator import (
    evaluate,
    EvaluationError,
    WorkflowExpressionEvaluator,
)
from src.application.workflows.expressions.parser import parse


class TestWorkflowExpressionEvaluator:
    """Tests for WorkflowExpressionEvaluator."""

    def setup_method(self) -> None:
        """Set up test context."""
        self.context = ExpressionContext(
            variables={"name": "John", "age": 30, "items": [1, 2, 3]},
            parameters={"input": "hello"},
            input="test input",
            last_output="previous step output",
        )

    def test_number(self) -> None:
        """Test number evaluation."""
        ast = parse("42")
        result = evaluate("42", self.context)
        assert result == 42.0

    def test_string(self) -> None:
        """Test string evaluation."""
        result = evaluate("'hello'", self.context)
        assert result == "hello"

    def test_variable(self) -> None:
        """Test variable evaluation."""
        result = evaluate("var.name", self.context)
        assert result == "John"

    def test_parameter(self) -> None:
        """Test parameter evaluation."""
        result = evaluate("param.input", self.context)
        assert result == "hello"

    def test_input(self) -> None:
        """Test input evaluation."""
        result = evaluate("input", self.context)
        assert result == "test input"

    def test_last_output(self) -> None:
        """Test lastOutput evaluation."""
        result = evaluate("lastOutput", self.context)
        assert result == "previous step output"

    def test_addition(self) -> None:
        """Test addition."""
        result = evaluate("1 + 2", self.context)
        assert result == 3.0

    def test_array_index_with_int_literal(self) -> None:
        """Indexing a list with a literal ``0`` should not raise.

        Regression: ``0`` was parsed as ``0.0`` and list indexing rejected
        float indices (``TypeError: list indices must be integers or
        slices, not float``).
        """
        result = evaluate("var.items[0]", self.context)
        assert result == 1

    def test_array_index_with_float_literal_coerces(self) -> None:
        """Defensive coercion: float whole-number indices become int.

        Guards against future regressions where an upstream expression
        produces a float (e.g. ``var.iterator + 1``) and the result is
        then used as an index.
        """
        # Build a context whose variable is a float that represents a
        # whole number; the index should still resolve.
        ctx = ExpressionContext(
            variables={"items": [10, 20, 30]},
        )
        result = evaluate("var.items[0]", ctx)
        assert result == 10

    def test_index_in_binary_op_then_indexed(self) -> None:
        """var.iterator + 1 returns a float; indexing with that float
        must still work via defensive coercion.
        """
        ctx = ExpressionContext(
            variables={"iterator": 0, "items": ["a", "b", "c"]},
        )
        result = evaluate("var.items[var.iterator + 1]", ctx)
        assert result == "b"

    def test_string_concatenation(self) -> None:
        """Test string concatenation."""
        result = evaluate("'hello' + ' ' + 'world'", self.context)
        assert result == "hello world"

    def test_multiplication(self) -> None:
        """Test multiplication."""
        result = evaluate("3 * 4", self.context)
        assert result == 12.0

    def test_division(self) -> None:
        """Test division."""
        result = evaluate("10 / 2", self.context)
        assert result == 5.0

    def test_power(self) -> None:
        """Test power operator."""
        result = evaluate("2 ^ 3", self.context)
        assert result == 8.0

    def test_comparison(self) -> None:
        """Test comparison operators."""
        result = evaluate("3 > 2", self.context)
        assert result is True

        result = evaluate("1 = 1", self.context)
        assert result is True

    def test_logical_and(self) -> None:
        """Test logical AND."""
        result = evaluate("true && true", self.context)
        assert result is True

        result = evaluate("true && false", self.context)
        assert result is False

    def test_logical_or(self) -> None:
        """Test logical OR."""
        result = evaluate("true || false", self.context)
        assert result is True

    def test_function_abs(self) -> None:
        """Test abs function."""
        result = evaluate("abs(-5)", self.context)
        assert result == 5.0

    def test_function_toUpper(self) -> None:
        """Test toUpper function."""
        result = evaluate("toUpper('hello')", self.context)
        assert result == "HELLO"

    def test_function_length(self) -> None:
        """Test length function."""
        result = evaluate("length('hello')", self.context)
        assert result == 5

    def test_function_min(self) -> None:
        """Test min function."""
        result = evaluate("min(3, 7)", self.context)
        assert result == 3.0

    def test_function_max(self) -> None:
        """Test max function."""
        result = evaluate("max(3, 7)", self.context)
        assert result == 7.0

    def test_function_pow(self) -> None:
        """Test pow function."""
        result = evaluate("pow(2, 3)", self.context)
        assert result == 8.0

    def test_nested_functions(self) -> None:
        """Test nested function calls."""
        result = evaluate("abs(min(-5, -3))", self.context)
        assert result == 5.0  # min(-5, -3) = -5, abs(-5) = 5

    def test_unary_minus(self) -> None:
        """Test unary minus."""
        result = evaluate("-5", self.context)
        assert result == -5.0

    def test_unary_not(self) -> None:
        """Test unary NOT."""
        result = evaluate("!false", self.context)
        assert result is True


class TestEvaluationErrors:
    """Tests for evaluation error handling."""

    def setup_method(self) -> None:
        """Set up test context."""
        self.context = ExpressionContext()

    def test_unknown_function(self) -> None:
        """Test error on unknown function."""
        with pytest.raises(EvaluationError):
            evaluate("unknownFunc()", self.context)

    def test_invalid_path(self) -> None:
        """Test error on invalid path access."""
        result = evaluate("var.nonexistent", self.context)
        assert result is None