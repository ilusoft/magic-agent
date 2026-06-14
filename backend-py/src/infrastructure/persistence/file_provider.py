"""JSON file-based agent definitions provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import structlog

logger = structlog.get_logger(__name__)


class FileAgentDefinitionsProvider:
    """Loads and persists agent definitions from JSON files.

    Agent definitions are stored in a directory containing one JSON file per agent
    or workflow. The provider watches the directory and can reload when files change.
    """

    def __init__(self, configs_path: Path) -> None:
        """Initialize the provider with the path to agent definitions.

        Args:
            configs_path: Path to directory containing agent JSON files.
        """
        self._configs_path = configs_path
        self._cache: dict[str, dict[str, Any]] = {}
        self._logger = logger.bind(component="FileAgentDefinitionsProvider")

    def _resolve_path(self, path: Path | str) -> Path:
        """Resolve a path relative to the configs directory.

        Args:
            path: Path to resolve

        Returns:
            Absolute path resolved against configs_path
        """
        if Path(path).is_absolute():
            return Path(path)
        return (self._configs_path / path).resolve()

    async def load_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Load a single agent definition by ID.

        Looks for a file named `{agent_id}.json` in the configs directory,
        or checks if the agent is defined within a multi-agent file.

        Args:
            agent_id: The agent identifier

        Returns:
            Agent definition dict or None if not found
        """
        # Check cache first
        if agent_id in self._cache:
            return self._cache[agent_id]

        # Try loading from individual file
        agent_file = self._configs_path / f"{agent_id}.json"
        if agent_file.exists():
            return await self._load_file(agent_file, agent_id)

        # Check if there's a multi-agent file (agents.json)
        multi_agent_file = self._configs_path / "agents.json"
        if multi_agent_file.exists():
            agents_data = await self._load_file(multi_agent_file, "agents")
            if "agents" in agents_data:
                for agent in agents_data["agents"]:
                    if agent.get("id") == agent_id or agent.get("name") == agent_id:
                        return cast(dict[str, Any], agent)

        self._logger.warning("agent_not_found", agent_id=agent_id)
        return None

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all agent definitions in the configs directory.

        Returns:
            List of agent definition dicts
        """
        agents: list[dict[str, Any]] = []

        if not self._configs_path.exists():
            self._logger.warning("configs_path_not_found", path=str(self._configs_path))
            return agents

        # Load from multi-agent file if it exists
        multi_agent_file = self._configs_path / "agents.json"
        if multi_agent_file.exists():
            data = await self._load_file(multi_agent_file, "agents")
            if "agents" in data:
                agents.extend(data["agents"])

        # Load individual agent files
        for file_path in self._configs_path.glob("*.json"):
            if file_path.name == "agents.json":
                continue
            agent_id = file_path.stem
            agent_data = await self._load_file(file_path, agent_id)
            if "agent" in agent_data:
                agents.append(agent_data["agent"])
            elif "agents" in agent_data:
                agents.extend(agent_data["agents"])
            else:
                # Single agent file without wrapper
                agents.append(agent_data)

        return agents

    async def get_full_document(self) -> dict[str, Any]:
        """Load the full agent definitions document.

        Returns the entire contents of agents.json (or equivalent)
        with all metadata preserved.

        Returns:
            Full agent definitions document dict
        """
        multi_agent_file = self._configs_path / "agents.json"
        if multi_agent_file.exists():
            return await self._load_file(multi_agent_file, "agents")

        # Fallback: return structure with list_agents result
        agents = await self.list_agents()
        return {"agents": agents}

    async def save_agent(
        self, agent_id: str, definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Save an agent definition to a JSON file.

        Args:
            agent_id: The agent identifier
            definition: The agent definition dict

        Returns:
            The saved definition
        """
        agent_file = self._configs_path / f"{agent_id}.json"
        agent_file.parent.mkdir(parents=True, exist_ok=True)

        await self._write_file(agent_file, definition)
        self._cache[agent_id] = definition

        self._logger.info("agent_saved", agent_id=agent_id, path=str(agent_file))
        return definition

    async def save_full_document(self, document: dict[str, Any]) -> dict[str, Any]:
        """Save the full agent definitions document.

        Writes the entire document (including agents array, viewLayout,
        streaming config, etc.) to agents.json.

        Args:
            document: The full agent definitions document

        Returns:
            The saved document
        """
        multi_agent_file = self._configs_path / "agents.json"
        multi_agent_file.parent.mkdir(parents=True, exist_ok=True)

        await self._write_file(multi_agent_file, document)
        self._cache["agents"] = document

        self._logger.info(
            "full_document_saved",
            path=str(multi_agent_file),
            agent_count=len(document.get("agents", [])),
        )
        return document

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent definition file.

        Args:
            agent_id: The agent identifier

        Returns:
            True if deleted, False if not found
        """
        agent_file = self._configs_path / f"{agent_id}.json"

        if not agent_file.exists():
            return False

        agent_file.unlink()
        self._cache.pop(agent_id, None)

        self._logger.info("agent_deleted", agent_id=agent_id)
        return True

    async def _load_file(
        self, file_path: Path, cache_key: str
    ) -> dict[str, Any]:
        """Load and parse a JSON file.

        Args:
            file_path: Path to JSON file
            cache_key: Key to use for caching

        Returns:
            Parsed JSON dict
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(content)

            # Resolve environment variables
            from src.lib.security import resolve_value

            data = resolve_value(data)
            self._cache[cache_key] = data

            return data
        except json.JSONDecodeError as e:
            self._logger.error(
                "invalid_json",
                path=str(file_path),
                error=str(e),
            )
            raise

    async def _write_file(self, file_path: Path, data: dict[str, Any]) -> None:
        """Write data to a JSON file.

        Args:
            file_path: Path to JSON file
            data: Data to write
        """
        content = json.dumps(data, indent=2, ensure_ascii=False)
        file_path.write_text(content, encoding="utf-8")