using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MagicAgent.Api.Application.AgentRunner;

namespace MagicAgent.Api.Infrastructure.AgentRunner;

public sealed class InMemoryAgentDiagnosticsStore : IAgentDiagnosticsStore
{
    private readonly ConcurrentDictionary<string, List<AgentRunResult>> _runs = new(StringComparer.OrdinalIgnoreCase);

    public Task SaveRunAsync(string conversationId, AgentRunResult runResult, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(conversationId))
        {
            return Task.CompletedTask;
        }

        var copy = CloneRunResult(runResult);

        _runs.AddOrUpdate(conversationId,
            _ => new List<AgentRunResult> { copy },
            (_, existing) =>
            {
                var updated = existing.ToList();
                updated.Add(copy);
                return updated;
            });

        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<AgentRunResult>> GetRunsAsync(string conversationId, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(conversationId))
        {
            return Task.FromResult<IReadOnlyList<AgentRunResult>>(Array.Empty<AgentRunResult>());
        }

        if (_runs.TryGetValue(conversationId, out var runs))
        {
            return Task.FromResult<IReadOnlyList<AgentRunResult>>(runs.Select(CloneRunResult).ToList());
        }

        return Task.FromResult<IReadOnlyList<AgentRunResult>>(Array.Empty<AgentRunResult>());
    }

    private static AgentRunResult CloneRunResult(AgentRunResult runResult)
    {
        var clonedSteps = runResult.Steps
            .Select(step => step with { })
            .ToArray();

        return new AgentRunResult(
            runResult.AgentId,
            runResult.Status,
            clonedSteps,
            runResult.ConversationId,
            runResult.CompletedAt);
    }
}
