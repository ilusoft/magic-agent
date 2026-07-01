using System;
using System.Threading;
using System.Threading.Tasks;

namespace MagicAgent.Api.Application.AgentRunner;

public interface IAgentRunProgressSink
{
    ValueTask StepStartingAsync(
        string agentId,
        string stepName,
        string stepType,
        int iteration,
        CancellationToken cancellationToken);

    ValueTask StepCompletedAsync(
        string agentId,
        AgentStepExecutionResult stepResult,
        TimeSpan elapsed,
        CancellationToken cancellationToken);

    ValueTask RunCompletedAsync(AgentRunResult runResult, CancellationToken cancellationToken);

    /// <summary>
    /// Emitted once per LLM turn inside an agent step. Carries the
    /// assistant's text (or an empty string when the turn was a pure
    /// tool-call turn) plus the names of the tools it requested, in
    /// order. Lets the UI render the model's intermediate reasoning
    /// instead of collapsing it into the final assistant message.
    /// </summary>
    ValueTask IterationAsync(
        string agentId,
        string stepName,
        AgentIterationTrace trace,
        CancellationToken cancellationToken);

    /// <summary>
    /// Emitted once per tool execution that the agent performed. This
    /// is the per-tool-call trace event surfaced in the UI; the
    /// aggregated list of all calls also travels on
    /// <see cref="AgentStepExecutionResult.ToolInvocations"/>.
    /// </summary>
    ValueTask ToolCallAsync(
        string agentId,
        string stepName,
        AgentToolCall toolCall,
        CancellationToken cancellationToken);
}
