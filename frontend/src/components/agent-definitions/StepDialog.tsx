import { useState, type ChangeEvent, type FormEventHandler } from "react";

import { Maximize2 } from "lucide-react";
import { DialogShell } from "./DialogShell";
import { STEP_TYPE_OPTIONS, type StepFormState, type StepType } from "./types";

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
interface VariablePresetOption {
  value: string;
  label: string;
  description: string;
}

const VARIABLE_PRESET_PREFIX = "$preset:" as const;
const VARIABLE_PRESET_CUSTOM_OPTION = "__custom__" as const;
const VARIABLE_PRESET_OPTIONS: ReadonlyArray<VariablePresetOption> = [
  {
    value: `${VARIABLE_PRESET_PREFIX}CurrentDate`,
    label: "Current date",
    description: "Local date formatted as YYYY-MM-DD.",
  },
  {
    value: `${VARIABLE_PRESET_PREFIX}LocalDateTime`,
    label: "Local date & time",
    description: "Local timestamp in ISO 8601 format.",
  },
  {
    value: `${VARIABLE_PRESET_PREFIX}UtcDateTime`,
    label: "UTC date & time",
    description: "UTC timestamp in ISO 8601 format.",
  },
  {
    value: `${VARIABLE_PRESET_PREFIX}DayOfTheWeek`,
    label: "Day of the week",
    description: "Returns values like Monday, Tuesday, etc.",
  },
  {
    value: `${VARIABLE_PRESET_PREFIX}ConversationId`,
    label: "Conversation ID",
    description: "Uses the conversation ID for the current run.",
  },
];

function isVariablePresetValue(value: string | undefined) {
  return typeof value === "string" && value.startsWith(VARIABLE_PRESET_PREFIX);
}

function getVariablePresetSelection(value: string | undefined) {
  return isVariablePresetValue(value) ? value! : VARIABLE_PRESET_CUSTOM_OPTION;
}

function getVariablePresetDetails(value: string) {
  return VARIABLE_PRESET_OPTIONS.find((option) => option.value === value);
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
  const isVariableStep = stepForm?.type === "setVariables";
  const supportsConversation = !isVariableStep;
  const supportsTools = !isVariableStep;

  const formatStepTypeLabel = (option: StepType) => {
    switch (option) {
      case "pass-through":
        return "Pass-through";
      case "setVariables":
        return "Set variables";
      default:
        return option.charAt(0).toUpperCase() + option.slice(1);
    }
  };

  const parameterHeading = isVariableStep ? "Variables" : "Parameters";
  const addParameterLabel = isVariableStep ? "Add variable" : "Add parameter";
  const emptyParametersText = isVariableStep
    ? "No variables defined yet. Use the button above to add key/value pairs."
    : "No parameters defined for this step type.";

  const handleVariablePresetChange = (entryId: string, selection: string) => {
    const handler = onParameterChange(entryId, "value");
    const nextValue =
      selection === VARIABLE_PRESET_CUSTOM_OPTION ? "" : selection;
    handler({ target: { value: nextValue } } as ChangeEvent<HTMLInputElement>);
  };

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
                    {formatStepTypeLabel(option)}
                  </option>
                ))}
              </select>
            </div>

            {supportsConversation ? (
              <label className="flex items-center gap-2 text-sm text-foreground/80">
                <input
                  type="checkbox"
                  checked={stepForm.conversationEnabled}
                  onChange={onConversationToggle}
                  className="h-4 w-4 rounded border-border"
                />
                Conversation enabled
              </label>
            ) : null}

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase text-foreground/60">
                  {parameterHeading}
                </span>
                <button
                  type="button"
                  className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                  onClick={() => onAddParameter()}
                >
                  {addParameterLabel}
                </button>
              </div>

              {stepForm.parameters.length === 0 ? (
                <p className="text-sm text-foreground/60">
                  {emptyParametersText}
                </p>
              ) : (
                <div className="space-y-2">
                  {stepForm.parameters.map((entry) => {
                    if (isVariableStep) {
                      const selection = getVariablePresetSelection(entry.value);
                      const isCustomValue =
                        selection === VARIABLE_PRESET_CUSTOM_OPTION;
                      const presetDetails = getVariablePresetDetails(selection);

                      return (
                        <div
                          key={entry.id}
                          className="space-y-3 rounded-md border border-border/70 bg-muted/10 p-3"
                        >
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                            <input
                              type="text"
                              placeholder="Variable name"
                              value={entry.key}
                              onChange={onParameterChange(entry.id, "key")}
                              className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            />
                            <button
                              type="button"
                              className="rounded-md border border-border px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
                              onClick={() => onRemoveParameter(entry.id)}
                            >
                              Remove
                            </button>
                          </div>

                          <div className="flex flex-col gap-2">
                            <label className="text-xs font-semibold uppercase text-foreground/60">
                              Value source
                            </label>
                            <select
                              value={selection}
                              onChange={(event) =>
                                handleVariablePresetChange(
                                  entry.id,
                                  event.target.value
                                )
                              }
                              className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                              <option value={VARIABLE_PRESET_CUSTOM_OPTION}>
                                Custom value
                              </option>
                              {VARIABLE_PRESET_OPTIONS.map((option) => (
                                <option key={option.value} value={option.value}>
                                  {option.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          {isCustomValue ? (
                            <div className="flex flex-col gap-2">
                              <label className="text-xs font-semibold uppercase text-foreground/60">
                                Custom value
                              </label>
                              <div className="flex gap-2">
                                <input
                                  type="text"
                                  placeholder="Value"
                                  value={entry.value}
                                  onChange={onParameterChange(
                                    entry.id,
                                    "value"
                                  )}
                                  className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                                <button
                                  type="button"
                                  className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                                  onClick={() => {
                                    setExpandedParamId(entry.id);
                                    setExpandedParamValue(entry.value ?? "");
                                  }}
                                >
                                  <Maximize2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="rounded-md border border-dashed border-border/70 bg-background/60 px-3 py-2 text-sm text-foreground/70">
                              {presetDetails?.description ? (
                                <span>{presetDetails.description}</span>
                              ) : (
                                <span>
                                  {presetDetails?.label ?? "Preset value"} will
                                  be provided when the workflow runs.
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    }

                    return (
                      <div
                        key={entry.id}
                        className="grid grid-cols-[1fr_auto_1fr_auto_auto] items-center gap-2"
                      >
                        <input
                          type="text"
                          placeholder="Parameter name"
                          value={entry.key}
                          onChange={onParameterChange(entry.id, "key")}
                          className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <span className="text-center text-xs text-foreground/60">
                          =
                        </span>
                        <input
                          type="text"
                          placeholder="Value"
                          value={entry.value}
                          onChange={onParameterChange(entry.id, "value")}
                          className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <button
                          type="button"
                          className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
                          onClick={() => {
                            setExpandedParamId(entry.id);
                            setExpandedParamValue(entry.value ?? "");
                          }}
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
                    );
                  })}
                </div>
              )}
              {isVariableStep ? (
                <p className="text-xs text-foreground/60">
                  Reference variables later with placeholders like{" "}
                  {"{{var.name}}"}.
                </p>
              ) : null}
            </div>

            {supportsTools && availableTools.length > 0 ? (
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
