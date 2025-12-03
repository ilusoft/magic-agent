import {
  type ChangeEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { Info, MoreHorizontal } from "lucide-react";

import {
  type StepDialogBaseProps,
  StepDialogContainer,
  StepNameField,
  useExpandedValueEditor,
} from "./StepDialogShared";
import type { KeyValueEntry, WorkflowVariableDataType } from "../types";
import { ExpressionBuilderButton } from "../expression-builder/ExpressionBuilderDialog";
import { SimpleTooltip } from "../../SimpleTooltip";

interface VariablePresetOption {
  value: string;
  label: string;
  description: string;
}

function valueContainsRuntime(value: string | undefined) {
  if (!value) {
    return false;
  }

  return value.includes("{{") || value.startsWith("$preset:");
}

function validateValueForType(
  value: string | undefined,
  type: WorkflowVariableDataType,
  runtimeExpression: boolean
) {
  if (!value || type === "string" || runtimeExpression) {
    return null;
  }

  const trimmed = value.trim();

  if (!trimmed) {
    return null;
  }

  if (type === "number") {
    return Number.isFinite(Number(trimmed))
      ? null
      : "Enter a valid number (e.g., 3.14).";
  }

  if (type === "dateTime") {
    return Number.isNaN(Date.parse(trimmed))
      ? "Use an ISO 8601 timestamp (e.g., 2024-05-01T10:00:00Z)."
      : null;
  }

  if (type === "json") {
    try {
      JSON.parse(trimmed);
      return null;
    } catch {
      return "Provide valid JSON (object or array).";
    }
  }

  if (type === "boolean") {
    return ["true", "false"].includes(trimmed.toLowerCase())
      ? null
      : "Enter either true or false.";
  }

  return null;
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

const VARIABLE_TYPE_HELP_TEXT: Record<WorkflowVariableDataType, string> = {
  string:
    "Stores the exact text (including placeholders like {{input}}) without modifications.",
  number: "Parses a floating-point number (e.g., 42 or 3.14).",
  dateTime:
    "Parses ISO 8601 timestamps (e.g., 2024-05-01T10:00:00Z or local presets).",
  json: "Validates JSON objects/arrays and stores a normalized string.",
  boolean: "Accepts either true or false (case-insensitive).",
};

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
          onDataTypeChange={props.onParameterDataTypeChange}
          apiBaseUrl={props.apiBaseUrl}
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
  onDataTypeChange?: (entryId: string, type: WorkflowVariableDataType) => void;
  apiBaseUrl: string;
}

function VariableParameterSection({
  entries,
  workflowParameters,
  onAdd,
  onRemove,
  onParameterChange,
  onPresetChange,
  onExpandValue,
  onDataTypeChange,
  apiBaseUrl,
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
        <div className="max-h-[360px] overflow-y-auto rounded-md border border-border/70">
          <div className="grid grid-cols-[1.2fr_0.9fr_1.25fr_minmax(0,1.05fr)_auto] gap-3 border-b border-border/70 bg-muted/40 px-3 py-2 text-[11px] font-semibold uppercase text-foreground/60">
            <HeaderCell
              label="Name"
              tooltip="Reference via {{var.name}} in later steps."
            />
            <HeaderCell
              label="Type"
              tooltip="Determines how custom values are validated and stored."
            />
            <HeaderCell
              label="Preset"
              tooltip="Choose a preset or keep a custom value/expression."
            />
            <HeaderCell
              label="Value"
              tooltip="Enter a literal, placeholder, or expression."
            />
            <span className="text-right">Actions</span>
          </div>
          <div className="divide-y divide-border/70">
            {entries.map((entry) => (
              <VariableParameterRow
                key={entry.id}
                entry={entry}
                onParameterChange={onParameterChange}
                onPresetChange={onPresetChange}
                onExpandValue={onExpandValue}
                onRemove={onRemove}
                onDataTypeChange={onDataTypeChange}
                apiBaseUrl={apiBaseUrl}
              />
            ))}
          </div>
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
  onDataTypeChange?: (entryId: string, type: WorkflowVariableDataType) => void;
}

function VariableParameterRow({
  entry,
  onParameterChange,
  onPresetChange,
  onExpandValue,
  onRemove,
  onDataTypeChange,
  apiBaseUrl,
}: VariableParameterRowProps & { apiBaseUrl: string }) {
  const selection = getVariablePresetSelection(entry.value);
  const isCustomValue = selection === VARIABLE_PRESET_CUSTOM_OPTION;
  const presetDetails = getVariablePresetDetails(selection);
  const valueSourceLabel = isCustomValue
    ? "Custom value"
    : presetDetails?.label ?? "Preset value";
  const selectedType: WorkflowVariableDataType = entry.dataType ?? "string";
  const runtimeExpression = isCustomValue && valueContainsRuntime(entry.value);
  const validationError = isCustomValue
    ? validateValueForType(entry.value, selectedType, runtimeExpression)
    : null;
  const applyExpression = (nextValue: string) => {
    const handler = onParameterChange(entry.id, "value");
    handler({ target: { value: nextValue } } as ChangeEvent<HTMLInputElement>);
  };

  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const expressionBuilderOpenRef = useRef<(() => void) | null>(null);

  const updateMenuPosition = useCallback(() => {
    const anchor = menuButtonRef.current;
    if (!anchor) {
      return;
    }

    const rect = anchor.getBoundingClientRect();
    setMenuPosition({
      top: rect.bottom + window.scrollY + 8,
      left: rect.right + window.scrollX,
    });
  }, []);

  useEffect(() => {
    if (!menuOpen) {
      return undefined;
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target as Node;
      if (menuButtonRef.current?.contains(target)) {
        return;
      }
      if (menuRef.current?.contains(target)) {
        return;
      }
      setMenuOpen(false);
    };

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }

    updateMenuPosition();

    const handleReposition = () => updateMenuPosition();
    window.addEventListener("scroll", handleReposition, true);
    window.addEventListener("resize", handleReposition);

    return () => {
      window.removeEventListener("scroll", handleReposition, true);
      window.removeEventListener("resize", handleReposition);
    };
  }, [menuOpen, updateMenuPosition]);

  return (
    <>
      <ExpressionBuilderButton
        value={entry.value}
        onApply={applyExpression}
        apiBaseUrl={apiBaseUrl}
        renderTrigger={({ open }) => {
          expressionBuilderOpenRef.current = open;
          return null;
        }}
      />

      <div className="grid grid-cols-[1.2fr_0.9fr_1.25fr_minmax(0,1.05fr)_auto] items-start gap-1 px-3 py-3 text-sm">
        <div>
          <input
            type="text"
            placeholder="Variable name"
            value={entry.key}
            onChange={onParameterChange(entry.id, "key")}
            className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        {onDataTypeChange ? (
          <div>
            <select
              value={selectedType}
              onChange={(event) =>
                onDataTypeChange(
                  entry.id,
                  event.target.value as WorkflowVariableDataType
                )
              }
              className="w-full rounded-md border border-border bg-background px-1 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="string">String</option>
              <option value="number">Number</option>
              <option value="dateTime">Date &amp; Time</option>
              <option value="json">JSON</option>
              <option value="boolean">Boolean</option>
            </select>
          </div>
        ) : (
          <span className="text-xs text-foreground/60">String</span>
        )}

        <div>
          <select
            value={selection}
            onChange={(event) => onPresetChange(entry.id, event.target.value)}
            className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            title={valueSourceLabel}
          >
            <option value={VARIABLE_PRESET_CUSTOM_OPTION}>Custom value</option>
            {VARIABLE_PRESET_OPTIONS.map((option: VariablePresetOption) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          {isCustomValue ? (
            <>
              <input
                type="text"
                title={VARIABLE_TYPE_HELP_TEXT[selectedType]}
                placeholder="Value"
                value={entry.value}
                onChange={onParameterChange(entry.id, "value")}
                className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
              {validationError ? (
                <p className="mt-1 text-[11px] text-destructive">
                  {validationError}
                </p>
              ) : null}
            </>
          ) : (
            <div className="group rounded-md border border-dashed border-border/70 bg-background/60 px-1 py-1.5 text-xs text-foreground/70">
              <span
                className="line-clamp-1 break-all"
                title={
                  (presetDetails?.label ?? "Preset value") +
                  " will resolve during execution."
                }
              >
                {presetDetails?.label ?? "Preset value"} will resolve during
                execution.
              </span>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            ref={menuButtonRef}
            className="rounded-md border border-border px-2 py-1 mt-0.5 text-xs text-foreground/70 hover:bg-muted"
            onClick={() => {
              if (menuOpen) {
                setMenuOpen(false);
              } else {
                updateMenuPosition();
                setMenuOpen(true);
              }
            }}
            aria-label="Variable actions"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>

          {menuOpen && menuPosition && typeof document !== "undefined"
            ? createPortal(
                <div
                  ref={menuRef}
                  className="z-[9999] w-48 rounded-md border border-border/80 bg-popover text-sm shadow-lg"
                  style={{
                    position: "fixed",
                    top: menuPosition.top,
                    left: menuPosition.left,
                    transform: "translateX(-100%)",
                  }}
                >
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-sm text-foreground/80 hover:bg-muted"
                    onClick={() => {
                      expressionBuilderOpenRef.current?.();
                      setMenuOpen(false);
                    }}
                  >
                    Open expression builder
                  </button>
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-sm text-foreground/80 hover:bg-muted"
                    onClick={() => {
                      setMenuOpen(false);
                      onExpandValue(entry.id, entry.value);
                    }}
                  >
                    Expand value editor
                  </button>
                  <button
                    type="button"
                    className="block w-full px-3 py-2 text-left text-sm text-destructive hover:bg-destructive/10"
                    onClick={() => {
                      setMenuOpen(false);
                      onRemove(entry.id);
                    }}
                  >
                    Remove variable
                  </button>
                </div>,
                document.body
              )
            : null}
        </div>
      </div>
    </>
  );
}

function HeaderCell({ label, tooltip }: { label: string; tooltip?: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2">
      {label}
      {tooltip ? (
        <SimpleTooltip content={tooltip}>
          <Info className="h-3 w-3 text-foreground/60" aria-hidden="true" />
        </SimpleTooltip>
      ) : null}
    </span>
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
