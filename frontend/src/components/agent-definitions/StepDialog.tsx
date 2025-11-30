import { DialogShell } from "./DialogShell";
import type { StepFormState } from "./types";
import type { StepDialogBaseProps } from "./step-dialogs/StepDialogShared";
import { ChatStepDialog } from "./step-dialogs/ChatStepDialog";
import { EchoStepDialog } from "./step-dialogs/EchoStepDialog";
import { VariableStepDialog } from "./step-dialogs/VariableStepDialog";

interface StepDialogProps extends Omit<StepDialogBaseProps, "stepForm"> {
  stepForm: StepFormState | null;
}

function formatStepTypeLabel(type: StepFormState["type"]) {
  switch (type) {
    case "setVariables":
      return "Variable Step";
    case "echo":
      return "Echo Step";
    case "chat":
    default:
      return "Chat Step";
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
  };

  switch (stepForm.type) {
    case "setVariables":
      return <VariableStepDialog {...sharedProps} />;
    case "echo":
      return <EchoStepDialog {...sharedProps} />;
    case "chat":
    default:
      return <ChatStepDialog {...sharedProps} />;
  }
}
