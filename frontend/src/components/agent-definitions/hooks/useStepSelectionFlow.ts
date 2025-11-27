import { useCallback, useState } from "react";
import type { OutcomeFormState } from "../types";

interface StepSelectionBase {
  title: string;
  description: string;
  confirmLabel?: string;
}

type StepSelectionRequest =
  | (StepSelectionBase & {
      kind: "outcome" | "termination";
      overrides?: Partial<OutcomeFormState>;
    })
  | (StepSelectionBase & {
      kind: "start";
    });

interface UseStepSelectionFlowOptions {
  stepNames: string[];
  openStepDialogForCreation: () => void;
  setStartStep: (stepName: string) => void;
  openOutcomeDialogForCreation: (
    sourceStep: string,
    overrides?: Partial<OutcomeFormState>
  ) => void;
}

interface UseStepSelectionFlowResult {
  stepSelection: StepSelectionRequest | null;
  handleAddOutcome: () => void;
  handleAddTermination: () => void;
  handleAddStart: () => void;
  handleStepSelectionCancel: () => void;
  handleStepSelectionConfirm: (stepName: string) => void;
}

export function useStepSelectionFlow({
  stepNames,
  openStepDialogForCreation,
  setStartStep,
  openOutcomeDialogForCreation,
}: UseStepSelectionFlowOptions): UseStepSelectionFlowResult {
  const [stepSelection, setStepSelection] =
    useState<StepSelectionRequest | null>(null);

  const handleAddOutcome = useCallback(() => {
    if (stepNames.length === 0) {
      openStepDialogForCreation();
      return;
    }

    setStepSelection({
      kind: "outcome",
      title: "Add Outcome",
      description: "Select the step that should receive the new outcome.",
    });
  }, [stepNames, openStepDialogForCreation]);

  const handleAddTermination = useCallback(() => {
    if (stepNames.length === 0) {
      openStepDialogForCreation();
      return;
    }

    setStepSelection({
      kind: "termination",
      title: "Add Termination",
      description:
        "Select the step whose outcome should terminate the workflow.",
      overrides: {
        endWorkflow: true,
        nextStep: "",
      },
      confirmLabel: "Add termination",
    });
  }, [stepNames, openStepDialogForCreation]);

  const handleAddStart = useCallback(() => {
    if (stepNames.length === 0) {
      openStepDialogForCreation();
      return;
    }

    setStepSelection({
      kind: "start",
      title: "Set Start Step",
      description:
        "Choose which step should run first when the workflow starts.",
      confirmLabel: "Set as start",
    });
  }, [stepNames, openStepDialogForCreation]);

  const handleStepSelectionCancel = useCallback(() => {
    setStepSelection(null);
  }, []);

  const handleStepSelectionConfirm = useCallback(
    (stepName: string) => {
      if (!stepSelection) {
        return;
      }

      if (stepSelection.kind === "start") {
        setStepSelection(null);
        setStartStep(stepName);
        return;
      }

      const overrides: Partial<OutcomeFormState> = {
        ...stepSelection.overrides,
      };

      if (stepSelection.kind === "termination") {
        overrides.endWorkflow = true;
        overrides.nextStep = "";
      }

      setStepSelection(null);
      openOutcomeDialogForCreation(stepName, overrides);
    },
    [stepSelection, setStartStep, openOutcomeDialogForCreation]
  );

  return {
    stepSelection,
    handleAddOutcome,
    handleAddTermination,
    handleAddStart,
    handleStepSelectionCancel,
    handleStepSelectionConfirm,
  };
}
