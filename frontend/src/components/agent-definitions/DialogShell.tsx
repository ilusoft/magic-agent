import type { ReactNode } from "react";
import { X } from "lucide-react";

interface DialogShellProps {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  contentClassName?: string;
}

export function DialogShell({
  title,
  open,
  onClose,
  children,
  contentClassName,
}: DialogShellProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur">
      <div
        className={`w-full ${
          contentClassName ?? "max-w-md"
        } rounded-lg border border-border bg-card p-4 shadow-lg`}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-foreground">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-md border-no-border text-foreground/70 transition-colors hover:bg-muted"
            title="Close"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-3 space-y-3 text-sm">{children}</div>
      </div>
    </div>
  );
}
