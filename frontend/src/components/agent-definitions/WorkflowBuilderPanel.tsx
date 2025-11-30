import type { ReactNode } from "react";
import { WorkflowToolbox } from "./WorkflowToolbox";

interface WorkflowBuilderPanelProps {
  disabled: boolean;
  onAddStep: () => void;
  onAddEchoStep: () => void;
  onAddVariableStep: () => void;
  onAddOutcome: () => void;
  onAddTool: () => void;
  onAddStart: () => void;
  onAddTermination: () => void;
  children: ReactNode;
}

export function WorkflowBuilderPanel({
  disabled,
  onAddStep,
  onAddEchoStep,
  onAddVariableStep,
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
        onAddEchoStep={onAddEchoStep}
        onAddVariableStep={onAddVariableStep}
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
