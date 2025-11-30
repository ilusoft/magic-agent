import { useCallback, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type {
  AgentDefinition,
  AgentDefinitionsDocument,
  AgentStepDefinition,
  AgentToolDefinition,
} from "../../../types/agents";
import {
  STEP_TYPE_OPTIONS,
  type StepFormState,
  type StepType,
  type WorkflowNode,
  type KeyValueEntry,
} from "../types";
import {
  createKeyValueEntry,
  entriesFromRecord,
  recordFromEntries,
} from "../util";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseStepDialogOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
}

const STEP_TYPE_PARAMETER_TEMPLATES: Record<StepType, string[]> = {
  chat: ["systemPrompt", "message"],
  echo: ["message"],
  "pass-through": [],
  setVariables: [],
};

const DEFAULT_STEP_TYPE: StepType = "chat";

function coerceStepType(value: string | undefined): StepType {
  if (value && STEP_TYPE_OPTIONS.includes(value as StepType)) {
    return value as StepType;
  }

  return DEFAULT_STEP_TYPE;
}

function ensureParametersForStepType(
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

function renameStepReferences(
  agent: AgentDefinition,
  originalName: string,
  nextName: string
) {
  if (!originalName || !nextName || originalName === nextName) {
    return;
  }

  agent.steps.forEach((step) => {
    step.outcomes?.forEach((outcome) => {
      if (outcome.nextStep === originalName) {
        outcome.nextStep = nextName;
      }
    });
  });

  const oldNodeId = `${agent.id}-${originalName}`;
  const newNodeId = `${agent.id}-${nextName}`;

  if (agent.ViewLayout?.nodes) {
    moveLayoutEntry(agent.ViewLayout.nodes, oldNodeId, newNodeId);
    moveLayoutEntry(agent.ViewLayout.nodes, originalName, nextName);
  }

  if (agent.ViewLayout?.edges) {
    renameLayoutEdgeKeys(agent.ViewLayout.edges, oldNodeId, newNodeId);
  }
}

function moveLayoutEntry<T>(
  collection: Record<string, T>,
  oldKey: string,
  newKey: string
) {
  if (!collection || oldKey === newKey || !(oldKey in collection)) {
    return;
  }

  collection[newKey] = collection[oldKey];
  delete collection[oldKey];
}

function renameLayoutEdgeKeys(
  edges: Record<string, { controlPoints?: { x: number; y: number }[] }>,
  oldNodeId: string,
  newNodeId: string
) {
  if (!edges || oldNodeId === newNodeId) {
    return;
  }

  Object.entries(edges).forEach(([edgeId, layout]) => {
    if (!edgeId.includes(oldNodeId)) {
      return;
    }

    const updatedKey = edgeId.split(oldNodeId).join(newNodeId);

    if (updatedKey === edgeId) {
      return;
    }

    edges[updatedKey] = layout;
    delete edges[edgeId];
  });
}

interface StepDialogBindings {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  stepForm: StepFormState | null;
  stepFormError: string | null;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onFieldChange: (
    field: "name" | "type"
  ) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  onConversationToggle: (event: ChangeEvent<HTMLInputElement>) => void;
  onAddParameter: () => void;
  onRemoveParameter: (entryId: string) => void;
  onParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  availableTools: { id: string; label: string }[];
  onToolToggle: (
    toolId: string
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  onDelete?: () => void;
}

interface UseStepDialogResult {
  dialogProps: StepDialogBindings;
  title: string;
  open: boolean;
  openForEditing: (workflowNode: WorkflowNode) => void;
  openForCreation: () => void;
  openForVariableCreation: () => void;
  reset: () => void;
}

export function useStepDialog({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
}: UseStepDialogOptions): UseStepDialogResult {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("edit");
  const [dialogTarget, setDialogTarget] = useState<WorkflowNode | null>(null);
  const [stepForm, setStepForm] = useState<StepFormState | null>(null);
  const [stepFormError, setStepFormError] = useState<string | null>(null);
  const [stepOriginalName, setStepOriginalName] = useState<string | null>(null);

  const availableTools = useMemo(() => {
    if (!draftDocument || !activeWorkflowId) {
      return [] as { id: string; label: string }[];
    }

    const agent = draftDocument.agents.find(
      (candidate) => candidate.id === activeWorkflowId
    );

    if (!agent || !Array.isArray(agent.tools)) {
      return [] as { id: string; label: string }[];
    }

    return agent.tools
      .filter((tool): tool is AgentToolDefinition => Boolean(tool?.id))
      .map((tool) => ({ id: tool.id, label: tool.name?.trim() || tool.id }));
  }, [draftDocument, activeWorkflowId]);

  const reset = useCallback(() => {
    setIsOpen(false);
    setMode("edit");
    setDialogTarget(null);
    setStepForm(null);
    setStepFormError(null);
    setStepOriginalName(null);
  }, []);

  const openForEditing = useCallback(
    (workflowNode: WorkflowNode) => {
      if (!draftDocument || !activeWorkflowId) {
        setStepForm(null);
        setStepFormError("Unable to locate workflow for editing.");
        setStepOriginalName(null);
        setMode("edit");
        setDialogTarget(workflowNode);
        setIsOpen(true);
        return;
      }

      const agent = draftDocument.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent) {
        setStepForm(null);
        setStepFormError("Unable to locate agent for this workflow.");
        setStepOriginalName(null);
        setMode("edit");
        setDialogTarget(workflowNode);
        setIsOpen(true);
        return;
      }

      const targetStepName = workflowNode.data.stepName;
      const existingStep = targetStepName
        ? agent.steps.find((step) => step.name === targetStepName)
        : undefined;

      const parameterEntries = entriesFromRecord(existingStep?.parameters);
      const stepType = coerceStepType(existingStep?.type);
      const ensuredEntries = ensureParametersForStepType(
        stepType,
        parameterEntries
      );
      const selectedTools = Array.isArray(existingStep?.tools)
        ? existingStep?.tools.filter((toolId) => typeof toolId === "string")
        : [];

      setStepForm({
        name: existingStep?.name ?? targetStepName ?? "",
        type: stepType,
        conversationEnabled: existingStep?.conversation?.enabled ?? false,
        parameters: ensuredEntries,
        tools: selectedTools,
      });
      setStepFormError(null);
      setStepOriginalName(existingStep?.name ?? targetStepName ?? null);
      setMode("edit");
      setDialogTarget(workflowNode);
      setIsOpen(true);
    },
    [draftDocument, activeWorkflowId]
  );

  const openForCreation = useCallback(() => {
    const initialType = DEFAULT_STEP_TYPE;
    setStepForm({
      name: "",
      type: initialType,
      conversationEnabled: false,
      parameters: ensureParametersForStepType(initialType, []),
      tools: [],
    });
    setStepFormError(null);
    setStepOriginalName(null);
    setMode("create");
    setDialogTarget(null);
    setIsOpen(true);
  }, []);

  const openForVariableCreation = useCallback(() => {
    const initialType: StepType = "setVariables";
    setStepForm({
      name: "",
      type: initialType,
      conversationEnabled: false,
      parameters: ensureParametersForStepType(initialType, []),
      tools: [],
    });
    setStepFormError(null);
    setStepOriginalName(null);
    setMode("create");
    setDialogTarget(null);
    setIsOpen(true);
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
            return {
              ...previous,
              type: nextType,
              parameters: nextParameters,
              conversationEnabled:
                nextType === "setVariables"
                  ? false
                  : previous.conversationEnabled,
              tools: nextType === "setVariables" ? [] : previous.tools ?? [],
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
            parameters: [...previous.parameters, createKeyValueEntry()],
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

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!stepForm || !draftDocument || !activeWorkflowId) {
        setStepFormError("Unable to update step — missing context.");
        return;
      }

      const trimmedName = stepForm.name.trim();
      const stepType = stepForm.type ?? DEFAULT_STEP_TYPE;

      if (!trimmedName) {
        setStepFormError("Step name is required.");
        return;
      }

      const parameters = recordFromEntries(stepForm.parameters);
      const conversation = stepForm.conversationEnabled
        ? { enabled: true }
        : undefined;
      const originalName = stepOriginalName ?? trimmedName;
      const uniqueTools = Array.from(new Set(stepForm.tools ?? [])).filter(
        (toolId) => toolId.trim().length > 0
      );

      if (mode === "create") {
        const duplicate = draftDocument.agents
          .find((candidate) => candidate.id === activeWorkflowId)
          ?.steps.some((step) => step.name === trimmedName);

        if (duplicate) {
          setStepFormError(
            "A step with this name already exists. Choose a different name or edit the existing step."
          );
          return;
        }
      }

      applyDocumentUpdate((draft) => {
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

        if (!conversation) {
          delete (updatedStep as Partial<AgentStepDefinition>).conversation;
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

      setStepFormError(null);
      reset();
    },
    [
      stepForm,
      draftDocument,
      activeWorkflowId,
      stepOriginalName,
      mode,
      applyDocumentUpdate,
      reset,
    ]
  );

  const handleDelete = useCallback(() => {
    if (!draftDocument || !activeWorkflowId || !stepOriginalName) {
      setStepFormError("Unable to delete step — missing context.");
      return;
    }

    applyDocumentUpdate((draft) => {
      const agent = draft.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent) {
        return draft;
      }

      const index = agent.steps.findIndex(
        (step) => step.name === stepOriginalName
      );

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

    setStepFormError(null);
    reset();
  }, [
    draftDocument,
    activeWorkflowId,
    stepOriginalName,
    applyDocumentUpdate,
    reset,
  ]);

  const title = useMemo(() => {
    if (mode === "create") {
      return "Create Step";
    }

    if (!dialogTarget) {
      return "Configure Step";
    }

    return `Configure Step “${
      dialogTarget.data.stepName ?? dialogTarget.data.label
    }”`;
  }, [mode, dialogTarget]);

  return {
    dialogProps: {
      open: isOpen,
      mode,
      title,
      stepForm,
      stepFormError,
      onClose: reset,
      onSubmit: handleSubmit,
      onFieldChange: handleFieldChange,
      onConversationToggle: handleConversationToggle,
      onAddParameter: handleAddParameter,
      onRemoveParameter: handleRemoveParameter,
      onParameterChange: handleParameterChange,
      availableTools,
      onToolToggle: handleToolToggle,
      onDelete: mode === "edit" ? handleDelete : undefined,
    },
    title,
    open: isOpen,
    openForEditing,
    openForCreation,
    openForVariableCreation,
    reset,
  };
}
