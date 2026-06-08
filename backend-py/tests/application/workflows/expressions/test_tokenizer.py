"""Tests for the expression tokenizer."""

from __future__ import annotations

import pytest

from src.application.workflows.expressions.tokenizer import (
    TokenKind,
    WorkflowExpressionTokenizer,
    tokenize,
)


class TestWorkflowExpressionTokenizer:
    """Tests for WorkflowExpressionTokenizer."""

    def test_numbers(self) -> None:
        """Test number tokenization."""
        tokens = tokenize("42")
        assert len(tokens) == 2  # NUMBER + EOF
        assert tokens[0].kind == TokenKind.NUMBER
        assert tokens[0].value == "42"

    def test_decimals(self) -> None:
        """Test decimal number tokenization."""
        tokens = tokenize("3.14")
        assert tokens[0].kind == TokenKind.NUMBER
        assert tokens[0].value == "3.14"

    def test_strings(self) -> None:
        """Test string tokenization."""
        tokens = tokenize("'hello'")
        assert tokens[0].kind == TokenKind.STRING
        assert tokens[0].value == "hello"

    def test_escape_sequences(self) -> None:
        """Test escape sequence handling."""
        tokens = tokenize("'hello\\nworld'")
        assert tokens[0].kind == TokenKind.STRING
        assert "hello" in tokens[0].value
        assert "\n" in tokens[0].value

    def test_identifiers(self) -> None:
        """Test identifier tokenization."""
        tokens = tokenize("var_name")
        assert tokens[0].kind == TokenKind.IDENTIFIER
        assert tokens[0].value == "var_name"

    def test_dotted_identifiers(self) -> None:
        """Test dotted identifier tokenization."""
        tokens = tokenize("var.name.path")
        assert tokens[0].kind == TokenKind.IDENTIFIER
        assert tokens[0].value == "var.name.path"

    def test_operators(self) -> None:
        """Test operator tokenization."""
        tokens = tokenize("+ - * / ^")
        assert all(t.kind == TokenKind.OPERATOR for t in tokens[:-1])

    def test_punctuation(self) -> None:
        """Test punctuation tokenization."""
        tokens = tokenize("()[].,")
        kinds = [t.kind for t in tokens[:-1]]
        assert TokenKind.LPAREN in kinds
        assert TokenKind.RPAREN in kinds
        assert TokenKind.LBRACKET in kinds
        assert TokenKind.RBRACKET in kinds
        assert TokenKind.DOT in kinds
        assert TokenKind.COMMA in kinds

    def test_whitespace(self) -> None:
        """Test whitespace handling."""
        tokens = tokenize("  42  +  3  ")
        assert len(tokens) == 4  # NUMBER + OPERATOR + NUMBER + EOF

    def test_function_call(self) -> None:
        """Test function call tokenization."""
        tokens = tokenize("toUpper('test')")
        # toUpper, (, 'test', )
        assert tokens[0].kind == TokenKind.IDENTIFIER
        assert tokens[0].value == "toUpper"
        assert tokens[1].kind == TokenKind.LPAREN
        assert tokens[2].kind == TokenKind.STRING
        assert tokens[3].kind == TokenKind.RPAREN

    def test_complex_expression(self) -> None:
        """Test complex expression tokenization."""
        tokens = tokenize("var.name + 2")
        # Should have identifiers, operators
        kinds = [t.kind for t in tokens[:-1]]
        assert TokenKind.IDENTIFIER in kinds
        assert TokenKind.OPERATOR in kinds


class TestTokenize:
    """Tests for the tokenize convenience function."""

    def test_simple_number(self) -> None:
        """Test simple number tokenization."""
        tokens = tokenize("123")
        assert len(tokens) == 2
        assert tokens[0].kind == TokenKind.NUMBER

    def test_empty_string(self) -> None:
        """Test empty string handling."""
        tokens = tokenize("")
        assert len(tokens) == 1  # Just EOF
        assert tokens[0].kind == TokenKind.EOF