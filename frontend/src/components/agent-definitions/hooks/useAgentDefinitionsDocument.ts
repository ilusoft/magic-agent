import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentDefinitionsDocument } from "../../../types/agents";
import { isWorkflowDebugLoggingEnabled } from "../utils/workflowDebug";

interface UseAgentDefinitionsDocumentOptions {
  definitions: AgentDefinitionsDocument | null;
  apiBaseUrl: string;
  onReload: () => Promise<void>;
  onDefinitionsUpdated: (document: AgentDefinitionsDocument) => void;
}

export interface AgentDefinitionsDocumentState {
  draftDocument: AgentDefinitionsDocument | null;
  jsonDraft: string;
  jsonError: string | null;
  isSaving: boolean;
  isDirty: boolean;
  successMessage: string | null;
  documentRevision: number;
  handleReload: () => Promise<void>;
  handleJsonDraftChange: (value: string) => void;
  applyDocumentUpdate: (
    updater: (
      draft: AgentDefinitionsDocument
    ) => AgentDefinitionsDocument | void
  ) => void;
  handleSave: () => Promise<void>;
  setSuccessMessage: (value: string | null) => void;
}

export function useAgentDefinitionsDocument({
  definitions,
  apiBaseUrl,
  onReload,
  onDefinitionsUpdated,
}: UseAgentDefinitionsDocumentOptions): AgentDefinitionsDocumentState {
  const [jsonDraft, setJsonDraft] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [documentRevision, setDocumentRevision] = useState(0);
  const initialSerializedRef = useRef<string>("");
  const currentSerializedRef = useRef<string>("");
  const documentRef = useRef<AgentDefinitionsDocument | null>(null);
  const workflowDebugLogging = isWorkflowDebugLoggingEnabled();

  useEffect(() => {
    if (definitions) {
      const clone = JSON.parse(
        JSON.stringify(definitions)
      ) as AgentDefinitionsDocument;
      documentRef.current = clone;
      const serialized = JSON.stringify(clone);
      const formatted = JSON.stringify(clone, null, 2);
      setJsonDraft(formatted);
      initialSerializedRef.current = serialized;
      currentSerializedRef.current = serialized;
      setJsonError(null);
      setIsDirty(false);
      setSuccessMessage(null);
      setDocumentRevision((previous) => previous + 1);
    } else {
      documentRef.current = null;
      setJsonDraft("");
      setJsonError(null);
      setIsDirty(false);
      setSuccessMessage(null);
      initialSerializedRef.current = "";
      currentSerializedRef.current = "";
      setDocumentRevision((previous) => previous + 1);
    }
  }, [definitions]);

  const handleReload = useCallback(async () => {
    setSuccessMessage(null);
    await onReload();
    setDocumentRevision((previous) => previous + 1);
  }, [onReload]);

  const handleJsonDraftChange = useCallback((value: string) => {
    setJsonDraft(value);

    try {
      const parsed = JSON.parse(value) as AgentDefinitionsDocument;

      if (!Array.isArray(parsed.agents)) {
        throw new Error('Document must include an "agents" array.');
      }

      documentRef.current = parsed;
      setJsonError(null);
      const serialized = JSON.stringify(parsed);
      currentSerializedRef.current = serialized;

      if (initialSerializedRef.current) {
        setIsDirty(serialized !== initialSerializedRef.current);
      } else {
        setIsDirty(true);
      }
      setDocumentRevision((previous) => previous + 1);
    } catch (parseError) {
      const message =
        parseError instanceof Error ? parseError.message : "Invalid JSON";
      setJsonError(message);
      setIsDirty(true);
    }
  }, []);

  const applyDocumentUpdate = useCallback(
    (
      updater: (
        draft: AgentDefinitionsDocument
      ) => AgentDefinitionsDocument | void
    ) => {
      let workingCopy: AgentDefinitionsDocument | null = null;

      if (currentSerializedRef.current) {
        workingCopy = JSON.parse(
          currentSerializedRef.current
        ) as AgentDefinitionsDocument;
      } else if (documentRef.current) {
        workingCopy = JSON.parse(
          JSON.stringify(documentRef.current)
        ) as AgentDefinitionsDocument;
      }

      if (!workingCopy) {
        if (workflowDebugLogging) {
          console.info("[Document] applyDocumentUpdate skipped (no draft)");
        }
        return;
      }

      const updated = updater(workingCopy);
      const nextDocument = (updated ?? workingCopy) as AgentDefinitionsDocument;
      const serialized = JSON.stringify(nextDocument);

      if (serialized === currentSerializedRef.current) {
        if (workflowDebugLogging) {
          console.info("[Document] applyDocumentUpdate no change detected");
        }
        return;
      }

      if (workflowDebugLogging) {
        const startFlags = nextDocument.agents.map((agent) => ({
          workflowId: agent.id,
          startStep:
            agent.steps.find((step) => step.isStartStep)?.name ??
            agent.steps[0]?.name,
        }));

        console.info("[Document] applyDocumentUpdate persisted", {
          isDirty: serialized !== initialSerializedRef.current,
          startFlags,
        });
      }

      documentRef.current = nextDocument;
      currentSerializedRef.current = serialized;
      setJsonDraft(JSON.stringify(nextDocument, null, 2));
      setIsDirty(serialized !== initialSerializedRef.current);
      setDocumentRevision((previous) => previous + 1);
    },
    [workflowDebugLogging]
  );

  const handleSave = useCallback(async () => {
    if (jsonError) {
      return;
    }

    const payloadJson =
      currentSerializedRef.current ||
      (documentRef.current ? JSON.stringify(documentRef.current) : "");

    if (!payloadJson) {
      return;
    }

    const payload = JSON.parse(payloadJson) as AgentDefinitionsDocument;

    setIsSaving(true);
    setSuccessMessage(null);

    try {
      const response = await fetch(`${apiBaseUrl}/api/agents/definitions`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: payloadJson,
      });

      if (!response.ok) {
        throw new Error(
          `Failed to save agent definitions (${response.status})`
        );
      }

      onDefinitionsUpdated(payload);
      setSuccessMessage("Definitions saved successfully.");
      initialSerializedRef.current = payloadJson;
      currentSerializedRef.current = payloadJson;
      setIsDirty(false);
    } catch (saveError) {
      const message =
        saveError instanceof Error
          ? saveError.message
          : "Unable to save definitions.";
      setJsonError(message);
    } finally {
      setIsSaving(false);
    }
  }, [apiBaseUrl, documentRef, jsonError, onDefinitionsUpdated]);

  return {
    draftDocument: documentRef.current,
    jsonDraft,
    jsonError,
    isSaving,
    isDirty,
    successMessage,
    documentRevision,
    handleReload,
    handleJsonDraftChange,
    applyDocumentUpdate,
    handleSave,
    setSuccessMessage,
  };
}
