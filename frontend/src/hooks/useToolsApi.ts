import { useCallback, useState } from "react";

import type { AgentToolDefinition } from "@/types/agents";
import { CascadeDeleteError } from "@/hooks/useLlmProfilesApi";

interface ToolsApi {
  tools: Record<string, AgentToolDefinition>;
  loading: boolean;
  error: string | null;
  load: () => Promise<void>;
  save: (tools: Record<string, AgentToolDefinition>) => Promise<void>;
  saveCascadeError: CascadeDeleteError | null;
  clearCascadeError: () => void;
  probe: (toolId: string) => Promise<ProbedTool[]>;
  probing: boolean;
}

export interface ProbedTool {
  name: string;
  description?: string;
}

export function useToolsApi(apiBaseUrl: string): ToolsApi {
  const [tools, setTools] = useState<Record<string, AgentToolDefinition>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveCascadeError, setSaveCascadeError] = useState<CascadeDeleteError | null>(null);
  const [probing, setProbing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/agent-definitions/tools`);
      if (!response.ok) {
        throw new Error(`Failed to load tools (${response.status})`);
      }
      const data = (await response.json()) as Record<string, AgentToolDefinition>;
      setTools(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load tools.");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  const save = useCallback(
    async (newTools: Record<string, AgentToolDefinition>) => {
      setError(null);
      setSaveCascadeError(null);
      const response = await fetch(`${apiBaseUrl}/api/agent-definitions/tools`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newTools),
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
        const message = `Failed to save tools (${response.status})`;
        setError(message);
        throw new Error(message);
      }

      setTools(newTools);
    },
    [apiBaseUrl]
  );

  const clearCascadeError = useCallback(() => setSaveCascadeError(null), []);

  const probe = useCallback(
    async (toolId: string): Promise<ProbedTool[]> => {
      setProbing(true);
      try {
        const response = await fetch(
          `${apiBaseUrl}/api/agent-definitions/tools/${encodeURIComponent(toolId)}/probe`,
          { method: "POST" }
        );
        if (!response.ok) {
          throw new Error(`Probe failed (${response.status})`);
        }
        return (await response.json()) as ProbedTool[];
      } finally {
        setProbing(false);
      }
    },
    [apiBaseUrl]
  );

  return {
    tools,
    loading,
    error,
    load,
    save,
    saveCascadeError,
    clearCascadeError,
    probe,
    probing,
  };
}
