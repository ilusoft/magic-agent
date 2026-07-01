import type {
  AgentIterationTrace,
  AgentStepExecutionResult,
  AgentStepLiveTrace,
  AgentToolCall,
} from "@/types/agents";

/**
 * A single node in the agent trace timeline. The panel renders one
 * row per entry, in array order, with iteration rows showing the
 * assistant's reasoning and tool-call rows showing the tool that
 * was executed.
 */
export type AgentTraceEntry =
  | { kind: "iteration"; trace: AgentIterationTrace }
  | { kind: "tool-call"; toolCall: AgentToolCall };

/**
 * Build the trace timeline for a single step. Prefers the
 * persisted data on `AgentStepExecutionResult` (the
 * `iterations` / `toolInvocations` arrays the backend stored in
 * the diagnostics store) and falls back to the live SSE trace
 * captured by `AgentRunnerView` while the run was streaming.
 *
 * The entries are interleaved: each iteration is followed by the
 * tool calls it triggered, then the next iteration, etc. The
 * strict order is only known from the SSE stream — both the
 * backend and the live trace collector append in execution
 * order, so we pair iterations and tool calls by walking the
 * `toolCalls` array in order rather than trying to match by
 * `toolName` (which conflates two iterations that both requested
 * the same tool).
 */
export function buildAgentTraceEntries(
  step: AgentStepExecutionResult,
  liveTrace: AgentStepLiveTrace | undefined
): AgentTraceEntry[] {
  const persistedIterations = step.iterations ?? [];
  const persistedToolCalls = step.toolInvocations ?? [];

  const useLive =
    persistedIterations.length === 0 &&
    (liveTrace?.iterations.length ?? 0) > 0;
  const iterations = useLive
    ? liveTrace!.iterations
    : persistedIterations;
  const toolCalls = useLive
    ? liveTrace?.toolCalls ?? []
    : persistedToolCalls;

  if (iterations.length === 0 && toolCalls.length === 0) {
    return [];
  }

  const entries: AgentTraceEntry[] = [];
  let toolCallCursor = 0;
  iterations.forEach((trace) => {
    entries.push({ kind: "iteration", trace });
    const expectedCallCount = trace.toolCallNames.length;
    for (
      let i = 0;
      i < expectedCallCount && toolCallCursor < toolCalls.length;
      i++
    ) {
      entries.push({
        kind: "tool-call",
        toolCall: toolCalls[toolCallCursor],
      });
      toolCallCursor++;
    }
  });
  // Any leftover tool calls (e.g. the persisted `iterations` list
  // dropped one but kept the call) are appended at the end so the
  // operator still sees them.
  while (toolCallCursor < toolCalls.length) {
    entries.push({ kind: "tool-call", toolCall: toolCalls[toolCallCursor] });
    toolCallCursor++;
  }

  return entries;
}
