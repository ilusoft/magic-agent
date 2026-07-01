import { useCallback, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type { AgentDefinitionsDocument } from "@/types/agents";
import {
  type StepFormState,
  type KeyValueEntry,
  type WorkflowVariableDataType,
} from "@/components/agent-definitions/types";
import { useWorkflowAgentContext } from "@/components/agent-definitions/hooks/useWorkflowAgentContext";
import { useStepDialogState } from "@/components/agent-definitions/hooks/useStepDialogState";
import { useStepForm } from "@/components/agent-definitions/hooks/useStepForm";
import type { ApplyDocumentUpdate } from "@/components/agent-definitions/hooks/types";
import { useStepPersistence } from "@/components/agent-definitions/hooks/useStepPersistence";
import {
  type StepDialogOpeners,
  useStepDialogOpeners,
} from "@/components/agent-definitions/hooks/useStepDialogOpeners";

interface UseStepDialogOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
  apiBaseUrl: string;
}

interface UseStepDialogResult {
  dialogProps: {
    open: boolean;
    mode: "create" | "edit";
    title: string;
    stepForm: StepFormState | null;
    stepFormError: string | null;
    workflowParameters: KeyValueEntry[];
    apiBaseUrl: string;
    onClose: () => void;
    onSubmit: (event: FormEvent<HTMLFormElement>) => void;
    onFieldChange: (
      field: "name" | "type"
    ) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
    onConversationToggle: (event: ChangeEvent<HTMLInputElement>) => void;
    onAddParameter: () => void;
    onRemoveParameter: (entryId: string) => void;
    onMoveParameter?: (entryId: string, direction: "up" | "down") => void;
    onParameterChange: (
      entryId: string,
      field: "key" | "value"
    ) => (event: ChangeEvent<HTMLInputElement>) => void;
    onParameterDataTypeChange?: (
      entryId: string,
      dataType: WorkflowVariableDataType
    ) => void;
    availableTools: { id: string; label: string }[];
    onToolToggle: (
      toolId: string
    ) => (event: ChangeEvent<HTMLInputElement>) => void;
    onDelete?: () => void;
  };
  title: string;
  open: boolean;
  openers: StepDialogOpeners;
  reset: () => void;
}

export function useStepDialog({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
  apiBaseUrl,
}: UseStepDialogOptions): UseStepDialogResult {
  const {
    stepForm,
    stepFormError,
    setStepFormState,
    setStepFormError,
    resetFormState,
    handleFieldChange,
    handleConversationToggle,
    handleAddParameter,
    handleRemoveParameter,
    handleMoveParameter,
    handleParameterChange,
    handleParameterDataTypeChange,
    handleToolToggle,
  } = useStepForm();
  const [stepOriginalName, setStepOriginalName] = useState<string | null>(null);
  const { agent, availableTools, workflowParameters } = useWorkflowAgentContext(
    {
      draftDocument,
      activeWorkflowId,
    }
  );
  const {
    open,
    mode,
    title,
    openDialog,
    reset: resetDialogState,
  } = useStepDialogState();
  const { persistStepWithValidation, deleteStepWithValidation } =
    useStepPersistence({
      applyDocumentUpdate,
    });

  const reset = useCallback(() => {
    resetDialogState();
    resetFormState();
    setStepOriginalName(null);
  }, [resetDialogState, resetFormState]);

  const openers = useStepDialogOpeners({
    draftDocument,
    activeWorkflowId,
    agent,
    setStepFormState,
    setStepFormError,
    setStepOriginalName,
    openDialog,
  });

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!stepForm) {
        setStepFormError("Unable to update step — missing context.");
        return;
      }

      const result = persistStepWithValidation({
        draftDocument,
        activeWorkflowId,
        mode,
        stepForm,
        stepOriginalName,
      });

      if (!result.success) {
        setStepFormError(result.error ?? "Unable to update step.");
        return;
      }

      setStepFormError(null);
      reset();
    },
    [
      stepForm,
      draftDocument,
      activeWorkflowId,
      stepOriginalName,
      mode,
      persistStepWithValidation,
      reset,
      setStepFormError,
    ]
  );

  const handleDelete = useCallback(() => {
    const result = deleteStepWithValidation({
      draftDocument,
      activeWorkflowId,
      stepOriginalName,
    });

    if (!result.success) {
      setStepFormError(result.error ?? "Unable to delete step.");
      return;
    }

    setStepFormError(null);
    reset();
  }, [
    draftDocument,
    activeWorkflowId,
    stepOriginalName,
    setStepFormError,
    deleteStepWithValidation,
    reset,
  ]);

  return {
    dialogProps: {
      open,
      mode,
      title,
      stepForm,
      stepFormError,
      workflowParameters,
      apiBaseUrl,
      onClose: reset,
      onSubmit: handleSubmit,
      onFieldChange: handleFieldChange,
      onConversationToggle: handleConversationToggle,
      onAddParameter: handleAddParameter,
      onRemoveParameter: handleRemoveParameter,
      onMoveParameter: handleMoveParameter,
      onParameterChange: handleParameterChange,
      onParameterDataTypeChange: handleParameterDataTypeChange,
      availableTools,
      onToolToggle: handleToolToggle,
      onDelete: mode === "edit" ? handleDelete : undefined,
    },
    title,
    open,
    openers,
    reset,
  };
}
