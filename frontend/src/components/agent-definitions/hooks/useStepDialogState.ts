import { useCallback, useMemo, useState } from "react";

import type { WorkflowNode } from "../types";

interface OpenDialogOptions {
  mode: "create" | "edit";
  target?: WorkflowNode | null;
}

interface UseStepDialogStateResult {
  open: boolean;
  mode: "create" | "edit";
  dialogTarget: WorkflowNode | null;
  title: string;
  openDialog: (options: OpenDialogOptions) => void;
  reset: () => void;
}

export function useStepDialogState(): UseStepDialogStateResult {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("edit");
  const [dialogTarget, setDialogTarget] = useState<WorkflowNode | null>(null);

  const openDialog = useCallback(
    ({ mode, target = null }: OpenDialogOptions) => {
      setMode(mode);
      setDialogTarget(target ?? null);
      setOpen(true);
    },
    []
  );

  const reset = useCallback(() => {
    setOpen(false);
    setMode("edit");
    setDialogTarget(null);
  }, []);

  const title = useMemo(() => {
    if (mode === "create") {
      return "Create Step";
    }

    if (!dialogTarget) {
      return "Configure Step";
    }

    return `Configure Step “${
      dialogTarget.data.stepName ?? dialogTarget.data.label
    }”`;
  }, [mode, dialogTarget]);

  return {
    open,
    mode,
    dialogTarget,
    title,
    openDialog,
    reset,
  };
}
