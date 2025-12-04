import { useCallback } from "react";

import type {
  AgentDefinitionsDocument,
  AgentStepDefinition,
} from "../../../types/agents";
import type {
  StepFormState,
  StepType,
  WorkflowVariableDataType,
} from "../types";
import { recordFromEntries, variableTypesFromEntries } from "../util";
import { DEFAULT_STEP_TYPE } from "./useStepForm";
import { renameStepReferences } from "./stepLayoutUtils";
import type { ApplyDocumentUpdate } from "./types";

interface SaveStepArgs {
  activeWorkflowId: string;
  originalName: string;
  trimmedName: string;
  stepType: StepType;
  parameters: AgentStepDefinition["parameters"];
  variableTypes: Record<string, WorkflowVariableDataType>;
  conversation?: AgentStepDefinition["conversation"];
  uniqueTools: string[];
}

interface DeleteStepArgs {
  activeWorkflowId: string;
  stepName: string;
}

interface UseStepPersistenceOptions {
  applyDocumentUpdate: ApplyDocumentUpdate;
}

interface ValidationResult {
  success: boolean;
  error?: string;
}

interface PersistWithValidationArgs {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  mode: "create" | "edit";
  stepForm: StepFormState;
  stepOriginalName: string | null;
}

interface DeleteWithValidationArgs {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  stepOriginalName: string | null;
}

export function useStepPersistence({
  applyDocumentUpdate,
}: UseStepPersistenceOptions) {
  const persistStep = useCallback(
    ({
      activeWorkflowId,
      originalName,
      trimmedName,
      stepType,
      parameters,
      variableTypes,
      conversation,
      uniqueTools,
    }: SaveStepArgs) => {
      applyDocumentUpdate((draft: AgentDefinitionsDocument) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        const existingIndex = agent.steps.findIndex(
          (step) => step.name === originalName
        );
        const previousStep =
          existingIndex >= 0 ? agent.steps[existingIndex] : undefined;
        const outcomes = previousStep?.outcomes ?? [];

        const updatedStep: AgentStepDefinition = {
          name: trimmedName,
          type: stepType,
          parameters,
          conversation,
          outcomes: outcomes ?? [],
        };

        if (previousStep?.isStartStep) {
          updatedStep.isStartStep = true;
        }

        if (!conversation) {
          delete (updatedStep as Partial<AgentStepDefinition>).conversation;
        }

        if (Object.keys(variableTypes).length > 0) {
          updatedStep.variableTypes = variableTypes;
        } else {
          delete (updatedStep as Partial<AgentStepDefinition>).variableTypes;
        }

        if (uniqueTools.length > 0) {
          updatedStep.tools = uniqueTools;
        } else {
          delete (updatedStep as Partial<AgentStepDefinition>).tools;
        }

        if (existingIndex >= 0) {
          agent.steps[existingIndex] = updatedStep;
        } else {
          agent.steps.push({
            ...updatedStep,
            outcomes: [],
            tools: updatedStep.tools,
          });
        }

        if (originalName !== trimmedName) {
          renameStepReferences(agent, originalName, trimmedName);
        }

        return draft;
      });
    },
    [applyDocumentUpdate]
  );

  const deleteStep = useCallback(
    ({ activeWorkflowId, stepName }: DeleteStepArgs) => {
      applyDocumentUpdate((draft: AgentDefinitionsDocument) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        const index = agent.steps.findIndex((step) => step.name === stepName);

        if (index === -1) {
          return draft;
        }

        const removedWasStart = agent.steps[index]?.isStartStep;

        agent.steps.splice(index, 1);

        if (removedWasStart && agent.steps.length > 0) {
          const fallback = agent.steps.find((step) => step.isStartStep);

          if (!fallback) {
            agent.steps[0].isStartStep = true;
          }
        }

        return draft;
      });
    },
    [applyDocumentUpdate]
  );

  const persistStepWithValidation = useCallback(
    ({
      draftDocument,
      activeWorkflowId,
      mode,
      stepForm,
      stepOriginalName,
    }: PersistWithValidationArgs): ValidationResult => {
      if (!draftDocument || !activeWorkflowId) {
        return {
          success: false,
          error: "Unable to update step — missing context.",
        };
      }

      const trimmedName = stepForm.name.trim();
      const stepType = stepForm.type ?? DEFAULT_STEP_TYPE;

      if (!trimmedName) {
        return { success: false, error: "Step name is required." };
      }

      if (mode === "create") {
        const duplicate = draftDocument.agents
          .find((candidate) => candidate.id === activeWorkflowId)
          ?.steps.some((step) => step.name === trimmedName);

        if (duplicate) {
          return {
            success: false,
            error:
              "A step with this name already exists. Choose a different name or edit the existing step.",
          };
        }
      }

      const parameters = recordFromEntries(stepForm.parameters);
      const variableTypes = variableTypesFromEntries(stepForm.parameters);
      const conversation = stepForm.conversationEnabled
        ? { enabled: true }
        : undefined;
      const originalName = stepOriginalName ?? trimmedName;
      const uniqueTools = Array.from(new Set(stepForm.tools ?? [])).filter(
        (toolId) => toolId.trim().length > 0
      );

      persistStep({
        activeWorkflowId,
        originalName,
        trimmedName,
        stepType,
        parameters,
        variableTypes,
        conversation,
        uniqueTools,
      });

      return { success: true };
    },
    [persistStep]
  );

  const deleteStepWithValidation = useCallback(
    ({
      draftDocument,
      activeWorkflowId,
      stepOriginalName,
    }: DeleteWithValidationArgs): ValidationResult => {
      if (!draftDocument || !activeWorkflowId || !stepOriginalName) {
        return {
          success: false,
          error: "Unable to delete step — missing context.",
        };
      }

      deleteStep({ activeWorkflowId, stepName: stepOriginalName });
      return { success: true };
    },
    [deleteStep]
  );

  return {
    persistStep,
    deleteStep,
    persistStepWithValidation,
    deleteStepWithValidation,
  };
}
