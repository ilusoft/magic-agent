import clsx from "clsx";
import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  AgentMessage,
  AgentRunResult,
  AgentStepExecutionResult,
} from "../types/agents";

interface WorkflowExecutionPanelProps {
  runs: AgentRunResult[];
  debugError: string | null;
  messages?: AgentMessage[];
}

function renderResolvedParameters(
  resolvedParameters: AgentStepExecutionResult["resolvedParameters"]
) {
  if (!resolvedParameters || Object.keys(resolvedParameters).length === 0) {
    return null;
  }

  const entries = Object.entries(resolvedParameters).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  return (
    <div className="mt-3">
      <span className="text-xs font-semibold uppercase text-foreground/60">
        Resolved Parameters
      </span>
      <div className="mt-1 space-y-1 rounded border border-border/50 bg-muted/20 p-2 text-sm">
        {entries.map(([key, value]) => (
          <div key={key} className="grid gap-1 sm:grid-cols-5">
            <span className="font-medium text-foreground/80 sm:col-span-2">
              {key}
            </span>
            <span className="sm:col-span-3 whitespace-pre-wrap text-foreground/90">
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface UserPromptSummary {
  content: string;
  timestampMs: number | null;
}

function renderThreadContext(
  threadContext: AgentStepExecutionResult["threadContext"]
) {
  if (threadContext === null || typeof threadContext === "undefined") {
    return null;
  }

  let formatted: string | null = null;

  if (typeof threadContext === "string") {
    const trimmed = threadContext.trim();

    if (!trimmed) {
      return null;
    }

    try {
      formatted = JSON.stringify(JSON.parse(trimmed), null, 2);
    } catch {
      formatted = trimmed;
    }
  } else {
    try {
      formatted = JSON.stringify(threadContext, null, 2);
    } catch {
      formatted = String(threadContext);
    }
  }

  if (!formatted) {
    return null;
  }

  return (
    <div className="mt-3">
      <span className="text-xs font-semibold uppercase text-foreground/60">
        Thread Context
      </span>
      <pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded bg-muted/40 p-2 text-sm text-foreground/90">
        {formatted}
      </pre>
    </div>
  );
}

function getRunKey(run: AgentRunResult, index: number): string {
  return `${run.conversationId ?? run.agentId}-${run.completedAt}-${index}`;
}

function findMatchingUserMessage(
  run: AgentRunResult,
  userMessages: UserPromptSummary[]
): UserPromptSummary | undefined {
  if (userMessages.length === 0) {
    return undefined;
  }

  const runTimestamp = Date.parse(run.completedAt);

  if (!Number.isNaN(runTimestamp)) {
    const toleranceMs = 5_000;

    for (let index = userMessages.length - 1; index >= 0; index -= 1) {
      const candidate = userMessages[index];

      if (
        candidate.timestampMs !== null &&
        candidate.timestampMs <= runTimestamp + toleranceMs
      ) {
        return candidate;
      }
    }
  }

  return userMessages[userMessages.length - 1];
}

function safeFormatDate(value: string): string {
  const timestamp = Date.parse(value);

  if (Number.isNaN(timestamp)) {
    return "Timestamp unavailable";
  }

  return new Date(timestamp).toLocaleString();
}

function renderToolResult(result: string | null | undefined) {
  if (!result || result.trim().length === 0) {
    return null;
  }

  const parsed = parseToolResult(result);
  const formatted =
    parsed !== undefined ? JSON.stringify(parsed, null, 2) : result;

  return (
    <div className="space-y-2">
      <div>
        <span className="text-[11px] font-semibold uppercase text-foreground/60">
          Result
        </span>
        <pre className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-background/60 p-2 text-sm text-foreground/90">
          {formatted}
        </pre>
      </div>

      {parsed !== undefined ? (
        <details className="text-xs text-foreground/70">
          <summary className="cursor-pointer select-none text-foreground/60">
            View raw response
          </summary>
          <pre className="mt-1 max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-muted/30 p-2">
            {result}
          </pre>
        </details>
      ) : null}
    </div>
  );
}

function parseToolResult(result: string): unknown | undefined {
  const trimmed = result.trim();

  if (!trimmed) {
    return undefined;
  }

  try {
    return JSON.parse(trimmed);
  } catch {
    return undefined;
  }
}

function renderToolArguments(argumentsJson: string) {
  if (!argumentsJson.trim()) {
    return null;
  }

  const parsed = parseToolResult(argumentsJson);
  const formatted =
    parsed !== undefined ? JSON.stringify(parsed, null, 2) : argumentsJson;

  return (
    <div className="space-y-2">
      <span className="text-[11px] font-semibold uppercase text-foreground/60">
        Arguments
      </span>
      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded bg-muted/30 p-2 text-sm text-foreground/90">
        {formatted}
      </pre>
    </div>
  );
}

export function WorkflowExecutionPanel({
  runs,
  debugError,
  messages,
}: WorkflowExecutionPanelProps) {
  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      const aTimestamp = getRunTimestamp(a);
      const bTimestamp = getRunTimestamp(b);

      if (aTimestamp === null && bTimestamp === null) {
        return 0;
      }

      if (aTimestamp === null) {
        return 1;
      }

      if (bTimestamp === null) {
        return -1;
      }

      return bTimestamp - aTimestamp;
    });
  }, [runs]);

  const userMessages = useMemo<UserPromptSummary[]>(() => {
    return (messages ?? [])
      .filter((message) => message.role === "user")
      .map((message) => {
        const timestampMs = Date.parse(message.timestamp);
        return {
          content: message.content ?? "",
          timestampMs: Number.isNaN(timestampMs) ? null : timestampMs,
        };
      })
      .sort((a, b) => {
        const aValue = a.timestampMs ?? Number.NEGATIVE_INFINITY;
        const bValue = b.timestampMs ?? Number.NEGATIVE_INFINITY;
        return aValue - bValue;
      });
  }, [messages]);

  const [openRunKey, setOpenRunKey] = useState<string | null>(null);

  useEffect(() => {
    if (sortedRuns.length === 0) {
      setOpenRunKey(null);
      return;
    }

    setOpenRunKey((previous) => {
      if (!previous) {
        return getRunKey(sortedRuns[0], 0);
      }

      const stillExists = sortedRuns.some((run, index) => {
        return getRunKey(run, index) === previous;
      });

      return stillExists ? previous : getRunKey(sortedRuns[0], 0);
    });
  }, [sortedRuns]);

  const handleToggle = (runKey: string) => {
    setOpenRunKey((previous) => (previous === runKey ? null : runKey));
  };

  return (
    <div className="space-y-3">
      <h3 className="text-lg font-semibold">Workflow Execution</h3>

      {debugError ? (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {debugError}
        </p>
      ) : null}

      {sortedRuns.length === 0 && !debugError ? (
        <p className="rounded-md border border-dashed border-border p-4 text-sm text-foreground/70">
          Run the agent to view how each workflow step executes and hands off
          data internally.
        </p>
      ) : null}

      {sortedRuns.length > 0 ? (
        <div className="space-y-3">
          {sortedRuns.length > 1 ? (
            <div className="flex justify-end">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1 text-xs text-foreground/70 hover:bg-muted"
                onClick={() => setOpenRunKey(null)}
              >
                Collapse all
              </button>
            </div>
          ) : null}

          <div className="space-y-2">
            {sortedRuns.map((run, runIndex) => {
              const runKey = getRunKey(run, runIndex);
              const isOpen = openRunKey === runKey;
              const summaryTitle = buildRunSummary(run, userMessages, runIndex);

              return (
                <div
                  key={runKey}
                  className="rounded-md border border-border bg-card"
                >
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm font-medium text-foreground/80 hover:bg-muted/40"
                    onClick={() => handleToggle(runKey)}
                  >
                    <span className="truncate">{summaryTitle}</span>
                    <ChevronDown
                      className={clsx(
                        "h-4 w-4 transition-transform duration-200",
                        isOpen ? "rotate-180" : "rotate-0"
                      )}
                    />
                  </button>

                  {isOpen ? (
                    <div className="space-y-3 border-t border-border/60 px-4 pb-4 pt-3">
                      {run.steps.length === 0 ? (
                        <p className="text-sm text-foreground/60">
                          No workflow steps were executed.
                        </p>
                      ) : (
                        <ol className="space-y-3">
                          {run.steps.map((step, index) => (
                            <li
                              key={`${runKey}-${step.name}-${index}`}
                              className="rounded-md border border-primary/40 bg-background/80 p-3"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <div className="text-sm font-medium">
                                  {step.name}
                                </div>
                                <span className="rounded bg-primary/10 px-2 py-1 text-xs uppercase tracking-wide text-primary">
                                  {step.type}
                                </span>
                              </div>

                              <div className="mt-3 grid gap-2 text-sm text-foreground/80">
                                {step.outcome ? (
                                  <div>
                                    <span className="text-xs font-semibold uppercase text-foreground/60">
                                      Outcome
                                    </span>
                                    <div>{step.outcome}</div>
                                  </div>
                                ) : null}

                                {step.nextStep ? (
                                  <div>
                                    <span className="text-xs font-semibold uppercase text-foreground/60">
                                      Next Step
                                    </span>
                                    <div>{step.nextStep}</div>
                                  </div>
                                ) : null}

                                {step.endWorkflow ? (
                                  <div>
                                    <span className="text-xs font-semibold uppercase text-foreground/60">
                                      Workflow
                                    </span>
                                    <div>Terminated</div>
                                  </div>
                                ) : null}
                              </div>

                              {step.input ? (
                                <div className="mt-3">
                                  <span className="text-xs font-semibold uppercase text-foreground/60">
                                    Input
                                  </span>
                                  <pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded bg-muted/40 p-2 text-sm text-foreground/90">
                                    {step.input}
                                  </pre>
                                </div>
                              ) : null}

                              <div className="mt-3">
                                <span className="text-xs font-semibold uppercase text-foreground/60">
                                  Output
                                </span>
                                <pre className="mt-1 max-h-52 overflow-y-auto whitespace-pre-wrap rounded bg-muted/40 p-2 text-sm text-foreground/90">
                                  {step.output}
                                </pre>
                              </div>

                              {renderThreadContext(step.threadContext)}

                              {renderResolvedParameters(
                                step.resolvedParameters
                              )}

                              {renderToolInvocations(step)}
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function buildRunSummary(
  run: AgentRunResult,
  userMessages: UserPromptSummary[],
  fallbackIndex: number
): string {
  const matchedMessage = findMatchingUserMessage(run, userMessages);
  const previewSource = matchedMessage?.content?.trim() ?? "";
  const preview = previewSource
    ? previewSource.slice(0, 20)
    : `Run #${fallbackIndex + 1}`;
  const includeEllipsis = previewSource.length > 20;

  const timestamp = matchedMessage?.timestampMs
    ? new Date(matchedMessage.timestampMs).toLocaleString()
    : safeFormatDate(run.completedAt);

  return `Run for: ${preview}${includeEllipsis ? "…" : ""} at ${timestamp}`;
}

function getRunTimestamp(run: AgentRunResult): number | null {
  if (!run.completedAt) {
    return null;
  }

  const timestamp = Date.parse(run.completedAt);

  return Number.isNaN(timestamp) ? null : timestamp;
}

function renderToolInvocations(step: AgentStepExecutionResult) {
  const toolInvocations = step.toolInvocations ?? [];

  if (toolInvocations.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-foreground/60">
          Tool Invocations
        </span>
        {step.toolErrorDetected ? (
          <span className="rounded bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-destructive">
            Errors detected
          </span>
        ) : null}
      </div>

      <ul className="space-y-2">
        {toolInvocations.map((invocation, index) => (
          <li
            key={`${step.name}-tool-${invocation.invocationId ?? index}`}
            className="rounded border border-border/60 bg-muted/20 p-3 text-sm text-foreground/80"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-medium">
                {invocation.toolName ?? "Unknown tool"}
              </div>
              {invocation.invocationId ? (
                <span className="text-xs uppercase tracking-wide text-foreground/60">
                  #{invocation.invocationId}
                </span>
              ) : null}
            </div>

            <div className="mt-2 space-y-3">
              {invocation.argumentsJson
                ? renderToolArguments(invocation.argumentsJson)
                : null}
              {renderToolResult(invocation.result)}
            </div>

            {invocation.errorMessage || invocation.errorDetails ? (
              <div className="mt-2 rounded border border-destructive/40 bg-destructive/5 p-2 text-[13px] text-destructive">
                {invocation.errorMessage ? (
                  <p className="font-semibold">{invocation.errorMessage}</p>
                ) : null}
                {invocation.errorDetails ? (
                  <p className="mt-1 whitespace-pre-wrap text-destructive/80">
                    {invocation.errorDetails}
                  </p>
                ) : null}
                {invocation.errorCode ? (
                  <p className="mt-1 text-xs uppercase tracking-wide text-destructive/60">
                    Code: {invocation.errorCode}
                  </p>
                ) : null}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
