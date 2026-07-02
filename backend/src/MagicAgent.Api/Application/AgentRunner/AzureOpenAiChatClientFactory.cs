using Azure;
using Azure.AI.OpenAI;
using Microsoft.Extensions.AI;

namespace MagicAgent.Api.Application.AgentRunner;

public sealed class AzureOpenAiChatClientFactory : IChatClientFactory
{
    public string Provider => "azure-openai";

    public (IChatClient Client, LLMCallConfig CallConfig) Create(AgentLlmProfileDefinition profile)
    {
        ArgumentNullException.ThrowIfNull(profile);

        if (string.IsNullOrWhiteSpace(profile.Endpoint))
        {
            throw new InvalidOperationException(
                $"LLM profile for provider '{Provider}' is missing 'endpoint'.");
        }

        if (string.IsNullOrWhiteSpace(profile.Deployment))
        {
            throw new InvalidOperationException(
                $"LLM profile for provider '{Provider}' is missing 'deployment'.");
        }

        if (string.IsNullOrWhiteSpace(profile.ApiKey))
        {
            throw new InvalidOperationException(
                $"LLM profile for provider '{Provider}' is missing 'apiKey'.");
        }

        var client = new AzureOpenAIClient(
            new Uri(profile.Endpoint),
            new AzureKeyCredential(profile.ApiKey));

        var chatClient = client.GetChatClient(profile.Deployment).AsIChatClient();

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
