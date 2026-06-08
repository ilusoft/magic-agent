"""Workflow expression AST node definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ASTNode(ABC):
    """Base class for expression AST nodes."""

    @abstractmethod
    def __repr__(self) -> str:
        pass


class NumberNode(ASTNode):
    """A numeric literal."""

    def __init__(self, value: float) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"NumberNode({self.value})"


class StringNode(ASTNode):
    """A string literal."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"StringNode({self.value!r})"


class BooleanNode(ASTNode):
    """A boolean literal."""

    def __init__(self, value: bool) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"BooleanNode({self.value})"


class NullNode(ASTNode):
    """A null literal."""

    def __repr__(self) -> str:
        return "NullNode()"


class IdentifierNode(ASTNode):
    """An identifier that may include property access."""

    def __init__(self, parts: list[str]) -> None:
        self.parts = parts

    @property
    def root(self) -> str:
        return self.parts[0] if self.parts else ""

    @property
    def path(self) -> list[str]:
        return self.parts[1:] if len(self.parts) > 1 else []

    def __repr__(self) -> str:
        return f"IdentifierNode({self.parts})"


class PropertyAccessNode(ASTNode):
    """Property access with dot notation."""

    def __init__(self, base: ASTNode, property_name: str) -> None:
        self.base = base
        self.property_name = property_name

    def __repr__(self) -> str:
        return f"PropertyAccessNode({self.base}, {self.property_name})"


class ArrayAccessNode(ASTNode):
    """Array or property access with bracket notation."""

    def __init__(self, base: ASTNode, index: ASTNode) -> None:
        self.base = base
        self.index = index

    def __repr__(self) -> str:
        return f"ArrayAccessNode({self.base}, {self.index})"


class BinaryOpNode(ASTNode):
    """A binary operation."""

    def __init__(self, left: ASTNode, operator: str, right: ASTNode) -> None:
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self) -> str:
        return f"BinaryOpNode({self.left} {self.operator} {self.right})"


class UnaryOpNode(ASTNode):
    """A unary operation."""

    def __init__(self, operator: str, operand: ASTNode) -> None:
        self.operator = operator
        self.operand = operand

    def __repr__(self) -> str:
        return f"UnaryOpNode({self.operator}{self.operand})"


class FunctionCallNode(ASTNode):
    """A function call."""

    def __init__(self, name: str, arguments: list[ASTNode]) -> None:
        self.name = name
        self.arguments = arguments

    def __repr__(self) -> str:
        return f"FunctionCallNode({self.name}, {self.arguments})"


class JsonNode(ASTNode):
    """A JSON object or array literal."""

    def __init__(self, value: Any) -> None:
        self.value = value

    def __repr__(self) -> str:
        return f"JsonNode({self.value})"