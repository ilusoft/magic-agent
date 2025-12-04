import { DialogShell } from "./DialogShell";
import type { StepFormState } from "./types";
import type { StepDialogBaseProps } from "./step-dialogs/StepDialogShared";
import { AgentStepDialog } from "./step-dialogs/AgentStepDialog";
import { EchoStepDialog } from "./step-dialogs/EchoStepDialog";
import { VariableStepDialog } from "./step-dialogs/VariableStepDialog";
import { ResetConversationStepDialog } from "./step-dialogs/ResetConversationStepDialog";

interface StepDialogProps extends Omit<StepDialogBaseProps, "stepForm"> {
  stepForm: StepFormState | null;
}

function formatStepTypeLabel(type: StepFormState["type"]) {
  switch (type) {
    case "setVariables":
      return "Variable Step";
    case "echo":
      return "Echo Step";
    case "resetConversation":
      return "Reset Conversation";
    case "agent":
    default:
      return "Agent Step";
  }
}

export function StepDialog(props: StepDialogProps) {
  if (!props.stepForm) {
    return (
      <DialogShell
        title={props.title}
        open={props.open}
        onClose={props.onClose}
        contentClassName="max-w-2xl"
      >
        <p className="text-sm text-destructive">
          Unable to load step details. Please close this dialog and try again.
        </p>
      </DialogShell>
    );
  }

  const { stepForm, ...rest } = props;
  const typeLabel = formatStepTypeLabel(stepForm.type);
  const sharedProps: StepDialogBaseProps = {
    ...rest,
    title: `${props.title} – ${typeLabel}`,
    stepForm,
    apiBaseUrl: props.apiBaseUrl,
  };

  switch (stepForm.type) {
    case "setVariables":
      return <VariableStepDialog {...sharedProps} />;
    case "echo":
      return <EchoStepDialog {...sharedProps} />;
    case "resetConversation":
      return (
        <ResetConversationStepDialog
          {...sharedProps}
          showConversationToggle={false}
          showTools={false}
          showParameters={false}
        />
      );
    case "agent":
    default:
      return <AgentStepDialog {...sharedProps} />;
  }
}
