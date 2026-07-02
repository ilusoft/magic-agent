using Microsoft.Extensions.AI;

namespace MagicAgent.Api.Application.AgentRunner;

public interface IChatClientFactory
{
    /// <summary>
    /// The provider name this factory handles (e.g. "azure-openai", "openai-compatible").
    /// The resolver matches this against <see cref="AgentLlmProfileDefinition.Provider"/>.
    /// </summary>
    string Provider { get; }

    /// <summary>
    /// Builds a chat client and a diagnostic <see cref="LLMCallConfig"/> snapshot
    /// from a fully-resolved LLM profile. Throws <see cref="InvalidOperationException"/>
    /// if the profile is missing fields required by this provider.
    /// </summary>
    (IChatClient Client, LLMCallConfig CallConfig) Create(AgentLlmProfileDefinition profile);
}
