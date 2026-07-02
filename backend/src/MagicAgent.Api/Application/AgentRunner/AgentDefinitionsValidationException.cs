namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Thrown when an <see cref="AgentDefinitionsDocument"/> fails validation.
/// The controller layer turns this into a 422 response with the list of
/// <see cref="Issues"/> so the UI can display every problem at once.
/// </summary>
public sealed class AgentDefinitionsValidationException : Exception
{
    public IReadOnlyList<AgentDefinitionsValidationIssue> Issues { get; }

    public AgentDefinitionsValidationException(IReadOnlyList<AgentDefinitionsValidationIssue> issues)
        : base(BuildMessage(issues))
    {
        Issues = issues;
    }

    private static string BuildMessage(IReadOnlyList<AgentDefinitionsValidationIssue> issues)
    {
        if (issues.Count == 0)
        {
            return "Agent definitions document is invalid.";
        }

        if (issues.Count == 1)
        {
            return $"Agent definitions document has 1 validation issue: {issues[0].Path} - {issues[0].Message}";
        }

        return $"Agent definitions document has {issues.Count} validation issues. First: {issues[0].Path} - {issues[0].Message}";
    }
}

public sealed record AgentDefinitionsValidationIssue(string Path, string Message);
