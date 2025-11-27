namespace MagicAgent.Api.Application.AgentRunner;

public interface IAgentConversationStore
{
    Task<IReadOnlyList<AgentMessage>> GetMessagesAsync(string conversationId, CancellationToken cancellationToken = default);

    Task SaveMessagesAsync(string conversationId, IReadOnlyList<AgentMessage> messages, CancellationToken cancellationToken = default);
}
