import type { ChangeEventHandler, FormEventHandler } from "react";

import { DialogShell } from "./DialogShell";
import type { OutcomeFormState } from "./types";

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
    field: "name" | "nextStep" | "conditionType"
  ) => ChangeEventHandler<HTMLInputElement | HTMLSelectElement>;
  onEndWorkflowToggle: ChangeEventHandler<HTMLInputElement>;
  onAddConditionParameter: () => void;
  onRemoveConditionParameter: (entryId: string) => void;
  onConditionParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => ChangeEventHandler<HTMLInputElement>;
  onDelete?: () => void;
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
  onAddConditionParameter,
  onRemoveConditionParameter,
  onConditionParameterChange,
  onDelete,
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

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-foreground/60">
                Condition
              </span>
              <button
                type="button"
                className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                onClick={onAddConditionParameter}
              >
                Add parameter
              </button>
            </div>

            <div className="space-y-2">
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold uppercase text-foreground/60">
                  Condition Type
                </label>
                <select
                  value={outcomeForm.conditionType}
                  onChange={onFieldChange("conditionType")}
                  className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Default (always)</option>
                  <option value="always">Always (no condition)</option>
                  <option value="contains">Contains</option>
                  <option value="equals">Equals</option>
                  <option value="startswith">Starts with</option>
                  <option value="endswith">Ends with</option>
                  <option value="notempty">Not empty</option>
                  <option value="empty">Empty</option>
                </select>
              </div>

              {outcomeForm.conditionParameters.length === 0 ? (
                <p className="text-xs text-foreground/60">
                  No condition parameters defined. Add one to provide additional
                  context for the condition.
                </p>
              ) : null}

              {outcomeForm.conditionParameters.map((entry) => (
                <div
                  key={entry.id}
                  className="grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2"
                >
                  <input
                    type="text"
                    value={entry.key}
                    onChange={onConditionParameterChange(entry.id, "key")}
                    className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Parameter key"
                  />
                  <span className="text-xs uppercase text-foreground/50">
                    →
                  </span>
                  <input
                    type="text"
                    value={entry.value}
                    onChange={onConditionParameterChange(entry.id, "value")}
                    className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Parameter value"
                  />
                  <button
                    type="button"
                    className="rounded-md border border-border px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                    onClick={() => onRemoveConditionParameter(entry.id)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
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
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
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
