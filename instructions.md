## Quick context for AI coding agents

This repository is a small, modular web app: a React + Vite SPA (frontend/) with two backend options:
- **Python Backend** (`backend-py/`) — FastAPI-based REST API with LangGraph agent runtime support
- **.NET Backend** (`backend/src/MagicAgent.Api/`) — ASP.NET Core 8 Web API that loads JSON-defined "agents" and executes them with the .NET Agent Framework

Use these concrete facts when making changes or generating code.

### What runs where

- Frontend: `frontend/` — Vite + React + TypeScript. Types for agent documents live in `frontend/src/types/agents.ts`.
- Python Backend API: `backend-py/src/` — FastAPI app with Pydantic settings, REST API layer, and LangGraph agent runtime.
- .NET Backend API: `backend/src/MagicAgent.Api/` — controllers, agent orchestration, and file-backed configuration.

### Key files to read before changing behavior

**Python Backend:**
- `backend-py/src/main.py` — FastAPI entry point, CORS, and service registration.
- `backend-py/src/config.py` — Pydantic settings for environment variables and runtime configuration.
- `backend-py/src/api/` — REST API layer (agents, runs, workflows endpoints).
- `backend-py/src/application/` — Use case orchestration and DTOs.
- `backend-py/src/agent_runtime/` — LangGraph integration and agent execution.

**.NET Backend:**
- `backend/src/MagicAgent.Api/Program.cs` — service registration, CORS, and options wiring.
- `backend/src/MagicAgent.Api/Infrastructure/AgentRunner/FileAgentDefinitionsProvider.cs` — how JSON definitions are loaded/saved and how the `AgentDefinitionsOptions.FilePath` is resolved (relative to backend content root).
- `backend/src/MagicAgent.Api/Application/AgentRunner/DefaultAgentRunner.cs` — core runtime: supports `chat` and `echo` step types, builds Azure OpenAI clients, and appends transcripts. Most runtime logic lives here.
- `backend/src/MagicAgent.Api/Application/AgentRunner/*.cs` — DTOs and interfaces (`IAgentRunner`, `AgentDefinition`, option classes).
- `backend/src/MagicAgent.Api/Controllers/AgentDefinitionsController.cs` and `AgentRunsController.cs` — REST surface: `GET/PUT /api/agents/definitions` and `POST /api/agents/{agentId}/runs`.
- `Configurations/agents.json` (and `configs/agents/`) — canonical examples of agent definitions. Note: sample file in repo contains an API key; do not commit secrets.

### Concrete conventions & patterns to follow

- Agent JSON shapes are authoritative. Backend types map to the JSON (see `AgentDefinition`, `AgentStepDefinition`). When changing formats, update both backend models and `frontend/src/types/agents.ts`.
- The `FileAgentDefinitionsProvider` expects `AgentDefinitionsOptions.FilePath` and resolves it against the backend app content root. Use that option rather than hardcoding paths.
- `DefaultAgentRunner` resolves configuration values first from the agent definition's `defaultParameters` / step `parameters`, then from environment variables named `AZURE_OPENAI_{KEY}` (e.g. `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_APIKEY`). Keep this resolution order in mind when adding config sources.
- Step types: currently handled values are `chat` (creates an LLM chat agent) and `echo`. If you add new step types, implement them in `ExecuteStepAsync` and ensure transcripts are appended consistently.

### Developer workflows (explicit commands)

- Start .NET backend (dev, with hot reload):

```bash
dotnet watch run --project backend/src/MagicAgent.Api/MagicAgent.Api.csproj
```

- Start Python backend (dev):

```bash
cd backend-py
uvicorn src.main:app --reload --port 8000
```

- Start frontend (dev):

```bash
pnpm --dir frontend dev
```

- Run .NET backend tests:

```bash
dotnet test backend/tests/MagicAgent.Api.Tests
```

- Run Python backend tests:

```bash
cd backend-py && pytest
```

- Run frontend tests:

```bash
pnpm --dir frontend test
```

### Important runtime behaviors & gotchas

- Secrets: agent JSON files may include `apiKey`. The runtime will prefer explicit parameters but will fallback to `AZURE_OPENAI_*` environment variables. Never commit production keys to `Configurations/agents.json`.
- CORS: `Program.cs` restricts origins to the dev frontend (`http://localhost:5173` / `https://localhost:5173`). If you run the frontend on another host, update CORS policy in `Program.cs`.
- Error handling: `DefaultAgentRunner` logs and falls back with a transcript message `[agent-framework-fallback] <input>` when LLM calls fail — maintain this pattern for consistent client-side display.

### Small examples you can use

- Minimal `agent.run` POST shape (to call from tests or UI):

```json
POST /api/agents/chat-agent/runs
{
  "input": "Explain the SOLID principles in 5 bullet points"
}
```

- Agent definition snippet (backend `AgentDefinition` shape): see `Configurations/agents.json` and `backend/src/MagicAgent.Api/Application/AgentRunner/*.cs` for the full schema.

### When editing code, check these files for consistency

**Python Backend:**
- `backend-py/src/main.py` (DI registrations and options)
- `backend-py/src/config.py` (Pydantic settings)
- `backend-py/src/api/` (REST endpoints)
- `backend-py/src/application/` (use case orchestration)

**.NET Backend:**
- `frontend/src/types/agents.ts` (mirror backend DTOs)
- `Configurations/agents.json` (sample content)
- `Program.cs` (DI registrations and options)
- `FileAgentDefinitionsProvider.cs` (IO/serialization)
- `DefaultAgentRunner.cs` (execution semantics)

If anything in this file is unclear or missing, tell me which area you'd like expanded (examples, more endpoints, or more sample agent JSON) and I will iterate.
