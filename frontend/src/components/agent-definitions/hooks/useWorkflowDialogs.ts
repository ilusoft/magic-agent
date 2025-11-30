import { useStepDialog } from "./useStepDialog";
import { useToolDialog } from "./useToolDialog";
import { useOutcomeDialog } from "./useOutcomeDialog";
import type { AgentDefinitionsDocument } from "../../../types/agents";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseWorkflowDialogsOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
}

export function useWorkflowDialogs({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
}: UseWorkflowDialogsOptions) {
  const {
    dialogProps,
    openForEditing: openStepDialogForNode,
    openForCreation: openStepDialogForCreation,
    openForEchoCreation,
    openForVariableCreation,
  } = useStepDialog({
    draftDocument,
    activeWorkflowId,
    applyDocumentUpdate,
  });

  const {
    dialogProps: toolDialogProps,
    openForEditing: openToolDialogForNode,
    openForCreation: openToolDialogForCreation,
  } = useToolDialog({
    draftDocument,
    activeWorkflowId,
    applyDocumentUpdate,
  });

  const {
    dialogProps: outcomeDialogProps,
    openForEdge: openOutcomeDialogForEdge,
    openForCreation: openOutcomeDialogForCreation,
  } = useOutcomeDialog({
    draftDocument,
    activeWorkflowId,
    applyDocumentUpdate,
  });

  return {
    stepDialogProps: dialogProps,
    openStepDialogForNode,
    openStepDialogForCreation,
    openEchoStepDialogForCreation: openForEchoCreation,
    openVariableStepDialogForCreation: openForVariableCreation,
    toolDialogProps,
    openToolDialogForNode,
    openToolDialogForCreation,
    outcomeDialogProps,
    openOutcomeDialogForEdge,
    openOutcomeDialogForCreation,
  };
}
