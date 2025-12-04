import type { StepDialogBaseProps } from "./StepDialogShared";
import { StandardStepDialog } from "./StepDialogShared";

export function ResetConversationStepDialog(props: StepDialogBaseProps) {
  return (
    <StandardStepDialog
      {...props}
      showConversationToggle={false}
      showTools={false}
      showParameters={false}
    />
  );
}
