# Magic Agent Backend - Python

FastAPI-based REST API for the Magic Agent Workflow Studio.

## Quick Start

```bash
# Install core dependencies
pip install -e .

# Install all optional dependencies (LangGraph, MCP, SSE support)
pip install -e ".[all]"

# Install dev dependencies
pip install -e ".[dev]"

# Run development server
python -m src.main

# Or with uvicorn
uvicorn src.main:app --reload --port 8000
```

## Optional Dependencies

The backend has optional dependencies for specific features:

| Extra | Description |
|-------|-------------|
| `langgraph` | LangGraph agent runtime support |
| `mcp` | MCP (Model Context Protocol) client support |
| `sse` | Server-Sent Events streaming support |
| `all` | All optional dependencies |

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
AGENT_RUNTIME_CONFIGS_PATH=../../configs/agents
LLM_PROVIDER=azure-openai
LLM_ENDPOINT=https://your-resource.openai.azure.com
LLM_API_KEY=${AZURE_OPENAI_KEY}
LLM_DEPLOYMENT=gpt-4o
MAX_ITERATIONS=50
DEFAULT_TIMEOUT_SECONDS=120
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

## Project Structure

```
backend-py/
├── src/                    # Source code
│   ├── main.py            # FastAPI entry point
│   ├── config.py          # Pydantic settings
│   ├── api/               # REST API layer
│   ├── application/       # Use case orchestration
│   ├── infrastructure/    # External concerns
│   ├── agent_runtime/     # LangGraph integration
│   └── lib/              # Shared utilities
├── tests/                 # Test suite
├── pyproject.toml
└── Dockerfile
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/agents/definitions` | GET, PUT | List/update agent definitions |
| `/api/agents/{agent_id}` | GET, DELETE | Get/delete single agent |
| `/api/agents/{agent_id}/runs` | POST | Trigger agent run (sync) |
| `/api/agents/{agent_id}/runs/stream` | POST | SSE streaming run |
| `/api/workflows/helpers` | GET | List expression helpers |
| `/api/workflows/evaluate` | POST | Evaluate expression |

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```