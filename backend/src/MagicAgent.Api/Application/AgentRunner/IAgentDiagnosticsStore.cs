namespace MagicAgent.Api.Application.AgentRunner;

public interface IAgentDiagnosticsStore
{
    Task SaveRunAsync(string conversationId, AgentRunResult runResult, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<AgentRunResult>> GetRunsAsync(string conversationId, CancellationToken cancellationToken = default);
}
