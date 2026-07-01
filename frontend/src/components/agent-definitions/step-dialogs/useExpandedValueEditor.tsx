import { useState, type ChangeEvent } from "react";
import { DialogShell } from "@/components/agent-definitions/DialogShell";
import type { StepDialogBaseProps } from "@/components/agent-definitions/step-dialogs/StepDialogShared";

export interface ExpandedEditorHandle {
  open: (entryId: string, value?: string) => void;
  dialog: React.ReactNode;
}

/**
 * Hook that manages the "expand parameter value into a full editor"
 * dialog. Returns an opener (called from the parameter row) and a
 * `dialog` element that the parent renders once at the bottom of
 * its tree.
 *
 * Lives in its own file so React Fast Refresh can hot-reload
 * ``StepDialogShared`` (which only exports components) without
 * having to refresh this hook.
 */
export function useExpandedValueEditor(
  onParameterChange: StepDialogBaseProps["onParameterChange"]
): ExpandedEditorHandle {
  const [state, setState] = useState<{ id: string; value: string } | null>(
    null
  );

  const close = () => setState(null);

  const save = () => {
    if (!state) {
      return;
    }

    const handler = onParameterChange(state.id, "value");
    handler({
      target: { value: state.value },
    } as ChangeEvent<HTMLInputElement>);
    setState(null);
  };

  const dialog = state ? (
    <DialogShell
      title="Edit Parameter Value"
      open={true}
      onClose={close}
      contentClassName="max-w-3xl"
    >
      <div className="space-y-3">
        <textarea
          className="h-64 w-full rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={state.value}
          onChange={(event) =>
            setState((prev) =>
              prev ? { ...prev, value: event.target.value } : prev
            )
          }
        />
        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground/80 hover:bg-muted"
            onClick={close}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
            onClick={save}
          >
            Save
          </button>
        </div>
      </div>
    </DialogShell>
  ) : null;

  return {
    open: (entryId, value) => setState({ id: entryId, value: value ?? "" }),
    dialog,
  };
}
