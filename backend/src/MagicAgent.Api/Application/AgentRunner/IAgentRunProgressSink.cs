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
}
