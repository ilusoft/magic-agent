namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Thrown when an agent step's <c>llmConfig.profileId</c> does not resolve to
/// any key in the document's <c>llmProfiles</c> map.
/// </summary>
public sealed class LlmProfileNotFoundException : Exception
{
    public string ProfileId { get; }
    public string StepName { get; }

    public LlmProfileNotFoundException(string profileId, string stepName)
        : base($"LLM profile '{profileId}' referenced by step '{stepName}' was not found in the document's llmProfiles map.")
    {
        ProfileId = profileId;
        StepName = stepName;
    }
}
