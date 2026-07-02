namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Thrown when a <c>PUT</c> on the per-section endpoints
/// (<c>/api/agent-definitions/llm-profiles</c> or
/// <c>/api/agent-definitions/tools</c>) removes an id that is
/// still referenced by one or more steps. The controller layer
/// turns this into a <c>409 Conflict</c> response with the list of
/// referencing agents and steps so the UI can show the user
/// exactly which workflows need to be updated before the
/// deletion can proceed.
/// </summary>
public sealed class AgentDefinitionsInUseException : Exception
{
    public IReadOnlyList<ReferencingStep> ReferencingSteps { get; }

    public AgentDefinitionsInUseException(
        string message,
        IReadOnlyList<ReferencingStep> referencingSteps)
        : base(message)
    {
        ReferencingSteps = referencingSteps;
    }
}

/// <summary>
/// Identifies a step that still references a removed
/// LLM profile or tool. Used in the <c>409</c> response payload
/// so the UI can deep-link to the offending workflow + step.
/// </summary>
public sealed record ReferencingStep(string AgentId, string StepName);
