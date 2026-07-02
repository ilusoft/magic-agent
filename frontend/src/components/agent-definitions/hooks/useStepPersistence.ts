import { useCallback } from "react";

import type {
  AgentDefinitionsDocument,
  AgentStepDefinition,
  AgentStepLlmConfig,
} from "@/types/agents";
import type {
  StepFormState,
  StepType,
  WorkflowVariableDataType,
} from "@/components/agent-definitions/types";
import { recordFromEntries, variableTypesFromEntries } from "@/components/agent-definitions/util";
import { DEFAULT_STEP_TYPE } from "@/components/agent-definitions/hooks/useStepForm";
import { renameStepReferences } from "@/components/agent-definitions/hooks/stepLayoutUtils";
import type { ApplyDocumentUpdate } from "@/components/agent-definitions/hooks/types";

interface SaveStepArgs {
  activeWorkflowId: string;
  originalName: string;
  trimmedName: string;
  stepType: StepType;
  parameters: AgentStepDefinition["parameters"];
  variableTypes: Record<string, WorkflowVariableDataType>;
  conversation?: AgentStepDefinition["conversation"];
  uniqueTools: string[];
  llmConfig?: AgentStepDefinition["llmConfig"];
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
      llmConfig,
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

        if (llmConfig) {
          updatedStep.llmConfig = llmConfig;
        } else {
          delete (updatedStep as Partial<AgentStepDefinition>).llmConfig;
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
      const llmConfig =
        stepForm.type === "agent" ? serializeLlmConfig(stepForm.llmConfig) : undefined;

      persistStep({
        activeWorkflowId,
        originalName,
        trimmedName,
        stepType,
        parameters,
        variableTypes,
        conversation,
        uniqueTools,
        llmConfig,
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

function serializeLlmConfig(
  form: StepFormState["llmConfig"]
): AgentStepLlmConfig | undefined {
  if (form.mode === "inherit") {
    return undefined;
  }

  if (form.mode === "profile") {
    if (!form.profileId.trim()) {
      return undefined;
    }
    return { profileId: form.profileId.trim() };
  }

  // mode === "inline"
  const out: AgentStepLlmConfig = {};
  if (form.provider.trim()) out.provider = form.provider.trim();
  if (form.endpoint.trim()) out.endpoint = form.endpoint.trim();
  if (form.deployment.trim()) out.deployment = form.deployment.trim();
  if (form.apiVersion.trim()) out.apiVersion = form.apiVersion.trim();
  if (form.baseUrl.trim()) out.baseUrl = form.baseUrl.trim();
  if (form.model.trim()) out.model = form.model.trim();
  if (form.apiKey.trim()) out.apiKey = form.apiKey.trim();
  if (form.temperature.trim()) {
    const t = Number(form.temperature);
    if (!Number.isNaN(t)) out.temperature = t;
  }
  if (form.maxTokens.trim()) {
    const n = Number(form.maxTokens);
    if (!Number.isNaN(n)) out.maxTokens = n;
  }
  return Object.keys(out).length > 0 ? out : undefined;
}
