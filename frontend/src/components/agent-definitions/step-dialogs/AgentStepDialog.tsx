import type { StepDialogBaseProps } from "./StepDialogShared";
import { StandardStepDialog } from "./StepDialogShared";

export function AgentStepDialog(props: StepDialogBaseProps) {
  return <StandardStepDialog {...props} />;
}
