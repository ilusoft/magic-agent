"""Workflow expression parser using Pratt parsing for operator precedence."""

from __future__ import annotations

from typing import Iterator

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
from src.application.workflows.expressions.tokenizer import Token, TokenKind, tokenize


class ParseError(Exception):
    """Raised when parsing fails."""

    def __init__(self, message: str, position: int = 0) -> None:
        self.position = position
        super().__init__(f"{message} at position {position}")


class WorkflowExpressionParser:
    """Pratt parser for workflow expressions.

    Operator precedence (highest to lowest):
    1. Parentheses ( )
    2. Function calls fn()
    3. Unary + - !
    4. Exponent ^
    5. Multiplicative * / %
    6. Additive + -
    7. Comparison = != < <= > >=
    8. Logical && ||
    """

    def __init__(self, expression: str) -> None:
        self._tokens = list(tokenize(expression))
        self._pos = 0

    def parse(self) -> ASTNode:
        """Parse the expression into an AST.

        Returns:
            Root AST node

        Raises:
            ParseError: If parsing fails
        """
        node = self._parse_expression(0)
        self._skip(TokenKind.EOF)
        return node

    def _peek(self, offset: int = 0) -> Token:
        """Peek at a token offset from current position."""
        idx = self._pos + offset
        if idx >= len(self._tokens):
            return self._tokens[-1]  # Return EOF
        return self._tokens[idx]

    def _advance(self) -> Token:
        """Consume and return the current token."""
        token = self._tokens[self._pos]
        self._pos = min(self._pos + 1, len(self._tokens))
        return token

    def _skip(self, kind: TokenKind) -> None:
        """Skip a token of expected kind."""
        if self._peek().kind == kind:
            self._advance()
        else:
            raise ParseError(
                f"Expected {kind.name}",
                self._peek().position,
            )

    def _parse_expression(self, min_prec: int) -> ASTNode:
        """Parse an expression with minimum precedence.

        Args:
            min_prec: Minimum precedence to accept

        Returns:
            AST node
        """
        left = self._parse_prefix()

        while True:
            token = self._peek()

            # Handle binary operators
            if token.kind == TokenKind.OPERATOR:
                prec = self._get_binary_prec(token.value)
                if prec < min_prec:
                    break

                op = self._advance().value
                right = self._parse_expression(prec + 1)
                left = BinaryOpNode(left, op, right)
            elif token.kind == TokenKind.DOT:
                self._advance()
                ident = self._advance()
                if ident.kind != TokenKind.IDENTIFIER:
                    raise ParseError("Expected identifier after .", ident.position)
                left = self._build_access(left, ident.value)
            elif token.kind == TokenKind.LBRACKET:
                self._advance()
                index = self._parse_expression(0)
                self._skip(TokenKind.RBRACKET)
                left = ArrayAccessNode(left, index)
            else:
                break

        return left

    def _build_access(self, base: ASTNode, path: str) -> ASTNode:
        """Build a property access node.

        Handles a.b.c style access from left to right.

        Args:
            base: Base node
            path: Dot-separated property path

        Returns:
            Property access node
        """
        parts = path.split(".")
        current = base
        for part in parts:
            current = PropertyAccessNode(current, part)
        return current

    def _parse_prefix(self) -> ASTNode:
        """Parse a prefix expression (unary, primary)."""
        token = self._peek()

        # Number
        if token.kind == TokenKind.NUMBER:
            return NumberNode(float(self._advance().value))

        # String
        if token.kind == TokenKind.STRING:
            return StringNode(self._advance().value)

        # Identifier or function call
        if token.kind == TokenKind.IDENTIFIER:
            return self._parse_identifier_or_call()

        # Parentheses for grouping or function call
        if token.kind == TokenKind.LPAREN:
            return self._parse_paren_or_call()

        # Unary operators
        if token.kind == TokenKind.OPERATOR:
            if token.value in ("+", "-", "!"):
                op = self._advance().value
                operand = self._parse_expression(8)
                return UnaryOpNode(op, operand)

        raise ParseError(f"Unexpected token {token}", token.position)

    def _parse_identifier_or_call(self) -> ASTNode:
        """Parse an identifier that might be a function call.

        Returns:
            Identifier or function call node
        """
        name_token = self._advance()
        name = name_token.value

        # Handle boolean literals
        if name.lower() == "true":
            return BooleanNode(True)
        if name.lower() == "false":
            return BooleanNode(False)
        if name.lower() == "null":
            return NullNode()

        # Check for function call
        if self._peek().kind == TokenKind.LPAREN:
            self._advance()
            args = self._parse_arguments()
            self._skip(TokenKind.RPAREN)
            return FunctionCallNode(name, args)

        # If identifier contains dots, split into parts
        if "." in name:
            parts = name.split(".")
            node: ASTNode = IdentifierNode(parts)
        else:
            node = IdentifierNode([name])

        # Handle . after identifier (for cases like "a.b" where tokenizer didn't split)
        while self._peek().kind == TokenKind.DOT:
            self._advance()
            prop_token = self._advance()
            if prop_token.kind != TokenKind.IDENTIFIER:
                raise ParseError("Expected identifier", prop_token.position)
            node = PropertyAccessNode(node, prop_token.value)

        return node

    def _parse_paren_or_call(self) -> ASTNode:
        """Parse parentheses for grouping or function call.

        Returns:
            Grouped expression or function call node
        """
        start_pos = self._peek().position
        self._advance()  # Skip (

        # Check if this is a function call (identifier followed by()
        if self._peek().kind == TokenKind.IDENTIFIER:
            name = self._peek().value
            if self._peek(1).kind == TokenKind.LPAREN:
                self._advance()  # Skip identifier
                self._advance()  # Skip (
                args = self._parse_arguments()
                self._skip(TokenKind.RPAREN)
                return FunctionCallNode(name, args)

        # Otherwise it's grouping
        expr = self._parse_expression(0)
        self._skip(TokenKind.RPAREN)
        return expr

    def _parse_arguments(self) -> list[ASTNode]:
        """Parse function arguments.

        Returns:
            List of argument AST nodes
        """
        args: list[ASTNode] = []

        if self._peek().kind != TokenKind.RPAREN:
            args.append(self._parse_expression(0))

        while self._peek().kind == TokenKind.COMMA:
            self._advance()
            args.append(self._parse_expression(0))

        return args

    def _get_binary_prec(self, op: str) -> int:
        """Get precedence for a binary operator.

        Args:
            op: Operator string

        Returns:
            Precedence value
        """
        prec_map = {
            "||": 1,
            "&&": 2,
            "=": 3,
            "!=": 3,
            "<": 4,
            "<=": 4,
            ">": 4,
            ">=": 4,
            "+": 5,
            "-": 5,
            "*": 6,
            "/": 6,
            "%": 6,
            "^": 7,
        }
        return prec_map.get(op, 0)


def parse(expression: str) -> ASTNode:
    """Parse an expression string into an AST.

    Args:
        expression: Expression to parse

    Returns:
        Root AST node

    Raises:
        ParseError: If parsing fails
    """
    parser = WorkflowExpressionParser(expression)
    return parser.parse()