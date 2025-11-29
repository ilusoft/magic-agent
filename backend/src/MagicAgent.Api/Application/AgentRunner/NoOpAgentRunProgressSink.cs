using System;
using System.Threading;
using System.Threading.Tasks;

namespace MagicAgent.Api.Application.AgentRunner;

internal sealed class NoOpAgentRunProgressSink : IAgentRunProgressSink
{
    public ValueTask StepStartingAsync(
        string agentId,
        string stepName,
        string stepType,
        int iteration,
        CancellationToken cancellationToken)
    {
        return ValueTask.CompletedTask;
    }

    public ValueTask StepCompletedAsync(
        string agentId,
        AgentStepExecutionResult stepResult,
        TimeSpan elapsed,
        CancellationToken cancellationToken)
    {
        return ValueTask.CompletedTask;
    }

    public ValueTask RunCompletedAsync(AgentRunResult runResult, CancellationToken cancellationToken)
    {
        return ValueTask.CompletedTask;
    }
}
