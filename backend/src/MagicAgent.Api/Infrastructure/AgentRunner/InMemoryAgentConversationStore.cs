using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using MagicAgent.Api.Application.AgentRunner;

namespace MagicAgent.Api.Infrastructure.AgentRunner;

public sealed class InMemoryAgentConversationStore : IAgentConversationStore
{
    private readonly ConcurrentDictionary<string, List<AgentMessage>> _conversations = new(StringComparer.OrdinalIgnoreCase);

    public Task<IReadOnlyList<AgentMessage>> GetMessagesAsync(string conversationId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(conversationId);

        if (_conversations.TryGetValue(conversationId, out var messages))
        {
            return Task.FromResult<IReadOnlyList<AgentMessage>>(messages.Select(CloneMessage).ToList());
        }

        return Task.FromResult<IReadOnlyList<AgentMessage>>(Array.Empty<AgentMessage>());
    }

    public Task SaveMessagesAsync(string conversationId, IReadOnlyList<AgentMessage> messages, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(conversationId);
        ArgumentNullException.ThrowIfNull(messages);

        var copy = messages.Select(CloneMessage).ToList();

        _conversations.AddOrUpdate(conversationId, copy, (_, _) => copy);

        return Task.CompletedTask;
    }

    public Task DeleteConversationAsync(string conversationId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(conversationId);

        _conversations.TryRemove(conversationId, out _);

        return Task.CompletedTask;
    }

    private static AgentMessage CloneMessage(AgentMessage message)
        => new(message.Role, message.Content, message.Timestamp);
}
