import { useCallback, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type {
  AgentDefinitionsDocument,
  AgentStepOutcomeDefinition,
} from "../../../types/agents";
import type { OutcomeFormState, WorkflowEdge } from "../types";
import {
  createKeyValueEntry,
  entriesFromRecord,
  recordFromEntries,
} from "../util";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseOutcomeDialogOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
}

interface OutcomeDialogBindings {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  outcomeForm: OutcomeFormState | null;
  outcomeFormError: string | null;
  availableSteps: string[];
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onFieldChange: (
    field: "name" | "nextStep" | "conditionType"
  ) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  onEndWorkflowToggle: (event: ChangeEvent<HTMLInputElement>) => void;
  onAddConditionParameter: () => void;
  onRemoveConditionParameter: (entryId: string) => void;
  onConditionParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  onDelete?: () => void;
}

interface UseOutcomeDialogResult {
  dialogProps: OutcomeDialogBindings;
  openForEdge: (edge: WorkflowEdge) => void;
  openForCreation: (
    sourceStep: string,
    overrides?: Partial<OutcomeFormState>
  ) => void;
  reset: () => void;
}

export function useOutcomeDialog({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
}: UseOutcomeDialogOptions): UseOutcomeDialogResult {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("edit");
  const [dialogTarget, setDialogTarget] = useState<WorkflowEdge | null>(null);
  const [outcomeForm, setOutcomeForm] = useState<OutcomeFormState | null>(null);
  const [outcomeFormError, setOutcomeFormError] = useState<string | null>(null);

  const availableSteps = useMemo(() => {
    if (!draftDocument || !activeWorkflowId) {
      return [] as string[];
    }

    const agent = draftDocument.agents.find(
      (candidate) => candidate.id === activeWorkflowId
    );
    return agent ? agent.steps.map((step) => step.name) : [];
  }, [draftDocument, activeWorkflowId]);

  const reset = useCallback(() => {
    setIsOpen(false);
    setMode("edit");
    setDialogTarget(null);
    setOutcomeForm(null);
    setOutcomeFormError(null);
  }, []);

  const buildOutcomeFormState = useCallback(
    (
      sourceStep: string,
      outcome: AgentStepOutcomeDefinition | null
    ): OutcomeFormState => {
      return {
        sourceStep,
        name: outcome?.name ?? "",
        nextStep: outcome?.nextStep ?? "",
        endWorkflow: outcome?.endWorkflow ?? false,
        conditionType: outcome?.condition?.type ?? "",
        conditionParameters: entriesFromRecord(outcome?.condition?.parameters),
      };
    },
    []
  );

  const openForEdge = useCallback(
    (edge: WorkflowEdge) => {
      setDialogTarget(edge);

      if (!draftDocument || !activeWorkflowId) {
        setOutcomeForm(null);
        setOutcomeFormError("Unable to update outcome — missing context.");
        setMode("edit");
        setIsOpen(true);
        return;
      }

      const sourceStep = edge.data?.sourceStep;
      if (!sourceStep) {
        setOutcomeForm(null);
        setOutcomeFormError(
          "Unable to determine source step for this outcome."
        );
        setMode("edit");
        setIsOpen(true);
        return;
      }

      const agent = draftDocument.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );
      if (!agent) {
        setOutcomeForm(null);
        setOutcomeFormError("Unable to locate agent for this workflow.");
        setMode("edit");
        setIsOpen(true);
        return;
      }

      const step = agent.steps.find(
        (candidate) => candidate.name === sourceStep
      );
      if (!step) {
        setOutcomeForm(null);
        setOutcomeFormError("Unable to locate step for this outcome.");
        setMode("edit");
        setIsOpen(true);
        return;
      }

      const existingOutcome = step.outcomes?.find(
        (candidate) => candidate.name === edge.data?.outcomeName
      );
      setMode(existingOutcome ? "edit" : "create");
      setOutcomeForm(
        buildOutcomeFormState(sourceStep, existingOutcome ?? null)
      );
      setOutcomeFormError(null);
      setIsOpen(true);
    },
    [draftDocument, activeWorkflowId, buildOutcomeFormState]
  );

  const openForCreation = useCallback(
    (sourceStep: string, overrides?: Partial<OutcomeFormState>) => {
      setDialogTarget(null);

      if (!draftDocument || !activeWorkflowId) {
        setOutcomeForm(null);
        setOutcomeFormError("Unable to create outcome — missing context.");
        setMode("create");
        setIsOpen(true);
        return;
      }

      const agent = draftDocument.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent) {
        setOutcomeForm(null);
        setOutcomeFormError("Unable to locate agent for this workflow.");
        setMode("create");
        setIsOpen(true);
        return;
      }

      const step = agent.steps.find(
        (candidate) => candidate.name === sourceStep
      );

      if (!step) {
        setOutcomeForm(null);
        setOutcomeFormError("Unable to locate the selected source step.");
        setMode("create");
        setIsOpen(true);
        return;
      }

      const baseForm = buildOutcomeFormState(step.name, null);
      const mergedForm: OutcomeFormState = {
        ...baseForm,
        ...overrides,
        conditionParameters:
          overrides?.conditionParameters ?? baseForm.conditionParameters,
      };

      setMode("create");
      setOutcomeForm(mergedForm);
      setOutcomeFormError(null);
      setIsOpen(true);
    },
    [draftDocument, activeWorkflowId, buildOutcomeFormState]
  );

  const handleFieldChange = useCallback(
    (field: "name" | "nextStep" | "conditionType") =>
      (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const value = event.target.value;
        setOutcomeForm((previous) =>
          previous ? { ...previous, [field]: value } : previous
        );
      },
    []
  );

  const handleEndWorkflowToggle = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const checked = event.target.checked;
      setOutcomeForm((previous) =>
        previous
          ? {
              ...previous,
              endWorkflow: checked,
              nextStep: checked ? "" : previous.nextStep,
            }
          : previous
      );
    },
    []
  );

  const handleAddConditionParameter = useCallback(() => {
    setOutcomeForm((previous) =>
      previous
        ? {
            ...previous,
            conditionParameters: [
              ...previous.conditionParameters,
              createKeyValueEntry(),
            ],
          }
        : previous
    );
  }, []);

  const handleRemoveConditionParameter = useCallback((entryId: string) => {
    setOutcomeForm((previous) => {
      if (!previous) {
        return previous;
      }

      return {
        ...previous,
        conditionParameters: previous.conditionParameters.filter(
          (entry) => entry.id !== entryId
        ),
      };
    });
  }, []);

  const handleConditionParameterChange = useCallback(
    (entryId: string, field: "key" | "value") =>
      (event: ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setOutcomeForm((previous) => {
          if (!previous) {
            return previous;
          }

          return {
            ...previous,
            conditionParameters: previous.conditionParameters.map((entry) =>
              entry.id === entryId ? { ...entry, [field]: value } : entry
            ),
          };
        });
      },
    []
  );

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!outcomeForm || !draftDocument || !activeWorkflowId) {
        setOutcomeFormError("Unable to update outcome — missing context.");
        return;
      }

      const trimmedName = outcomeForm.name.trim();

      if (!trimmedName) {
        setOutcomeFormError("Outcome name is required.");
        return;
      }

      if (!outcomeForm.endWorkflow && !outcomeForm.nextStep.trim()) {
        setOutcomeFormError(
          "Select a next step or mark the outcome as ending the workflow."
        );
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        const step = agent.steps.find(
          (candidate) => candidate.name === outcomeForm.sourceStep
        );

        if (!step) {
          return draft;
        }

        step.outcomes = step.outcomes ?? [];

        const conditionParameters = recordFromEntries(
          outcomeForm.conditionParameters
        );
        const hasConditionParameters =
          Object.keys(conditionParameters).length > 0;
        const condition =
          outcomeForm.conditionType.trim() || hasConditionParameters
            ? {
                type: outcomeForm.conditionType.trim() || undefined,
                parameters: hasConditionParameters
                  ? conditionParameters
                  : undefined,
              }
            : undefined;

        const updatedOutcome: AgentStepOutcomeDefinition = {
          name: trimmedName,
          nextStep: outcomeForm.endWorkflow
            ? undefined
            : outcomeForm.nextStep.trim() || undefined,
          endWorkflow: outcomeForm.endWorkflow || undefined,
          condition,
        };

        if (!updatedOutcome.endWorkflow) {
          delete (updatedOutcome as Partial<AgentStepOutcomeDefinition>)
            .endWorkflow;
        }

        if (
          updatedOutcome.condition &&
          (!updatedOutcome.condition.parameters ||
            Object.keys(updatedOutcome.condition.parameters).length === 0)
        ) {
          delete updatedOutcome.condition.parameters;
        }

        if (mode === "edit") {
          const existingIndex = step.outcomes.findIndex(
            (candidate) =>
              candidate.name ===
              (dialogTarget?.data?.outcomeName ?? trimmedName)
          );

          if (existingIndex >= 0) {
            step.outcomes[existingIndex] = updatedOutcome;
          } else {
            step.outcomes.push(updatedOutcome);
          }
        } else {
          step.outcomes.push(updatedOutcome);
        }

        step.outcomes = step.outcomes.map((candidate) => ({
          ...candidate,
          name: candidate.name.trim(),
        }));

        return draft;
      });

      setOutcomeFormError(null);
      reset();
    },
    [
      outcomeForm,
      draftDocument,
      activeWorkflowId,
      mode,
      dialogTarget,
      applyDocumentUpdate,
      reset,
    ]
  );

  const handleDelete = useCallback(() => {
    if (
      !draftDocument ||
      !activeWorkflowId ||
      !dialogTarget?.data?.outcomeName ||
      !dialogTarget.data?.sourceStep
    ) {
      setOutcomeFormError("Unable to delete outcome — missing context.");
      return;
    }

    applyDocumentUpdate((draft) => {
      const agent = draft.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent) {
        return draft;
      }

      const step = agent.steps.find(
        (candidate) => candidate.name === dialogTarget.data!.sourceStep
      );

      if (!step || !Array.isArray(step.outcomes)) {
        return draft;
      }

      step.outcomes = step.outcomes.filter(
        (candidate) => candidate.name !== dialogTarget.data!.outcomeName
      );

      return draft;
    });

    setOutcomeFormError(null);
    reset();
  }, [
    draftDocument,
    activeWorkflowId,
    dialogTarget,
    applyDocumentUpdate,
    reset,
  ]);

  const title = useMemo(() => {
    if (mode === "create") {
      return "Create Outcome";
    }

    if (!dialogTarget) {
      return "Configure Outcome";
    }

    return `Configure Outcome “${
      dialogTarget.data?.outcomeName ?? dialogTarget.label ?? "outcome"
    }”`;
  }, [mode, dialogTarget]);

  return {
    dialogProps: {
      open: isOpen,
      mode,
      title,
      outcomeForm,
      outcomeFormError,
      availableSteps,
      onClose: reset,
      onSubmit: handleSubmit,
      onFieldChange: handleFieldChange,
      onEndWorkflowToggle: handleEndWorkflowToggle,
      onAddConditionParameter: handleAddConditionParameter,
      onRemoveConditionParameter: handleRemoveConditionParameter,
      onConditionParameterChange: handleConditionParameterChange,
      onDelete: mode === "edit" ? handleDelete : undefined,
    },
    openForEdge,
    openForCreation,
    reset,
  };
}
