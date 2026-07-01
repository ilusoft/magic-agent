import clsx from "clsx";
import { Bot, ChevronDown, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  AgentMessage,
  AgentRunResult,
  AgentStepExecutionResult,
  AgentStepLiveTrace,
  LLMCallConfig,
  WorkflowVariableDataType,
} from "@/types/agents";
import {
  buildAgentTraceEntries,
  type AgentTraceEntry,
} from "@/lib/agentTrace";

interface WorkflowExecutionPanelProps {
  runs: AgentRunResult[];
  debugError: string | null;
  messages?: AgentMessage[];
  /**
   * Optional live trace entries captured from the SSE stream. Keyed
   * by step name. Used to render the agent's reasoning as it
   * happens, then superseded by the persisted `iterations` and
   * `toolInvocations` arrays once the diagnostics payload loads.
   */
  liveTraces?: Record<string, AgentStepLiveTrace>;
}

function renderParameterDebug(
  parameterDebug: AgentStepExecutionResult["parameterDebug"]
) {
  if (!parameterDebug || Object.keys(parameterDebug).length === 0) {
    return null;
  }

  const entries = Object.entries(parameterDebug).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold uppercase text-foreground/60">
          Parameter Debug
        </span>
        <span className="text-foreground/50">
          Original templates vs. resolved values
        </span>
      </div>

      {entries.map(([key, details]) => (
        <div
          key={key}
          className="space-y-2 rounded border border-border/40 bg-muted/10 p-2 text-sm text-foreground/80"
        >
          <span className="font-medium text-foreground">{key}</span>
          <dl className="grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="font-semibold text-foreground/70">
                Original value
              </dt>
              <dd className="whitespace-pre-wrap text-foreground/90">
                {formatDebugValue(details.originalValue)}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-foreground/70">
                Resolved value
              </dt>
              <dd className="whitespace-pre-wrap text-foreground/90">
                {formatDebugValue(details.resolvedValue)}
              </dd>
            </div>
          </dl>
          <div className="text-xs">
            <dt className="font-semibold text-foreground/70">Placeholders</dt>
            <dd className="mt-1 flex flex-wrap gap-1">
              {renderPlaceholderBadges(details.placeholders)}
            </dd>
          </div>
        </div>
      ))}
    </div>
  );
}

function renderPlaceholderBadges(placeholders?: string[]) {
  if (!placeholders || placeholders.length === 0) {
    return <span className="text-foreground/50">None referenced</span>;
  }

  return placeholders.map((placeholder) => (
    <span
      key={placeholder}
      className="rounded bg-primary/10 px-1.5 py-0.5 text-[11px] font-medium text-primary"
    >
      {`{{${placeholder}}}`}
    </span>
  ));
}

function renderVariableDebug(
  variableDebug: AgentStepExecutionResult["variableDebug"]
) {
  if (!variableDebug || Object.keys(variableDebug).length === 0) {
    return null;
  }

  const entries = Object.entries(variableDebug).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold uppercase text-foreground/60">
          Variable Assignments
        </span>
        <span className="text-foreground/50">
          Raw inputs vs. stored values per data type
        </span>
      </div>

      {entries.map(([key, details]) => (
        <div
          key={key}
          className="space-y-2 rounded border border-border/40 bg-muted/10 p-2 text-sm text-foreground/80"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-medium text-foreground">{key}</span>
            <span className="rounded bg-primary/10 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-primary">
              {formatVariableTypeLabel(details.type)}
            </span>
          </div>
          <dl className="grid gap-3 text-xs sm:grid-cols-2">
            <div>
              <dt className="font-semibold text-foreground/70">Raw value</dt>
              <dd className="whitespace-pre-wrap text-foreground/90">
                {formatDebugValue(details.rawValue)}
              </dd>
            </div>
            <div>
              <dt className="font-semibold text-foreground/70">Stored value</dt>
              <dd className="whitespace-pre-wrap text-foreground/90">
                {formatDebugValue(details.convertedValue)}
              </dd>
            </div>
          </dl>
          {details.error ? (
            <p className="text-xs text-destructive">{details.error}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

const VARIABLE_TYPE_LABELS: Record<WorkflowVariableDataType, string> = {
  string: "String",
  number: "Number",
  boolean: "Boolean",
  dateTime: "Date & Time",
  json: "JSON",
};

function formatVariableTypeLabel(type?: WorkflowVariableDataType) {
  if (!type) {
    return VARIABLE_TYPE_LABELS.string;
  }

  return VARIABLE_TYPE_LABELS[type] ?? VARIABLE_TYPE_LABELS.string;
}

function formatDebugValue(value: string | undefined) {
  if (typeof value === "undefined" || value === null) {
    return "—";
  }

  if (value.length === 0) {
    return "(empty string)";
  }

  return value;
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

const PROVIDER_LABELS: Record<string, string> = {
  "azure-openai": "Azure OpenAI",
  "openai-compatible": "OpenAI-compatible (local)",
  openai: "OpenAI",
};

function formatProviderLabel(provider?: string | null) {
  if (!provider) {
    return "Unknown provider";
  }
  return PROVIDER_LABELS[provider] ?? provider;
}

function hasLLMConfigContent(config: LLMCallConfig | null | undefined) {
  if (!config) {
    return false;
  }
  return Boolean(
    config.provider ||
      config.model ||
      config.endpoint ||
      config.baseUrl ||
      config.deployment ||
      config.apiVersion ||
      config.temperature !== undefined && config.temperature !== null ||
      config.maxTokens ||
      config.apiKeyFingerprint
  );
}

function renderLLMConfig(llmConfig: AgentStepExecutionResult["llmConfig"]) {
  if (!hasLLMConfigContent(llmConfig)) {
    return null;
  }

  const provider = llmConfig?.provider ?? null;
  const model = llmConfig?.model ?? null;
  const endpoint = llmConfig?.endpoint ?? null;
  const baseUrl = llmConfig?.baseUrl ?? null;
  const deployment = llmConfig?.deployment ?? null;
  const apiVersion = llmConfig?.apiVersion ?? null;
  const apiKeyFingerprint = llmConfig?.apiKeyFingerprint ?? null;
  const temperature = llmConfig?.temperature;
  const maxTokens = llmConfig?.maxTokens ?? null;

  const rows: Array<{ label: string; value: string | null }> = [
    { label: "Provider", value: formatProviderLabel(provider) },
    { label: "Model", value: model },
    { label: "Endpoint", value: endpoint },
    { label: "Base URL", value: baseUrl },
    { label: "Deployment", value: deployment },
    { label: "API version", value: apiVersion },
    {
      label: "Temperature",
      value:
        temperature === undefined || temperature === null
          ? null
          : String(temperature),
    },
    { label: "Max tokens", value: maxTokens === null ? null : String(maxTokens) },
    { label: "API key", value: apiKeyFingerprint },
  ];

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold uppercase text-foreground/60">
          LLM Call
        </span>
        {provider ? (
          <span
            className={clsx(
              "rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
              provider === "azure-openai" &&
                "bg-primary/10 text-primary",
              provider === "openai-compatible" &&
                "bg-amber-500/15 text-amber-700 dark:text-amber-300",
              provider === "openai" && "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
            )}
          >
            {formatProviderLabel(provider)}
          </span>
        ) : null}
      </div>

      <dl className="grid gap-2 rounded border border-border/40 bg-muted/10 p-2 text-xs text-foreground/80 sm:grid-cols-2">
        {rows
          .filter((row) => row.value !== null && row.value !== "")
          .map((row) => (
            <div key={row.label} className="min-w-0">
              <dt className="font-semibold text-foreground/60">{row.label}</dt>
              <dd className="break-words whitespace-pre-wrap text-foreground/90">
                {row.value}
              </dd>
            </div>
          ))}
      </dl>
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
  liveTraces,
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

      {renderLiveTracePanel(liveTraces)}

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

                              {renderParameterDebug(step.parameterDebug)}

                              {renderResolvedParameters(
                                step.resolvedParameters
                              )}

                              {renderVariableDebug(step.variableDebug)}

                              {renderLLMConfig(step.llmConfig)}

                              {renderToolInvocations(step)}

                              {renderAgentTrace(step, liveTraces?.[step.name])}
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

/**
 * Render the in-flight live trace while the SSE stream is still
 * producing events. The diagnostics payload (and the per-step
 * ``Agent Trace`` rendered inside the persisted run list) will
 * supersede this once it arrives; this section is what the
 * operator watches while the agent is mid-run.
 */
function renderLiveTracePanel(
  liveTraces: Record<string, AgentStepLiveTrace> | undefined
) {
  if (!liveTraces) {
    return null;
  }
  const entries = Object.values(liveTraces).filter(
    (trace) =>
      trace.iterations.length > 0 || trace.toolCalls.length > 0
  );
  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
            Live Trace
          </span>
          <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
            Running
          </span>
        </div>
        <span className="text-xs text-foreground/60">
          {entries.length} {entries.length === 1 ? "step" : "steps"} in
          flight
        </span>
      </div>
      <div className="space-y-3">
        {entries
          .sort((a, b) => a.stepName.localeCompare(b.stepName))
          .map((trace) => {
            const syntheticStep: AgentStepExecutionResult = {
              name: trace.stepName,
              type: "agent",
              output: "",
              iterations: trace.iterations,
              toolInvocations: trace.toolCalls,
            };
            return (
              <div
                key={`live-${trace.stepName}`}
                className="rounded border border-border/40 bg-background/80 p-3"
              >
                <div className="mb-2 flex items-center justify-between text-xs">
                  <span className="font-semibold uppercase text-foreground/60">
                    {trace.stepName}
                  </span>
                  <span className="text-foreground/60">
                    {trace.iterations.length}{" "}
                    {trace.iterations.length === 1
                      ? "iteration"
                      : "iterations"}
                    , {trace.toolCalls.length}{" "}
                    {trace.toolCalls.length === 1
                      ? "tool call"
                      : "tool calls"}
                  </span>
                </div>
                {renderAgentTraceEntries(
                  buildAgentTraceEntries(syntheticStep, trace),
                  trace.stepName
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}

function renderAgentTraceEntries(entries: AgentTraceEntry[], stepName: string) {
  if (entries.length === 0) {
    return null;
  }

  return (
    <ol className="mt-4 space-y-2">
      {entries.map((entry, index) => {
        if (entry.kind === "iteration") {
          return (
            <li
              key={`${stepName}-iter-${entry.trace.iteration}-${index}`}
              className="rounded border border-primary/30 bg-primary/5 p-3 text-sm text-foreground/90"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium">
                  <Bot className="h-3.5 w-3.5 text-primary" />
                  <span>
                    Iteration {entry.trace.iteration + 1}
                  </span>
                  {entry.trace.hasToolCalls ? (
                    <span className="rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
                      Tool call
                    </span>
                  ) : null}
                </div>
                <span className="text-xs uppercase tracking-wide text-foreground/60">
                  {formatIterationTimestamp(entry.trace.timestamp)}
                </span>
              </div>
              {entry.trace.content ? (
                <p className="mt-2 whitespace-pre-wrap text-foreground/80">
                  {entry.trace.content}
                </p>
              ) : (
                <p className="mt-2 text-xs italic text-foreground/60">
                  (assistant produced no text on this turn — it
                  requested{" "}
                  {entry.trace.toolCallNames.length === 1
                    ? `the ${entry.trace.toolCallNames[0]} tool`
                    : `${entry.trace.toolCallNames.length} tools`}
                  )
                </p>
              )}
              {entry.trace.toolCallNames.length > 0 ? (
                <p className="mt-1 text-xs text-foreground/60">
                  Tools requested: {entry.trace.toolCallNames.join(", ")}
                </p>
              ) : null}
            </li>
          );
        }

        const call = entry.toolCall;
        return (
          <li
            key={`${stepName}-trace-tool-${call.invocationId ?? index}`}
            className={clsx(
              "rounded border p-3 text-sm",
              call.errorMessage
                ? "border-destructive/40 bg-destructive/5"
                : "border-emerald-500/40 bg-emerald-500/5"
            )}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-medium text-foreground/90">
                <Wrench className="h-3.5 w-3.5" />
                <span>{call.toolName ?? "Unknown tool"}</span>
              </div>
              {call.invocationId ? (
                <span className="text-xs uppercase tracking-wide text-foreground/60">
                  #{call.invocationId}
                </span>
              ) : null}
            </div>
            {call.argumentsJson ? renderToolArguments(call.argumentsJson) : null}
            {renderToolResult(call.result)}
            {call.errorMessage || call.errorDetails ? (
              <div className="mt-2 rounded border border-destructive/40 bg-destructive/10 p-2 text-[13px] text-destructive">
                {call.errorMessage ? (
                  <p className="font-semibold">{call.errorMessage}</p>
                ) : null}
                {call.errorDetails ? (
                  <p className="mt-1 whitespace-pre-wrap text-destructive/80">
                    {call.errorDetails}
                  </p>
                ) : null}
                {call.errorCode ? (
                  <p className="mt-1 text-xs uppercase tracking-wide text-destructive/60">
                    Code: {call.errorCode}
                  </p>
                ) : null}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function formatIterationTimestamp(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return "—";
  }
  return new Date(timestamp).toLocaleTimeString();
}

function renderAgentTrace(
  step: AgentStepExecutionResult,
  liveTrace: AgentStepLiveTrace | undefined
) {
  const entries = buildAgentTraceEntries(step, liveTrace);
  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-foreground/60">
          Agent Trace
        </span>
        <span className="text-xs text-foreground/60">
          {entries.filter((entry) => entry.kind === "iteration").length}{" "}
          {entries.filter((entry) => entry.kind === "iteration").length === 1
            ? "iteration"
            : "iterations"}
          ,{" "}
          {entries.filter((entry) => entry.kind === "tool-call").length}{" "}
          {entries.filter((entry) => entry.kind === "tool-call").length === 1
            ? "tool call"
            : "tool calls"}
        </span>
      </div>
      {renderAgentTraceEntries(entries, step.name)}
    </div>
  );
}
