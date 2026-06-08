"""Pytest fixtures for testing."""

from __future__ import annotations

import pytest
from pytest import FixtureRequest

from src.config import Settings, get_settings


@pytest.fixture
def settings() -> Settings:
    """Get test settings."""
    return get_settings()


@pytest.fixture
def sample_agent_definition() -> dict:
    """Sample agent definition for testing."""
    return {
        "name": "test-agent",
        "description": "A test agent",
        "llm": {
            "provider": "azure-openai",
            "model": "gpt-4o",
            "api_key_secret": "AZURE_OPENAI_KEY",
        },
        "system_prompt": "You are a helpful assistant.",
        "tools": [],
        "workflow": {
            "steps": [
                {"id": "input", "type": "input", "description": "Get input"},
                {"id": "chat", "type": "chat", "agent": "test-agent"},
            ],
            "outputs": [],
        },
        "runtime": {
            "max_iterations": 10,
            "timeout_seconds": 60,
        },
    }


@pytest.fixture
def sample_expressions() -> list[tuple[str, str]]:
    """Sample expression strings for testing."""
    return [
        ("{{var.name}}", "simple placeholder"),
        ("${{1 + 2}}", "numeric expression"),
        ("Hello ${{toUpper('world')}}!", "function call"),
        ("${{var.items[0]}}", "array access"),
    ]