import { useCallback, useState } from "react";

import type { AgentLlmProfileDefinition } from "@/types/agents";

interface LlmProfileApi {
  profiles: Record<string, AgentLlmProfileDefinition>;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  save: (
    profiles: Record<string, AgentLlmProfileDefinition>
  ) => Promise<void>;
  saveCascadeError: CascadeDeleteError | null;
  clearCascadeError: () => void;
}

export class CascadeDeleteError extends Error {
  referencingSteps: { agentId: string; stepName: string }[];

  constructor(message: string, referencingSteps: { agentId: string; stepName: string }[]) {
    super(message);
    this.referencingSteps = referencingSteps;
  }
}

export function useLlmProfilesApi(apiBaseUrl: string): LlmProfileApi {
  const [profiles, setProfiles] = useState<Record<string, AgentLlmProfileDefinition>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveCascadeError, setSaveCascadeError] = useState<CascadeDeleteError | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/agent-definitions/llm-profiles`);
      if (!response.ok) {
        throw new Error(`Failed to load LLM profiles (${response.status})`);
      }
      const data = (await response.json()) as Record<string, AgentLlmProfileDefinition>;
      setProfiles(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load LLM profiles.");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  const save = useCallback(
    async (newProfiles: Record<string, AgentLlmProfileDefinition>) => {
      setError(null);
      setSaveCascadeError(null);
      const response = await fetch(`${apiBaseUrl}/api/agent-definitions/llm-profiles`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newProfiles),
      });

      if (response.status === 409) {
        const payload = (await response.json()) as {
          message: string;
          referencingSteps: { agentId: string; stepName: string }[];
        };
        const err = new CascadeDeleteError(payload.message, payload.referencingSteps);
        setSaveCascadeError(err);
        throw err;
      }

      if (!response.ok) {
        const message = `Failed to save LLM profiles (${response.status})`;
        setError(message);
        throw new Error(message);
      }

      setProfiles(newProfiles);
    },
    [apiBaseUrl]
  );

  const clearCascadeError = useCallback(() => setSaveCascadeError(null), []);

  return { profiles, loading, error, load, save, saveCascadeError, clearCascadeError };
}
