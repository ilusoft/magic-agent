"""Workflow expression helper functions.

Helpers are functions that can be called in expressions, e.g., ${{toUpper('hello')}}.
Each helper is decorated with @workflow_helper and its parameters with @workflow_helper_param.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, Field


class WorkflowHelperParam(BaseModel):
    """Metadata for a helper function parameter."""

    name: str
    description: str | None = None
    optional: bool = False
    default: Any = None


class WorkflowHelperDescriptor(BaseModel):
    """Metadata for a helper function."""

    name: str
    description: str | None = None
    category: str
    parameters: list[WorkflowHelperParam]
    examples: list[str] = Field(default_factory=list)


def workflow_helper(
    name: str | None = None,
    category: str = "General",
    description: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to mark a function as a workflow helper.

    Args:
        name: Helper name (defaults to function name)
        category: Helper category (Math, Strings, Arrays, Dates)
        description: Helper description

    Returns:
        Decorator function
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn._workflow_helper = True  # type: ignore[attr-defined]
        fn._helper_name = name or fn.__name__  # type: ignore[attr-defined]
        fn._helper_category = category  # type: ignore[attr-defined]
        fn._helper_description = description  # type: ignore[attr-defined]
        return fn
    return decorator


def workflow_helper_param(
    name: str,
    description: str | None = None,
    optional: bool = False,
    default: Any = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to mark a parameter of a workflow helper.

    Args:
        name: Parameter name
        description: Parameter description
        optional: Whether the parameter is optional
        default: Default value for optional parameters

    Returns:
        Decorator function
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if not hasattr(fn, "_helper_params"):
            fn._helper_params = []  # type: ignore[attr-defined]
        fn._helper_params.append({  # type: ignore[attr-defined]
            "name": name,
            "description": description,
            "optional": optional,
            "default": default,
        })
        return fn
    return decorator


class WorkflowHelperRegistry:
    """Registry of workflow helper functions.

    Provides metadata and invocation for all available helpers.
    """

    def __init__(self) -> None:
        self._helpers: dict[str, Callable[..., Any]] = {}
        self._discover_helpers()

    def _discover_helpers(self) -> None:
        """Discover all helpers from the Math, Strings, Arrays, Dates classes."""
        from src.application.workflows.expressions.helpers import (
            MathHelpers,
            StringHelpers,
            ArrayHelpers,
            DateHelpers,
        )

        for cls in [MathHelpers, StringHelpers, ArrayHelpers, DateHelpers]:
            for name in dir(cls):
                if name.startswith("_"):
                    continue
                attr = getattr(cls, name)
                if hasattr(attr, "_workflow_helper"):
                    helper_name = attr._helper_name
                    self._helpers[helper_name.lower()] = attr

    def get_helpers(self) -> list[WorkflowHelperDescriptor]:
        """Get metadata for all available helpers.

        Returns:
            List of helper descriptors
        """
        descriptors = []
        for name, fn in self._helpers.items():
            params = []
            if hasattr(fn, "_helper_params"):
                for p in fn._helper_params:
                    params.append(WorkflowHelperParam(**p))

            descriptors.append(WorkflowHelperDescriptor(
                name=name,
                description=getattr(fn, "_helper_description", None),
                category=getattr(fn, "_helper_category", "General"),
                parameters=params,
            ))

        return descriptors

    def invoke(self, name: str, args: list[Any]) -> Any:
        """Invoke a helper function.

        Args:
            name: Helper name (case-insensitive)
            args: Arguments to pass to the helper

        Returns:
            Helper return value

        Raises:
            ValueError: If helper not found
        """
        fn = self._helpers.get(name.lower())
        if not fn:
            raise ValueError(f"Unknown helper: {name}")

        # Apply default values for missing optional args
        if hasattr(fn, "_helper_params"):
            params = fn._helper_params
            while len(args) < len(params):
                param = params[len(args)]
                if param["optional"]:
                    args.append(param["default"])
                else:
                    break

        return fn(*args)

    def get_helper(self, name: str) -> Callable[..., Any] | None:
        """Get a helper function by name.

        Args:
            name: Helper name

        Returns:
            Helper function or None
        """
        return self._helpers.get(name.lower())


# Math helpers
class MathHelpers:
    """Mathematical helper functions."""

    @staticmethod
    @workflow_helper("abs", category="Math", description="Returns the absolute value of a number")
    @workflow_helper_param("value", "The number to get absolute value of")
    def abs(value: float) -> float:
        return abs(value)

    @staticmethod
    @workflow_helper("sqr", category="Math", description="Returns the square of a number")
    @workflow_helper_param("value", "The number to square")
    def sqr(value: float) -> float:
        return value ** 2

    @staticmethod
    @workflow_helper("sqrt", category="Math", description="Returns the square root of a number")
    @workflow_helper_param("value", "The number to get square root of")
    def sqrt(value: float) -> float:
        return math.sqrt(value)

    @staticmethod
    @workflow_helper("pow", category="Math", description="Returns base raised to exponent")
    @workflow_helper_param("base", "The base number")
    @workflow_helper_param("exponent", "The exponent")
    def pow(base: float, exponent: float) -> float:
        result: float = base ** exponent
        return result

    @staticmethod
    @workflow_helper("min", category="Math", description="Returns the minimum of two numbers")
    @workflow_helper_param("a", "First number")
    @workflow_helper_param("b", "Second number")
    def min(a: float, b: float) -> float:
        return min(a, b)

    @staticmethod
    @workflow_helper("max", category="Math", description="Returns the maximum of two numbers")
    @workflow_helper_param("a", "First number")
    @workflow_helper_param("b", "Second number")
    def max(a: float, b: float) -> float:
        return max(a, b)


# String helpers
class StringHelpers:
    """String manipulation helper functions."""

    @staticmethod
    @workflow_helper("length", category="Strings", description="Returns the length of a string")
    @workflow_helper_param("value", "The string to get length of")
    def length(value: str) -> int:
        return len(value)

    @staticmethod
    @workflow_helper("toUpper", category="Strings", description="Converts a string to uppercase")
    @workflow_helper_param("value", "The string to convert")
    def toUpper(value: str) -> str:
        return value.upper()

    @staticmethod
    @workflow_helper("toLower", category="Strings", description="Converts a string to lowercase")
    @workflow_helper_param("value", "The string to convert")
    def toLower(value: str) -> str:
        return value.lower()

    @staticmethod
    @workflow_helper("substring", category="Strings", description="Returns a substring")
    @workflow_helper_param("value", "The source string")
    @workflow_helper_param("start", "Start index (0-based)")
    @workflow_helper_param("length", "Length of substring", optional=True)
    def substring(value: str, start: int, length: int | None = None) -> str:
        if length is None:
            return value[start:]
        return value[start:start + length]

    @staticmethod
    @workflow_helper("replace", category="Strings", description="Replaces occurrences of a string")
    @workflow_helper_param("value", "The source string")
    @workflow_helper_param("search", "String to search for")
    @workflow_helper_param("replace", "String to replace with")
    def replace(value: str, search: str, replace: str) -> str:
        return value.replace(search, replace)

    @staticmethod
    @workflow_helper("indexOf", category="Strings", description="Returns the index of a substring")
    @workflow_helper_param("value", "The source string")
    @workflow_helper_param("search", "String to search for")
    def indexOf(value: str, search: str) -> int:
        idx = value.find(search)
        return idx if idx >= 0 else -1

    @staticmethod
    @workflow_helper("trim", category="Strings", description="Removes leading and trailing whitespace")
    @workflow_helper_param("value", "The string to trim")
    def trim(value: str) -> str:
        return value.strip()

    @staticmethod
    @workflow_helper("split", category="Strings", description="Splits a string into an array")
    @workflow_helper_param("value", "The string to split")
    @workflow_helper_param("separator", "The separator", optional=True, default=",")
    def split(value: str, separator: str = ",") -> list[str]:
        return value.split(separator)

    @staticmethod
    @workflow_helper("contains", category="Strings", description="Checks if a string contains a substring")
    @workflow_helper_param("value", "The source string")
    @workflow_helper_param("search", "String to search for")
    def contains(value: str, search: str) -> bool:
        return search in value

    @staticmethod
    @workflow_helper("startsWith", category="Strings", description="Checks if a string starts with a prefix")
    @workflow_helper_param("value", "The source string")
    @workflow_helper_param("prefix", "The prefix to check")
    def startsWith(value: str, prefix: str) -> bool:
        return value.startswith(prefix)

    @staticmethod
    @workflow_helper("endsWith", category="Strings", description="Checks if a string ends with a suffix")
    @workflow_helper_param("value", "The source string")
    @workflow_helper_param("suffix", "The suffix to check")
    def endsWith(value: str, suffix: str) -> bool:
        return value.endswith(suffix)

    @staticmethod
    @workflow_helper("compare", category="Strings", description="Compares two strings")
    @workflow_helper_param("a", "First string")
    @workflow_helper_param("b", "Second string")
    @workflow_helper_param("caseSensitive", "Case sensitive comparison", optional=True, default=False)
    @workflow_helper_param("trimWhitespace", "Trim whitespace before comparison", optional=True, default=False)
    def compare(a: str, b: str, caseSensitive: bool = False, trimWhitespace: bool = False) -> int:
        if trimWhitespace:
            a = a.strip()
            b = b.strip()
        if not caseSensitive:
            a = a.lower()
            b = b.lower()
        if a < b:
            return -1
        elif a > b:
            return 1
        return 0

    @staticmethod
    @workflow_helper("isNullOrEmpty", category="Strings", description="Checks if a value is null or empty")
    @workflow_helper_param("value", "The value to check")
    def isNullOrEmpty(value: str | None) -> bool:
        return value is None or value == ""

    @staticmethod
    @workflow_helper("isNull", category="Strings", description="Checks if a value is null")
    @workflow_helper_param("value", "The value to check")
    def isNull(value: Any) -> bool:
        return value is None


# Array/JSON helpers
class ArrayHelpers:
    """Array and JSON manipulation helper functions."""

    @staticmethod
    @workflow_helper("addToArray", category="Arrays/JSON", description="Adds an item to an array")
    @workflow_helper_param("array", "The array to add to")
    @workflow_helper_param("item", "The item to add")
    def addToArray(array: list[Any], item: Any) -> list[Any]:
        result = list(array)
        result.append(item)
        return result

    @staticmethod
    @workflow_helper("removeFromArray", category="Arrays/JSON", description="Removes items from an array")
    @workflow_helper_param("array", "The array to remove from")
    @workflow_helper_param("removeAll", "Remove all occurrences", optional=True, default=False)
    def removeFromArray(array: list[Any], removeAll: bool = False) -> list[Any]:
        if removeAll or len(array) == 1:
            return []
        return list(array[:-1])

    @staticmethod
    @workflow_helper("indexOnArray", category="Arrays/JSON", description="Gets index from end of array")
    @workflow_helper_param("array", "The array")
    @workflow_helper_param("startFromEnd", "Start counting from end", optional=True, default=False)
    def indexOnArray(array: list[Any], startFromEnd: bool = False) -> int:
        if startFromEnd:
            return len(array) - 1
        return 0

    @staticmethod
    @workflow_helper("replaceElement", category="Arrays/JSON", description="Replaces elements in an array")
    @workflow_helper_param("array", "The array")
    @workflow_helper_param("replaceAll", "Replace all occurrences", optional=True, default=False)
    def replaceElement(array: list[Any], replaceAll: bool = False) -> list[Any]:
        return list(array)

    @staticmethod
    @workflow_helper("subArray", category="Arrays/JSON", description="Returns a sub-array")
    @workflow_helper_param("array", "The array")
    @workflow_helper_param("invert", "Invert the array", optional=True, default=False)
    def subArray(array: list[Any], invert: bool = False) -> list[Any]:
        if invert:
            return list(reversed(array))
        return list(array)

    @staticmethod
    @workflow_helper("concatArrays", category="Arrays/JSON", description="Concatenates two arrays")
    @workflow_helper_param("array1", "First array")
    @workflow_helper_param("array2", "Second array")
    def concatArrays(array1: list[Any], array2: list[Any]) -> list[Any]:
        return list(array1) + list(array2)

    @staticmethod
    @workflow_helper("stringToJson", category="Arrays/JSON", description="Parses a JSON string")
    @workflow_helper_param("value", "The JSON string to parse")
    def stringToJson(value: str) -> Any:
        import json
        return json.loads(value)

    @staticmethod
    @workflow_helper("jsonToString", category="Arrays/JSON", description="Converts a value to JSON string")
    @workflow_helper_param("value", "The value to convert")
    def jsonToString(value: Any) -> str:
        import json
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    @workflow_helper("arrayLength", category="Arrays/JSON", description="Returns the length of an array")
    @workflow_helper_param("array", "The array")
    def arrayLength(array: list[Any]) -> int:
        return len(array)


# Date helpers
class DateHelpers:
    """Date manipulation helper functions."""

    @staticmethod
    def _to_datetime(value: str | datetime) -> datetime:
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    @workflow_helper("dateAdd", category="Dates", description="Adds time to a date")
    @workflow_helper_param("date", "The date string or datetime")
    @workflow_helper_param("amount", "Amount to add")
    @workflow_helper_param("unit", "Unit (day, hour, minute, second)", optional=True, default="day")
    def dateAdd(date: str | datetime, amount: float, unit: str = "day") -> datetime:
        dt = DateHelpers._to_datetime(date)
        unit_lower = unit.lower()
        if unit_lower == "day":
            return dt + timedelta(days=amount)
        elif unit_lower == "hour":
            return dt + timedelta(hours=amount)
        elif unit_lower == "minute":
            return dt + timedelta(minutes=amount)
        elif unit_lower == "second":
            return dt + timedelta(seconds=amount)
        return dt

    @staticmethod
    @workflow_helper("dateDiff", category="Dates", description="Returns difference between two dates in specified unit")
    @workflow_helper_param("date1", "First date")
    @workflow_helper_param("date2", "Second date")
    @workflow_helper_param("unit", "Unit (day, hour, minute, second)", optional=True, default="day")
    def dateDiff(date1: str | datetime, date2: str | datetime, unit: str = "day") -> float:
        dt1 = DateHelpers._to_datetime(date1)
        dt2 = DateHelpers._to_datetime(date2)
        delta = dt2 - dt1
        unit_lower = unit.lower()
        if unit_lower == "day":
            return delta.total_seconds() / 86400
        elif unit_lower == "hour":
            return delta.total_seconds() / 3600
        elif unit_lower == "minute":
            return delta.total_seconds() / 60
        elif unit_lower == "second":
            return delta.total_seconds()
        return delta.total_seconds()

    @staticmethod
    @workflow_helper("dayOfWeek", category="Dates", description="Returns day of week (0=Monday, 6=Sunday)")
    @workflow_helper_param("date", "The date string or datetime")
    @workflow_helper_param("culture", "Culture for localization", optional=True, default=None)
    def dayOfWeek(date: str | datetime, culture: str | None = None) -> int:
        dt = DateHelpers._to_datetime(date)
        return dt.weekday()

    @staticmethod
    @workflow_helper("toLocalDate", category="Dates", description="Converts to local date")
    @workflow_helper_param("date", "The date string or datetime")
    def toLocalDate(date: str | datetime) -> datetime:
        dt = DateHelpers._to_datetime(date)
        return dt.astimezone()

    @staticmethod
    @workflow_helper("toDateUtc", category="Dates", description="Converts to UTC date")
    @workflow_helper_param("date", "The date string or datetime")
    @workflow_helper_param("offsetMinutes", "Timezone offset in minutes", optional=True, default=0)
    def toDateUtc(date: str | datetime, offsetMinutes: int = 0) -> datetime:
        dt = DateHelpers._to_datetime(date)
        return dt.replace(tzinfo=timezone.utc) - timedelta(minutes=offsetMinutes)

    @staticmethod
    @workflow_helper("localOffset", category="Dates", description="Returns local timezone offset in minutes")
    def localOffset() -> int:
        offset = datetime.now().astimezone().utcoffset()
        if offset is None:
            return 0
        return int(offset.total_seconds() // 60)

    @staticmethod
    @workflow_helper("dateConvert", category="Dates", description="Converts date to string")
    @workflow_helper_param("date", "The date string or datetime")
    @workflow_helper_param("format", "Output format", optional=True, default="%Y-%m-%d")
    def dateConvert(date: str | datetime, format: str = "%Y-%m-%d") -> str:
        dt = DateHelpers._to_datetime(date)
        return dt.strftime(format)

    @staticmethod
    @workflow_helper("stringToDate", category="Dates", description="Parses a string to date")
    @workflow_helper_param("value", "The date string")
    @workflow_helper_param("format", "Input format", optional=True, default=None)
    @workflow_helper_param("culture", "Culture", optional=True, default=None)
    def stringToDate(value: str, format: str | None = None, culture: str | None = None) -> datetime:
        if format:
            return datetime.strptime(value, format)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    @workflow_helper("datePart", category="Dates", description="Extracts part of a date")
    @workflow_helper_param("date", "The date string or datetime")
    @workflow_helper_param("part", "Part to extract (year, month, day, hour, minute, second)")
    def datePart(date: str | datetime, part: str) -> int:
        dt = DateHelpers._to_datetime(date)
        part_lower = part.lower()
        if part_lower == "year":
            return dt.year
        elif part_lower == "month":
            return dt.month
        elif part_lower == "day":
            return dt.day
        elif part_lower == "hour":
            return dt.hour
        elif part_lower == "minute":
            return dt.minute
        elif part_lower == "second":
            return dt.second
        return 0