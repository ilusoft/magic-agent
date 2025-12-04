using Azure;
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace MagicAgent.Api.Application.AgentRunner;

internal static class AgentStepFactory
{
    internal static AIAgent CreateAgent(
        AgentDefinition definition,
        AgentStepDefinition step,
        IDictionary<string, string> parameters,
        IReadOnlyList<AITool> tools)
    {
        var chatClient = CreateChatClient(parameters);
        var instructions = step.Parameters.TryGetValue("systemPrompt", out var systemPrompt)
            ? systemPrompt
            : definition.Description;

        if (tools is not null && tools.Count > 0)
        {
            var toolList = new List<AITool>(tools);

            return chatClient.CreateAIAgent(
                instructions: instructions,
                name: definition.Name,
                description: definition.Description,
                tools: toolList);
        }

        return chatClient.CreateAIAgent(
            instructions: instructions,
            name: definition.Name,
            description: definition.Description);
    }

    private static IChatClient CreateChatClient(IDictionary<string, string> parameters)
    {
        var endpoint = ResolveConfiguration(parameters, "endpoint")
            ?? throw new InvalidOperationException("Azure OpenAI endpoint is required for agent steps.");

        var deployment = ResolveConfiguration(parameters, "deployment")
            ?? ResolveConfiguration(parameters, "model")
            ?? throw new InvalidOperationException("Azure OpenAI deployment name is required for agent steps.");

        var client = CreateAzureOpenAiClient(new Uri(endpoint), parameters);
        return client.GetChatClient(deployment).AsIChatClient();
    }

    private static AzureOpenAIClient CreateAzureOpenAiClient(Uri endpoint, IDictionary<string, string> parameters)
    {
        var apiKey = ResolveConfiguration(parameters, "apiKey");
        if (!string.IsNullOrWhiteSpace(apiKey))
        {
            return new AzureOpenAIClient(endpoint, new AzureKeyCredential(apiKey));
        }

        var tenantId = ResolveConfiguration(parameters, "tenantId");
        if (!string.IsNullOrWhiteSpace(tenantId))
        {
            var clientId = ResolveConfiguration(parameters, "clientId");
            var clientSecret = ResolveConfiguration(parameters, "clientSecret");

            if (string.IsNullOrWhiteSpace(clientId) || string.IsNullOrWhiteSpace(clientSecret))
            {
                throw new InvalidOperationException("Client credentials authentication requires clientId and clientSecret values.");
            }

            var credential = new ClientSecretCredential(tenantId, clientId, clientSecret);
            return new AzureOpenAIClient(endpoint, credential);
        }

        return new AzureOpenAIClient(endpoint, new AzureCliCredential());
    }

    private static string? ResolveConfiguration(IDictionary<string, string> parameters, string key)
    {
        if (parameters.TryGetValue(key, out var parameterValue) && !string.IsNullOrWhiteSpace(parameterValue))
        {
            return parameterValue;
        }

        var environmentValue = Environment.GetEnvironmentVariable($"AZURE_OPENAI_{key.ToUpperInvariant()}");
        if (!string.IsNullOrWhiteSpace(environmentValue))
        {
            return environmentValue;
        }

        return null;
    }
}
