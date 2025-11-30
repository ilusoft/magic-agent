import type { StepDialogBaseProps } from "./StepDialogShared";
import { StandardStepDialog } from "./StepDialogShared";

export function EchoStepDialog(props: StepDialogBaseProps) {
  return <StandardStepDialog {...props} showTools={false} />;
}
