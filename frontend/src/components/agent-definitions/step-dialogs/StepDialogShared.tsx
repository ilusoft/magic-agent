import {
  type ChangeEvent,
  type FormEventHandler,
  type ReactNode,
} from "react";

import { Maximize2 } from "lucide-react";

import { ExpressionBuilderButton } from "@/components/agent-definitions/expression-builder/ExpressionBuilderDialog";
import { DialogShell } from "@/components/agent-definitions/DialogShell";
import { useExpandedValueEditor } from "@/components/agent-definitions/step-dialogs/useExpandedValueEditor";
import {
  type KeyValueEntry,
  type StepFormState,
  type WorkflowVariableDataType,
} from "@/components/agent-definitions/types";

export interface StepDialogBaseProps {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  stepForm: StepFormState;
  stepFormError: string | null;
  workflowParameters: KeyValueEntry[];
  apiBaseUrl: string;
  onClose: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onFieldChange: (
    field: "name" | "type"
  ) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  onConversationToggle: (event: ChangeEvent<HTMLInputElement>) => void;
  onAddParameter: () => void;
  onRemoveParameter: (entryId: string) => void;
  onMoveParameter?: (entryId: string, direction: "up" | "down") => void;
  onParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  onParameterDataTypeChange?: (
    entryId: string,
    dataType: WorkflowVariableDataType
  ) => void;
  availableTools: { id: string; label: string }[];
  onToolToggle: (
    toolId: string
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  onDelete?: () => void;
}

export interface StandardStepDialogProps extends StepDialogBaseProps {
  showConversationToggle?: boolean;
  showTools?: boolean;
  showParameters?: boolean;
}

export interface ParameterListProps {
  entries: KeyValueEntry[];
  onAdd: () => void;
  onRemove: (entryId: string) => void;
  onParameterChange: StepDialogBaseProps["onParameterChange"];
  onExpandValue: (entryId: string, value: string | undefined) => void;
  apiBaseUrl: string;
}

export function StepDialogContainer({
  title,
  open,
  mode,
  stepFormError,
  onClose,
  onSubmit,
  onDelete,
  contentClassName,
  children,
}: {
  title: string;
  open: boolean;
  mode: "create" | "edit";
  stepFormError: string | null;
  onClose: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onDelete?: () => void;
  contentClassName?: string;
  children: ReactNode;
}) {
  return (
    <DialogShell
      title={title}
      open={open}
      onClose={onClose}
      contentClassName={contentClassName ?? "max-w-2xl max-h-[85vh]"}
    >
      <form className="flex max-h-[80vh] flex-col gap-4" onSubmit={onSubmit}>
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">{children}</div>

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
    </DialogShell>
  );
}

export function StepNameField({
  value,
  hasError,
  onChange,
}: {
  value: string;
  hasError: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-semibold uppercase text-foreground/60">
        Step Name
      </label>
      <input
        type="text"
        value={value}
        onChange={onChange}
        className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        placeholder="Enter step name"
        aria-invalid={hasError ? true : undefined}
      />
    </div>
  );
}

export function ConversationToggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-foreground/80">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="h-4 w-4 rounded border-border"
        aria-label="Conversation enabled"
      />
      Conversation enabled
    </label>
  );
}

export function ParameterList({
  entries,
  onAdd,
  onRemove,
  onParameterChange,
  onExpandValue,
  apiBaseUrl,
}: ParameterListProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-foreground/60">
          Parameters
        </span>
        <button
          type="button"
          className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
          onClick={onAdd}
        >
          Add parameter
        </button>
      </div>

      {entries.length === 0 ? (
        <p className="text-sm text-foreground/60">
          No parameters defined for this step type.
        </p>
      ) : (
        <div className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
          {entries.map((entry) => (
            <ParameterListItem
              key={entry.id}
              entry={entry}
              onParameterChange={onParameterChange}
              onRemove={onRemove}
              onExpandValue={onExpandValue}
              apiBaseUrl={apiBaseUrl}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ParameterListItem({
  entry,
  onParameterChange,
  onRemove,
  onExpandValue,
  apiBaseUrl,
}: {
  entry: KeyValueEntry;
  onParameterChange: StepDialogBaseProps["onParameterChange"];
  onRemove: (entryId: string) => void;
  onExpandValue: (entryId: string, value: string | undefined) => void;
  apiBaseUrl: string;
}) {
  const applyExpression = (nextValue: string) => {
    const handler = onParameterChange(entry.id, "value");
    handler({ target: { value: nextValue } } as ChangeEvent<HTMLInputElement>);
  };

  return (
    <div className="grid grid-cols-[1fr_auto_minmax(0,1fr)_auto_auto_auto] items-center gap-2">
      <input
        type="text"
        placeholder="Parameter name"
        value={entry.key}
        onChange={onParameterChange(entry.id, "key")}
        className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <span className="text-center text-xs text-foreground/60">=</span>
      <input
        type="text"
        placeholder="Value"
        value={entry.value}
        onChange={onParameterChange(entry.id, "value")}
        className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <ExpressionBuilderButton
        value={entry.value}
        onApply={applyExpression}
        apiBaseUrl={apiBaseUrl}
      />
      <button
        type="button"
        className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
        onClick={() => onExpandValue(entry.id, entry.value)}
      >
        <Maximize2 className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        className="rounded-md border border-border px-2 py-1 text-xs text-destructive hover:bg-destructive/10"
        onClick={() => onRemove(entry.id)}
      >
        Remove
      </button>
    </div>
  );
}

export function StandardStepDialog({
  showConversationToggle = true,
  showTools = true,
  showParameters = true,
  ...props
}: StandardStepDialogProps) {
  const expandedEditor = useExpandedValueEditor(props.onParameterChange);

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
        {showConversationToggle ? (
          <ConversationToggle
            checked={props.stepForm.conversationEnabled}
            onChange={props.onConversationToggle}
          />
        ) : null}
        {showParameters ? (
          <ParameterList
            entries={props.stepForm.parameters}
            onAdd={props.onAddParameter}
            onRemove={props.onRemoveParameter}
            onParameterChange={props.onParameterChange}
            onExpandValue={expandedEditor.open}
            apiBaseUrl={props.apiBaseUrl}
          />
        ) : null}
        {showTools && props.availableTools.length > 0 ? (
          <div className="space-y-2">
            <span className="text-xs font-semibold uppercase text-foreground/60">
              Allowed Tools
            </span>
            <div className="flex flex-col gap-2">
              {props.availableTools.map((tool) => (
                <label
                  key={tool.id}
                  className="flex items-center gap-2 text-sm text-foreground/80"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-border"
                    checked={props.stepForm.tools.includes(tool.id)}
                    onChange={props.onToolToggle(tool.id)}
                  />
                  <span className="truncate">{tool.label}</span>
                </label>
              ))}
            </div>
          </div>
        ) : null}
      </StepDialogContainer>
      {expandedEditor.dialog}
    </>
  );
}
