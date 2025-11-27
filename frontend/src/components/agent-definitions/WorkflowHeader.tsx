import clsx from "clsx";

interface WorkflowHeaderProps {
  loading: boolean;
  showAdvanced: boolean;
  isSaving: boolean;
  saveDisabled: boolean;
  onReload: () => void;
  onToggleAdvanced: () => void;
  onSave: () => void;
}

export function WorkflowHeader({
  loading,
  showAdvanced,
  isSaving,
  saveDisabled,
  onReload,
  onToggleAdvanced,
  onSave,
}: WorkflowHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-xl font-semibold">Agent Definitions</h2>
        <p className="text-sm text-foreground/70">
          Visualize and manage workflow configuration. Switch to the advanced
          editor for direct JSON edits.
        </p>
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded-md border border-border px-3 py-2 text-sm"
          onClick={onReload}
          disabled={loading}
        >
          Reload
        </button>
        <button
          type="button"
          className={clsx(
            "rounded-md border border-border px-3 py-2 text-sm",
            showAdvanced ? "bg-muted text-foreground/90" : "bg-card"
          )}
          onClick={onToggleAdvanced}
          disabled={loading}
        >
          {showAdvanced ? "Hide Advanced" : "Show Advanced"}
        </button>
        <button
          type="button"
          className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-70"
          onClick={onSave}
          disabled={saveDisabled}
        >
          {isSaving ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
