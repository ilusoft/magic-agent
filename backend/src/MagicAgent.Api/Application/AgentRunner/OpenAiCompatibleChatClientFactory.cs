using System.ClientModel;
using Microsoft.Extensions.AI;
using OpenAI;

namespace MagicAgent.Api.Application.AgentRunner;

public sealed class OpenAiCompatibleChatClientFactory : IChatClientFactory
{
    public string Provider => "openai-compatible";

    public (IChatClient Client, LLMCallConfig CallConfig) Create(AgentLlmProfileDefinition profile)
    {
        ArgumentNullException.ThrowIfNull(profile);

        if (string.IsNullOrWhiteSpace(profile.BaseUrl))
        {
            throw new InvalidOperationException(
                $"LLM profile for provider '{Provider}' is missing 'baseUrl'.");
        }

        if (string.IsNullOrWhiteSpace(profile.Model))
        {
            throw new InvalidOperationException(
                $"LLM profile for provider '{Provider}' is missing 'model'.");
        }

        if (string.IsNullOrWhiteSpace(profile.ApiKey))
        {
            throw new InvalidOperationException(
                $"LLM profile for provider '{Provider}' is missing 'apiKey'.");
        }

        // TODO(Q6 follow-up): add a System.ClientModel PipelinePolicy that injects
        // profile.Headers into every request. OpenAIClientOptions does not expose a
        // DefaultHeaders collection in the 2.6.0 SDK, so custom-header support
        // requires a custom policy. The current Qwen config only uses apiKey auth,
        // so this is a non-blocking limitation.
        _ = profile.Headers;

        var options = new OpenAIClientOptions
        {
            Endpoint = new Uri(profile.BaseUrl, UriKind.Absolute),
        };

        var client = new OpenAIClient(new ApiKeyCredential(profile.ApiKey), options);
        var chatClient = client.GetChatClient(profile.Model).AsIChatClient();

        var callConfig = new LLMCallConfig(
            Provider: Provider,
            Model: profile.Model,
            Endpoint: profile.Endpoint,
            BaseUrl: profile.BaseUrl,
            Deployment: profile.Deployment,
            ApiVersion: profile.ApiVersion,
            Temperature: profile.Temperature,
            MaxTokens: profile.MaxTokens,
            ApiKeyFingerprint: LLMCallConfig.FingerprintApiKey(profile.ApiKey));

        return (chatClient, callConfig);
    }
}

