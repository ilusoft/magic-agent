"""Tests for the workflow helper functions (Math, Strings, Arrays, Dates)."""

from __future__ import annotations

import pytest

from src.application.workflows.expressions.helpers import (
    ArrayHelpers,
    StringHelpers,
)


class TestAddToArray:
    """Regression tests for ``addToArray``."""

    def test_appends_to_existing_list(self) -> None:
        assert ArrayHelpers.addToArray([1, 2], 3) == [1, 2, 3]

    def test_appends_to_empty_list(self) -> None:
        assert ArrayHelpers.addToArray([], "item") == ["item"]

    def test_string_first_arg_does_not_iterate_chars(self) -> None:
        """Regression: ``list("Hola mundo")`` iterates the string as
        characters. The helper must wrap a non-list in ``[...]`` so the
        string survives as a single element.
        """
        result = ArrayHelpers.addToArray("Hola mundo", "world")
        assert result == ["Hola mundo", "world"]

    def test_non_list_first_arg_is_wrapped(self) -> None:
        """Any non-list first argument should be wrapped, not iterated."""
        result = ArrayHelpers.addToArray(42, "x")
        assert result == [42, "x"]

        result = ArrayHelpers.addToArray({"k": 1}, "x")
        assert result == [{"k": 1}, "x"]

    def test_returns_new_list_does_not_mutate_input(self) -> None:
        original = [1, 2]
        result = ArrayHelpers.addToArray(original, 3)
        assert result == [1, 2, 3]
        assert original == [1, 2]
