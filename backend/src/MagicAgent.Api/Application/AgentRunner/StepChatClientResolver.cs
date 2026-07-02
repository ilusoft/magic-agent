using Microsoft.Extensions.AI;

namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Resolves the chat client that should be used for a given agent step.
///
/// Resolution order:
///   1. If <c>step.LlmConfig.ProfileId</c> is set, look up
///      <c>document.LlmProfiles[profileId]</c>. Missing -> <see cref="LlmProfileNotFoundException"/>.
///   2. Merge any inline fields on <c>step.LlmConfig</c> over the resolved profile
///      (non-null inline fields win; null inherits from the base profile).
///   3. If neither a profile nor inline is set, build a profile from
///      <c>AZURE_OPENAI_*</c> environment variables (current fallback behaviour).
///   4. Pick the <see cref="IChatClientFactory"/> whose <c>Provider</c> matches the
///      resolved profile and let it build the <see cref="IChatClient"/> + the
///      diagnostic <see cref="LLMCallConfig"/> snapshot.
/// </summary>
public sealed class StepChatClientResolver
{
    private readonly IReadOnlyDictionary<string, IChatClientFactory> _factories;

    public StepChatClientResolver(IEnumerable<IChatClientFactory> factories)
    {
        ArgumentNullException.ThrowIfNull(factories);

        _factories = factories.ToDictionary(
            f => f.Provider,
            StringComparer.OrdinalIgnoreCase);
    }

    public (IChatClient Client, LLMCallConfig CallConfig) Resolve(
        AgentDefinitionsDocument document,
        AgentDefinition workflow,
        AgentStepDefinition step)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(workflow);
        ArgumentNullException.ThrowIfNull(step);

        var resolvedProfile = ResolveProfile(document, step);
        var factory = ResolveFactory(resolvedProfile.Provider);
        return factory.Create(resolvedProfile);
    }

    private static AgentLlmProfileDefinition ResolveProfile(
        AgentDefinitionsDocument document,
        AgentStepDefinition step)
    {
        AgentLlmProfileDefinition baseProfile;

        if (!string.IsNullOrWhiteSpace(step.LlmConfig?.ProfileId))
        {
            if (!document.LlmProfiles.TryGetValue(step.LlmConfig.ProfileId, out baseProfile!))
            {
                throw new LlmProfileNotFoundException(step.LlmConfig.ProfileId, step.Name);
            }
        }
        else
        {
            baseProfile = BuildFromEnvironment();
        }

        return MergeInline(baseProfile, step.LlmConfig);
    }

    private static AgentLlmProfileDefinition BuildFromEnvironment()
    {
        return new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT"),
            Deployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT"),
            ApiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_APIKEY"),
        };
    }

    private static AgentLlmProfileDefinition MergeInline(
        AgentLlmProfileDefinition baseProfile,
        AgentStepLlmConfig? inline)
    {
        if (inline is null)
        {
            return baseProfile;
        }

        return new AgentLlmProfileDefinition
        {
            Provider = inline.Provider ?? baseProfile.Provider,
            Endpoint = inline.Endpoint ?? baseProfile.Endpoint,
            Deployment = inline.Deployment ?? baseProfile.Deployment,
            ApiVersion = inline.ApiVersion ?? baseProfile.ApiVersion,
            BaseUrl = inline.BaseUrl ?? baseProfile.BaseUrl,
            Model = inline.Model ?? baseProfile.Model,
            ApiKey = inline.ApiKey ?? baseProfile.ApiKey,
            Headers = inline.Headers.Count > 0 ? inline.Headers : baseProfile.Headers,
            Temperature = inline.Temperature ?? baseProfile.Temperature,
            MaxTokens = inline.MaxTokens ?? baseProfile.MaxTokens,
        };
    }

    private IChatClientFactory ResolveFactory(string provider)
    {
        if (string.IsNullOrWhiteSpace(provider))
        {
            throw new InvalidOperationException(
                "LLM profile is missing 'provider' after resolution. Set provider on the profile or on the step's inline llmConfig.");
        }

        if (!_factories.TryGetValue(provider, out var factory))
        {
            throw new InvalidOperationException(
                $"No chat client factory registered for provider '{provider}'. Registered providers: {string.Join(", ", _factories.Keys)}.");
        }

        return factory;
    }
}
