
namespace MagicAgent.Api.Application.AgentRunner;

internal sealed class ConversationContext
{
    private readonly IAgentConversationStore _conversationStore;
    private readonly List<AgentMessage> _messages;

    private ConversationContext(
        IAgentConversationStore conversationStore,
        bool enabled,
        string? conversationId,
        List<AgentMessage> messages)
    {
        _conversationStore = conversationStore;
        Enabled = enabled;
        ConversationId = conversationId;
        _messages = messages;
    }

    internal bool Enabled { get; }

    internal string? ConversationId { get; }

    internal IReadOnlyList<AgentMessage> PreviousMessages => _messages;

    internal static async Task<ConversationContext> CreateAsync(
        IAgentConversationStore conversationStore,
        AgentStepDefinition step,
        string? conversationId,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(conversationStore);
        ArgumentNullException.ThrowIfNull(step);

        var enabled = step.Conversation?.Enabled ?? false;
        string? activeConversationId = conversationId;
        var messages = new List<AgentMessage>();

        if (enabled)
        {
            if (string.IsNullOrWhiteSpace(activeConversationId))
            {
                activeConversationId = Guid.NewGuid().ToString("N");
            }

            var existingMessages = await conversationStore.GetMessagesAsync(activeConversationId!, cancellationToken).ConfigureAwait(false);
            if (existingMessages is { Count: > 0 })
            {
                messages.AddRange(existingMessages);
            }
        }

        return new ConversationContext(conversationStore, enabled, activeConversationId, messages);
    }

    internal Task SaveMessagesAsync(IEnumerable<AgentMessage?> additionalMessages, CancellationToken cancellationToken)
    {
        if (!Enabled || ConversationId is null)
        {
            return Task.CompletedTask;
        }

        if (additionalMessages is not null)
        {
            foreach (var message in additionalMessages)
            {
                if (message is not null)
                {
                    _messages.Add(message);
                }
            }
        }

        return _conversationStore.SaveMessagesAsync(ConversationId, _messages, cancellationToken);
    }
}
