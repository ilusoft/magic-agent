# Global LLM profiles & tool pool — plan

> **Status:** planning — awaiting review before implementation.
> **Scope:** hoist **LLM profiles** and **tool definitions** out of the per-workflow `AgentDefinition` and into global, reusable collections at the document root. Agent steps keep referencing them by id. Fix the broken `openai-compatible` provider path at the same time. Touches the `.NET backend`, the `Python backend`, the `frontend`, and the canonical `configs/agents/agents.json`.

This plan supersedes `docs/architecture/per-step-llm-refactor.md`. The earlier "per-step LLM refactor" draft is the predecessor design; the user feedback after that draft was to push profiles and tools one level higher.

---

## 1. Goals & non-goals

### Goals

1. **A single workflow can mix LLMs** — e.g. one step on Azure OpenAI, another on a local Qwen via an OpenAI-compatible endpoint.
2. **LLM configs are defined once and shared.** A new agent that wants the same Qwen endpoint points at the existing profile; no copy/paste of `baseUrl` / `apiKey` / `model`.
3. **Tool configs are defined once and shared.** A new agent that wants `tavily-mcp` reuses the existing tool definition; no copy/paste of `serverUrl` / `headers` / `allowedTools`.
4. **The runtime supports both declared providers** (`azure-openai` and `openai-compatible`) end-to-end. Today only `azure-openai` works because `AgentStepFactory` is hardcoded to `AzureOpenAIClient`.
5. **The diagnostics panel starts showing real data.** The frontend already has `LLMCallConfig` on `AgentStepExecutionResult` and `renderLLMConfig` in `WorkflowExecutionPanel.tsx`; the backend just needs to populate it.
6. **Per-section API surface.** A new tool page shouldn't have to PUT the entire `agents.json` document to add a tool. The API exposes three sections with independent GET/PUT.

### Non-goals (explicitly out of scope)

- New LLM providers (Anthropic, Bedrock, etc.).
- New step types.
- Per-step instance overrides on tools (if you need a different MCP config, you create a new global tool id). Inline overrides are supported for **LLM profiles** but not for tools.
- Touching the workflow canvas / view layout — those keys survive the migration unchanged.
- Streaming protocol changes. The SSE event payload already carries the step result, so adding `llmConfig` to it Just Works.
- Concurrent-editing safety across sections. The file is loaded/saved atomically per request; if two users edit different sections simultaneously, last write wins. A follow-up can introduce a section-scoped lock or a CRDT if needed.

---

## 2. New JSON shape

### Document — three top-level sections

```jsonc
{
  "llmProfiles": {
    "qwen-local": { "provider": "openai-compatible", "baseUrl": "...", "model": "...", "apiKey": "..." },
    "azure-gpt5": { "provider": "azure-openai", "endpoint": "...", "deployment": "...", "apiVersion": "..." }
  },
  "tools": {
    "tavily-mcp": { "type": "mcp", "serverUrl": "...", "protocol": "auto", "headers": {...}, "allowedTools": [...] }
  },
  "agents": [
    {
      "id": "web-search-tavily-qwen-local",
      "name": "Web Search Agent - Tavily MCP + Qwen Local LLM",
      "defaultParameters": { "temperature": "1" },
      "steps": [
        {
          "name": "web-search-agent",
          "type": "agent",
          "parameters": { "systemPrompt": "...", "message": "{{var.userQuestion}}" },
          "llmConfig": { "profileId": "qwen-local" },
          "tools": ["tavily-mcp"],
          "conversation": { "enabled": true },
          "outcomes": [ ... ]
        }
      ],
      "viewLayout": { ... },
      "streaming": { "enabled": true, "mode": "sse" }
    }
  ]
}
```

`llmProfiles` and `tools` are both keyed by id. The same `id` cannot appear in both maps (sanity check on save).

### `AgentLlmProfileDefinition` (new)

| Field         | Type    | Required for provider | Notes                                                                                                             |
| ------------- | ------- | --------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `provider`    | string  | always                | `"azure-openai"` or `"openai-compatible"`                                                                         |
| `endpoint`    | string? | `azure-openai`        | Azure OpenAI resource endpoint                                                                                    |
| `deployment`  | string? | `azure-openai`        | Azure OpenAI deployment name                                                                                      |
| `apiVersion`  | string? | `azure-openai`        | Azure OpenAI API version (e.g. `2024-12-01-preview`)                                                              |
| `baseUrl`     | string? | `openai-compatible`   | OpenAI-compatible base URL (e.g. `http://127.0.0.1:8000/v1`)                                                      |
| `model`       | string? | `openai-compatible`   | Model name sent in the chat request                                                                               |
| `apiKey`      | string? | always                | API key. May be a literal value or a `{ENV_VAR}` placeholder (replaced by `AgentDefinitionConfigurationResolver`) |
| `headers`     | object? | `openai-compatible`   | Extra HTTP headers (non-bearer auth)                                                                              |
| `temperature` | number? | optional              | Default sampling temperature                                                                                      |
| `maxTokens`   | number? | optional              | Default max tokens                                                                                                |

### `AgentToolDefinition` (already exists, moves to the document root)

The shape is unchanged from the current `AgentToolDefinition` (`backend/src/MagicAgent.Api/Application/AgentRunner/AgentOrchestrationOptions.cs:219`). It already supports `mcp` / `mcp-http` types and exposes the right fields (`serverUrl`, `protocol`, `headers`, `allowedTools`, `actions`, `forwardAuthorizationHeader`, `stopOnToolInitError`). The only change is that it now lives at the document root under `tools` and the agent's `tools` array is removed.

### `AgentDefinition` — LLM keys and tool array removed

```jsonc
{
  "id": "...",
  "name": "...",
  "description": "...",
  "defaultParameters": { "temperature": "1" },
  "steps": [ ... ],
  "viewLayout": { ... },
  "streaming": { ... }
  // LLM keys gone. tools[] gone.
}
```

**Removed from `AgentDefinition`:** `endpoint`, `deployment`, `apiKey`, `apiVersion`, `baseUrl`, `model`, `provider`, `tools`.

**Reused on `AgentDefinition`:** `defaultParameters` stays. It is _only_ the placeholder substitution bag for step `parameters` (e.g. `{{param.temperature}}`); it is **not** an LLM config surface.

### `AgentStepDefinition` — gains `llmConfig`; legacy fields removed

```jsonc
{
  "name": "web-search-agent",
  "type": "agent",
  "parameters": { "systemPrompt": "...", "message": "..." },
  "variableTypes": {},
  "conversation": { "enabled": true },
  "tools": ["tavily-mcp"],        // ← references global tool ids (unchanged mechanism)
  "outcomes": [ ... ],
  "isStartStep": false,
  "llmConfig": { "profileId": "qwen-local" }
}
```

**New on `AgentStepDefinition`:** `llmConfig?: AgentStepLlmConfig`. Reference shape unchanged from the previous plan: either a `profileId` reference, an inline override, or a profile + inline combo.

**Removed from `AgentStepDefinition`:** `provider`, `options` (always `{}` in the real file; unused). `inputSource` is kept.

### `AgentStepLlmConfig` (new) — profile reference, inline, or both

```jsonc
// A — reference a profile defined on the document
{ "profileId": "qwen-local" }

// B — inline (no profile)
{
  "provider": "openai-compatible",
  "baseUrl": "http://127.0.0.1:8000/v1",
  "model": "Qwen3.6-35B-A3B-OptiQ-4bit"
}

// C — reference a profile, then override one field on top
{ "profileId": "azure-gpt5", "temperature": 0.2 }
```

**Resolution order (per step, at runtime):**

1. If `profileId` is set, look up `document.llmProfiles[profileId]`. If missing → runtime error (`StepChatClientResolver` throws a typed `LlmProfileNotFoundException` that the runner surfaces in the diagnostic result).
2. Any inline field on `llmConfig` overrides the corresponding profile field (deep merge, last write wins).
3. If the step has no `llmConfig` and the document has no profile referenced, the chat client factory falls back to `AZURE_OPENAI_*` env vars (current behaviour preserved for `appsettings.json`-driven development).
4. `provider` is mandatory after resolution. Without it the step is invalid.

### Diagnostics: `AgentStepExecutionResult.llmConfig` (new backend field)

Already defined on the frontend at `frontend/src/types/agents.ts:126` as `LLMCallConfig`. The backend populates it on every `type=agent` step:

```json
{
  "provider": "openai-compatible",
  "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
  "endpoint": null,
  "baseUrl": "http://127.0.0.1:8000/v1",
  "deployment": null,
  "apiVersion": null,
  "temperature": 1,
  "maxTokens": null,
  "apiKeyFingerprint": "***2S"
}
```

`apiKeyFingerprint` is the last 4 characters of the resolved key, prefixed with `***` (matches `backend-py/src/application/agents/run_result.py:37`).

---

## 3. New C# types (`MagicAgent.Api`)

All live next to the existing ones in `backend/src/MagicAgent.Api/Application/AgentRunner/AgentOrchestrationOptions.cs`.

```csharp
public sealed class AgentDefinitionsDocument
{
    public IDictionary<string, AgentLlmProfileDefinition> LlmProfiles { get; init; }
        = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase);
    public IDictionary<string, AgentToolDefinition> Tools { get; init; }
        = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase);
    public IList<AgentDefinition> Agents { get; init; } = [];
}

public sealed class AgentLlmProfileDefinition
{
    public string Provider { get; init; } = "azure-openai"; // "azure-openai" | "openai-compatible"
    public string? Endpoint { get; init; }
    public string? Deployment { get; init; }
    public string? ApiVersion { get; init; }
    public string? BaseUrl { get; init; }
    public string? Model { get; init; }
    public string? ApiKey { get; init; }
    public IDictionary<string, string> Headers { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public double? Temperature { get; init; }
    public int? MaxTokens { get; init; }
}

public sealed class AgentStepLlmConfig
{
    public string? ProfileId { get; init; }
    public string? Provider { get; init; }
    public string? Endpoint { get; init; }
    public string? Deployment { get; init; }
    public string? ApiVersion { get; init; }
    public string? BaseUrl { get; init; }
    public string? Model { get; init; }
    public string? ApiKey { get; init; }
    public IDictionary<string, string> Headers { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public double? Temperature { get; init; }
    public int? MaxTokens { get; init; }
}

public sealed record LLMCallConfig(
    string Provider,
    string? Model,
    string? Endpoint,
    string? BaseUrl,
    string? Deployment,
    string? ApiVersion,
    double? Temperature,
    int? MaxTokens,
    string? ApiKeyFingerprint);
```

`AgentDefinition` simplifies (the `tools` array and the LLM keys are gone):

```csharp
public sealed class AgentDefinition
{
    public required string Id { get; init; }
    public string Name { get; init; } = "";
    public string? Description { get; init; }
    public IDictionary<string, string> DefaultParameters { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public IList<AgentStepDefinition> Steps { get; init; } = [];
    public AgentViewLayout? ViewLayout { get; init; }
    public AgentStreamingOptions? Streaming { get; init; }
}
```

`AgentStepDefinition` gains `LlmConfig`; drops `Provider` and `Options`. `InputSource` stays.

```csharp
public sealed class AgentStepDefinition
{
    public required string Name { get; init; }
    public required string Type { get; init; }
    public IDictionary<string, string> Parameters { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public IDictionary<string, WorkflowVariableDataType> VariableTypes { get; init; } = new(StringComparer.OrdinalIgnoreCase);
    public AgentStepLlmConfig? LlmConfig { get; init; }
    public AgentStepConversationOptions? Conversation { get; init; }
    public IList<string> Tools { get; init; } = [];            // references to document.tools ids
    public bool StopOnToolError { get; init; }
    public string InputSource { get; init; } = "usePrevious";
    public IList<AgentStepOutcomeDefinition> Outcomes { get; init; } = [];
    public bool IsStartStep { get; set; }
}
```

`AgentStepExecutionResult` gains `LlmConfig`:

```csharp
public sealed record AgentStepExecutionResult(string Name, string Type, string Output)
{
    // ... existing fields ...
    public LLMCallConfig? LlmConfig { get; init; }
}
```

`AgentToolDefinition` is unchanged.

---

## 4. New Pydantic types (`backend-py`)

Mirror in `backend-py/src/application/agents/schemas.py`:

```python
class LLMProfileDefinition(BaseModel):
    provider: str
    endpoint: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    headers: dict[str, str] | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class StepLlmConfig(BaseModel):
    profile_id: str | None = None
    provider: str | None = None
    endpoint: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    headers: dict[str, str] | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class AgentDefinitionsDocument(BaseModel):
    llm_profiles: dict[str, LLMProfileDefinition] = Field(default_factory=dict)
    tools: dict[str, ToolDefinition] = Field(default_factory=dict)
    agents: list[AgentDefinition] = Field(default_factory=list)
```

The old `LLMConfig` (single, on agent) is removed. `AgentStepDefinition` gains `llm_config: StepLlmConfig | None`.

---

## 5. Runtime changes

### 5.1 Chat client factories (.NET)

Replace the monolithic `AgentStepFactory` (`backend/src/MagicAgent.Api/Application/AgentRunner/AgentStepFactory.cs`) with:

```
StepChatClientResolver (new)
├── IChatClientFactory (new interface)
│   ├── AzureOpenAiChatClientFactory
│   └── OpenAiCompatibleChatClientFactory
```

`StepChatClientResolver.Resolve(AgentDefinitionsDocument document, AgentDefinition workflow, AgentStepDefinition step)`:

1. If `step.LlmConfig?.ProfileId` is set, look up `document.LlmProfiles[profileId]`. Missing → throw `LlmProfileNotFoundException(profileId, step.Name)`.
2. Merge any inline fields from `step.LlmConfig` over the resolved profile.
3. If neither a profile nor inline is set, build a profile from `AZURE_OPENAI_*` env vars.
4. Validate the resolved profile: required fields per provider are present.
5. Pick the right `IChatClientFactory` by `provider`.
6. Return `(IChatClient, LLMCallConfig)` — the `LLMCallConfig` carries the resolved values with `apiKey` fingerprinted.

**Provider dispatch:**

| `provider`          | SDK call                                                                                                                                                        |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `azure-openai`      | `new AzureOpenAIClient(endpoint, new AzureKeyCredential(apiKey)).GetChatClient(deployment).AsIChatClient()`                                                     |
| `openai-compatible` | `new OpenAIClient(new ApiKeyCredential(apiKey), new OpenAIClientOptions { Endpoint = baseUrl, DefaultHeaders = headers }).GetChatClient(model).AsIChatClient()` |

`temperature` and `maxTokens` are applied via `ChatOptions` passed to `agent.RunAsync` inside `DefaultAgentRunner.ExecuteAgentStepAsync`.

### 5.2 Tool resolution (.NET)

`AgentToolBuilder` (`backend/src/MagicAgent.Api/Application/AgentRunner/AgentToolBuilder.cs`) currently takes an `AgentDefinition` and iterates its `Tools` list. The new signature:

```csharp
internal async Task<AgentToolContext> BuildAsync(
    AgentDefinitionsDocument document,
    AgentDefinition workflow,
    IReadOnlyDictionary<string, string>? requestHeaders,
    CancellationToken cancellationToken)
```

It now:

1. Collects the union of `step.Tools` across all steps in the workflow (deduplicated, preserves order).
2. For each tool id, looks up `document.Tools[toolId]`. If missing → log warning, skip.
3. Builds MCP clients as before using the resolved tool config.
4. Returns the same `AgentToolContext` shape; per-step tool filtering (`step.Tools`) is unchanged downstream.

This means an agent only pays the cost of initializing the tools its steps actually reference, not the full global pool. Lazy loading is a follow-up.

### 5.3 `DefaultAgentRunner` changes

- Remove the agent-level LLM field injection into the per-step `parameters` dict (lines 60-73 of `DefaultAgentRunner.cs`).
- For each `type=agent` step, call `StepChatClientResolver.Resolve(document, workflow, step)` and pass the resulting `IChatClient` to `agent.RunAsync`.
- Emit the resolved `LLMCallConfig` on `AgentStepExecutionResult` for `type=agent` steps. `echo` / `setVariables` / `resetConversation` get `null`.
- Tool resolution: call the new `AgentToolBuilder.BuildAsync(document, workflow, ...)`.

### 5.4 Python runtime changes

- `backend-py/src/infrastructure/llm/factory.py`: already dispatches by `provider`. Verify `openai-compatible` end-to-end and add `headers` support if missing.
- `backend-py/src/agent_runtime/executor.py`: built per-step now (the workflow executor resolves per-step LLM config and builds the graph for each agent step). The current per-run graph caching goes away; the OpenAI SDK is cheap to construct.
- `backend-py/src/application/agents/run_result.py`: `LLMCallConfig` gains `temperature` and `max_tokens`.

### 5.5 Configuration placeholders

`AgentDefinitionConfigurationResolver` recurses into every string in the document, so the migration's `{AZURE_OPENAI_KEY}` placeholder inside a profile's `apiKey` field is still resolved at load time. No change.

### 5.6 Validation

A new `AgentDefinitionsDocumentValidator` runs at load time (`FileAgentDefinitionsProvider.GetDefinitionsAsync`) and on every PUT. It checks:

- Every `step.llmConfig.profileId` resolves to a key in `document.llmProfiles`.
- Every `step.tools[i]` resolves to a key in `document.tools`.
- Every profile has the required fields for its declared `provider`.
- No two profiles share a key. No two tools share a key. (Trivially true for `IDictionary`, but the validator covers inline JSON parses too.)
- Every workflow has exactly one `isStartStep: true` (existing rule, kept).

Failures throw a typed `AgentDefinitionsValidationException` that the controller turns into a 422 response with a structured payload listing every issue (so the UI can show all errors at once, not one at a time).

---

## 6. API surface

### New per-section endpoints

The existing `GET/PUT /api/agents/definitions` (whole document) is **kept** as a convenience (and used by the migration tool), and three new per-section endpoints are added:

| Verb | Path                                    | Returns                                     |
| ---- | --------------------------------------- | ------------------------------------------- |
| GET  | `/api/agent-definitions/llm-profiles`   | `Record<string, AgentLlmProfileDefinition>` |
| PUT  | `/api/agent-definitions/llm-profiles`   | `Record<string, AgentLlmProfileDefinition>` |
| GET  | `/api/agent-definitions/tools`          | `Record<string, AgentToolDefinition>`       |
| PUT  | `/api/agent-definitions/tools`          | `Record<string, AgentToolDefinition>`       |
| GET  | `/api/agent-definitions/agents`         | `AgentDefinition[]`                         |
| PUT  | `/api/agent-definitions/agents`         | `AgentDefinition[]`                         |
| GET  | `/api/agent-definitions`                | full `AgentDefinitionsDocument`             |
| PUT  | `/api/agent-definitions`                | full `AgentDefinitionsDocument`             |
| GET  | `/api/agents/{agentId}/runs`            | unchanged (run endpoint)                    |
| GET  | `/api/agents/{agentId}/runs/{id}/debug` | unchanged                                   |

The per-section endpoints read the whole file, replace the section in memory, and write the file back. The validator runs on every write.

The new per-section endpoints live in three controllers (`LlmProfilesController`, `ToolsController`, `AgentsController`) under `backend/src/MagicAgent.Api/Controllers/`. The existing `AgentDefinitionsController` is renamed/repurposed to handle the whole-document `GET/PUT`.

### Tool/profile cascade-delete protection

PUT on `/api/agent-definitions/tools` accepts a body with profiles _removed_. If a removed tool id is still referenced by any step in any agent, the PUT is rejected with **409 Conflict** and a payload like:

```json
{
  "message": "Cannot remove tool 'tavily-mcp': still referenced by 1 step(s).",
  "referencingSteps": [
    {
      "agentId": "web-search-tavily-qwen-local",
      "stepName": "web-search-agent"
    }
  ]
}
```

Same behavior for `/api/agent-definitions/llm-profiles`. The UI uses this to surface "X is in use by Y" before letting the user force-delete (or, more typically, guiding them to update the steps first).

---

## 7. Frontend changes

### 7.1 Types (`frontend/src/types/agents.ts`)

- Add `AgentLlmProfileDefinition` interface.
- Add `AgentStepLlmConfig` interface.
- `AgentDefinitionsDocument` becomes `{ llmProfiles, tools, agents }`.
- `AgentDefinition` drops `endpoint`, `deployment`, `apiKey`, `apiVersion`, `baseUrl`, `model`, `provider`, `tools`.
- `AgentStepDefinition` gains `llmConfig?`; drops `provider` and `options`. `inputSource` stays. `tools: string[]` (global tool id references) stays.
- `LLMCallConfig` stays as-is.

### 7.2 Navigation

Top-level nav gets three items instead of one (today only "Agent Definitions" exists):

```
┌─ LLM Profiles    (new)
├─ Tools           (new)
└─ Workflows       (renamed from "Agent Definitions"; the same component, scoped to the agents section)
```

Implemented in `frontend/src/views/`. New `LlmProfilesView.tsx` and `ToolsView.tsx`; `AgentDefinitionsView.tsx` stays but its title becomes "Workflows" and it loads only the `agents` section.

### 7.3 `LlmProfilesView` (new)

- Lists all profiles as cards. Each card has inline-editable fields:
  - Profile id (the map key; editable — rename triggers a "profile X has been renamed; N steps updated" toast)
  - Provider (radio: `azure-openai` | `openai-compatible`)
  - Endpoint / baseUrl (toggled by provider)
  - Deployment / model (toggled by provider)
  - ApiKey (with show/hide toggle)
  - ApiVersion (azure-openai only)
  - Headers (key-value editor, openai-compatible only)
  - Temperature / maxTokens (both)
- Add / rename / delete buttons. Delete triggers the cascade-delete check from §6 — if the profile is in use, the user sees a list of referencing steps and is guided to update them first.
- Form state lives in a new `useLlmProfilesManager` hook.

### 7.4 `ToolsView` (new)

- Same pattern as `LlmProfilesView` but for `AgentToolDefinition`.
- Renders a card per tool id. Each card shows:
  - Id, type, name, description
  - serverUrl, protocol
  - headers (key-value editor)
  - allowedTools (multi-select; sourced from a fresh MCP probe — see below)
  - actions (list editor — one per remote tool alias)
  - forwardAuthorizationHeader toggle + authorizationHeaderName input
  - stopOnToolInitError toggle
- A "Probe server" button hits a new backend endpoint `POST /api/agent-definitions/tools/{id}/probe` that returns the MCP server's available tools so the user can pick from them when configuring `allowedTools` and `actions`. (This already exists implicitly in `AgentToolBuilder.BuildMcpToolsAsync`; we just need to expose it as a probe endpoint.)
- Delete triggers the cascade-delete check, same as profiles.

### 7.5 Workflow view — step dialog LLM section

`AgentStepDialog` (and the `StandardStepDialog` it wraps) gets a new `LlmConfigSection`:

- Radio: **Use profile** | **Inline override** | **Inherit (env vars)**
- **Use profile:** dropdown of `Object.keys(document.llmProfiles)`.
- **Inline override:** reveals provider + all override fields (subset of profile fields, collapsible "advanced" section for headers/temperature/maxTokens).
- **Inherit:** `step.llmConfig` is `undefined` and the runtime falls back to env vars.

The section is **only shown** for `type === "agent"` steps. For `echo` / `setVariables` / `resetConversation` it's hidden and `llmConfig` is forced to `undefined` on save.

### 7.6 Workflow view — step dialog Tools section

Today the step dialog shows a checkbox list of `availableTools` (currently sourced from `agent.tools`). The new behavior:

- The checkbox list is sourced from the **document-level** `document.tools` (i.e. the global pool).
- An optional agent-level "Available tools" filter could narrow the list shown (not in this PR; the global pool is the source of truth).
- The labels come from the global tool's `name` field, not from a per-agent override.

### 7.7 Hooks

- `frontend/src/components/agent-definitions/hooks/useStepForm.ts`: extend `StepFormState` with `llmConfigMode: "profile" | "inline" | "inherit"`, `llmConfigProfileId`, and the inline override fields.
- `frontend/src/components/agent-definitions/hooks/useStepPersistence.ts`: serialize the new `llmConfig` back into `AgentStepDefinition`. Clear it for non-agent step types.
- `frontend/src/components/agent-definitions/hooks/useStepDialogOpeners.ts`: when opening a step for edit, populate the new fields from the existing `step.llmConfig` (or default to `inherit`).
- `frontend/src/components/agent-definitions/hooks/useWorkflowSelection.ts`: drop the LLM fields from the workflow form entirely. The workflow dialog no longer has Endpoint / Deployment / API Key / API Version inputs.
- `frontend/src/components/agent-definitions/hooks/useToolDialog.ts`: adapt to the new global tools model (the dialog edits a tool in `document.tools`, not `agent.tools`).
- `frontend/src/components/agent-definitions/hooks/__tests__/workflowHooks.test.ts`: update existing assertions for the dropped workflow-level LLM fields; add tests for the new LLM profile add/edit/remove/rename, the cascade-delete error path, and the step dialog LLM section's three modes.

### 7.8 Per-section API hooks

New `useLlmProfilesApi`, `useToolsApi`, `useAgentsApi` hooks (each thin wrapper around fetch + the new endpoints). The existing `useAgentDefinitionsDocument` hook is split so the three views can subscribe to the section they care about — but a single in-memory copy of the document is still the source of truth (cross-section updates stay consistent).

---

## 8. Migration strategy

### One-shot, no backwards-compat loader

The migration is a one-shot operation. The loader rejects the old shape and the migration tool is the only thing that knows both shapes.

### Script: `tools/AgentsMigrator/` (new .NET 8 console)

Why .NET: the migration is a pure data transformation between two C# types. Reusing the existing JSON contracts means the script can never produce invalid output.

```
tools/AgentsMigrator/
├── AgentsMigrator.csproj
└── Program.cs
```

**Behavior:**

1. CLI: `dotnet run --project tools/AgentsMigrator -- <path-to-agents.json> [--dry-run]`.
2. Read the file as the _old_ shape (define the legacy types in `LegacyModels.cs` inside the migrator project — do not modify the production types).
3. Build the new top-level `llmProfiles` map:
   - For each agent, collect its LLM keys (top-level + from `defaultParameters`):
     - `endpoint`, `deployment`, `apiKey`, `apiVersion`, `baseUrl`, `model`, `provider`.
   - For each distinct LLM config (deep-equal), emit one profile id. Use `<agent.id>-default` for the first occurrence; subsequent matches reuse the same id.
   - **Move `temperature` / `maxTokens` from `defaultParameters` into the profile** (if present in the workflow). This makes the chat client factory actually apply them — today they're only used as placeholder values.
4. Build the new top-level `tools` map:
   - For each agent, collect its `tools[]` entries (the full `AgentToolDefinition` payloads).
   - For each distinct tool config (deep-equal), emit one tool id. Use the original tool id; subsequent matches reuse it.
5. Rewrite each agent:
   - Drop the LLM keys (top-level + from `defaultParameters`).
   - Drop the `tools[]` array.
   - For each step: set `llmConfig: { profileId: <resolved-id> }`. Drop the legacy `provider` and `options` fields. Keep `tools: ["tavily-mcp", ...]` (the references stay — they now resolve against the global pool).
6. Validate the produced document against `AgentDefinitionsDocumentValidator` and fail loudly on any issue.
7. Write the new file in place.
8. Write `agents.json.bak` next to the original (only if the original content differs).
9. Print a summary:

```
[ok] added profile 'qwen-local' (provider=openai-compatible, model=Qwen3.6-35B-A3B-OptiQ-4bit)
[ok] added profile 'azure-gpt5' (provider=azure-openai, deployment=gpt-5-mini)
[ok] added tool 'tavily-mcp' (type=mcp, serverUrl=https://mcp.tavily.com/...)
[ok] rewired 4 step(s) in 'multi-language-translator-qwen-local' to profile 'qwen-local'
[ok] rewired 1 step(s) in 'web-search-tavily-qwen-local' to profile 'qwen-local'
[ok] rewired 1 step(s) in 'multi-language-translator-azopenai' to profile 'azure-gpt5'
[ok] rewired 1 step(s) in 'web-search-tavily-qwen-local' to tool 'tavily-mcp'
[ok] dropped 9 legacy key(s)
[ok] wrote configs/agents/agents.json
[ok] wrote configs/agents/agents.json.bak
```

**Idempotency:** running the script on the already-migrated file is a no-op (the new shape is detected by the presence of top-level `llmProfiles` / `tools`).

**Dry run:** `--dry-run` prints the diff (using `System.Text.Json`'s node-by-node compare) without writing.

### Expected output for the current `configs/agents/agents.json`

After migration, the document has two LLM profiles and one tool:

```json
{
  "llmProfiles": {
    "qwen-local": {
      "provider": "openai-compatible",
      "baseUrl": "http://127.0.0.1:8000/v1",
      "model": "Qwen3.6-35B-A3B-OptiQ-4bit",
      "apiKey": "C2BI6MWzkBS2zvvarw2S",
      "temperature": 1
    },
    "azure-gpt5": {
      "provider": "azure-openai",
      "endpoint": "https://jorge-mafrq1ph-eastus2.cognitiveservices.azure.com/",
      "deployment": "gpt-5-mini",
      "apiVersion": "2024-12-01-preview",
      "temperature": 1
    }
  },
  "tools": {
    "tavily-mcp": {
      "type": "mcp",
      "name": "TavilyWebSearch",
      "description": "...",
      "serverUrl": "https://mcp.tavily.com/mcp/?tavilyApiKey=...",
      "protocol": "auto",
      "allowedTools": ["tavily_search", "tavily_extract"],
      "actions": [ ... ],
      "forwardAuthorizationHeader": false,
      "stopOnToolInitError": false
    }
  },
  "agents": [
    { "id": "multi-language-translator-qwen-local", "defaultParameters": {}, "steps": [ { ..., "llmConfig": { "profileId": "qwen-local" } } ], ... },
    { "id": "web-search-tavily-qwen-local",       "defaultParameters": {}, "steps": [ { ..., "llmConfig": { "profileId": "qwen-local" }, "tools": ["tavily-mcp"] } ], ... },
    { "id": "multi-language-translator-azopenai",  "defaultParameters": {}, "steps": [ { ..., "llmConfig": { "profileId": "azure-gpt5" } } ], ... }
  ]
}
```

### Loader change (no backwards-compat)

After the migration ships, the loader will simply deserialize the new shape. Any agent definitions JSON that's still in the old shape will fail to load with a clear error message:

> `Agent definitions document is missing 'llmProfiles' / 'tools' top-level keys. Run tools/AgentsMigrator to upgrade configs/agents/agents.json.`

This is enforced via a startup check in `FileAgentDefinitionsProvider` that returns a typed `MigrationRequiredException` (new) which the controller turns into a `426 Upgrade Required` response.

---

## 9. Test plan

### Unit (.NET, `backend/tests/MagicAgent.Api.Tests/`)

1. **`StepChatClientResolverTests`** (new):
   - `Resolves_ProfileId_To_Factory_And_Emits_LLMCallConfig`
   - `Inline_Overrides_Override_Profile_Fields`
   - `Missing_ProfileId_Throws_LlmProfileNotFoundException`
   - `Env_Var_Fallback_When_No_LlmConfig_And_No_Profiles`
   - `ApiKeyFingerprint_Strips_To_Last4`
2. **`AzureOpenAiChatClientFactoryTests`** (new, mocked SDK):
   - `Builds_ChatClient_With_Endpoint_Deployment_And_Key`
   - `Missing_Endpoint_Throws`
3. **`OpenAiCompatibleChatClientFactoryTests`** (new, mocked SDK):
   - `Builds_ChatClient_With_BaseUrl_Model_And_Key`
   - `Applies_Headers_When_Provided`
4. **`AgentToolBuilderTests`** (new):
   - `Resolves_Tool_Ids_From_Document_Pool`
   - `Missing_Tool_Id_Logs_Warning_And_Skips`
   - `Builds_MCP_Transport_From_Global_Tool_Config`
5. **`AgentDefinitionsDocumentValidatorTests`** (new):
   - `Rejects_Step_Referencing_Missing_Profile`
   - `Rejects_Step_Referencing_Missing_Tool`
   - `Rejects_Profile_Missing_Required_Provider_Fields`
   - `Accepts_Well_Formed_Document`
6. **`DefaultAgentRunnerConversionTests`** (existing): update the canned test agent to use the new shape; add a second test that runs a workflow with two different profiles across two steps.
7. **`TestApiFactory.cs`**: rewrite the canned `TestAgentDefinition` to use `document.LlmProfiles` and a per-step `LlmConfig` reference; add a global tool to the test document.
8. **`AgentDefinitionsControllerCascadeDeleteTests`** (new, integration via `WebApplicationFactory`):
   - `PutTools_Removing_Referenced_Tool_Returns_409_With_Referencing_Steps`
   - `PutLlmProfiles_Removing_Referenced_Profile_Returns_409_With_Referencing_Steps`
   - `PutTools_Removing_Unreferenced_Tool_Succeeds`

### Unit (Python, `backend-py/tests/`)

1. `test_schemas.py`: new tests for `LLMProfileDefinition` / `StepLlmConfig` / `AgentDefinitionsDocument` Pydantic parsing (round-trip, missing fields, type coercion).
2. `test_executor.py`: update fixtures to use the new document shape; the per-step chat client is built from the resolved `StepLlmConfig` × `LLMProfileDefinition`.
3. `test_factory.py`: assert `openai-compatible` builds an `OpenAI` (LangChain) chat model with `base_url`, `api_key`, and `default_headers`; assert `azure-openai` builds the Azure variant.
4. `test_run_result.py`: `LLMCallConfig.from_dict` round-trip includes `temperature` and `max_tokens`.

### Frontend

1. `frontend/src/components/agent-definitions/hooks/__tests__/workflowHooks.test.ts`: update existing assertions for the dropped workflow-level LLM fields. Add tests for:
   - `useLlmProfilesManager`: add / edit / remove / rename + cascade-delete 409 handling.
   - `useToolsManager`: same, plus the probe endpoint flow (mocked).
   - Step dialog LLM section: three modes (profile / inline / inherit) and serialization back to `step.llmConfig`.
2. Run `pnpm --dir frontend test` to confirm everything passes.

### Integration

1. `.NET`: new test in `WorkflowPipelineIntegrationTests.cs` that:
   - Defines a document with two profiles (`azure-gpt5` and `qwen-local`) and one tool (`tavily-mcp`).
   - Defines an agent with two `type=agent` steps, each referencing a different profile; one step also references `tavily-mcp`.
   - Mocks the Azure + OpenAI SDKs to capture the calls.
   - Asserts each step's chat client was built with the right `endpoint` / `baseUrl`.
   - Asserts the emitted `AgentStepExecutionResult.LlmConfig` carries the expected provider, deployment / model, and `apiKeyFingerprint`.
   - Asserts the tool builder built the MCP client from the global tool's `serverUrl`.
2. Manual smoke test against the migrated `configs/agents/agents.json`:
   - `dotnet test backend/tests/MagicAgent.Api.Tests` — all green.
   - Start the .NET backend and run all three agents via the existing UI.
   - Open the diagnostic panel and confirm the LLM card shows `provider` / `model` / `baseUrl` / `apiKeyFingerprint` for the Qwen agent.
   - Open the new "LLM Profiles" and "Tools" pages and confirm CRUD works.

---

## 10. Phasing / order of work

The work is broken into nine PRs (or nine commits). Each step leaves the tree in a working state.

| #   | Phase                                                                                                                                                                                                                                                                                                                                  | Touches                                                                                                                                                   | Reversible?      |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| 1   | **Backend types: add new, keep old.** Add `AgentLlmProfileDefinition`, `AgentStepLlmConfig`, `LLMCallConfig`, the new document shape, and `LlmProfiles` / `LlmConfig` properties. Old properties stay.                                                                                                                                 | `AgentOrchestrationOptions.cs`, `IAgentRunner.cs`                                                                                                         | Yes              |
| 2   | **Backend: chat client factories + resolver.** Implement `IChatClientFactory` with both providers, plus `StepChatClientResolver`. Wire into `Program.cs`. Keep `AgentStepFactory` as a thin shim.                                                                                                                                      | `AgentStepFactory.cs` (refactored), new files, `Program.cs`                                                                                               | Yes              |
| 3   | **Backend: tool resolution + validator.** `AgentToolBuilder` reads from the document pool. New `AgentDefinitionsDocumentValidator`. Wire into `FileAgentDefinitionsProvider`.                                                                                                                                                          | `AgentToolBuilder.cs`, new `AgentDefinitionsDocumentValidator.cs`, `FileAgentDefinitionsProvider.cs`                                                      | Yes              |
| 4   | **Backend: DefaultAgentRunner switches to per-step resolution + new tool builder.** Drop agent-level LLM injection, call resolver, emit `LlmConfig`, call new tool builder. Keep env-var fallback.                                                                                                                                     | `DefaultAgentRunner.cs`                                                                                                                                   | Yes              |
| 5   | **Backend tests updated + new.** Update `TestApiFactory`, add the new unit + integration tests.                                                                                                                                                                                                                                        | `backend/tests/**`                                                                                                                                        | Yes              |
| 6   | **Python: schemas + factory + executor + run result.** Mirror the new types and resolution. Update tests.                                                                                                                                                                                                                              | `backend-py/src/**`, `backend-py/tests/**`                                                                                                                | Yes              |
| 7   | **Backend: per-section API endpoints + cascade-delete check.** New `LlmProfilesController`, `ToolsController`, `AgentsController`.                                                                                                                                                                                                     | new `Controllers/*`                                                                                                                                       | Yes              |
| 8   | **Frontend types + LLM Profiles view + Tools view + step dialog LLM section.** Add new, keep old fields as deprecated read-only. UI works against the new shape but still tolerates the old shape so the team can flip the agent JSON at their own pace.                                                                               | `frontend/src/**` (types, views, components, hooks)                                                                                                       | Yes              |
| 9   | **Migration script + run on canonical file + drop legacy fields.** Ship `tools/AgentsMigrator`, run it on `configs/agents/agents.json`, commit the migrated file. Then remove the deprecated fields from `AgentDefinition` / `AgentStepDefinition` and add the startup `MigrationRequiredException` in `FileAgentDefinitionsProvider`. | `tools/AgentsMigrator/**`, `configs/agents/agents.json`, `*.bak`, `AgentOrchestrationOptions.cs`, frontend types/forms, `FileAgentDefinitionsProvider.cs` | No (destructive) |

> **Why phase 9 is last:** until the migration script has run on the canonical file, removing the old fields would break loads. The check in `FileAgentDefinitionsProvider` is the safety net.

---

## 11. Risks & follow-ups

### Risks

1. **Breaking change for any agent JSON the team has locally.** Mitigated by the migrator being idempotent and the `.bak` file. If a developer has uncommitted local edits to the old shape, they run the migrator themselves; the diff is reviewable in the standard git workflow.
2. **`OpenAI` SDK availability.** The `OpenAI` package (or `Azure.AI.OpenAI`'s transitive `OpenAI`) must be referenced by `MagicAgent.Api`. Will verify at phase 2; if it requires a new package reference, that's a one-line change.
3. **Per-step profile caching.** Building a chat client per step is cheap but does mean we don't share an `HttpClient` across providers in the same run. Acceptable for now; the `AgentToolBuilder` already follows the same pattern. If profiling shows it's an issue, a follow-up can introduce an `IChatClientCache`.
4. **`temperature` / `maxTokens` semantics.** Pending Q2 in §12 — recommendation is to move these into the profile during migration.
5. **Tool instance vs definition.** If two agents want the same MCP server with different `allowedTools` or `headers`, they have to define two global tools with different ids (no per-step override). The current `agents.json` has only one tool (`tavily-mcp`) used by one agent, so no collision today. We can add per-step tool instance overrides in a follow-up if the team hits this in practice.
6. **`viewLayout` casing.** Pending Q3 in §12 — recommendation is to leave the casing as-is to minimize the migration diff.
7. **Cascade-delete behavior.** Locked in: 409 + list of referencing steps. Non-destructive (no data is lost) but a "delete" can fail with a clear reason.

### Follow-ups (explicitly out of scope for this PR)

- New providers (Anthropic, Bedrock, Gemini, etc.).
- Per-step tool instance overrides (a different `allowedTools` for the same tool id).
- Per-section file lock or CRDT for concurrent editing.
- Lazy tool initialization (only build the tools a step actually uses, even within a run).
- A "Test this profile" UI affordance (single-shot chat call).
- LLM profile / tool import-export.
- A separate UI for inline `llmConfig` headers (we'll ship a generic key/value editor for now).
- Renaming `ViewLayout` → `viewLayout` in `agents.json` (casing normalization — pending Q3).

---

## 12. Decisions and open questions

### Decisions (locked in)

- **File layout:** keep a single file (`configs/agents/agents.json`) with three top-level keys (`llmProfiles`, `tools`, `agents`). **No file split.**
- **Cascade-delete behavior:** removing a profile or tool that's still referenced returns **409 Conflict** with a payload listing the referencing agents/steps. No auto-rewire, no soft-delete.
- **Migration strategy:** one-shot `tools/AgentsMigrator` script. The loader rejects the old shape from day one of phase 9 (no transitional dual-shape support).
- **Inline LLM overrides:** allowed. Steps can reference a profile and override any subset of its fields, or define the LLM config fully inline with no profile.
- **Inline tool overrides:** not allowed in this PR. If you need a different MCP config, create a new global tool id. (Can be revisited later.)
- **Concurrent editing:** out of scope. The file is read/written atomically per request. Last write wins.

### Open questions

Each question has a **recommended default**. Confirm the defaults, or pick an alternative, before phase 1 starts. If the recommended defaults are all acceptable, a single "go with the defaults" answer is enough.

#### Q1. `InputSource` on steps

The field is honored but only `usePrevious` is used in the real file.

- **(Recommended) Keep it.** No behavior change; preserves a documented knob for future use.
- Drop it. Smaller schema, but the only "input source" mechanism goes away.

#### Q2. `temperature` / `maxTokens` semantics

Today `defaultParameters.temperature` is _only_ a placeholder substitution value — the chat client factory doesn't read it, so `temperature: "1"` on the Qwen workflow is currently never sent to the model.

- **(Recommended) Move it into the profile during migration.** After this, the chat client factory honors it. **Behavior change:** the Qwen workflow will start sending `temperature=1` to Qwen, where today it doesn't.
- Leave it in `defaultParameters` only. The factory still doesn't read it; temperature is purely a placeholder value. No behavior change, but the profile is "incomplete" relative to what the SDK supports, and the team has to manually move it later.

#### Q3. `viewLayout` casing

The current file has `ViewLayout` (PascalCase), inconsistent with the rest of the JSON. The `AgentDefinition.ViewLayout` C# property uses `[JsonPropertyName("ViewLayout")]` and the type is case-insensitive on read.

- **(Recommended) Leave the casing as-is** to minimize the migration diff. A follow-up normalization PR can fix it.
- Normalize to `viewLayout` in the same PR. Cleaner JSON, larger diff.

#### Q4. `OpenAI` SDK package

`Azure.AI.OpenAI` 2.x transitively depends on the `OpenAI` SDK. We can use `OpenAI.OpenAIClient` and `OpenAI.Chat` without adding a new package reference.

- **(Recommended) Stay on the transitive dependency.** No new `<PackageReference>` in `MagicAgent.Api.csproj`.
- Add an explicit `<PackageReference Include="OpenAI" />` for clarity. Trivial change, but it is a project file edit that needs a `dotnet restore`.

#### Q5. Profile / tool rename UX

When a user renames a profile id in the LLM Profiles view (or a tool id in the Tools view), there can be existing steps that reference the old id.

- **(Recommended) Auto-rewire.** Rename updates every `step.llmConfig.profileId` (or every `step.tools[i]`) that points at the old id, in a single atomic save. UI shows a toast: "Renamed `qwen-local` to `qwen-local-2`. Updated 4 step(s)."
- Fail the rename with a 409 listing the referencing steps. The user has to update the steps first, then come back to rename. Simpler logic, worse UX.

#### Q6. MCP tool probe endpoint

The new `ToolsView` needs a way to populate `allowedTools` and `actions` with the actual tool names exposed by the MCP server.

- **(Recommended) Add `POST /api/agent-definitions/tools/{id}/probe`** that calls `mcpClient.ListToolsAsync` with the tool's `serverUrl` + `headers` and returns the remote tool names + descriptions. The UI calls it when the user clicks "Probe server" in the tool editor. The MCP client is short-lived and disposed after the probe.
- Skip the probe endpoint. The user types tool names by hand (free-form text fields instead of a multi-select). Smaller PR, worse UX, and the existing `tavily-mcp` tool already has hard-coded names in its JSON so a hand-typed approach is possible but error-prone.

#### Q7. Cascade-delete UX

When a user tries to delete a profile or tool that's in use, the API returns 409 with a list of referencing steps. The UI needs to handle this.

- **(Recommended) Error toast** with the list of referencing agents and steps. The user dismisses it, goes to the Workflows view to update the steps, then comes back to delete.
- Modal with the list and an "Open referencing step" button that navigates to the Workflows view, selects the right agent, and opens that step in the step dialog. Friendlier UX, more work.

### Ready to start

Once Q1–Q7 are answered (or the recommended defaults are accepted), phase 1 of section 10 begins: add the new .NET types alongside the old ones.
