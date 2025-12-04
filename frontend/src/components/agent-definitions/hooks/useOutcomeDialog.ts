import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type {
  AgentDefinitionsDocument,
  AgentDefinition,
  AgentStepDefinition,
  AgentStepOutcomeDefinition,
} from "../../../types/agents";
import type {
  ExpressionValidationContextPayload,
  ExpressionValidationContextValue,
  ExpressionValidationState,
  OutcomeFormState,
  WorkflowEdge,
} from "../types";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseOutcomeDialogOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
  apiBaseUrl: string;
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
    field: "name" | "nextStep" | "order"
  ) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  onEndWorkflowToggle: (event: ChangeEvent<HTMLInputElement>) => void;
  onExecuteByDefaultToggle: (event: ChangeEvent<HTMLInputElement>) => void;
  onExpressionChange: (value: string) => void;
  onDelete?: () => void;
  expressionValidationState: ExpressionValidationState;
  saveDisabled?: boolean;
}

interface UseOutcomeDialogResult {
  dialogProps: OutcomeDialogBindings & { apiBaseUrl: string };
  openForEdge: (edge: WorkflowEdge) => void;
  openForCreation: (
    sourceStep: string,
    overrides?: Partial<OutcomeFormState>
  ) => void;
  reset: () => void;
}

type ExpressionValidationResponse = {
  success: boolean;
  error?: string | null;
  errorCode?: string | null;
  resultKind?: string | null;
  referencedIdentifiers?: string[] | null;
};

export function useOutcomeDialog({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
  apiBaseUrl,
}: UseOutcomeDialogOptions): UseOutcomeDialogResult {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("edit");
  const [dialogTarget, setDialogTarget] = useState<WorkflowEdge | null>(null);
  const [outcomeForm, setOutcomeForm] = useState<OutcomeFormState | null>(null);
  const [outcomeFormError, setOutcomeFormError] = useState<string | null>(null);
  const [expressionValidationState, setExpressionValidationState] =
    useState<ExpressionValidationState>({
      status: "idle",
    });
  const validationRequestId = useRef(0);

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
    validationRequestId.current += 1;
    setExpressionValidationState({ status: "idle" });
  }, []);

  const validateExpression = useCallback(
    async (
      expression: string,
      context?: ExpressionValidationContextPayload
    ): Promise<ExpressionValidationResponse> => {
      const normalizedBase = apiBaseUrl.endsWith("/")
        ? apiBaseUrl.slice(0, -1)
        : apiBaseUrl;

      try {
        const response = await fetch(
          `${normalizedBase}/api/workflows/expressions/validate`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ expression, context }),
          }
        );

        if (!response.ok) {
          return {
            success: false,
            error: "Unable to validate expression. Please try again.",
            errorCode: "request_failed",
          };
        }

        const payload = (await response.json()) as ExpressionValidationResponse;
        return payload;
      } catch (error) {
        console.error("Expression validation failed", error);
        return {
          success: false,
          error: "Unable to validate expression due to a network error.",
          errorCode: "network_error",
        };
      }
    },
    [apiBaseUrl]
  );

  const scheduleExpressionValidation = useCallback(
    (expression: string, context?: ExpressionValidationContextPayload) => {
      const trimmed = expression.trim();
      const requestId = ++validationRequestId.current;

      if (!trimmed) {
        setExpressionValidationState({
          status: "invalid",
          message: "Provide a boolean expression.",
        });
        return;
      }

      setExpressionValidationState({ status: "pending" });

      validateExpression(trimmed, context).then((result) => {
        if (validationRequestId.current !== requestId) {
          return;
        }

        if (result.success) {
          setExpressionValidationState({ status: "valid" });
          return;
        }

        setExpressionValidationState({
          status: "invalid",
          message:
            result.error ?? "Expression must evaluate to a boolean value.",
        });
      });
    },
    [validateExpression]
  );

  const buildOutcomeFormState = useCallback(
    (
      sourceStep: string,
      outcome: AgentStepOutcomeDefinition | null,
      options?: { defaultOrder?: number }
    ): OutcomeFormState => {
      const resolvedOrder =
        outcome?.order !== undefined && outcome.order > 0
          ? outcome.order
          : options?.defaultOrder;

      return {
        sourceStep,
        name: outcome?.name ?? "",
        nextStep: outcome?.nextStep ?? "",
        endWorkflow: outcome?.endWorkflow ?? false,
        expression: outcome?.condition?.expression ?? "",
        order: resolvedOrder ? String(resolvedOrder) : "",
        executeByDefault: !Boolean(outcome?.condition?.expression),
      };
    },
    []
  );

  const computeNormalizedOrder = useCallback(
    (
      candidate: AgentStepOutcomeDefinition | null | undefined,
      index: number
    ) => {
      if (candidate?.order && candidate.order > 0) {
        return candidate.order;
      }

      return index + 1;
    },
    []
  );

  const computeNextOrderForStep = useCallback(
    (step: AgentStepDefinition) => {
      if (!Array.isArray(step.outcomes) || step.outcomes.length === 0) {
        return 1;
      }

      const normalizedOrders = step.outcomes.map((candidate, index) =>
        computeNormalizedOrder(candidate, index)
      );

      return Math.max(...normalizedOrders) + 1;
    },
    [computeNormalizedOrder]
  );

  const ensureUniqueOutcomeOrders = useCallback(
    (step: AgentStepDefinition, priorityOutcomeName: string) => {
      if (!Array.isArray(step.outcomes) || step.outcomes.length === 0) {
        return;
      }

      const positiveOrder = (
        candidate: AgentStepOutcomeDefinition | null | undefined
      ) =>
        candidate?.order && candidate.order > 0 ? candidate.order : undefined;

      let maxOrder = step.outcomes.reduce((highest, candidate) => {
        const candidateOrder = positiveOrder(candidate);
        return candidateOrder && candidateOrder > highest
          ? candidateOrder
          : highest;
      }, 0);

      const claimedOrders = new Set<number>();

      const assignNextOrder = (outcome: AgentStepOutcomeDefinition | null) => {
        if (!outcome) {
          return;
        }

        maxOrder = Math.max(maxOrder, 0) + 1;
        while (claimedOrders.has(maxOrder)) {
          maxOrder += 1;
        }

        outcome.order = maxOrder;
        claimedOrders.add(maxOrder);
      };

      const claimExistingOrder = (
        outcome: AgentStepOutcomeDefinition | null
      ): boolean => {
        if (!outcome) {
          return false;
        }

        const desired = positiveOrder(outcome);
        if (desired && !claimedOrders.has(desired)) {
          claimedOrders.add(desired);
          if (desired > maxOrder) {
            maxOrder = desired;
          }
          return true;
        }

        return false;
      };

      const priorityOutcome = step.outcomes.find(
        (candidate) => candidate?.name === priorityOutcomeName
      );

      if (priorityOutcome) {
        if (!claimExistingOrder(priorityOutcome)) {
          assignNextOrder(priorityOutcome);
        }
      }

      for (const outcome of step.outcomes) {
        if (!outcome) {
          continue;
        }

        if (priorityOutcome && outcome === priorityOutcome) {
          continue;
        }

        if (claimExistingOrder(outcome)) {
          continue;
        }

        assignNextOrder(outcome);
      }
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

      const existingOutcomeIndex = step.outcomes?.findIndex(
        (candidate) => candidate.name === edge.data?.outcomeName
      );
      const existingOutcome =
        existingOutcomeIndex !== undefined && existingOutcomeIndex >= 0
          ? step.outcomes?.[existingOutcomeIndex] ?? null
          : null;
      setMode(existingOutcome ? "edit" : "create");
      setOutcomeForm(
        buildOutcomeFormState(sourceStep, existingOutcome ?? null, {
          defaultOrder:
            existingOutcomeIndex !== undefined && existingOutcomeIndex >= 0
              ? existingOutcomeIndex + 1
              : undefined,
        })
      );
      setOutcomeFormError(null);
      setIsOpen(true);
    },
    [draftDocument, activeWorkflowId, buildOutcomeFormState]
  );

  const buildValidationContext = useCallback(
    (
      agent: AgentDefinition,
      sourceStepName?: string
    ): ExpressionValidationContextPayload => {
      const payload: ExpressionValidationContextPayload = {
        runtimeState: {
          output: { type: "string", value: "" },
          stepName: { type: "string", value: sourceStepName ?? "" },
          stepType: { type: "string", value: "" },
        },
        stepInput: { type: "string", value: "" },
        lastStepOutput: { type: "string", value: "" },
      };

      const variables: Record<string, ExpressionValidationContextValue> = {};
      agent.steps.forEach((step) => {
        const declared = step.variableTypes ?? {};
        Object.entries(declared).forEach(([name, type]) => {
          if (variables[name]) {
            return;
          }

          const value =
            step.type === "setVariables" ? step.parameters?.[name] : undefined;

          variables[name] = {
            type,
            value,
          };
        });
      });

      if (Object.keys(variables).length > 0) {
        payload.variables = variables;
      }

      const parameterEntries: Record<string, ExpressionValidationContextValue> =
        {};
      Object.entries(agent.defaultParameters ?? {}).forEach(([name, value]) => {
        parameterEntries[name] = { type: "string", value };
      });

      if (sourceStepName) {
        const sourceStep = agent.steps.find(
          (candidate) => candidate.name === sourceStepName
        );

        if (sourceStep) {
          Object.entries(sourceStep.parameters ?? {}).forEach(
            ([name, value]) => {
              parameterEntries[name] = { type: "string", value };
            }
          );

          if (payload.runtimeState) {
            payload.runtimeState.stepType = {
              type: "string",
              value: sourceStep.type ?? "",
            };
          }
        }
      }

      if (Object.keys(parameterEntries).length > 0) {
        payload.parameters = parameterEntries;
      }

      return payload;
    },
    []
  );

  const validationContext = useMemo(() => {
    if (!draftDocument || !activeWorkflowId || !outcomeForm) {
      return undefined;
    }

    const agent = draftDocument.agents.find(
      (candidate) => candidate.id === activeWorkflowId
    );

    if (!agent) {
      return undefined;
    }

    return buildValidationContext(agent, outcomeForm.sourceStep);
  }, [draftDocument, activeWorkflowId, outcomeForm, buildValidationContext]);

  useEffect(() => {
    if (!isOpen || !outcomeForm) {
      return;
    }

    if (outcomeForm.executeByDefault) {
      if (expressionValidationState.status !== "valid") {
        setExpressionValidationState({ status: "valid" });
      }
      return;
    }

    if (expressionValidationState.status !== "idle") {
      return;
    }

    scheduleExpressionValidation(
      outcomeForm.expression ?? "",
      validationContext
    );
  }, [
    isOpen,
    outcomeForm,
    expressionValidationState.status,
    scheduleExpressionValidation,
    validationContext,
  ]);

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

      const nextOrder = computeNextOrderForStep(step);
      const baseForm = buildOutcomeFormState(step.name, null, {
        defaultOrder: nextOrder,
      });
      const mergedForm: OutcomeFormState = {
        ...baseForm,
        ...overrides,
        order: overrides?.order ?? baseForm.order,
        executeByDefault:
          overrides?.executeByDefault ?? baseForm.executeByDefault,
      };

      setMode("create");
      setOutcomeForm(mergedForm);
      validationRequestId.current += 1;
      setExpressionValidationState({ status: "idle" });
      setOutcomeFormError(null);
      setIsOpen(true);
    },
    [draftDocument, activeWorkflowId, buildOutcomeFormState]
  );

  const handleFieldChange = useCallback(
    (field: "name" | "nextStep" | "order") =>
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

  const handleExpressionChange = useCallback(
    (value: string) => {
      setOutcomeForm((previous) => {
        if (!previous) {
          return previous;
        }

        const next = { ...previous, expression: value };
        if (!next.executeByDefault) {
          scheduleExpressionValidation(value, validationContext);
        }

        return next;
      });
    },
    [scheduleExpressionValidation, validationContext]
  );

  const handleExecuteByDefaultToggle = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const checked = event.target.checked;
      validationRequestId.current += 1;
      setOutcomeForm((previous) =>
        previous ? { ...previous, executeByDefault: checked } : previous
      );

      if (checked) {
        setExpressionValidationState({ status: "valid" });
        return;
      }

      setExpressionValidationState({ status: "idle" });
      scheduleExpressionValidation(
        outcomeForm?.expression ?? "",
        validationContext
      );
    },
    [scheduleExpressionValidation, validationContext, outcomeForm]
  );

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
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

      const trimmedExpression = outcomeForm.expression.trim();
      const requiresExpression = !outcomeForm.executeByDefault;

      if (requiresExpression && !trimmedExpression) {
        setOutcomeFormError("Provide a boolean expression for this outcome.");
        return;
      }

      const trimmedOrder = outcomeForm.order.trim();
      const parsedOrder = Number.parseInt(trimmedOrder, 10);

      if (!trimmedOrder || Number.isNaN(parsedOrder) || parsedOrder <= 0) {
        setOutcomeFormError("Outcome order must be a positive integer.");
        return;
      }

      if (requiresExpression && expressionValidationState.status !== "valid") {
        setOutcomeFormError(
          expressionValidationState.message ??
            "Expression must evaluate to a boolean value."
        );
        return;
      }

      if (requiresExpression) {
        const validation = await validateExpression(
          trimmedExpression,
          validationContext
        );

        if (!validation.success) {
          setOutcomeFormError(
            validation.error ?? "Expression must evaluate to a boolean value."
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

        const step = agent.steps.find(
          (candidate) => candidate.name === outcomeForm.sourceStep
        );

        if (!step) {
          return draft;
        }

        step.outcomes = step.outcomes ?? [];

        const updatedOutcome: AgentStepOutcomeDefinition = {
          name: trimmedName,
          nextStep: outcomeForm.endWorkflow
            ? undefined
            : outcomeForm.nextStep.trim() || undefined,
          endWorkflow: outcomeForm.endWorkflow || undefined,
          order: parsedOrder,
        };

        if (requiresExpression) {
          updatedOutcome.condition = {
            expression: trimmedExpression,
          };
        } else {
          delete (updatedOutcome as Partial<AgentStepOutcomeDefinition>)
            .condition;
        }

        if (!updatedOutcome.endWorkflow) {
          delete (updatedOutcome as Partial<AgentStepOutcomeDefinition>)
            .endWorkflow;
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

        ensureUniqueOutcomeOrders(step, trimmedName);

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
      computeNormalizedOrder,
      ensureUniqueOutcomeOrders,
      expressionValidationState,
      validationContext,
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
      onExecuteByDefaultToggle: handleExecuteByDefaultToggle,
      onExpressionChange: handleExpressionChange,
      onDelete: mode === "edit" ? handleDelete : undefined,
      apiBaseUrl,
      expressionValidationState,
      saveDisabled:
        !outcomeForm ||
        (!outcomeForm.executeByDefault &&
          expressionValidationState.status !== "valid"),
    },
    openForEdge,
    openForCreation,
    reset,
  };
}
