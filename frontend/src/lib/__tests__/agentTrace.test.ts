import { describe, expect, it } from "vitest";
import { buildAgentTraceEntries } from "@/lib/agentTrace";
import type {
  AgentIterationTrace,
  AgentStepExecutionResult,
  AgentStepLiveTrace,
  AgentToolCall,
} from "@/types/agents";

function iteration(
  index: number,
  content: string | null,
  toolCallNames: string[]
): AgentIterationTrace {
  return {
    iteration: index,
    content,
    toolCallNames,
    hasToolCalls: toolCallNames.length > 0,
    timestamp: new Date(2026, 0, 1, 12, index).toISOString(),
  };
}

function toolCall(
  toolName: string,
  invocationId: string,
  result = "ok"
): AgentToolCall {
  return {
    toolName,
    invocationId,
    argumentsJson: "{}",
    result,
    errorMessage: null,
    errorDetails: null,
    errorCode: null,
  };
}

const baseStep: AgentStepExecutionResult = {
  name: "research",
  type: "agent",
  output: "",
};

describe("buildAgentTraceEntries", () => {
  it("returns an empty list when neither persisted nor live data has anything", () => {
    expect(buildAgentTraceEntries(baseStep, undefined)).toEqual([]);
    expect(buildAgentTraceEntries(baseStep, {
      stepName: "research",
      iterations: [],
      toolCalls: [],
      persisted: false,
    })).toEqual([]);
  });

  it("prefers persisted data on the step when both are present", () => {
    const persisted: AgentStepExecutionResult = {
      ...baseStep,
      iterations: [iteration(0, "persisted", [])],
      toolInvocations: [],
    };
    const live: AgentStepLiveTrace = {
      stepName: "research",
      iterations: [iteration(0, "live", [])],
      toolCalls: [],
      persisted: false,
    };
    const entries = buildAgentTraceEntries(persisted, live);
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      kind: "iteration",
      trace: { content: "persisted" },
    });
  });

  it("pairs tool calls to iterations by array order, not by tool name", () => {
    // Two iterations that both request the same tool. A
    // name-based matcher would conflate the calls; the
    // order-based pairing keeps iteration 0's call first and
    // iteration 1's call second.
    const persisted: AgentStepExecutionResult = {
      ...baseStep,
      iterations: [
        iteration(0, "first", ["web_search"]),
        iteration(1, "second", ["web_search"]),
      ],
      toolInvocations: [
        toolCall("web_search", "call_1"),
        toolCall("web_search", "call_2"),
      ],
    };
    const entries = buildAgentTraceEntries(persisted, undefined);
    expect(entries).toHaveLength(4);
    expect(entries[0]).toMatchObject({ kind: "iteration" });
    expect(entries[1]).toMatchObject({
      kind: "tool-call",
      toolCall: { invocationId: "call_1" },
    });
    expect(entries[2]).toMatchObject({ kind: "iteration" });
    expect(entries[3]).toMatchObject({
      kind: "tool-call",
      toolCall: { invocationId: "call_2" },
    });
  });

  it("handles iterations with multiple tool calls interleaved correctly", () => {
    const persisted: AgentStepExecutionResult = {
      ...baseStep,
      iterations: [
        iteration(0, "look up the user", ["user_lookup", "account_lookup"]),
        iteration(1, "summarise", []),
        iteration(2, null, ["log_result"]),
      ],
      toolInvocations: [
        toolCall("user_lookup", "call_1"),
        toolCall("account_lookup", "call_2"),
        toolCall("log_result", "call_3"),
      ],
    };
    const entries = buildAgentTraceEntries(persisted, undefined);
    expect(entries.map((entry) => entry.kind)).toEqual([
      "iteration",
      "tool-call",
      "tool-call",
      "iteration",
      "iteration",
      "tool-call",
    ]);
  });

  it("appends leftover tool calls whose iteration was dropped", () => {
    // The persisted trace kept the call but lost the iteration
    // metadata — should still surface the call at the end.
    const persisted: AgentStepExecutionResult = {
      ...baseStep,
      iterations: [iteration(0, "started", [])],
      toolInvocations: [toolCall("web_search", "call_1")],
    };
    const entries = buildAgentTraceEntries(persisted, undefined);
    expect(entries).toHaveLength(2);
    expect(entries[0].kind).toBe("iteration");
    expect(entries[1]).toMatchObject({
      kind: "tool-call",
      toolCall: { invocationId: "call_1" },
    });
  });

  it("falls back to the live trace when the persisted step has no iterations", () => {
    const live: AgentStepLiveTrace = {
      stepName: "research",
      iterations: [iteration(0, "live text", ["web_search"])],
      toolCalls: [toolCall("web_search", "call_live")],
      persisted: false,
    };
    const entries = buildAgentTraceEntries(baseStep, live);
    expect(entries).toHaveLength(2);
    expect(entries[0]).toMatchObject({
      kind: "iteration",
      trace: { content: "live text" },
    });
    expect(entries[1]).toMatchObject({
      kind: "tool-call",
      toolCall: { invocationId: "call_live" },
    });
  });

  it("does not fall back to live trace if persisted iterations are present", () => {
    // Even when the live trace has more entries, persisted
    // wins once it has at least one iteration.
    const persisted: AgentStepExecutionResult = {
      ...baseStep,
      iterations: [iteration(0, "persisted only", [])],
      toolInvocations: [],
    };
    const live: AgentStepLiveTrace = {
      stepName: "research",
      iterations: [
        iteration(0, "live 0", ["x"]),
        iteration(1, "live 1", ["y"]),
      ],
      toolCalls: [toolCall("x", "cx"), toolCall("y", "cy")],
      persisted: false,
    };
    const entries = buildAgentTraceEntries(persisted, live);
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      kind: "iteration",
      trace: { content: "persisted only" },
    });
  });
});
