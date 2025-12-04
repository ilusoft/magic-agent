import type { AgentDefinitionsDocument } from "../../../types/agents";

export type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;
