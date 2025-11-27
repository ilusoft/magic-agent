import type { ReactNode } from "react";
import { WorkflowToolbox } from "./WorkflowToolbox";

interface WorkflowBuilderPanelProps {
  disabled: boolean;
  onAddStep: () => void;
  onAddOutcome: () => void;
  onAddTool: () => void;
  onAddStart: () => void;
  onAddTermination: () => void;
  children: ReactNode;
}

export function WorkflowBuilderPanel({
  disabled,
  onAddStep,
  onAddOutcome,
  onAddTool,
  onAddStart,
  onAddTermination,
  children,
}: WorkflowBuilderPanelProps) {
  return (
    <>
      <WorkflowToolbox
        disabled={disabled}
        onAddStep={onAddStep}
        onAddOutcome={onAddOutcome}
        onAddTool={onAddTool}
        onAddStart={onAddStart}
        onAddTermination={onAddTermination}
      />

      <div className="relative left-1/2 w-screen -translate-x-1/2">
        <div
          className="mx-auto rounded-md border border-border bg-card"
          style={{
            height: "calc(100vh - 19rem)",
            minHeight: "24rem",
            width: "90vw",
          }}
        >
          {children}
        </div>
      </div>
    </>
  );
}
