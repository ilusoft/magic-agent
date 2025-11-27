import { useCallback, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import type {
  AgentDefinitionsDocument,
  AgentToolDefinition,
} from "../../../types/agents";
import type { ToolFormState, WorkflowNode } from "../types";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseToolDialogOptions {
  draftDocument: AgentDefinitionsDocument | null;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
}

interface ToolDialogBindings {
  open: boolean;
  mode: "create" | "edit";
  title: string;
  toolForm: ToolFormState | null;
  toolFormError: string | null;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onFieldChange: (
    field: keyof ToolFormState
  ) => (event: ChangeEvent<HTMLInputElement>) => void;
  onDelete?: () => void;
}

interface UseToolDialogResult {
  dialogProps: ToolDialogBindings;
  openForEditing: (workflowNode: WorkflowNode) => void;
  openForCreation: () => void;
  reset: () => void;
}

export function useToolDialog({
  draftDocument,
  activeWorkflowId,
  applyDocumentUpdate,
}: UseToolDialogOptions): UseToolDialogResult {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<"create" | "edit">("edit");
  const [dialogTarget, setDialogTarget] = useState<WorkflowNode | null>(null);
  const [toolForm, setToolForm] = useState<ToolFormState | null>(null);
  const [toolFormError, setToolFormError] = useState<string | null>(null);
  const [toolOriginalId, setToolOriginalId] = useState<string | null>(null);

  const reset = useCallback(() => {
    setIsOpen(false);
    setMode("edit");
    setDialogTarget(null);
    setToolForm(null);
    setToolFormError(null);
    setToolOriginalId(null);
  }, []);

  const openForEditing = useCallback(
    (workflowNode: WorkflowNode) => {
      if (!draftDocument || !activeWorkflowId) {
        setToolForm(null);
        setToolFormError("Unable to locate workflow for editing.");
        setToolOriginalId(null);
        setMode("edit");
        setDialogTarget(workflowNode);
        setIsOpen(true);
        return;
      }

      const agent = draftDocument.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent) {
        setToolForm(null);
        setToolFormError("Unable to locate agent for this workflow.");
        setToolOriginalId(null);
        setMode("edit");
        setDialogTarget(workflowNode);
        setIsOpen(true);
        return;
      }

      const existingTool = workflowNode.data.toolId
        ? agent.tools?.find((tool) => tool.id === workflowNode.data.toolId)
        : undefined;

      setToolForm({
        id: existingTool?.id ?? workflowNode.data.toolId ?? "",
        type: existingTool?.type ?? "",
        name: existingTool?.name ?? "",
        serverUrl: existingTool?.serverUrl ?? "",
        description: existingTool?.description ?? "",
        allowedTools: existingTool?.allowedTools?.join(", ") ?? "",
      });
      setToolFormError(null);
      setToolOriginalId(existingTool?.id ?? workflowNode.data.toolId ?? null);
      setMode("edit");
      setDialogTarget(workflowNode);
      setIsOpen(true);
    },
    [draftDocument, activeWorkflowId]
  );

  const openForCreation = useCallback(() => {
    setToolForm({
      id: "",
      type: "",
      name: "",
      serverUrl: "",
      description: "",
      allowedTools: "",
    });
    setToolFormError(null);
    setToolOriginalId(null);
    setMode("create");
    setDialogTarget(null);
    setIsOpen(true);
  }, []);

  const handleFieldChange = useCallback(
    (field: keyof ToolFormState) => (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;
      setToolForm((previous) =>
        previous ? { ...previous, [field]: value } : previous
      );
    },
    []
  );

  const handleSubmit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!toolForm || !draftDocument || !activeWorkflowId) {
        setToolFormError("Unable to update tool — missing context.");
        return;
      }

      const trimmedId = toolForm.id.trim();
      const trimmedType = toolForm.type.trim();

      if (!trimmedId) {
        setToolFormError("Tool ID is required.");
        return;
      }

      if (!trimmedType) {
        setToolFormError("Tool type is required.");
        return;
      }

      if (mode === "create") {
        const duplicate = draftDocument.agents
          .find((candidate) => candidate.id === activeWorkflowId)
          ?.tools?.some((tool) => tool.id === trimmedId);

        if (duplicate) {
          setToolFormError(
            "A tool with this ID already exists. Choose a different identifier or edit the existing tool."
          );
          return;
        }
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        agent.tools = agent.tools ?? [];

        const existingIndex = toolOriginalId
          ? agent.tools.findIndex((tool) => tool.id === toolOriginalId)
          : agent.tools.findIndex((tool) => tool.id === trimmedId);

        const updatedTool: AgentToolDefinition = {
          id: trimmedId,
          type: trimmedType,
          name: toolForm.name.trim() || undefined,
          serverUrl: toolForm.serverUrl.trim() || undefined,
          description: toolForm.description.trim() || undefined,
          allowedTools: toolForm.allowedTools
            .split(",")
            .map((entry) => entry.trim())
            .filter((entry) => entry.length > 0),
        };

        if (
          !updatedTool.allowedTools ||
          updatedTool.allowedTools.length === 0
        ) {
          delete updatedTool.allowedTools;
        }

        if (existingIndex >= 0) {
          agent.tools[existingIndex] = {
            ...agent.tools[existingIndex],
            ...updatedTool,
          };
        } else {
          agent.tools.push(updatedTool);
        }

        return draft;
      });

      setToolFormError(null);
      reset();
    },
    [
      toolForm,
      draftDocument,
      activeWorkflowId,
      toolOriginalId,
      mode,
      applyDocumentUpdate,
      reset,
    ]
  );

  const handleDelete = useCallback(() => {
    if (!draftDocument || !activeWorkflowId || !toolOriginalId) {
      setToolFormError("Unable to delete tool — missing context.");
      return;
    }

    applyDocumentUpdate((draft) => {
      const agent = draft.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent || !Array.isArray(agent.tools)) {
        return draft;
      }

      agent.tools = agent.tools.filter((tool) => tool.id !== toolOriginalId);

      // Remove references to this tool from all steps in the workflow
      agent.steps = agent.steps.map((step) => ({
        ...step,
        tools: step.tools?.filter((id) => id !== toolOriginalId),
      }));

      return draft;
    });

    setToolFormError(null);
    reset();
  }, [
    draftDocument,
    activeWorkflowId,
    toolOriginalId,
    applyDocumentUpdate,
    reset,
  ]);

  const title = useMemo(() => {
    if (mode === "create") {
      return "Create Tool";
    }

    if (!dialogTarget) {
      return "Configure Tool";
    }

    return `Configure Tool “${
      dialogTarget.data.toolId ?? dialogTarget.data.label
    }”`;
  }, [mode, dialogTarget]);

  return {
    dialogProps: {
      open: isOpen,
      mode,
      title,
      toolForm,
      toolFormError,
      onClose: reset,
      onSubmit: handleSubmit,
      onFieldChange: handleFieldChange,
      onDelete: mode === "edit" ? handleDelete : undefined,
    },
    openForEditing,
    openForCreation,
    reset,
  };
}
