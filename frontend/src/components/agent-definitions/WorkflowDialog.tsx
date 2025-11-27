import type { ChangeEventHandler, FormEventHandler } from "react";
import { DialogShell } from "./DialogShell";
import type { WorkflowFormState } from "./types";

interface WorkflowDialogProps {
  open: boolean;
  title: string;
  workflowForm: WorkflowFormState | null;
  workflowFormError: string | null;
  onClose: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onFieldChange: (
    field: keyof WorkflowFormState
  ) => ChangeEventHandler<HTMLInputElement>;
  mode: "create" | "edit";
  onAddDefaultParameter: () => void;
  onDefaultParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => ChangeEventHandler<HTMLInputElement>;
  onRemoveDefaultParameter: (entryId: string) => void;
}

export function WorkflowDialog({
  open,
  title,
  workflowForm,
  workflowFormError,
  onClose,
  onSubmit,
  onFieldChange,
  mode,
  onAddDefaultParameter,
  onDefaultParameterChange,
  onRemoveDefaultParameter,
}: WorkflowDialogProps) {
  return (
    <DialogShell
      title={title}
      open={open}
      onClose={onClose}
      contentClassName="max-w-2xl"
    >
      {workflowForm ? (
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Workflow ID
            </label>
            <input
              type="text"
              value={workflowForm.id}
              onChange={onFieldChange("id")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="inventory-workflow"
              autoComplete="off"
              aria-invalid={workflowFormError ? true : undefined}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Display Name
            </label>
            <input
              type="text"
              value={workflowForm.name}
              onChange={onFieldChange("name")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="New Workflow"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Description
            </label>
            <input
              type="text"
              value={workflowForm.description}
              onChange={onFieldChange("description")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Optional description"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Endpoint
            </label>
            <input
              type="text"
              value={workflowForm.endpoint}
              onChange={onFieldChange("endpoint")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="https://..."
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Deployment
            </label>
            <input
              type="text"
              value={workflowForm.deployment}
              onChange={onFieldChange("deployment")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Model deployment (optional)"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              API Key
            </label>
            <input
              type="text"
              value={workflowForm.apiKey}
              onChange={onFieldChange("apiKey")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Optional API key"
              autoComplete="off"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase text-foreground/60">
                Default Parameters
              </span>
              <button
                type="button"
                className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                onClick={onAddDefaultParameter}
              >
                Add parameter
              </button>
            </div>

            {workflowForm.defaultParameters.length === 0 ? (
              <p className="text-xs text-foreground/60">
                No default parameters defined. Add one to provide model
                configuration values such as temperature or model name.
              </p>
            ) : null}

            <div className="space-y-2">
              {workflowForm.defaultParameters.map((entry) => (
                <div
                  key={entry.id}
                  className="grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2"
                >
                  <input
                    type="text"
                    value={entry.key}
                    onChange={onDefaultParameterChange(entry.id, "key")}
                    className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Parameter key"
                  />
                  <span className="text-xs uppercase text-foreground/50">
                    →
                  </span>
                  <input
                    type="text"
                    value={entry.value}
                    onChange={onDefaultParameterChange(entry.id, "value")}
                    className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    placeholder="Parameter value"
                  />
                  <button
                    type="button"
                    className="rounded-md border border-border px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                    onClick={() => onRemoveDefaultParameter(entry.id)}
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>

          {workflowFormError ? (
            <p className="text-sm text-destructive">{workflowFormError}</p>
          ) : null}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              className="rounded-md border border-border px-3 py-2 text-sm text-foreground/80 hover:bg-muted"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
            >
              {mode === "create" ? "Create Workflow" : "Save Changes"}
            </button>
          </div>
        </form>
      ) : null}
    </DialogShell>
  );
}
