import clsx from 'clsx';

interface WorkflowToolboxProps {
  disabled: boolean;
  onAddStep: () => void;
  onAddOutcome: () => void;
  onAddTool: () => void;
  onAddStart: () => void;
  onAddTermination: () => void;
}

const TOOLBOX_ACTIONS = [
  { label: 'Add Step', action: (props: WorkflowToolboxProps) => props.onAddStep() },
  { label: 'Add Outcome', action: (props: WorkflowToolboxProps) => props.onAddOutcome() },
  { label: 'Add Tool', action: (props: WorkflowToolboxProps) => props.onAddTool() },
  { label: 'Add Start', action: (props: WorkflowToolboxProps) => props.onAddStart() },
  { label: 'Add Termination', action: (props: WorkflowToolboxProps) => props.onAddTermination() },
] as const;

export function WorkflowToolbox(props: WorkflowToolboxProps) {
  const { disabled } = props;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-foreground/60">Toolbox</span>
      {TOOLBOX_ACTIONS.map(({ label, action }) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          onClick={() => action(props)}
          className={clsx(
            'rounded-md border px-2.5 py-1 text-xs transition-colors',
            disabled
              ? 'cursor-not-allowed border-border/60 bg-muted/40 text-foreground/40'
              : 'border-border bg-card text-foreground/80 hover:bg-muted/50'
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
