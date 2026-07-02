import { useCallback, useEffect, useState } from "react";

import type { AgentToolDefinition } from "@/types/agents";
import { CascadeDeleteError } from "@/hooks/useLlmProfilesApi";
import { useToolsApi } from "@/hooks/useToolsApi";

interface ToolsViewProps {
  apiBaseUrl: string;
}

const EMPTY_TOOL: AgentToolDefinition = {
  id: "",
  type: "mcp",
  name: "",
  serverUrl: "",
};

export function ToolsView({ apiBaseUrl }: ToolsViewProps) {
  const api = useToolsApi(apiBaseUrl);
  const [edits, setEdits] = useState<Record<string, AgentToolDefinition>>({});
  const [error, setError] = useState<string | null>(null);
  const [cascadeError, setCascadeError] = useState<CascadeDeleteError | null>(null);
  const [newToolId, setNewToolId] = useState("");

  useEffect(() => {
    api.load();
  }, [api.load]);

  useEffect(() => setError(api.error), [api.error]);
  useEffect(() => setCascadeError(api.saveCascadeError), [api.saveCascadeError]);

  const update = useCallback(
    (toolId: string, patch: Partial<AgentToolDefinition>) => {
      setEdits((prev) => ({
        ...prev,
        [toolId]: {
          ...(prev[toolId] ?? api.tools[toolId] ?? EMPTY_TOOL),
          ...patch,
        },
      }));
    },
    [api.tools]
  );

  const handleAdd = useCallback(() => {
    const id = newToolId.trim();
    if (!id) return;
    if (api.tools[id] || edits[id]) {
      setError(`Tool '${id}' already exists.`);
      return;
    }
    setEdits((prev) => ({ ...prev, [id]: { ...EMPTY_TOOL, id } }));
    setNewToolId("");
  }, [newToolId, api.tools, edits]);

  const handleSave = useCallback(
    async (toolId: string) => {
      const edited = edits[toolId];
      if (!edited) return;
      try {
        const next = { ...api.tools, [toolId]: edited };
        await api.save(next);
        setEdits((prev) => {
          const { [toolId]: _, ...rest } = prev;
          return rest;
        });
        setCascadeError(null);
      } catch (e) {
        if (!(e instanceof CascadeDeleteError)) {
          setError(e instanceof Error ? e.message : "Save failed.");
        }
      }
    },
    [edits, api]
  );

  const handleDelete = useCallback(
    async (toolId: string) => {
      const next = { ...api.tools };
      delete next[toolId];
      try {
        await api.save(next);
        setEdits((prev) => {
          const { [toolId]: _, ...rest } = prev;
          return rest;
        });
        setCascadeError(null);
      } catch (e) {
        if (!(e instanceof CascadeDeleteError)) {
          setError(e instanceof Error ? e.message : "Delete failed.");
        }
      }
    },
    [api]
  );

  const handleDiscard = useCallback((toolId: string) => {
    setEdits((prev) => {
      const { [toolId]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  const toolIds = Object.keys(api.tools);
  const editingIds = Object.keys(edits);
  const allIds = Array.from(new Set([...toolIds, ...editingIds])).sort();

  if (api.loading && toolIds.length === 0) {
    return <div className="p-8 text-center text-sm text-foreground/70">Loading tools…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Tools</h2>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newToolId}
            onChange={(e) => setNewToolId(e.target.value)}
            placeholder="new-tool-id"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="button"
            onClick={handleAdd}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          >
            Add tool
          </button>
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {cascadeError ? (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          <p className="font-medium">{cascadeError.message}</p>
          <p className="mt-1">Referencing steps:</p>
          <ul className="ml-4 list-disc">
            {cascadeError.referencingSteps.map((s) => (
              <li key={`${s.agentId}:${s.stepName}`}>
                {s.agentId} → {s.stepName}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {allIds.length === 0 ? (
        <p className="rounded-md border border-dashed border-border bg-card/40 p-8 text-center text-sm text-foreground/70">
          No tools defined yet. Add one above.
        </p>
      ) : (
        <div className="space-y-3">
          {allIds.map((id) => {
            const draft = edits[id] ?? api.tools[id];
            const isDirty = id in edits;
            return (
              <ToolCard
                key={id}
                tool={draft}
                isDirty={isDirty}
                onChange={(patch) => update(id, patch)}
                onSave={() => handleSave(id)}
                onDelete={() => handleDelete(id)}
                onDiscard={() => handleDiscard(id)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

interface ToolCardProps {
  tool: AgentToolDefinition;
  isDirty: boolean;
  onChange: (patch: Partial<AgentToolDefinition>) => void;
  onSave: () => void;
  onDelete: () => void;
  onDiscard: () => void;
}

function ToolCard({ tool, isDirty, onChange, onSave, onDelete, onDiscard }: ToolCardProps) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-sm font-semibold">{tool.id}</h3>
        <div className="flex items-center gap-2">
          {isDirty ? (
            <>
              <button
                type="button"
                onClick={onDiscard}
                className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={onSave}
                className="rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground"
              >
                Save
              </button>
            </>
          ) : null}
          <button
            type="button"
            onClick={onDelete}
            className="rounded-md border border-destructive px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
          >
            Delete
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Field label="Type">
          <select
            value={tool.type}
            onChange={(e) => onChange({ type: e.target.value })}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="mcp">mcp</option>
            <option value="mcp-http">mcp-http</option>
          </select>
        </Field>

        <Field label="Name">
          <input
            type="text"
            value={tool.name ?? ""}
            onChange={(e) => onChange({ name: e.target.value })}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>

        <Field label="Server URL" fullWidth>
          <input
            type="text"
            value={tool.serverUrl ?? ""}
            onChange={(e) => onChange({ serverUrl: e.target.value })}
            className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>

        <Field label="Protocol">
          <select
            value={tool.protocol ?? "auto"}
            onChange={(e) => onChange({ protocol: e.target.value })}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="auto">auto</option>
            <option value="sse">sse</option>
            <option value="streamable-http">streamable-http</option>
          </select>
        </Field>

        <Field label="Authorization header">
          <input
            type="text"
            value={tool.authorizationHeaderName ?? "Authorization"}
            onChange={(e) => onChange({ authorizationHeaderName: e.target.value })}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
  fullWidth,
}: {
  label: string;
  children: React.ReactNode;
  fullWidth?: boolean;
}) {
  return (
    <div className={fullWidth ? "sm:col-span-2" : ""}>
      <label className="block text-xs font-semibold uppercase text-foreground/60">
        {label}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
