"""Security utilities (token resolution, secret handling)."""

from __future__ import annotations

import os
import re
from typing import Any


def _lookup_env_var(name: str) -> str | None:
    """Look up an environment variable, falling back to pydantic Settings.

    The fallback lets placeholder syntax like ``${LLM_API_KEY}`` resolve to
    values declared in ``.env`` even though pydantic-settings only loads them
    into the ``Settings`` object (not ``os.environ``).

    Args:
        name: Environment variable name (e.g. ``LLM_API_KEY``).

    Returns:
        The resolved value, or ``None`` if not found anywhere.
    """
    direct = os.environ.get(name)
    if direct:
        return direct

    try:
        from src.config import get_settings

        settings = get_settings()
    except Exception:
        return None

    attr_name = name.lower()
    if not hasattr(settings, attr_name):
        return None

    value = getattr(settings, attr_name)
    return value if isinstance(value, str) and value else None


def resolve_env_vars(value: str) -> str:
    """Resolve environment variable placeholders in a string.

    Supports both ${ENV_VAR} and {ENV_VAR} syntax. Falls back to the
    application's ``Settings`` when the variable is not present in the
    process environment (e.g. when pydantic-settings loaded it from
    ``.env``).

    Args:
        value: String potentially containing environment variable placeholders

    Returns:
        String with resolved environment variables. Unresolved placeholders
        are preserved verbatim.

    Example:
        >>> resolve_env_vars("${AZURE_OPENAI_KEY}")
        "actual-key-value"
        >>> resolve_env_vars("{AZURE_OPENAI_KEY}")
        "actual-key-value"
    """
    pattern = r"\$\{([^}]+)\}|\{([A-Z_][A-Z0-9_]*)\}"

    def replacer(match: re.Match[str]) -> str:
        env_var = match.group(1) or match.group(2)
        return _lookup_env_var(env_var) or match.group(0)

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