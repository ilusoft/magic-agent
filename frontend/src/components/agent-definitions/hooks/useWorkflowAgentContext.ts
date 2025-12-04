import { useMemo } from "react";

import type {
  AgentDefinition,
  AgentDefinitionsDocument,
  AgentToolDefinition,
} from "../../../types/agents";
import type { KeyValueEntry } from "../types";
import { entriesFromRecord } from "../util";

interface UseWorkflowAgentContextOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
}

interface WorkflowAgentContext {
  agent: AgentDefinition | null;
  availableTools: { id: string; label: string }[];
  workflowParameters: KeyValueEntry[];
}

export function useWorkflowAgentContext({
  draftDocument,
  activeWorkflowId,
}: UseWorkflowAgentContextOptions): WorkflowAgentContext {
  const agent = useMemo(() => {
    if (!draftDocument || !activeWorkflowId) {
      return null;
    }

    return (
      draftDocument.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      ) ?? null
    );
  }, [draftDocument, activeWorkflowId]);

  const availableTools = useMemo(() => {
    if (!agent || !Array.isArray(agent.tools)) {
      return [] as { id: string; label: string }[];
    }

    return agent.tools
      .filter((tool): tool is AgentToolDefinition => Boolean(tool?.id))
      .map((tool) => ({ id: tool.id, label: tool.name?.trim() || tool.id }));
  }, [agent]);

  const workflowParameters = useMemo(() => {
    if (!agent) {
      return [] as KeyValueEntry[];
    }

    const entries = entriesFromRecord(agent.defaultParameters);
    return entries.length > 0 ? entries : [];
  }, [agent]);

  return useMemo(
    () => ({ agent, availableTools, workflowParameters }),
    [agent, availableTools, workflowParameters]
  );
}
