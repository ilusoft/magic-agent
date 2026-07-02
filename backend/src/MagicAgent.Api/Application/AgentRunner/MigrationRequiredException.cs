namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Thrown by the file-based definitions provider when the on-disk
/// document is in the pre-refactor shape (workflow-level
/// <c>endpoint</c>/<c>deployment</c>/<c>apiKey</c>/<c>tools</c>,
/// per-step <c>provider</c>/<c>options</c>). The controller layer
/// turns this into a <c>426 Upgrade Required</c> response pointing
/// the operator at <c>tools/AgentsMigrator</c>.
/// </summary>
public sealed class MigrationRequiredException : Exception
{
    public string? DocumentPath { get; }

    public MigrationRequiredException(string message, string? documentPath = null)
        : base(message)
    {
        DocumentPath = documentPath;
    }
}
