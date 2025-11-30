import { Flag, GitCommitHorizontal, Play, Wrench } from "lucide-react";
import clsx from "clsx";

import { STEP_TYPE_VISUALS } from "./stepTypeVisuals";

interface WorkflowToolboxProps {
  disabled: boolean;
  onAddStep: () => void;
  onAddVariableStep: () => void;
  onAddOutcome: () => void;
  onAddTool: () => void;
  onAddStart: () => void;
  onAddTermination: () => void;
}

const CHAT_STEP_VISUAL = STEP_TYPE_VISUALS.chat;
const VARIABLE_STEP_VISUAL = STEP_TYPE_VISUALS.setVariables;

const TOOLBOX_ACTIONS = [
  {
    label: CHAT_STEP_VISUAL.toolboxLabel,
    icon: CHAT_STEP_VISUAL.icon,
    action: (props: WorkflowToolboxProps) => props.onAddStep(),
  },
  {
    label: VARIABLE_STEP_VISUAL.toolboxLabel,
    icon: VARIABLE_STEP_VISUAL.icon,
    action: (props: WorkflowToolboxProps) => props.onAddVariableStep(),
  },
  {
    label: "Outcome",
    icon: GitCommitHorizontal,
    action: (props: WorkflowToolboxProps) => props.onAddOutcome(),
  },
  {
    label: "Tool",
    icon: Wrench,
    action: (props: WorkflowToolboxProps) => props.onAddTool(),
  },
  {
    label: "Start",
    icon: Play,
    action: (props: WorkflowToolboxProps) => props.onAddStart(),
  },
  {
    label: "Termination",
    icon: Flag,
    action: (props: WorkflowToolboxProps) => props.onAddTermination(),
  },
] as const;

export function WorkflowToolbox(props: WorkflowToolboxProps) {
  const { disabled } = props;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-sm">
      <span className="text-xs font-semibold uppercase text-foreground/60">
        Toolbox
      </span>
      {TOOLBOX_ACTIONS.map(({ label, action, icon: Icon }) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          onClick={() => action(props)}
          className={clsx(
            "flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs transition-colors",
            disabled
              ? "cursor-not-allowed border-border/60 bg-muted/40 text-foreground/40"
              : "border-border bg-card text-foreground/80 hover:bg-muted/50"
          )}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}
