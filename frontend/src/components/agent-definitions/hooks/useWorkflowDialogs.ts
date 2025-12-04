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
  apiBaseUrl: string;
}

export function useWorkflowDialogs({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
  apiBaseUrl,
}: UseWorkflowDialogsOptions) {
  const {
    dialogProps,
    openForEditing: openStepDialogForNode,
    openForCreation: openStepDialogForCreation,
    openForEchoCreation,
    openForVariableCreation,
    openForResetCreation,
  } = useStepDialog({
    draftDocument,
    activeWorkflowId,
    applyDocumentUpdate,
    apiBaseUrl,
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
    apiBaseUrl,
  });

  return {
    stepDialogProps: dialogProps,
    openStepDialogForNode,
    openStepDialogForCreation,
    openEchoStepDialogForCreation: openForEchoCreation,
    openVariableStepDialogForCreation: openForVariableCreation,
    openResetStepDialogForCreation: openForResetCreation,
    toolDialogProps,
    openToolDialogForNode,
    openToolDialogForCreation,
    outcomeDialogProps,
    openOutcomeDialogForEdge,
    openOutcomeDialogForCreation,
  };
}
