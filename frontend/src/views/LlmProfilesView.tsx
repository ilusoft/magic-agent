import { useCallback, useEffect, useState } from "react";

import type { AgentLlmProfileDefinition } from "@/types/agents";
import { CascadeDeleteError, useLlmProfilesApi } from "@/hooks/useLlmProfilesApi";

interface LlmProfilesViewProps {
  apiBaseUrl: string;
}

const EMPTY_PROFILE: AgentLlmProfileDefinition = {
  provider: "azure-openai",
  endpoint: "",
  deployment: "",
  apiKey: "",
};

export function LlmProfilesView({ apiBaseUrl }: LlmProfilesViewProps) {
  const api = useLlmProfilesApi(apiBaseUrl);
  const [edits, setEdits] = useState<Record<string, AgentLlmProfileDefinition>>({});
  const [error, setError] = useState<string | null>(null);
  const [cascadeError, setCascadeError] = useState<CascadeDeleteError | null>(null);
  const [newProfileId, setNewProfileId] = useState("");

  useEffect(() => {
    api.load();
  }, [api.load]);

  useEffect(() => {
    setError(api.error);
  }, [api.error]);

  useEffect(() => {
    setCascadeError(api.saveCascadeError);
  }, [api.saveCascadeError]);

  const update = useCallback(
    (profileId: string, patch: Partial<AgentLlmProfileDefinition>) => {
      setEdits((prev) => ({
        ...prev,
        [profileId]: {
          ...(prev[profileId] ?? api.profiles[profileId] ?? EMPTY_PROFILE),
          ...patch,
        },
      }));
    },
    [api.profiles]
  );

  const handleAdd = useCallback(() => {
    const id = newProfileId.trim();
    if (!id) return;
    if (api.profiles[id] || edits[id]) {
      setError(`Profile '${id}' already exists.`);
      return;
    }
    setEdits((prev) => ({ ...prev, [id]: { ...EMPTY_PROFILE } }));
    setNewProfileId("");
  }, [newProfileId, api.profiles, edits]);

  const handleSave = useCallback(
    async (profileId: string) => {
      const edited = edits[profileId];
      if (!edited) return;
      try {
        const next = { ...api.profiles, [profileId]: edited };
        await api.save(next);
        setEdits((prev) => {
          const { [profileId]: _, ...rest } = prev;
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
    async (profileId: string) => {
      const next = { ...api.profiles };
      delete next[profileId];
      try {
        await api.save(next);
        setEdits((prev) => {
          const { [profileId]: _, ...rest } = prev;
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

  const handleDiscard = useCallback((profileId: string) => {
    setEdits((prev) => {
      const { [profileId]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  const handleProviderChange = useCallback(
    (profileId: string, provider: string) => {
      update(profileId, { provider });
    },
    [update]
  );

  const profileIds = Object.keys(api.profiles);
  const editingIds = Object.keys(edits);
  const allIds = Array.from(new Set([...profileIds, ...editingIds])).sort();

  if (api.loading && profileIds.length === 0) {
    return <div className="p-8 text-center text-sm text-foreground/70">Loading LLM profiles…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">LLM Profiles</h2>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={newProfileId}
            onChange={(e) => setNewProfileId(e.target.value)}
            placeholder="new-profile-id"
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            type="button"
            onClick={handleAdd}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
          >
            Add profile
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
          No LLM profiles defined yet. Add one above.
        </p>
      ) : (
        <div className="space-y-3">
          {allIds.map((id) => {
            const draft = edits[id] ?? api.profiles[id];
            const isDirty = id in edits;
            return (
              <ProfileCard
                key={id}
                profileId={id}
                profile={draft}
                isDirty={isDirty}
                onChange={(patch) => update(id, patch)}
                onProviderChange={(provider) => handleProviderChange(id, provider)}
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

interface ProfileCardProps {
  profileId: string;
  profile: AgentLlmProfileDefinition;
  isDirty: boolean;
  onChange: (patch: Partial<AgentLlmProfileDefinition>) => void;
  onProviderChange: (provider: string) => void;
  onSave: () => void;
  onDelete: () => void;
  onDiscard: () => void;
}

function ProfileCard({
  profileId,
  profile,
  isDirty,
  onChange,
  onProviderChange,
  onSave,
  onDelete,
  onDiscard,
}: ProfileCardProps) {
  const isAzure = profile.provider === "azure-openai";

  return (
    <div className="rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-sm font-semibold">{profileId}</h3>
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
        <Field label="Provider">
          <select
            value={profile.provider}
            onChange={(e) => onProviderChange(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="azure-openai">azure-openai</option>
            <option value="openai-compatible">openai-compatible</option>
          </select>
        </Field>

        {isAzure ? (
          <>
            <Field label="Endpoint">
              <input
                type="text"
                value={profile.endpoint ?? ""}
                onChange={(e) => onChange({ endpoint: e.target.value })}
                className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Deployment">
              <input
                type="text"
                value={profile.deployment ?? ""}
                onChange={(e) => onChange({ deployment: e.target.value })}
                className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="API version">
              <input
                type="text"
                value={profile.apiVersion ?? ""}
                onChange={(e) => onChange({ apiVersion: e.target.value })}
                className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
          </>
        ) : (
          <>
            <Field label="Base URL">
              <input
                type="text"
                value={profile.baseUrl ?? ""}
                onChange={(e) => onChange({ baseUrl: e.target.value })}
                className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
            <Field label="Model">
              <input
                type="text"
                value={profile.model ?? ""}
                onChange={(e) => onChange({ model: e.target.value })}
                className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </Field>
          </>
        )}

        <Field label="API key" fullWidth>
          <input
            type="text"
            value={profile.apiKey ?? ""}
            onChange={(e) => onChange({ apiKey: e.target.value })}
            placeholder="literal value or ${ENV_VAR}"
            className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>

        <Field label="Temperature">
          <input
            type="number"
            step="0.1"
            value={profile.temperature ?? ""}
            onChange={(e) =>
              onChange({ temperature: e.target.value ? Number(e.target.value) : undefined })
            }
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </Field>

        <Field label="Max tokens">
          <input
            type="number"
            value={profile.maxTokens ?? ""}
            onChange={(e) =>
              onChange({ maxTokens: e.target.value ? Number(e.target.value) : undefined })
            }
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
