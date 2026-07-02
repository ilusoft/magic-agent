import { useCallback } from "react";

import type {
  AgentDefinition,
  AgentDefinitionsDocument,
} from "@/types/agents";
import {
  EMPTY_STEP_LLM_FORM,
  type StepFormState,
  type StepLlmFormState,
  type StepType,
  type WorkflowNode,
} from "@/components/agent-definitions/types";
import { entriesFromRecord } from "@/components/agent-definitions/util";
import { coerceStepType, ensureParametersForStepType } from "@/components/agent-definitions/hooks/useStepForm";

interface OpenDialogOptions {
  mode: "create" | "edit";
  target?: WorkflowNode | null;
}

interface UseStepDialogOpenersOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  agent: AgentDefinition | null;
  setStepFormState: (value: StepFormState | null) => void;
  setStepFormError: (value: string | null) => void;
  setStepOriginalName: (value: string | null) => void;
  openDialog: (options: OpenDialogOptions) => void;
}

export interface StepDialogOpeners {
  openForEditing: (workflowNode: WorkflowNode) => void;
  openForCreation: () => void;
  openForEchoCreation: () => void;
  openForVariableCreation: () => void;
  openForResetCreation: () => void;
}

export function useStepDialogOpeners({
  draftDocument,
  activeWorkflowId,
  agent,
  setStepFormState,
  setStepFormError,
  setStepOriginalName,
  openDialog,
}: UseStepDialogOpenersOptions): StepDialogOpeners {
  const openForEditing = useCallback(
    (workflowNode: WorkflowNode) => {
      if (!draftDocument || !activeWorkflowId) {
        setStepFormState(null);
        setStepFormError("Unable to locate workflow for editing.");
        setStepOriginalName(null);
        openDialog({ mode: "edit", target: workflowNode });
        return;
      }

      if (!agent) {
        setStepFormState(null);
        setStepFormError("Unable to locate agent for this workflow.");
        setStepOriginalName(null);
        openDialog({ mode: "edit", target: workflowNode });
        return;
      }

      const targetStepName = workflowNode.data.stepName;
      const existingStep = targetStepName
        ? agent.steps.find((step) => step.name === targetStepName)
        : undefined;

      const parameterEntries = entriesFromRecord(
        existingStep?.parameters,
        existingStep?.variableTypes
      );
      const stepType = coerceStepType(existingStep?.type);
      const ensuredEntries = ensureParametersForStepType(
        stepType,
        parameterEntries
      );
      const selectedTools = Array.isArray(existingStep?.tools)
        ? existingStep?.tools.filter((toolId) => typeof toolId === "string")
        : [];

      setStepFormState({
        name: existingStep?.name ?? targetStepName ?? "",
        type: stepType,
        conversationEnabled: existingStep?.conversation?.enabled ?? false,
        parameters: ensuredEntries,
        tools: selectedTools,
        variableTypes: existingStep?.variableTypes,
        llmConfig: buildLlmFormState(existingStep?.llmConfig),
      });
      setStepFormError(null);
      setStepOriginalName(existingStep?.name ?? targetStepName ?? null);
      openDialog({ mode: "edit", target: workflowNode });
    },
    [
      draftDocument,
      activeWorkflowId,
      agent,
      setStepFormState,
      setStepFormError,
      setStepOriginalName,
      openDialog,
    ]
  );

  const openForTypeCreation = useCallback(
    (initialType: StepType) => {
      setStepFormState({
        name: "",
        type: initialType,
        conversationEnabled: false,
        parameters: ensureParametersForStepType(initialType, []),
        tools: [],
        llmConfig: buildLlmFormState(undefined),
      });
      setStepFormError(null);
      setStepOriginalName(null);
      openDialog({ mode: "create" });
    },
    [setStepFormState, setStepFormError, setStepOriginalName, openDialog]
  );

  const openForCreation = useCallback(
    () => openForTypeCreation("agent"),
    [openForTypeCreation]
  );

  const openForEchoCreation = useCallback(
    () => openForTypeCreation("echo"),
    [openForTypeCreation]
  );

  const openForVariableCreation = useCallback(
    () => openForTypeCreation("setVariables"),
    [openForTypeCreation]
  );

  const openForResetCreation = useCallback(
    () => openForTypeCreation("resetConversation"),
    [openForTypeCreation]
  );

  return {
    openForEditing,
    openForCreation,
    openForEchoCreation,
    openForVariableCreation,
    openForResetCreation,
  };
}

function buildLlmFormState(
  llmConfig: AgentDefinition["steps"][number]["llmConfig"]
): StepLlmFormState {
  if (!llmConfig) {
    return { ...(EMPTY_STEP_LLM_FORM as StepLlmFormState) };
  }

  const mode = llmConfig.profileId
    ? "profile"
    : hasAnyInlineField(llmConfig)
    ? "inline"
    : "inherit";

  return {
    mode,
    profileId: llmConfig.profileId ?? "",
    provider: llmConfig.provider ?? "azure-openai",
    endpoint: llmConfig.endpoint ?? "",
    deployment: llmConfig.deployment ?? "",
    apiVersion: llmConfig.apiVersion ?? "",
    baseUrl: llmConfig.baseUrl ?? "",
    model: llmConfig.model ?? "",
    apiKey: llmConfig.apiKey ?? "",
    temperature: llmConfig.temperature?.toString() ?? "",
    maxTokens: llmConfig.maxTokens?.toString() ?? "",
  };
}

function hasAnyInlineField(
  llmConfig: NonNullable<AgentDefinition["steps"][number]["llmConfig"]>
): boolean {
  return Boolean(
    llmConfig.provider ||
      llmConfig.endpoint ||
      llmConfig.deployment ||
      llmConfig.apiVersion ||
      llmConfig.baseUrl ||
      llmConfig.model ||
      llmConfig.apiKey ||
      llmConfig.headers ||
      llmConfig.temperature !== undefined ||
      llmConfig.maxTokens !== undefined
  );
}
