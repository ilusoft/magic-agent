"""Workflow expression tokenizer."""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import Iterator


class TokenKind(Enum):
    """Token kinds for workflow expressions."""

    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    OPERATOR = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    DOT = auto()
    COMMA = auto()
    EOF = auto()


class Token:
    """A token in a workflow expression."""

    def __init__(
        self,
        kind: TokenKind,
        value: str,
        position: int = 0,
    ) -> None:
        self.kind = kind
        self.value = value
        self.position = position

    def __repr__(self) -> str:
        return f"Token({self.kind.name}, {self.value!r}, pos={self.position})"


class WorkflowExpressionTokenizer:
    """Tokenizes workflow expressions.

    Handles:
    - Numbers: 42, 3.14, .5, 1e-3
    - Strings: 'hello', "world" with escape sequences
    - Identifiers: var.name, param.name, toUpper
    - Operators: +, -, *, /, ^, %, =, !=, <, <=, >, >=, &&, ||
    - Punctuation: ( ) [ ] . ,
    """

    OPERATORS = {
        "+": "PLUS",
        "-": "MINUS",
        "*": "MULTIPLY",
        "/": "DIVIDE",
        "%": "MODULO",
        "^": "POWER",
        "=": "EQUAL",
        "!=": "NOT_EQUAL",
        "<": "LESS_THAN",
        "<=": "LESS_EQUAL",
        ">": "GREATER_THAN",
        ">=": "GREATER_EQUAL",
        "!": "NOT",
        "&": "AND",
        "|": "OR",
    }

    def __init__(self, expression: str) -> None:
        self._expression = expression
        self._pos = 0
        self._len = len(expression)

    def tokenize(self) -> Iterator[Token]:
        """Tokenize the expression.

        Yields:
            Tokens in order
        """
        while self._pos < self._len:
            char = self._expression[self._pos]

            # Whitespace
            if char.isspace():
                self._advance()
                continue

            # Numbers
            if char.isdigit() or (char == "." and self._peek(1).isdigit()):
                yield self._read_number()
                continue

            # Strings
            if char in ("'", '"'):
                yield self._read_string()
                continue

            # Operators (check multi-char first)
            if self._pos + 1 < self._len:
                two_char = self._expression[self._pos : self._pos + 2]
                if two_char in ("==", "!=", "<=", ">=", "&&", "||"):
                    yield Token(TokenKind.OPERATOR, two_char, self._pos)
                    self._advance(2)
                    continue

            # Single char operators and punctuation
            if char in self.OPERATORS:
                yield Token(TokenKind.OPERATOR, char, self._pos)
                self._advance()
                continue

            # Punctuation
            if char == "(":
                yield Token(TokenKind.LPAREN, char, self._pos)
                self._advance()
                continue
            if char == ")":
                yield Token(TokenKind.RPAREN, char, self._pos)
                self._advance()
                continue
            if char == "[":
                yield Token(TokenKind.LBRACKET, char, self._pos)
                self._advance()
                continue
            if char == "]":
                yield Token(TokenKind.RBRACKET, char, self._pos)
                self._advance()
                continue
            if char == ".":
                yield Token(TokenKind.DOT, char, self._pos)
                self._advance()
                continue
            if char == ",":
                yield Token(TokenKind.COMMA, char, self._pos)
                self._advance()
                continue

            # Identifiers
            if char.isalpha() or char == "_":
                yield self._read_identifier()
                continue

            # Unknown character
            raise ValueError(f"Unexpected character '{char}' at position {self._pos}")

        yield Token(TokenKind.EOF, "", self._pos)

    def _advance(self, count: int = 1) -> None:
        """Advance the position by count characters."""
        self._pos = min(self._pos + count, self._len)

    def _peek(self, offset: int = 0) -> str:
        """Peek at a character offset from current position."""
        idx = self._pos + offset
        if idx >= self._len:
            return ""
        return self._expression[idx]

    def _read_number(self) -> Token:
        """Read a number token."""
        start = self._pos
        has_decimal = False
        has_exponent = False

        while self._pos < self._len:
            char = self._expression[self._pos]

            if char.isdigit():
                self._advance()
            elif char == "." and not has_decimal and not has_exponent:
                has_decimal = True
                self._advance()
            elif char in ("e", "E") and not has_exponent:
                has_exponent = True
                self._advance()
                if self._peek() in ("+", "-"):
                    self._advance()
            else:
                break

        return Token(TokenKind.NUMBER, self._expression[start : self._pos], start)

    def _read_string(self) -> Token:
        """Read a string token with escape sequences."""
        quote = self._expression[self._pos]
        start = self._pos
        self._advance()  # Skip opening quote

        result = []
        while self._pos < self._len:
            char = self._expression[self._pos]

            if char == quote:
                self._advance()  # Skip closing quote
                break

            if char == "\\":
                self._advance()
                escape_char = self._expression[self._pos]
                escape_map = {
                    "n": "\n",
                    "t": "\t",
                    "r": "\r",
                    "\\": "\\",
                    "'": "'",
                    '"': "\"",
                }
                result.append(escape_map.get(escape_char, escape_char))
                self._advance()
            else:
                result.append(char)
                self._advance()

        return Token(TokenKind.STRING, "".join(result), start)

    def _read_identifier(self) -> Token:
        """Read an identifier token."""
        start = self._pos

        while self._pos < self._len:
            char = self._expression[self._pos]
            if char.isalnum() or char == "_" or char == ".":
                self._advance()
            else:
                break

        return Token(
            TokenKind.IDENTIFIER,
            self._expression[start : self._pos],
            start,
        )


def tokenize(expression: str) -> list[Token]:
    """Tokenize an expression string.

    Args:
        expression: Expression string to tokenize

    Returns:
        List of tokens
    """
    return list(WorkflowExpressionTokenizer(expression).tokenize())