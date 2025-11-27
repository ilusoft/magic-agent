import { useCallback, useMemo } from "react";

import { isWorkflowDebugLoggingEnabled } from "../utils/workflowDebug";

import type {
  AgentDefinition,
  AgentDefinitionsDocument,
} from "../../../types/agents";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseWorkflowActionsOptions {
  activeAgent: AgentDefinition | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
}

interface UseWorkflowActionsResult {
  stepNames: string[];
  setStartStep: (stepName: string) => void;
}

export function useWorkflowActions({
  activeAgent,
  activeWorkflowId,
  applyDocumentUpdate,
}: UseWorkflowActionsOptions): UseWorkflowActionsResult {
  const debugLoggingEnabled = isWorkflowDebugLoggingEnabled();

  const stepNames = useMemo(
    () =>
      (activeAgent?.steps.map((step) => step.name) ?? []).filter(
        (name) => !!name
      ),
    [activeAgent]
  );

  const setStartStep = useCallback(
    (stepName: string) => {
      if (!activeWorkflowId || !activeAgent) {
        return;
      }

      if (!stepName) {
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        const matchingStep = agent.steps.find((step) => step.name === stepName);

        if (!matchingStep) {
          return draft;
        }

        agent.steps.forEach((step) => {
          step.isStartStep = step.name === stepName;
        });

        if (debugLoggingEnabled) {
          console.info("[Workflow] setStartStep", {
            workflowId: agent.id,
            startStep: stepName,
            steps: agent.steps.map((step) => ({
              name: step.name,
              isStartStep: step.isStartStep,
            })),
          });
        }

        return draft;
      });
    },
    [activeWorkflowId, activeAgent, applyDocumentUpdate, debugLoggingEnabled]
  );

  return {
    stepNames,
    setStartStep,
  };
}
