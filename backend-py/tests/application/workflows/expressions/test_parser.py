"""Tests for the expression parser."""

from __future__ import annotations

import pytest

from src.application.workflows.expressions.parser import (
    NumberNode,
    StringNode,
    IdentifierNode,
    FunctionCallNode,
    BinaryOpNode,
    UnaryOpNode,
    parse,
    ParseError,
)
from src.application.workflows.expressions.nodes import PropertyAccessNode


class TestWorkflowExpressionParser:
    """Tests for WorkflowExpressionParser."""

    def test_number(self) -> None:
        """Test number parsing."""
        ast = parse("42")
        assert isinstance(ast, NumberNode)
        assert ast.value == 42.0

    def test_negative_number(self) -> None:
        """Test negative number parsing."""
        ast = parse("-42")
        assert isinstance(ast, UnaryOpNode)
        assert ast.operator == "-"

    def test_string(self) -> None:
        """Test string parsing."""
        ast = parse("'hello'")
        assert isinstance(ast, StringNode)
        assert ast.value == "hello"

    def test_identifier(self) -> None:
        """Test identifier parsing."""
        ast = parse("var_name")
        assert isinstance(ast, IdentifierNode)
        assert ast.parts == ["var_name"]

    def test_dotted_identifier(self) -> None:
        """Test dotted identifier parsing."""
        ast = parse("var.name.path")
        assert isinstance(ast, IdentifierNode)
        assert ast.parts == ["var", "name", "path"]

    def test_simple_addition(self) -> None:
        """Test simple addition parsing."""
        ast = parse("1 + 2")
        assert isinstance(ast, BinaryOpNode)
        assert ast.operator == "+"

    def test_multiplication(self) -> None:
        """Test multiplication parsing."""
        ast = parse("3 * 4")
        assert isinstance(ast, BinaryOpNode)
        assert ast.operator == "*"

    def test_precedence(self) -> None:
        """Test operator precedence."""
        ast = parse("1 + 2 * 3")
        assert isinstance(ast, BinaryOpNode)
        assert ast.operator == "+"
        assert isinstance(ast.right, BinaryOpNode)
        assert ast.right.operator == "*"

    def test_parentheses(self) -> None:
        """Test parentheses grouping."""
        ast = parse("(1 + 2) * 3")
        assert isinstance(ast, BinaryOpNode)
        assert ast.operator == "*"
        assert isinstance(ast.left, BinaryOpNode)
        assert ast.left.operator == "+"

    def test_function_call(self) -> None:
        """Test function call parsing."""
        ast = parse("toUpper('test')")
        assert isinstance(ast, FunctionCallNode)
        assert ast.name == "toUpper"
        assert len(ast.arguments) == 1

    def test_function_with_multiple_args(self) -> None:
        """Test function with multiple arguments."""
        ast = parse("min(1, 2)")
        assert isinstance(ast, FunctionCallNode)
        assert ast.name == "min"
        assert len(ast.arguments) == 2

    def test_nested_function_calls(self) -> None:
        """Test nested function calls."""
        ast = parse("toUpper(trim('  hello  '))")
        assert isinstance(ast, FunctionCallNode)
        assert ast.name == "toUpper"
        assert isinstance(ast.arguments[0], FunctionCallNode)
        assert ast.arguments[0].name == "trim"

    def test_unary_not(self) -> None:
        """Test unary NOT parsing."""
        ast = parse("!true")
        assert isinstance(ast, UnaryOpNode)
        assert ast.operator == "!"

    def test_power_operator(self) -> None:
        """Test power operator parsing."""
        ast = parse("2 ^ 3")
        assert isinstance(ast, BinaryOpNode)
        assert ast.operator == "^"


class TestParseFunction:
    """Tests for the parse convenience function."""

    def test_simple_expression(self) -> None:
        """Test simple expression parsing."""
        ast = parse("1 + 2")
        assert ast is not None

    def test_whitespace_only(self) -> None:
        """Test whitespace-only expression raises error."""
        with pytest.raises(ParseError):
            parse("   ")


class TestParseErrors:
    """Tests for parse error handling."""

    def test_unexpected_character(self) -> None:
        """Test error on unexpected character."""
        with pytest.raises((ParseError, ValueError)):
            parse("@invalid")

    def test_unclosed_paren(self) -> None:
        """Test error on unclosed parenthesis."""
        with pytest.raises(ParseError):
            parse("(1 + 2")

    def test_unclosed_bracket(self) -> None:
        """Test error on unclosed bracket."""
        with pytest.raises(ParseError):
            parse("arr[0")