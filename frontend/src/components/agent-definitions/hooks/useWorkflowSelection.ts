import { useCallback, useEffect, useState } from "react";
import type {
  AgentDefinition,
  AgentDefinitionsDocument,
} from "@/types/agents";
import type { WorkflowFormState } from "@/components/agent-definitions/types";
import {
  createKeyValueEntry,
  entriesFromRecord,
  recordFromEntries,
} from "@/components/agent-definitions/util";

type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

interface UseWorkflowSelectionOptions {
  draftDocument: AgentDefinitionsDocument | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
}

interface UseWorkflowSelectionResult {
  activeWorkflowId: string | null;
  setActiveWorkflowId: (id: string | null) => void;
  isWorkflowDialogOpen: boolean;
  workflowForm: WorkflowFormState | null;
  workflowFormError: string | null;
  workflowDialogMode: "create" | "edit";
  openWorkflowDialog: () => void;
  openWorkflowDialogForEdit: (agent: AgentDefinition) => void;
  handleWorkflowFieldChange: (
    field: keyof WorkflowFormState
  ) => (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleStreamingToggle: (enabled: boolean) => void;
  handleAddDefaultParameter: () => void;
  handleDefaultParameterChange: (
    entryId: string,
    field: "key" | "value"
  ) => (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleRemoveDefaultParameter: (entryId: string) => void;
  handleWorkflowSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  handleWorkflowDialogClose: () => void;
  handleRemoveWorkflow: (
    workflowId: string
  ) => (event: React.MouseEvent<HTMLButtonElement>) => void;
  handleWorkflowKeyDown: (
    workflowId: string
  ) => (event: React.KeyboardEvent<HTMLDivElement>) => void;
}

export function useWorkflowSelection({
  draftDocument,
  applyDocumentUpdate,
}: UseWorkflowSelectionOptions): UseWorkflowSelectionResult {
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [isWorkflowDialogOpen, setIsWorkflowDialogOpen] = useState(false);
  const [workflowForm, setWorkflowForm] = useState<WorkflowFormState | null>(
    null
  );
  const [workflowFormError, setWorkflowFormError] = useState<string | null>(
    null
  );
  const [workflowDialogMode, setWorkflowDialogMode] = useState<
    "create" | "edit"
  >("create");
  const [workflowOriginalId, setWorkflowOriginalId] = useState<string | null>(
    null
  );

  // Keep active workflow ID valid when the document changes
  useEffect(() => {
    if (!draftDocument) {
      setActiveWorkflowId(null);
      return;
    }

    setActiveWorkflowId((previous) => {
      if (
        previous &&
        draftDocument.agents.some((agent) => agent.id === previous)
      ) {
        return previous;
      }

      return draftDocument.agents[0]?.id ?? null;
    });
  }, [draftDocument]);

  const openWorkflowDialog = useCallback(() => {
    setWorkflowForm({
      id: "",
      name: "",
      description: "",
      endpoint: "",
      deployment: "",
      apiKey: "",
      apiVersion: "",
      defaultParameters: [createKeyValueEntry()],
      streamingEnabled: false,
      streamingMode: "sse",
    });
    setWorkflowFormError(null);
    setWorkflowDialogMode("create");
    setWorkflowOriginalId(null);
    setIsWorkflowDialogOpen(true);
  }, []);

  const openWorkflowDialogForEdit = useCallback((agent: AgentDefinition) => {
    const parameterEntries = entriesFromRecord(agent.defaultParameters);

    setWorkflowForm({
      id: agent.id,
      name: agent.name ?? "",
      description: agent.description ?? "",
      endpoint: agent.endpoint ?? "",
      deployment: agent.deployment ?? "",
      apiKey: agent.apiKey ?? "",
      apiVersion: agent.apiVersion ?? "",
      defaultParameters:
        parameterEntries.length > 0
          ? parameterEntries
          : [createKeyValueEntry()],
      streamingEnabled: agent.streaming?.enabled ?? false,
      streamingMode: agent.streaming?.mode ?? "sse",
    });
    setWorkflowFormError(null);
    setWorkflowDialogMode("edit");
    setWorkflowOriginalId(agent.id);
    setIsWorkflowDialogOpen(true);
  }, []);

  const handleWorkflowFieldChange = useCallback(
    (field: keyof WorkflowFormState) =>
      (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setWorkflowForm((previous) =>
          previous ? { ...previous, [field]: value } : previous
        );
      },
    []
  );

  const handleStreamingToggle = useCallback((enabled: boolean) => {
    setWorkflowForm((previous) =>
      previous ? { ...previous, streamingEnabled: enabled } : previous
    );
  }, []);

  const handleAddDefaultParameter = useCallback(() => {
    setWorkflowForm((previous) =>
      previous
        ? {
            ...previous,
            defaultParameters: [
              ...previous.defaultParameters,
              createKeyValueEntry(),
            ],
          }
        : previous
    );
  }, []);

  const handleDefaultParameterChange = useCallback(
    (entryId: string, field: "key" | "value") =>
      (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setWorkflowForm((previous) =>
          previous
            ? {
                ...previous,
                defaultParameters: previous.defaultParameters.map((entry) =>
                  entry.id === entryId ? { ...entry, [field]: value } : entry
                ),
              }
            : previous
        );
      },
    []
  );

  const handleRemoveDefaultParameter = useCallback((entryId: string) => {
    setWorkflowForm((previous) => {
      if (!previous) {
        return previous;
      }

      const next = previous.defaultParameters.filter(
        (entry) => entry.id !== entryId
      );

      return {
        ...previous,
        defaultParameters: next.length > 0 ? next : [createKeyValueEntry()],
      };
    });
  }, []);

  const handleWorkflowSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();

      if (!workflowForm) {
        return;
      }

      if (!workflowForm.id.trim()) {
        setWorkflowFormError("Workflow ID is required.");
        return;
      }

      if (!workflowForm.name.trim()) {
        setWorkflowFormError("Workflow name is required.");
        return;
      }

      const trimmedId = workflowForm.id.trim();
      const trimmedApiKey = workflowForm.apiKey.trim();
      const trimmedApiVersion = workflowForm.apiVersion.trim();
      const defaultParametersRecord = recordFromEntries(
        workflowForm.defaultParameters
      );

      if (workflowDialogMode === "create") {
        const duplicate = draftDocument?.agents.some(
          (agent) => agent.id === trimmedId
        );

        if (duplicate) {
          setWorkflowFormError(
            "A workflow with this ID already exists. Choose a different identifier."
          );
          return;
        }

        applyDocumentUpdate((draft) => {
          const newWorkflow: AgentDefinition = {
            id: trimmedId,
            name: workflowForm.name.trim(),
            description: workflowForm.description.trim() || undefined,
            endpoint: workflowForm.endpoint.trim() || undefined,
            deployment: workflowForm.deployment.trim() || undefined,
            apiKey: trimmedApiKey || undefined,
            apiVersion: trimmedApiVersion || undefined,
            defaultParameters: defaultParametersRecord,
            steps: [],
            tools: [],
            ViewLayout: { nodes: {} },
            streaming: workflowForm.streamingEnabled
              ? {
                  enabled: true,
                  mode: workflowForm.streamingMode.trim() || "sse",
                }
              : undefined,
          };

          draft.agents.push(newWorkflow);
          return draft;
        });
      } else {
        const originalId = workflowOriginalId ?? workflowForm.id;
        const duplicate = draftDocument?.agents.some(
          (agent) => agent.id === trimmedId && agent.id !== originalId
        );

        if (duplicate) {
          setWorkflowFormError(
            "A workflow with this ID already exists. Choose a different identifier."
          );
          return;
        }

        applyDocumentUpdate((draft) => {
          const targetIndex = draft.agents.findIndex(
            (agent) => agent.id === originalId
          );

          if (targetIndex === -1) {
            return draft;
          }

          const existing = draft.agents[targetIndex];
          draft.agents[targetIndex] = {
            ...existing,
            id: trimmedId,
            name: workflowForm.name.trim() || existing.name,
            description: workflowForm.description.trim() || undefined,
            endpoint: workflowForm.endpoint.trim() || undefined,
            deployment: workflowForm.deployment.trim() || undefined,
            apiKey: trimmedApiKey || undefined,
            apiVersion: trimmedApiVersion || undefined,
            defaultParameters: defaultParametersRecord,
            streaming: workflowForm.streamingEnabled
              ? {
                  enabled: true,
                  mode: workflowForm.streamingMode.trim() || "sse",
                }
              : undefined,
          };

          return draft;
        });
      }

      setActiveWorkflowId(trimmedId);
      setIsWorkflowDialogOpen(false);
      setWorkflowForm(null);
      setWorkflowOriginalId(null);
      setWorkflowDialogMode("create");
    },
    [
      workflowForm,
      draftDocument,
      applyDocumentUpdate,
      workflowDialogMode,
      workflowOriginalId,
    ]
  );

  const handleWorkflowDialogClose = useCallback(() => {
    setIsWorkflowDialogOpen(false);
    setWorkflowForm(null);
    setWorkflowFormError(null);
    setWorkflowOriginalId(null);
    setWorkflowDialogMode("create");
  }, []);

  const handleRemoveWorkflow = useCallback(
    (workflowId: string) => (event: React.MouseEvent<HTMLButtonElement>) => {
      event.stopPropagation();

      if (!draftDocument) {
        return;
      }

      const shouldRemove = window.confirm(
        "Remove this workflow definition? This action cannot be undone."
      );

      if (!shouldRemove) {
        return;
      }

      let nextActiveId: string | null = activeWorkflowId;

      applyDocumentUpdate((draft) => {
        const index = draft.agents.findIndex(
          (agent) => agent.id === workflowId
        );

        if (index === -1) {
          return draft;
        }

        draft.agents.splice(index, 1);

        if (activeWorkflowId === workflowId) {
          nextActiveId = draft.agents[0]?.id ?? null;
        }

        return draft;
      });

      setActiveWorkflowId((current) =>
        current === workflowId ? nextActiveId : current
      );
    },
    [draftDocument, activeWorkflowId, applyDocumentUpdate]
  );

  const handleWorkflowKeyDown = useCallback(
    (workflowId: string) => (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setActiveWorkflowId(workflowId);
      }
    },
    []
  );

  return {
    activeWorkflowId,
    setActiveWorkflowId,
    isWorkflowDialogOpen,
    workflowForm,
    workflowFormError,
    workflowDialogMode,
    openWorkflowDialog,
    openWorkflowDialogForEdit,
    handleWorkflowFieldChange,
    handleStreamingToggle,
    handleAddDefaultParameter,
    handleDefaultParameterChange,
    handleRemoveDefaultParameter,
    handleWorkflowSubmit,
    handleWorkflowDialogClose,
    handleRemoveWorkflow,
    handleWorkflowKeyDown,
  };
}
