import { useEffect, useMemo, useState } from 'react';

import { DialogShell } from './DialogShell';

interface WorkflowStepSelectorDialogProps {
  open: boolean;
  steps: string[];
  title: string;
  description: string;
  confirmLabel?: string;
  onCancel: () => void;
  onConfirm: (stepName: string) => void;
}

export function WorkflowStepSelectorDialog({
  open,
  steps,
  title,
  description,
  confirmLabel = 'Continue',
  onCancel,
  onConfirm,
}: WorkflowStepSelectorDialogProps) {
  const availableSteps = useMemo(() => steps.filter(Boolean), [steps]);
  const [selectedStep, setSelectedStep] = useState<string>('');

  useEffect(() => {
    if (open) {
      setSelectedStep((previous) => {
        if (previous && availableSteps.includes(previous)) {
          return previous;
        }

        return availableSteps[0] ?? '';
      });
    }
  }, [open, availableSteps]);

  const handleSubmit = () => {
    if (!selectedStep) {
      return;
    }

    onConfirm(selectedStep);
  };

  const isConfirmDisabled = !selectedStep;

  return (
    <DialogShell title={title} open={open} onClose={onCancel}>
      <div className="space-y-4 text-sm text-foreground/80">
        <p>{description}</p>

        {availableSteps.length > 0 ? (
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase text-foreground/60">Source step</label>
            <select
              className="w-full rounded-md border border-border bg-card px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={selectedStep}
              onChange={(event) => setSelectedStep(event.target.value)}
            >
              {availableSteps.map((step) => (
                <option key={step} value={step}>
                  {step}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <p className="text-xs text-foreground/60">
            Define at least one step before creating an outcome.
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground/80 hover:bg-muted"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-60"
            onClick={handleSubmit}
            disabled={isConfirmDisabled}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </DialogShell>
  );
}
