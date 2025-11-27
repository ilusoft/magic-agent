import { DialogShell } from "./DialogShell";
import type { ToolFormState } from "./types";
import type { ChangeEventHandler, FormEventHandler } from "react";

interface ToolDialogProps {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  toolForm: ToolFormState | null;
  toolFormError: string | null;
  onClose: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onFieldChange: (
    field: keyof ToolFormState
  ) => ChangeEventHandler<HTMLInputElement | HTMLTextAreaElement>;
  onDelete?: () => void;
}

export function ToolDialog({
  open,
  mode,
  title,
  toolForm,
  toolFormError,
  onClose,
  onSubmit,
  onFieldChange,
  onDelete,
}: ToolDialogProps) {
  return (
    <DialogShell
      title={title}
      open={open}
      onClose={onClose}
      contentClassName="max-w-2xl"
    >
      {toolForm ? (
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Tool ID
            </label>
            <input
              type="text"
              value={toolForm.id}
              onChange={onFieldChange("id")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="unique-tool-id"
              autoComplete="off"
              aria-invalid={toolFormError ? true : undefined}
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Tool Type
            </label>
            <input
              type="text"
              value={toolForm.type}
              onChange={onFieldChange("type")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="http, internal, etc."
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Tool Name
            </label>
            <input
              type="text"
              value={toolForm.name}
              onChange={onFieldChange("name")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Display name (optional)"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Server URL
            </label>
            <input
              type="text"
              value={toolForm.serverUrl}
              onChange={onFieldChange("serverUrl")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="https://example.com/api"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Description
            </label>
            <input
              type="text"
              value={toolForm.description}
              onChange={onFieldChange("description")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="What does this tool do?"
              autoComplete="off"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">
              Allowed Tools
            </label>
            <input
              type="text"
              value={toolForm.allowedTools}
              onChange={onFieldChange("allowedTools")}
              className="rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Comma-separated tool names"
              autoComplete="off"
            />
            <p className="text-xs text-foreground/60">
              Leave blank to expose every tool available from the connected MCP
              server.
            </p>
          </div>

          {toolFormError ? (
            <p className="text-sm text-destructive">{toolFormError}</p>
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
                Delete Tool
              </button>
            ) : null}
            <button
              type="submit"
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground"
            >
              {mode === "create" ? "Create Tool" : "Save Changes"}
            </button>
          </div>
        </form>
      ) : (
        <p className="text-sm text-destructive">
          Unable to load tool details. Please close this dialog and try again.
        </p>
      )}
    </DialogShell>
  );
}
