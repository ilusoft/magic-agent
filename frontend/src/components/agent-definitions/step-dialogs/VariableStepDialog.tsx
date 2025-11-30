import type { ChangeEvent } from "react";

import { Maximize2 } from "lucide-react";

import {
  type StepDialogBaseProps,
  StepDialogContainer,
  StepNameField,
  useExpandedValueEditor,
} from "./StepDialogShared";
import type { KeyValueEntry } from "../types";

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
] as const;

function isVariablePresetValue(value: string | undefined) {
  return typeof value === "string" && value.startsWith(VARIABLE_PRESET_PREFIX);
}

function getVariablePresetSelection(value: string | undefined) {
  return isVariablePresetValue(value) ? value! : VARIABLE_PRESET_CUSTOM_OPTION;
}

function getVariablePresetDetails(value: string) {
  return VARIABLE_PRESET_OPTIONS.find((option) => option.value === value);
}

export function VariableStepDialog(props: StepDialogBaseProps) {
  const expandedEditor = useExpandedValueEditor(props.onParameterChange);

  const handlePresetChange = (entryId: string, selection: string) => {
    const handler = props.onParameterChange(entryId, "value");
    const nextValue =
      selection === VARIABLE_PRESET_CUSTOM_OPTION ? "" : selection;
    handler({
      target: { value: nextValue },
    } as ChangeEvent<HTMLInputElement>);
  };

  return (
    <>
      <StepDialogContainer
        title={props.title}
        open={props.open}
        mode={props.mode}
        stepFormError={props.stepFormError}
        onClose={props.onClose}
        onSubmit={props.onSubmit}
        onDelete={props.onDelete}
      >
        <StepNameField
          value={props.stepForm.name}
          hasError={Boolean(props.stepFormError)}
          onChange={props.onFieldChange("name")}
        />
        <VariableParameterSection
          entries={props.stepForm.parameters}
          workflowParameters={props.workflowParameters}
          onAdd={props.onAddParameter}
          onRemove={props.onRemoveParameter}
          onParameterChange={props.onParameterChange}
          onPresetChange={handlePresetChange}
          onExpandValue={expandedEditor.open}
        />
      </StepDialogContainer>
      {expandedEditor.dialog}
    </>
  );
}

interface VariableParameterSectionProps {
  entries: KeyValueEntry[];
  workflowParameters: KeyValueEntry[];
  onAdd: () => void;
  onRemove: (entryId: string) => void;
  onParameterChange: StepDialogBaseProps["onParameterChange"];
  onPresetChange: (entryId: string, selection: string) => void;
  onExpandValue: (entryId: string, value: string | undefined) => void;
}

function VariableParameterSection({
  entries,
  workflowParameters,
  onAdd,
  onRemove,
  onParameterChange,
  onPresetChange,
  onExpandValue,
}: VariableParameterSectionProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-foreground/60">
          Variables
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
          onClick={onAdd}
        >
          Add variable
        </button>
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-foreground/60">
          No variables defined yet. Use the button above to add key/value pairs.
        </p>
      ) : (
        <div className="max-h-[320px] space-y-3 overflow-y-auto pr-1">
          {entries.map((entry) => (
            <VariableParameterRow
              key={entry.id}
              entry={entry}
              onParameterChange={onParameterChange}
              onPresetChange={onPresetChange}
              onExpandValue={onExpandValue}
              onRemove={onRemove}
            />
          ))}
        </div>
      )}

      <div className="max-h-[200px] overflow-y-auto pr-1">
        <VariableGuidance workflowParameters={workflowParameters} />
      </div>
    </div>
  );
}

interface VariableParameterRowProps {
  entry: KeyValueEntry;
  onParameterChange: StepDialogBaseProps["onParameterChange"];
  onPresetChange: (entryId: string, selection: string) => void;
  onExpandValue: (entryId: string, value: string | undefined) => void;
  onRemove: (entryId: string) => void;
}

function VariableParameterRow({
  entry,
  onParameterChange,
  onPresetChange,
  onExpandValue,
  onRemove,
}: VariableParameterRowProps) {
  const selection = getVariablePresetSelection(entry.value);
  const isCustomValue = selection === VARIABLE_PRESET_CUSTOM_OPTION;
  const presetDetails = getVariablePresetDetails(selection);

  return (
    <div className="space-y-3 rounded-md border border-border/70 bg-muted/10 p-3">
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
          onClick={() => onRemove(entry.id)}
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
          onChange={(event) => onPresetChange(entry.id, event.target.value)}
          className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value={VARIABLE_PRESET_CUSTOM_OPTION}>Custom value</option>
          {VARIABLE_PRESET_OPTIONS.map((option: VariablePresetOption) => (
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
              onChange={onParameterChange(entry.id, "value")}
              className="flex-1 rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="button"
              className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
              onClick={() => onExpandValue(entry.id, entry.value)}
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
              {presetDetails?.label ?? "Preset value"} will be provided when the
              workflow runs.
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function VariableGuidance({
  workflowParameters,
}: {
  workflowParameters: KeyValueEntry[];
}) {
  const availableParameters = workflowParameters.filter((entry) =>
    entry.key?.trim()
  );

  return (
    <div className="space-y-3 text-xs text-foreground/70">
      <p>
        Variable values support placeholders so you can override step parameters
        later without editing every step.
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <span className="font-semibold">Workflow parameters:</span> use tokens
          like{" "}
          <code className="rounded bg-muted px-1">{"{{param.apiKey}}"}</code>
          (available keys listed below).
        </li>
        <li>
          <span className="font-semibold">Previously set variables:</span>
          reference them with
          <code className="rounded bg-muted px-1">
            {"{{var.variableName}}"}
          </code>
          .
        </li>
        <li>
          <span className="font-semibold">Workflow context:</span>
          <code className="rounded bg-muted px-1">{"{{input}}"}</code>,
          <code className="rounded bg-muted px-1">{"{{lastOutput}}"}</code>, or
          any preset (current date, conversation id, etc.).
        </li>
      </ul>
      <div className="rounded-md border border-dashed border-border/70 bg-muted/30 p-3 text-xs">
        <p className="mb-2 font-semibold uppercase tracking-wider text-foreground/60">
          Workflow parameters
        </p>
        {availableParameters.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {availableParameters.map((param) => (
              <span
                key={param.id}
                className="rounded-full border border-border/70 bg-background/80 px-2 py-1 text-[11px] font-medium text-foreground/80"
              >
                {param.key}
              </span>
            ))}
          </div>
        ) : (
          <p>
            Define defaults in the workflow settings to make them available as
            <code>{"{{param.*}}"}</code> tokens.
          </p>
        )}
      </div>
    </div>
  );
}
