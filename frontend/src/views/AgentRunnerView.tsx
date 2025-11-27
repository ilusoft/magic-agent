import { useCallback, useEffect, useMemo } from "react";
import clsx from "clsx";
import { BugPlay, MessageCircle } from "lucide-react";
import type {
  AgentConversationDiagnostics,
  AgentDefinitionsDocument,
  AgentMessage,
  AgentWorkflowResult,
} from "../types/agents";
import { AgentChat } from "../components/AgentChat";
import { WorkflowExecutionPanel } from "../components/WorkflowExecutionPanel";

export interface AgentRunnerState {
  selectedAgentId?: string;
  input: string;
  conversationId: string | null;
  conversation: AgentMessage[];
  isRunning: boolean;
  runError: string | null;
  authHeaderName: string;
  authHeaderValue: string;
  diagnostics: AgentConversationDiagnostics | null;
  debugError: string | null;
  showDebugPanel: boolean;
}

interface AgentRunnerViewProps {
  definitions: AgentDefinitionsDocument | null;
  loading: boolean;
  error: string | null;
  apiBaseUrl: string;
  runnerState: AgentRunnerState;
  setRunnerState: React.Dispatch<React.SetStateAction<AgentRunnerState>>;
}

export function AgentRunnerView({
  definitions,
  loading,
  error,
  apiBaseUrl,
  runnerState,
  setRunnerState,
}: AgentRunnerViewProps) {
  const agents = definitions?.agents ?? [];
  const {
    selectedAgentId,
    input,
    conversationId,
    conversation,
    isRunning,
    runError,
    authHeaderName,
    authHeaderValue,
    diagnostics,
    debugError,
    showDebugPanel,
  } = runnerState;

  const handleSelectAgent = useCallback(
    (id: string) => {
      if (id === selectedAgentId) {
        return;
      }

      setRunnerState((previous) => ({
        ...previous,
        selectedAgentId: id,
        conversation: [],
        conversationId: null,
        diagnostics: null,
        debugError: null,
        runError: null,
        showDebugPanel: false,
        input: "",
      }));
    },
    [selectedAgentId, setRunnerState]
  );

  const selectedAgent = useMemo(() => {
    if (!selectedAgentId) {
      return undefined;
    }

    return agents.find((agent) => agent.id === selectedAgentId);
  }, [agents, selectedAgentId]);

  const sortMessages = useCallback((messages: AgentMessage[]) => {
    return [...messages].sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, []);

  const createAuthHeaders = useCallback(() => {
    const headerName = authHeaderName.trim() || "Authorization";
    const headerValue = authHeaderValue.trim();

    if (!headerValue) {
      return {};
    }

    return { [headerName]: headerValue };
  }, [authHeaderName, authHeaderValue]);

  const loadDiagnostics = useCallback(
    async (
      agentId: string,
      conversationIdentifier: string,
      headers: Record<string, string>
    ) => {
      try {
        setRunnerState((previous) => ({
          ...previous,
          debugError: null,
        }));

        const response = await fetch(
          `${apiBaseUrl}/api/agents/${agentId}/runs/${conversationIdentifier}/debug`,
          {
            method: "GET",
            headers,
          }
        );

        if (response.status === 404) {
          setRunnerState((previous) => ({
            ...previous,
            diagnostics: null,
            debugError: "No diagnostics available yet for this conversation.",
          }));
          return;
        }

        if (!response.ok) {
          throw new Error(`Failed to load diagnostics (${response.status})`);
        }

        const diagnosticsData =
          (await response.json()) as AgentConversationDiagnostics;
        setRunnerState((previous) => ({
          ...previous,
          diagnostics: diagnosticsData,
        }));
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Unable to load diagnostics.";
        setRunnerState((previous) => ({
          ...previous,
          debugError: message,
        }));
      }
    },
    [apiBaseUrl, setRunnerState]
  );

  useEffect(() => {
    if (agents.length > 0) {
      setRunnerState((previous) => ({
        ...previous,
        selectedAgentId: previous.selectedAgentId ?? agents[0].id,
      }));
    } else {
      setRunnerState((previous) => ({
        ...previous,
        selectedAgentId: undefined,
        conversation: [],
        conversationId: null,
        diagnostics: null,
        debugError: null,
        runError: null,
      }));
    }
  }, [agents, setRunnerState]);

  const handleRun = async () => {
    if (!selectedAgentId || !input.trim()) {
      return;
    }

    setRunnerState((previous) => ({
      ...previous,
      isRunning: true,
      runError: null,
      debugError: null,
    }));

    try {
      const authHeaders = createAuthHeaders();

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...authHeaders,
      };

      const userMessage: AgentMessage = {
        role: "user",
        content: input,
        timestamp: new Date().toISOString(),
      };

      setRunnerState((previous) => ({
        ...previous,
        conversation: sortMessages([...previous.conversation, userMessage]),
      }));

      const response = await fetch(
        `${apiBaseUrl}/api/agents/${selectedAgentId}/runs`,
        {
          method: "POST",
          headers,
          body: JSON.stringify({ input, conversationId }),
        }
      );

      if (!response.ok) {
        throw new Error(`Agent run failed (${response.status})`);
      }

      const result = (await response.json()) as AgentWorkflowResult;

      const assistantOutput = result.lastStep?.output;

      if (assistantOutput) {
        const assistantMessage: AgentMessage = {
          role: "assistant",
          content: assistantOutput,
          timestamp: new Date().toISOString(),
        };

        setRunnerState((previous) => ({
          ...previous,
          conversation: sortMessages([
            ...previous.conversation,
            assistantMessage,
          ]),
        }));
      }

      if (result.conversationId) {
        setRunnerState((previous) => ({
          ...previous,
          conversationId: result.conversationId ?? null,
        }));
        await loadDiagnostics(
          selectedAgentId,
          result.conversationId,
          authHeaders
        );
      }

      setRunnerState((previous) => ({
        ...previous,
        input: "",
      }));
    } catch (runErr) {
      const message =
        runErr instanceof Error ? runErr.message : "Agent run failed.";
      setRunnerState((previous) => ({
        ...previous,
        runError: message,
      }));
    } finally {
      setRunnerState((previous) => ({
        ...previous,
        isRunning: false,
      }));
    }
  };

  const handleResetConversation = () => {
    setRunnerState((previous) => ({
      ...previous,
      conversation: [],
      conversationId: null,
      runError: null,
      diagnostics: null,
      debugError: null,
      input: "",
    }));
  };

  const workflowRuns = diagnostics?.runs ?? [];

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-4">
      <div className="rounded-md border border-border bg-card p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">Agent Runner</h2>
            <p className="text-sm text-foreground/70">
              Select a workflow to chat with and inspect execution details.
            </p>
          </div>

          <button
            type="button"
            className="self-start rounded-md border border-border px-3 py-2 text-sm disabled:opacity-60"
            onClick={handleResetConversation}
            disabled={conversation.length === 0 && !conversationId}
          >
            Reset conversation
          </button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {agents.length === 0 ? (
            <p className="text-sm text-foreground/60">
              No workflows available.
            </p>
          ) : (
            agents.map((agent) => {
              const isActive = selectedAgentId === agent.id;

              return (
                <button
                  key={agent.id}
                  type="button"
                  className={clsx(
                    "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
                    isActive
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-background text-foreground/80 hover:bg-muted/60"
                  )}
                  onClick={() => handleSelectAgent(agent.id)}
                  disabled={loading}
                  title={agent.name?.trim() ? agent.name : agent.id}
                >
                  <span className="truncate">
                    {agent.name?.trim() ? agent.name : agent.id}
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="block font-medium">Authorization header name</span>
            <input
              type="text"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={authHeaderName}
              onChange={(event) =>
                setRunnerState((previous) => ({
                  ...previous,
                  authHeaderName: event.target.value,
                }))
              }
              placeholder="Authorization"
            />
          </label>

          <label className="space-y-1 text-sm md:col-span-1">
            <span className="block font-medium">
              Authorization header value
            </span>
            <input
              type="text"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={authHeaderValue}
              onChange={(event) =>
                setRunnerState((previous) => ({
                  ...previous,
                  authHeaderValue: event.target.value,
                }))
              }
              placeholder="Bearer &lt;token&gt;"
            />
          </label>

          <p className="md:col-span-2 text-xs text-foreground/60">
            Tokens entered here are forwarded with each run for MCP tools
            configured with
            <code className="mx-1 rounded bg-muted px-1">
              forwardAuthorizationHeader
            </code>
            .
          </p>
        </div>
      </div>

      {error ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-2">
        <div className="text-sm text-foreground/70">
          <span className="font-semibold">View:</span>{" "}
          <span>
            {showDebugPanel ? "Workflow execution & tools" : "Conversation"}
          </span>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-foreground/80 hover:bg-muted"
          onClick={() =>
            setRunnerState((previous) => ({
              ...previous,
              showDebugPanel: !previous.showDebugPanel,
            }))
          }
        >
          {showDebugPanel ? (
            <>
              <MessageCircle className="h-3.5 w-3.5" />
              <span>Show conversation</span>
            </>
          ) : (
            <>
              <BugPlay className="h-3.5 w-3.5" />
              <span>Show debug</span>
            </>
          )}
        </button>
      </div>

      <div className="flex-1 overflow-hidden rounded-md border border-border bg-card">
        {showDebugPanel ? (
          <div className="flex h-full flex-col overflow-y-auto p-4">
            <WorkflowExecutionPanel
              runs={workflowRuns}
              debugError={debugError}
              messages={conversation}
            />

            <div className="mt-6 space-y-3">
              <h3 className="text-lg font-semibold">Tools</h3>

              {selectedAgent?.tools && selectedAgent.tools.length > 0 ? (
                <div className="space-y-3">
                  {selectedAgent.tools.map((tool) => (
                    <div
                      key={tool.id}
                      className="rounded-md border border-border bg-card p-4 text-sm"
                    >
                      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div className="font-medium">
                          {tool.name || tool.id}
                        </div>
                        <span className="text-xs uppercase tracking-wide text-foreground/60">
                          {tool.type}
                        </span>
                      </div>

                      {tool.description ? (
                        <p className="mt-1 text-foreground/70">
                          {tool.description}
                        </p>
                      ) : null}

                      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                        {tool.serverUrl ? (
                          <div>
                            <dt className="text-xs font-semibold uppercase text-foreground/60">
                              Server URL
                            </dt>
                            <dd className="break-all text-foreground/80">
                              {tool.serverUrl}
                            </dd>
                          </div>
                        ) : null}

                        {tool.protocol ? (
                          <div>
                            <dt className="text-xs font-semibold uppercase text-foreground/60">
                              Protocol
                            </dt>
                            <dd className="text-foreground/80">
                              {tool.protocol}
                            </dd>
                          </div>
                        ) : null}

                        {tool.allowedTools && tool.allowedTools.length > 0 ? (
                          <div className="sm:col-span-2">
                            <dt className="text-xs font-semibold uppercase text-foreground/60">
                              Allowed tools
                            </dt>
                            <dd className="text-foreground/80">
                              {tool.allowedTools.join(", ")}
                            </dd>
                          </div>
                        ) : null}
                      </dl>

                      {tool.headers && Object.keys(tool.headers).length > 0 ? (
                        <div className="mt-3">
                          <p className="text-xs font-semibold uppercase text-foreground/60">
                            Headers
                          </p>
                          <ul className="mt-1 space-y-1">
                            {Object.entries(tool.headers).map(
                              ([headerKey, headerValue]) => (
                                <li
                                  key={headerKey}
                                  className="flex justify-between gap-3 rounded bg-muted px-2 py-1 text-xs"
                                >
                                  <span className="font-medium">
                                    {headerKey}
                                  </span>
                                  <span className="truncate">
                                    {headerValue}
                                  </span>
                                </li>
                              )
                            )}
                          </ul>
                        </div>
                      ) : null}

                      {tool.actions && tool.actions.length > 0 ? (
                        <div className="mt-3 space-y-2">
                          <p className="text-xs font-semibold uppercase text-foreground/60">
                            Actions
                          </p>
                          <ul className="space-y-2">
                            {tool.actions.map((action) => (
                              <li
                                key={action.name}
                                className="rounded border border-border/60 px-2 py-2"
                              >
                                <div className="flex items-center justify-between text-xs font-medium">
                                  <span>{action.name}</span>
                                  {action.parameters &&
                                  Object.keys(action.parameters).length > 0 ? (
                                    <span className="text-foreground/60">
                                      {action.parameters.tool ?? ""}
                                    </span>
                                  ) : null}
                                </div>
                                {action.description ? (
                                  <p className="mt-1 text-xs text-foreground/70">
                                    {action.description}
                                  </p>
                                ) : null}
                                {action.parameters &&
                                Object.keys(action.parameters).length > 0 ? (
                                  <div className="mt-2 text-[11px] text-foreground/70">
                                    <p className="font-semibold uppercase text-foreground/60">
                                      Parameters
                                    </p>
                                    <ul className="mt-1 space-y-1">
                                      {Object.entries(action.parameters).map(
                                        ([paramKey, paramValue]) => (
                                          <li
                                            key={`${action.name}-${paramKey}`}
                                            className="flex justify-between gap-3"
                                          >
                                            <span className="font-medium">
                                              {paramKey}
                                            </span>
                                            <span className="truncate">
                                              {paramValue}
                                            </span>
                                          </li>
                                        )
                                      )}
                                    </ul>
                                  </div>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="rounded-md border border-dashed border-border p-4 text-sm text-foreground/70">
                  This agent does not have any MCP tools configured.
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="flex h-full flex-col p-4">
            <AgentChat
              conversation={conversation}
              input={input}
              onInputChange={(value) =>
                setRunnerState((previous) => ({
                  ...previous,
                  input: value,
                }))
              }
              onSend={handleRun}
              isRunning={isRunning}
              runError={runError}
              disableSend={!selectedAgentId || !input.trim()}
            />
          </div>
        )}
      </div>
    </div>
  );
}
