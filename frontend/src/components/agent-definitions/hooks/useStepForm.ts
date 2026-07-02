import { useCallback, useState } from "react";
import type { ChangeEvent } from "react";

import {
  STEP_TYPE_OPTIONS,
  type KeyValueEntry,
  type LlmConfigMode,
  type StepFormState,
  type StepLlmFormState,
  type StepType,
  type WorkflowVariableDataType,
} from "@/components/agent-definitions/types";
import { createKeyValueEntry } from "@/components/agent-definitions/util";

const STEP_TYPE_PARAMETER_TEMPLATES: Record<StepType, string[]> = {
  agent: ["systemPrompt", "message"],
  echo: ["message"],
  setVariables: [],
  resetConversation: [],
};

export const DEFAULT_STEP_TYPE: StepType = "agent";

export function coerceStepType(value: string | undefined): StepType {
  if (value === "pass-through") {
    return "setVariables";
  }

  if (value && STEP_TYPE_OPTIONS.includes(value as StepType)) {
    return value as StepType;
  }

  return DEFAULT_STEP_TYPE;
}

export function ensureParametersForStepType(
  type: StepType,
  currentParameters: KeyValueEntry[]
): KeyValueEntry[] {
  const templateKeys = STEP_TYPE_PARAMETER_TEMPLATES[type] ?? [];

  if (templateKeys.length === 0) {
    return currentParameters;
  }

  const existingByKey = new Map(
    currentParameters.map((entry) => [entry.key, entry])
  );

  const templateEntries = templateKeys.map((key) => {
    const existing = existingByKey.get(key);

    if (existing) {
      return existing;
    }

    return createKeyValueEntry(key);
  });

  const extras = currentParameters.filter(
    (entry) => !templateKeys.includes(entry.key)
  );

  return [...templateEntries, ...extras];
}

interface UseStepFormResult {
  stepForm: StepFormState | null;
  stepFormError: string | null;
  setStepFormState: (value: StepFormState | null) => void;
  setStepFormError: (value: string | null) => void;
  resetFormState: () => void;
  handleFieldChange: (
    field: "name" | "type"
  ) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  handleConversationToggle: (event: ChangeEvent<HTMLInputElement>) => void;
  handleAddParameter: () => void;
  handleRemoveParameter: (entryId: string) => void;
  handleMoveParameter: (entryId: string, direction: "up" | "down") => void;
  handleParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  handleParameterDataTypeChange: (
    entryId: string,
    dataType: WorkflowVariableDataType
  ) => void;
  handleToolToggle: (
    toolId: string
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  handleLlmConfigModeChange: (mode: LlmConfigMode) => void;
  handleLlmConfigChange: (patch: Partial<StepLlmFormState>) => void;
}

export function useStepForm(): UseStepFormResult {
  const [stepForm, setStepForm] = useState<StepFormState | null>(null);
  const [stepFormError, setStepFormError] = useState<string | null>(null);

  const setStepFormState = useCallback((value: StepFormState | null) => {
    setStepForm(value);
  }, []);

  const resetFormState = useCallback(() => {
    setStepForm(null);
    setStepFormError(null);
  }, []);

  const handleFieldChange = useCallback(
    (field: "name" | "type") =>
      (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const value = event.target.value;
        setStepForm((previous) => {
          if (!previous) {
            return previous;
          }

          if (field === "type") {
            const nextType = coerceStepType(value);
            const nextParameters = ensureParametersForStepType(
              nextType,
              previous.parameters ?? []
            );
            const normalizedParameters = nextParameters.map((entry) => ({
              ...entry,
              dataType:
                nextType === "setVariables"
                  ? entry.dataType ?? "string"
                  : undefined,
            }));
            const isVariableStep = nextType === "setVariables";
            const isResetStep = nextType === "resetConversation";
            return {
              ...previous,
              type: nextType,
              parameters: normalizedParameters,
              conversationEnabled:
                isVariableStep || isResetStep
                  ? false
                  : previous.conversationEnabled,
              tools: isVariableStep || isResetStep ? [] : previous.tools ?? [],
            };
          }

          return { ...previous, [field]: value };
        });
      },
    []
  );

  const handleConversationToggle = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const checked = event.target.checked;
      setStepForm((previous) =>
        previous ? { ...previous, conversationEnabled: checked } : previous
      );
    },
    []
  );

  const handleParameterChange = useCallback(
    (entryId: string, field: "key" | "value") =>
      (event: ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setStepForm((previous) =>
          previous
            ? {
                ...previous,
                parameters: previous.parameters.map((entry) =>
                  entry.id === entryId ? { ...entry, [field]: value } : entry
                ),
              }
            : previous
        );
      },
    []
  );

  const handleAddParameter = useCallback(() => {
    setStepForm((previous) =>
      previous
        ? {
            ...previous,
            parameters: [
              ...previous.parameters,
              createKeyValueEntry(
                "",
                "",
                previous.type === "setVariables" ? "string" : undefined
              ),
            ],
          }
        : previous
    );
  }, []);

  const handleRemoveParameter = useCallback((entryId: string) => {
    setStepForm((previous) => {
      if (!previous) {
        return previous;
      }

      const remaining = previous.parameters.filter(
        (entry) => entry.id !== entryId
      );

      return {
        ...previous,
        parameters: remaining,
      };
    });
  }, []);

  const handleMoveParameter = useCallback(
    (entryId: string, direction: "up" | "down") => {
      setStepForm((previous) => {
        if (!previous) {
          return previous;
        }

        const currentIndex = previous.parameters.findIndex(
          (entry) => entry.id === entryId
        );

        if (currentIndex === -1) {
          return previous;
        }

        const targetIndex =
          direction === "up" ? currentIndex - 1 : currentIndex + 1;

        if (targetIndex < 0 || targetIndex >= previous.parameters.length) {
          return previous;
        }

        const nextParameters = [...previous.parameters];
        const [moved] = nextParameters.splice(currentIndex, 1);
        nextParameters.splice(targetIndex, 0, moved);

        return { ...previous, parameters: nextParameters };
      });
    },
    []
  );

  const handleParameterDataTypeChange = useCallback(
    (entryId: string, dataType: WorkflowVariableDataType) => {
      setStepForm((previous) =>
        previous
          ? {
              ...previous,
              parameters: previous.parameters.map((entry) =>
                entry.id === entryId ? { ...entry, dataType } : entry
              ),
            }
          : previous
      );
    },
    []
  );

  const handleToolToggle = useCallback(
    (toolId: string) => (event: ChangeEvent<HTMLInputElement>) => {
      const checked = event.target.checked;

      setStepForm((previous) => {
        if (!previous) {
          return previous;
        }

        const currentTools = new Set(previous.tools ?? []);

        if (checked) {
          currentTools.add(toolId);
        } else {
          currentTools.delete(toolId);
        }

        return {
          ...previous,
          tools: Array.from(currentTools),
        };
      });
    },
    []
  );

  const handleLlmConfigModeChange = useCallback((mode: LlmConfigMode) => {
    setStepForm((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        llmConfig: { ...previous.llmConfig, mode },
      };
    });
  }, []);

  const handleLlmConfigChange = useCallback((patch: Partial<StepLlmFormState>) => {
    setStepForm((previous) => {
      if (!previous) {
        return previous;
      }
      return {
        ...previous,
        llmConfig: { ...previous.llmConfig, ...patch },
      };
    });
  }, []);

  return {
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
    handleLlmConfigModeChange,
    handleLlmConfigChange,
  };
}
