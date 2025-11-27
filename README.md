# Magic Agent Workflow Studio

A modular web application for designing, testing, and running AI agent workflows. The stack combines a .NET backend that orchestrates agent executions using the .NET Agent Framework with a modern React + TypeScript SPA powered by Vite, Tailwind CSS, and shadcn/ui components.

## Architecture Overview

```
+----------------------------+           +---------------------------+
|   React + Vite SPA (UI)    |<--HTTP--> | ASP.NET Core Web API      |
|  - Workflow Designer       |           |  - REST endpoints         |
|  - Run Console & Insights  |           |  - WebSocket/SignalR (*)  |
+-------------+--------------+           +-----------+---------------+
              |                                      |
              | JSON Agent Config                    | Agent Orchestration
              v                                      v
+-------------+--------------+           +-----------+---------------+
|  JSON Configuration Store  |           |  Agent Runtime Service    |
|  - Agent prompts & tools   |           |  - .NET Agent Framework   |
|  - Workflow definitions    |           |  - Execution engine       |
+-------------+--------------+           +-----------+---------------+
                                                      |
                                                      v
                                          +-----------+---------------+
                                          |  LLM / Tool Providers     |
                                          |  - OpenAI / Azure OpenAI  |
                                          |  - Custom tools & APIs    |
                                          +---------------------------+
```

> (\*) Real-time updates may be powered by SignalR once run streaming is implemented.

### Core Concepts

1. **Frontend SPA** – Presents the workflow editor, run dashboard, and configuration controls.
2. **Backend API** – Exposes endpoints for CRUD on workflows, triggering runs, streaming events, and managing configuration files.
3. **Agent Runtime** – Loads JSON-defined agent profiles, instantiates the .NET Agent Framework runtime, and manages execution lifecycles.
4. **Configuration Store** – Version-controlled JSON files describing agents, workflows, tool chains, environment variables, and runtime policies.
5. **LLM/Tool Providers** – Pluggable connectors to LLMs and external capabilities.

## Technology Stack

| Layer            | Technology Choices                                                         |
| ---------------- | -------------------------------------------------------------------------- |
| Frontend         | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Zustand (state)\*     |
| Backend API      | ASP.NET Core 8 Web API, MediatR*, FluentValidation*, Serilog/Seq\*         |
| Agent Runtime    | .NET Agent Framework (official), Polly for resilience\*, BackgroundService |
| Persistence      | Local JSON files (MVP), optional Postgres/Azure Storage roadmap            |
| Messaging        | REST + WebSockets/SignalR\*                                                |
| Tooling / DevOps | pnpm, dotnet CLI, Vitest, xUnit, Playwright*, GitHub Actions*              |

> \*Items marked with an asterisk are recommended defaults and can be refined as requirements evolve.

## Repository Layout (proposed)

```
magic-agent/
├── README.md
├── backend/
│   ├── src/
│   │   └── MagicAgent.Api/
│   │       ├── Controllers/
│   │       ├── Application/            # CQRS handlers, validators, mappings
│   │       ├── Infrastructure/         # Agent framework adapters, persistence
│   │       ├── AgentRuntime/           # Background services, runners
│   │       └── MagicAgent.Api.csproj
│   └── tests/
│       └── MagicAgent.Api.Tests/
├── frontend/
│   ├── src/
│   │   ├── app/                        # routing, layout, providers
│   │   ├── features/
│   │   ├── components/
│   │   ├── lib/                        # utilities, API clients
│   │   └── types/
│   ├── public/
│   └── package.json
├── configs/
│   └── agents/                         # JSON agent/workflow definitions
└── docs/
    └── architecture/                   # Extended design notes, diagrams
```

## Agent Configuration JSON

Agent behavior is driven by JSON definitions persisted under `configs/agents`. A single file can encapsulate one workflow or a suite of related scenarios.

```jsonc
{
  "agent": {
    "name": "code-reviewer",
    "llm": {
      "provider": "azure-openai",
      "model": "gpt-4o",
      "apiKeySecret": "AZURE_OPENAI_KEY",
      "endpoint": "https://api.openai.azure.com/..."
    },
    "systemPrompt": "You are a helpful code reviewer...",
    "tools": [
      {
        "type": "http",
        "name": "issue-tracker",
        "baseUrl": "https://jira.example.com"
      }
    ]
  },
  "workflow": {
    "steps": [
      {
        "id": "ingest-pr",
        "type": "input",
        "description": "Load pull request diff"
      },
      { "id": "analyze", "type": "agent-step", "agent": "code-reviewer" },
      { "id": "summarize", "type": "agent-step", "agent": "summarizer" }
    ],
    "outputs": [{ "id": "report", "type": "markdown" }]
  },
  "runtime": {
    "maxIterations": 8,
    "timeoutSeconds": 120,
    "retryPolicy": { "maxRetries": 2 }
  }
}
```

### Configuration Conventions

- **Secrets**: Reference environment variables or secure vault keys; never store plain tokens.
- **Validation**: Backend validates JSON against schemas before enabling a workflow.
- **Versioning**: Treat configuration files as code—use PR reviews for changes.

### Configuring MCP Tools

The agent runtime can connect to [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers declared in each agent definition. Tools are resolved at run time and surfaced to the AI agent so it can call remote capabilities.

```jsonc
{
  "agents": [
    {
      "id": "docs-assistant",
      "name": "Docs Assistant",
      "description": "Answers questions using internal documentation.",
      "defaultParameters": {
        "endpoint": "https://my-azure-openai-host.openai.azure.com/",
        "deployment": "gpt-4o"
      },
      "steps": [
        {
          "name": "chat",
          "type": "chat",
          "parameters": {
            "systemPrompt": "You are a helpful support assistant. Use tools when needed."
          },
          "conversation": { "enabled": true }
        }
      ],
      "tools": [
        {
          "id": "knowledge-base",
          "type": "mcp",
          "name": "KnowledgeBase",
          "description": "Searches the internal documentation site.",
          "serverUrl": "https://mcp.example.com/api",
          "protocol": "sse",
          "headers": {
            "Authorization": "Bearer ${INTERNAL_DOCS_TOKEN}"
          },
          "allowedTools": ["search", "get_article"],
          "actions": [
            {
              "name": "doc-search",
              "description": "Search the documentation for a topic",
              "parameters": {
                "tool": "search"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

Key properties:

| Field          | Required | Notes                                                                                                                                                                         |
| -------------- | -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | ✅       | Unique tool identifier used in logs.                                                                                                                                          |
| `type`         | ✅       | Use `mcp` (or `mcp-http`) for HTTP/SSE hosted MCP servers.                                                                                                                    |
| `serverUrl`    | ✅       | Base URL for the MCP server endpoint. Must be HTTP/HTTPS.                                                                                                                     |
| `protocol`     | ➖       | `auto` (default), `http`/`streamable-http`, or `sse`.                                                                                                                         |
| `headers`      | ➖       | Key/value pairs forwarded on every MCP request (authenticate with bearer/API keys here).                                                                                      |
| `allowedTools` | ➖       | Whitelist of remote tool names returned by the MCP server. Filters out any other tools.                                                                                       |
| `actions`      | ➖       | Optional local aliases that customize tool `name`/`description` or map to different MCP tool IDs via the `parameters.tool` property. Useful for renaming tools for the model. |

At runtime, the backend instantiates an MCP `HttpClientTransport`, completes the server handshake, and loads available MCP tools. The selected or aliased tools are then passed to the .NET Agent Framework as `AITool` instances. The frontend Agent Runner lists the configured MCP tools so you can verify connectivity options before running a conversation.

#### Security Recommendations

- Store tokens referenced by `headers` in environment variables (e.g., `${INTERNAL_DOCS_TOKEN}`) and resolve them via your secrets provider.
- Favor HTTPS endpoints; avoid exposing internal MCP servers publicly.
- Use `allowedTools` to prevent agents from calling experimental or destructive remote tools.
- Monitor MCP server logs for troubleshooting and auditing tool usage.

## Development Environment Setup

### Prerequisites

- Node.js ≥ 20.x and pnpm 9.x (`corepack enable` recommended)
- .NET SDK 8.0
- Optional: Docker Desktop (for future containerized services)
- Recommended IDEs: VS Code with C# Dev Kit and Tailwind IntelliSense

### Clone & Bootstrap

```bash
pnpm install --dir frontend
pnpm dlx shadcn-ui@latest init --dir frontend  # one-time component registry setup

dotnet restore backend/src/MagicAgent.Api/MagicAgent.Api.csproj
```

### Environment Variables

Create `backend/src/MagicAgent.Api/appsettings.Development.json` (or use Secret Manager):

```jsonc
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft": "Warning"
    }
  },
  "AgentRuntime": {
    "ConfigsPath": "../../../../configs/agents"
  },
  "LLM": {
    "Providers": {
      "AzureOpenAi": {
        "Endpoint": "https://api.openai.azure.com/...",
        "ApiKey": "${AZURE_OPENAI_KEY}",
        "Deployment": "gpt-4o"
      }
    }
  }
}
```

For the frontend, add `.env.local` under `frontend/`:

```
VITE_API_BASE_URL=https://localhost:5001
```

## Running the Stack (Development)

1. **Backend**
   ```bash
   dotnet watch run --project backend/src/MagicAgent.Api/MagicAgent.Api.csproj
   ```
2. **Frontend**
   ```bash
   pnpm --dir frontend dev
   ```

The SPA will proxy API calls to `VITE_API_BASE_URL`. Configure CORS in the backend for the dev origin (`http://localhost:5173`).

## Testing & Quality Gates

- **Backend**: xUnit + FluentAssertions + WebApplicationFactory for integration tests. `dotnet test backend/tests/MagicAgent.Api.Tests`.
- **Frontend**: Vitest + Testing Library + MSW for API mocking. `pnpm --dir frontend test`.
- **E2E**: Playwright (planned) to validate workflow execution end-to-end.
- **Static Analysis**: ESLint, Stylelint, TypeScript strict mode, and `dotnet format`/Roslyn analyzers.

## Deployment Strategy (Roadmap)

| Environment | Deployment Target                    | Notes                                  |
| ----------- | ------------------------------------ | -------------------------------------- |
| Dev         | Local containers / GitHub Codespaces | Rapid iteration, hot reload            |
| Staging     | Azure App Service + Static Web Apps  | Automated CI/CD with integration tests |
| Production  | Azure App Service / Kubernetes       | Observability via Application Insights |

Artifacts: docker images for backend, static build for frontend (`pnpm build`).

---

This README captures the target architecture and conventions guiding future code generation and implementation tasks.
