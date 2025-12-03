import type { ChangeEventHandler, FormEventHandler } from "react";

import { DialogShell } from "./DialogShell";
import { ExpressionBuilderButton } from "../agent-definitions/expression-builder/ExpressionBuilderDialog";
import type { ExpressionValidationState, OutcomeFormState } from "./types";

interface OutcomeDialogProps {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  outcomeForm: OutcomeFormState | null;
  outcomeFormError: string | null;
  availableSteps: string[];
  onClose: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onFieldChange: (
    field: "name" | "nextStep" | "order"
  ) => ChangeEventHandler<HTMLInputElement | HTMLSelectElement>;
  onEndWorkflowToggle: ChangeEventHandler<HTMLInputElement>;
  onExpressionChange: (value: string) => void;
  onDelete?: () => void;
  apiBaseUrl: string;
  expressionValidationState: ExpressionValidationState;
  saveDisabled?: boolean;
}

export function OutcomeDialog({
  open,
  mode,
  title,
  outcomeForm,
  outcomeFormError,
  availableSteps,
  onClose,
  onSubmit,
  onFieldChange,
  onEndWorkflowToggle,
  onExpressionChange,
  onDelete,
  apiBaseUrl,
  expressionValidationState,
  saveDisabled = false,
}: OutcomeDialogProps) {
  return (
    <DialogShell
      title={title}
      open={open}
      onClose={onClose}
      contentClassName="max-w-2xl"
    >
      {outcomeForm ? (
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Outcome Name
            </label>
            <input
              type="text"
              value={outcomeForm.name}
              onChange={onFieldChange("name")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Outcome name (e.g. success, failure)"
              aria-invalid={outcomeFormError ? true : undefined}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Evaluation Order
            </label>
            <input
              type="number"
              min={1}
              step={1}
              value={outcomeForm.order}
              onChange={onFieldChange("order")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="1"
            />
            <p className="text-xs text-foreground/60">
              Outcomes are evaluated from lowest order to highest before hitting
              a default "always" outcome.
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Next Step
            </label>
            <select
              value={outcomeForm.nextStep}
              onChange={onFieldChange("nextStep")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={outcomeForm.endWorkflow}
            >
              <option value="">— Select next step —</option>
              {availableSteps.map((step) => (
                <option key={step} value={step}>
                  {step}
                </option>
              ))}
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm text-foreground/80">
            <input
              type="checkbox"
              checked={outcomeForm.endWorkflow}
              onChange={onEndWorkflowToggle}
              className="h-4 w-4 rounded border-border"
            />
            End workflow when this outcome occurs
          </label>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-foreground/60">
                Expression
              </span>
              <ExpressionBuilderButton
                value={outcomeForm.expression}
                onApply={onExpressionChange}
                apiBaseUrl={apiBaseUrl}
                mode="direct"
                renderTrigger={({ open }) => (
                  <button
                    type="button"
                    className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                    onClick={open}
                  >
                    Open builder
                  </button>
                )}
              />
            </div>
            <textarea
              value={outcomeForm.expression}
              onChange={(event) => onExpressionChange(event.target.value)}
              className="h-24 w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder={`Example: contains(state.output, "ROUTE: research")`}
            />
            <p className="text-xs text-foreground/60">
              Expressions must evaluate to a boolean. Helper functions and
              workflow data are available inside the builder.
            </p>
            {expressionValidationState.status === "pending" ? (
              <p className="text-xs text-foreground/60">Validating…</p>
            ) : null}
            {expressionValidationState.status === "invalid" &&
            expressionValidationState.message ? (
              <p className="text-xs text-destructive">
                {expressionValidationState.message}
              </p>
            ) : null}
          </div>

          {outcomeFormError ? (
            <p className="text-sm text-destructive">{outcomeFormError}</p>
          ) : null}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm text-foreground/80 hover:bg-muted"
              onClick={onClose}
            >
              Cancel
            </button>
            {mode === "edit" && onDelete ? (
              <button
                type="button"
                className="rounded-md border border-destructive px-3 py-2 text-sm text-destructive hover:bg-destructive/10"
                onClick={onDelete}
              >
                Delete Outcome
              </button>
            ) : null}
            <button
              type="submit"
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-60"
              disabled={saveDisabled}
            >
              {mode === "create" ? "Create Outcome" : "Save Changes"}
            </button>
          </div>
        </form>
      ) : (
        <p className="text-sm text-destructive">
          Unable to load outcome details. Please close this dialog and try
          again.
        </p>
      )}
    </DialogShell>
  );
}
