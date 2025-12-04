import { useCallback } from "react";

import type {
  AgentDefinition,
  AgentDefinitionsDocument,
} from "../../../types/agents";
import type { StepFormState, StepType, WorkflowNode } from "../types";
import { entriesFromRecord } from "../util";
import { coerceStepType, ensureParametersForStepType } from "./useStepForm";

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
