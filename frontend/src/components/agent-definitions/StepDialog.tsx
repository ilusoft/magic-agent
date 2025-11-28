import {
  useState,
  type ChangeEventHandler,
  type FormEventHandler,
} from "react";

import { Maximize2 } from "lucide-react";
import { DialogShell } from "./DialogShell";
import { STEP_TYPE_OPTIONS, type StepFormState } from "./types";

interface StepDialogProps {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  stepForm: StepFormState | null;
  stepFormError: string | null;
  onClose: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onFieldChange: (
    field: "name" | "type"
  ) => ChangeEventHandler<HTMLInputElement | HTMLSelectElement>;
  onConversationToggle: ChangeEventHandler<HTMLInputElement>;
  onAddParameter: () => void;
  onRemoveParameter: (entryId: string) => void;
  onParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => ChangeEventHandler<HTMLInputElement>;
  availableTools: { id: string; label: string }[];
  onToolToggle: (toolId: string) => ChangeEventHandler<HTMLInputElement>;
  onDelete?: () => void;
}

export function StepDialog({
  open,
  mode,
  title,
  stepForm,
  stepFormError,
  onClose,
  onSubmit,
  onFieldChange,
  onConversationToggle,
  onAddParameter,
  onRemoveParameter,
  onParameterChange,
  availableTools,
  onToolToggle,
  onDelete,
}: StepDialogProps) {
  const [expandedParamId, setExpandedParamId] = useState<string | null>(null);
  const [expandedParamValue, setExpandedParamValue] = useState("");

  const handleExpandedSave = () => {
    if (!expandedParamId) {
      return;
    }

    const handler = onParameterChange(expandedParamId, "value");

    handler({ target: { value: expandedParamValue } } as any);
    setExpandedParamId(null);
    setExpandedParamValue("");
  };

  const handleExpandedClose = () => {
    setExpandedParamId(null);
    setExpandedParamValue("");
  };

  return (
    <>
      <DialogShell
        title={title}
        open={open}
        onClose={onClose}
        contentClassName="max-w-2xl"
      >
        {stepForm ? (
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase text-foreground/60">
                Step Name
              </label>
              <input
                type="text"
                value={stepForm.name}
                onChange={onFieldChange("name")}
                className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Enter step name"
                aria-invalid={stepFormError ? true : undefined}
              />
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-xs font-semibold uppercase text-foreground/60">
                Step Type
              </label>
              <select
                value={stepForm.type}
                onChange={onFieldChange("type")}
                className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                {STEP_TYPE_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option === "pass-through"
                      ? "Pass-through"
                      : option.charAt(0).toUpperCase() + option.slice(1)}
                  </option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 text-sm text-foreground/80">
              <input
                type="checkbox"
                checked={stepForm.conversationEnabled}
                onChange={onConversationToggle}
                className="h-4 w-4 rounded border-border"
              />
              Conversation enabled
            </label>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-foreground/60">
                  Parameters
                </span>
                <button
                  type="button"
                  className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                  onClick={() => onAddParameter()}
                >
                  Add parameter
                </button>
              </div>

              {stepForm.parameters.length === 0 ? (
                <p className="text-sm text-foreground/60">
                  No parameters defined for this step type.
                </p>
              ) : (
                <div className="space-y-2">
                  {stepForm.parameters.map((entry) => (
                    <div
                      key={entry.id}
                      className="grid grid-cols-[1fr_auto_1fr_auto_auto] items-center gap-2"
                    >
                      <input
                        type="text"
                        value={entry.key}
                        onChange={onParameterChange(entry.id, "key")}
                        className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        placeholder="Parameter key"
                      />
                      <span className="text-xs uppercase text-foreground/50">
                        →
                      </span>
                      <input
                        type="text"
                        value={entry.value}
                        onChange={onParameterChange(entry.id, "value")}
                        className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        placeholder="Parameter value"
                      />
                      <button
                        type="button"
                        className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-xs text-foreground/70 hover:bg-muted"
                        onClick={() => {
                          setExpandedParamId(entry.id);
                          setExpandedParamValue(entry.value ?? "");
                        }}
                        title="Expand value editor"
                      >
                        <Maximize2 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        className="rounded-md border border-border px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                        onClick={() => onRemoveParameter(entry.id)}
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {availableTools.length > 0 ? (
              <div className="space-y-2">
                <span className="text-xs font-semibold uppercase text-foreground/60">
                  Allowed Tools
                </span>
                <div className="flex flex-col gap-2">
                  {availableTools.map((tool) => (
                    <label
                      key={tool.id}
                      className="flex items-center gap-2 text-sm text-foreground/80"
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-border"
                        checked={stepForm.tools.includes(tool.id)}
                        onChange={onToolToggle(tool.id)}
                      />
                      <span className="truncate">{tool.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            ) : null}

            {stepFormError ? (
              <p className="text-sm text-destructive">{stepFormError}</p>
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
                  Delete Step
                </button>
              ) : null}
              <button
                type="submit"
                className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
              >
                {mode === "create" ? "Create Step" : "Save Changes"}
              </button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-destructive">
            Unable to load step details. Please close this dialog and try again.
          </p>
        )}
      </DialogShell>

      {expandedParamId ? (
        <DialogShell
          title="Edit Parameter Value"
          open={true}
          onClose={handleExpandedClose}
          contentClassName="max-w-3xl"
        >
          <div className="space-y-3">
            <textarea
              className="h-64 w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={expandedParamValue}
              onChange={(event) => setExpandedParamValue(event.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-2 text-sm text-foreground/80 hover:bg-muted"
                onClick={handleExpandedClose}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
                onClick={handleExpandedSave}
              >
                Save
              </button>
            </div>
          </div>
        </DialogShell>
      ) : null}
    </>
  );
}
