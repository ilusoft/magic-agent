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
  type LlmConfigMode,
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
  availableLlmProfiles?: { id: string; provider: string; label?: string }[];
  onLlmConfigModeChange?: (mode: LlmConfigMode) => void;
  onLlmConfigChange?: (patch: Partial<StepFormState["llmConfig"]>) => void;
  onDelete?: () => void;
}

export interface StandardStepDialogProps extends StepDialogBaseProps {
  showConversationToggle?: boolean;
  showTools?: boolean;
  showParameters?: boolean;
  showLlmConfig?: boolean;
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
  showLlmConfig = true,
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
        {showLlmConfig ? (
          <LlmConfigSection
            llmConfig={props.stepForm.llmConfig}
            availableLlmProfiles={props.availableLlmProfiles ?? []}
            onModeChange={props.onLlmConfigModeChange ?? (() => {})}
            onChange={props.onLlmConfigChange ?? (() => {})}
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

function LlmConfigSection({
  llmConfig,
  availableLlmProfiles,
  onModeChange,
  onChange,
}: {
  llmConfig: StepFormState["llmConfig"];
  availableLlmProfiles: { id: string; provider: string }[];
  onModeChange: (mode: LlmConfigMode) => void;
  onChange: (patch: Partial<StepFormState["llmConfig"]>) => void;
}) {
  return (
    <div className="space-y-2 rounded-md border border-border bg-card/40 p-3">
      <span className="text-xs font-semibold uppercase text-foreground/60">
        LLM Configuration
      </span>

      <div className="flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="llmConfigMode"
            checked={llmConfig.mode === "profile"}
            onChange={() => onModeChange("profile")}
            className="h-3.5 w-3.5"
          />
          Use profile
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="llmConfigMode"
            checked={llmConfig.mode === "inline"}
            onChange={() => onModeChange("inline")}
            className="h-3.5 w-3.5"
          />
          Inline override
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            name="llmConfigMode"
            checked={llmConfig.mode === "inherit"}
            onChange={() => onModeChange("inherit")}
            className="h-3.5 w-3.5"
          />
          Inherit (env vars)
        </label>
      </div>

      {llmConfig.mode === "profile" ? (
        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase text-foreground/60">
            Profile
          </label>
          {availableLlmProfiles.length === 0 ? (
            <p className="text-sm text-foreground/60">
              No LLM profiles defined. Open the LLM Profiles view to create one.
            </p>
          ) : (
            <select
              value={llmConfig.profileId}
              onChange={(e) => onChange({ profileId: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="">Select a profile…</option>
              {availableLlmProfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id} ({p.provider})
                </option>
              ))}
            </select>
          )}
        </div>
      ) : null}

      {llmConfig.mode === "inline" ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Field label="Provider">
            <select
              value={llmConfig.provider}
              onChange={(e) => onChange({ provider: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="azure-openai">azure-openai</option>
              <option value="openai-compatible">openai-compatible</option>
            </select>
          </Field>
          {llmConfig.provider === "azure-openai" ? (
            <>
              <Field label="Endpoint">
                <input
                  type="text"
                  value={llmConfig.endpoint}
                  onChange={(e) => onChange({ endpoint: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
              <Field label="Deployment">
                <input
                  type="text"
                  value={llmConfig.deployment}
                  onChange={(e) => onChange({ deployment: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
              <Field label="API version">
                <input
                  type="text"
                  value={llmConfig.apiVersion}
                  onChange={(e) => onChange({ apiVersion: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
            </>
          ) : (
            <>
              <Field label="Base URL">
                <input
                  type="text"
                  value={llmConfig.baseUrl}
                  onChange={(e) => onChange({ baseUrl: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
              <Field label="Model">
                <input
                  type="text"
                  value={llmConfig.model}
                  onChange={(e) => onChange({ model: e.target.value })}
                  className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </Field>
            </>
          )}
          <Field label="API key" fullWidth>
            <input
              type="text"
              value={llmConfig.apiKey}
              onChange={(e) => onChange({ apiKey: e.target.value })}
              placeholder="literal value or ${ENV_VAR}"
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Temperature">
            <input
              type="number"
              step="0.1"
              value={llmConfig.temperature}
              onChange={(e) => onChange({ temperature: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
          <Field label="Max tokens">
            <input
              type="number"
              value={llmConfig.maxTokens}
              onChange={(e) => onChange({ maxTokens: e.target.value })}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </Field>
        </div>
      ) : null}

      {llmConfig.mode === "inherit" ? (
        <p className="text-sm text-foreground/60">
          The runner will fall back to the <code>AZURE_OPENAI_*</code>{" "}
          environment variables at execution time.
        </p>
      ) : null}
    </div>
  );
}

function Field({
  label,
  children,
  fullWidth,
}: {
  label: string;
  children: ReactNode;
  fullWidth?: boolean;
}) {
  return (
    <div className={fullWidth ? "sm:col-span-2" : ""}>
      <label className="block text-xs font-semibold uppercase text-foreground/60">
        {label}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
