"""JSON store for generic JSON file read/write operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import structlog

logger = structlog.get_logger(__name__)


class JsonStore:
    """Generic JSON file read/write utility."""

    @staticmethod
    def read(file_path: Path | str) -> dict[str, Any] | None:
        """Read a JSON file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Parsed JSON dict or None if file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            parsed: dict[str, Any] = json.loads(content)
            return parsed
        except json.JSONDecodeError as e:
            logger.error("json_decode_error", path=str(path), error=str(e))
            raise

    @staticmethod
    def write(file_path: Path | str, data: dict[str, Any]) -> None:
        """Write data to a JSON file.

        Args:
            file_path: Path to the JSON file
            data: Data to write
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        content = json.dumps(data, indent=2, ensure_ascii=False)
        path.write_text(content, encoding="utf-8")

    @staticmethod
    def update(
        file_path: Path | str,
        update_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Read, apply a transformation function, and write back.

        Args:
            file_path: Path to the JSON file
            update_fn: Function that takes current data and returns new data

        Returns:
            The updated data
        """
        current = JsonStore.read(file_path) or {}
        updated = update_fn(current)
        JsonStore.write(file_path, updated)
        return updated