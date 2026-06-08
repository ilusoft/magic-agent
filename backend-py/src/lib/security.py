"""Security utilities (token resolution, secret handling)."""

from __future__ import annotations

import os
import re
from typing import Any


def resolve_env_vars(value: str) -> str:
    """Resolve ${ENV_VAR} placeholders in a string with environment variable values.

    Args:
        value: String potentially containing ${ENV_VAR} placeholders

    Returns:
        String with resolved environment variables

    Example:
        >>> resolve_env_vars("${AZURE_OPENAI_KEY}")
        "actual-key-value"
    """
    pattern = r"\$\{([^}]+)\}"

    def replacer(match: re.Match[str]) -> str:
        env_var = match.group(1)
        return os.environ.get(env_var, match.group(0))

    return re.sub(pattern, replacer, value)


def resolve_value(value: Any) -> Any:
    """Recursively resolve environment variables in a value.

    Args:
        value: Any value (str, dict, list, etc.)

    Returns:
        Value with resolved environment variables
    """
    if isinstance(value, str):
        return resolve_env_vars(value)
    elif isinstance(value, dict):
        return {k: resolve_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_value(item) for item in value]
    return value