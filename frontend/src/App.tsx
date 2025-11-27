import { useCallback, useEffect, useMemo, useState } from "react";
import "./index.css";
import type { AgentDefinitionsDocument } from "./types/agents";
import { AgentDefinitionsView } from "./views/AgentDefinitionsView";
import { AgentRunnerView } from "./views/AgentRunnerView";
import type { AgentRunnerState } from "./views/AgentRunnerView";

type ActiveView = "editor" | "runner";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5134";

function App() {
  const [activeView, setActiveView] = useState<ActiveView>("editor");
  const [definitions, setDefinitions] =
    useState<AgentDefinitionsDocument | null>(null);
  const [loadingDefs, setLoadingDefs] = useState(false);
  const [definitionsError, setDefinitionsError] = useState<string | null>(null);
  const [runnerState, setRunnerState] = useState<AgentRunnerState>({
    selectedAgentId: undefined,
    input: "",
    conversationId: null,
    conversation: [],
    isRunning: false,
    runError: null,
    authHeaderName: "Authorization",
    authHeaderValue: "",
    diagnostics: null,
    debugError: null,
    showDebugPanel: false,
  });

  const loadDefinitions = useCallback(async () => {
    setLoadingDefs(true);
    setDefinitionsError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/agents/definitions`);

      if (!response.ok) {
        throw new Error(
          `Failed to load agent definitions (${response.status})`
        );
      }

      const document = (await response.json()) as AgentDefinitionsDocument;
      setDefinitions(document);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to load agent definitions.";
      setDefinitionsError(message);
    } finally {
      setLoadingDefs(false);
    }
  }, []);

  useEffect(() => {
    loadDefinitions();
  }, [loadDefinitions]);

  const handleDefinitionsUpdated = (document: AgentDefinitionsDocument) => {
    setDefinitions(document);
  };

  const handleReloadDefinitions = useCallback(async () => {
    await loadDefinitions();
  }, [loadDefinitions]);

  const content = useMemo(() => {
    if (activeView === "editor") {
      return (
        <AgentDefinitionsView
          definitions={definitions}
          loading={loadingDefs}
          error={definitionsError}
          onReload={handleReloadDefinitions}
          onDefinitionsUpdated={handleDefinitionsUpdated}
          apiBaseUrl={API_BASE_URL}
        />
      );
    }

    return (
      <AgentRunnerView
        definitions={definitions}
        loading={loadingDefs}
        error={definitionsError}
        apiBaseUrl={API_BASE_URL}
        runnerState={runnerState}
        setRunnerState={setRunnerState}
      />
    );
  }, [
    activeView,
    definitions,
    loadingDefs,
    definitionsError,
    handleReloadDefinitions,
    runnerState,
  ]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <img className="h-10" src="robot-color.svg" alt="Magic Agent" />
            <span className="text-lg font-semibold">Magic Agent Console</span>
          </div>
          <nav className="flex items-center gap-2">
            <HeaderButton
              active={activeView === "editor"}
              onClick={() => setActiveView("editor")}
            >
              Agent Definitions
            </HeaderButton>

            <HeaderButton
              active={activeView === "runner"}
              onClick={() => setActiveView("runner")}
            >
              Agent Runner
            </HeaderButton>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">{content}</main>
    </div>
  );
}

interface HeaderButtonProps {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}

function HeaderButton({ active, children, onClick }: HeaderButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-primary text-primary-foreground"
          : "text-foreground/70 hover:bg-muted hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}
export default App;
