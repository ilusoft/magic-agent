using System.Text.Json;

namespace MagicAgent.Api.Application.AgentRunner;

public sealed record AgentRunRequest(
    string AgentId,
    string? Input,
    string? ConversationId = null,
    IReadOnlyDictionary<string, string>? Headers = null,
    IAgentRunProgressSink? ProgressSink = null);

public sealed record AgentStepExecutionResult(string Name, string Type, string Output)
{
    public string? Input { get; init; }

    public IReadOnlyDictionary<string, string>? ResolvedParameters { get; init; }

    public JsonElement? ThreadContext { get; init; }

    public string? Outcome { get; init; }

    public string? NextStep { get; init; }

    public bool EndWorkflow { get; init; }

    public List<AgentToolCall> ToolInvocations { get; init; } = [];

    public bool ToolErrorDetected { get; init; }
}

public sealed record AgentMessage(string Role, string Content, DateTimeOffset Timestamp);

public sealed record AgentToolCall(
    string? ToolName,
    string? InvocationId,
    string? Result,
    string? ArgumentsJson,
    string? ErrorMessage,
    string? ErrorDetails,
    string? ErrorCode);

public sealed record AgentRunResult(
    string AgentId,
    string Status,
    IReadOnlyCollection<AgentStepExecutionResult> Steps,
    string? ConversationId,
    DateTimeOffset CompletedAt);

public interface IAgentDefinitionsProvider
{
    Task<AgentDefinitionsDocument> GetDefinitionsAsync(CancellationToken cancellationToken = default);
    Task<AgentDefinition?> GetAgentDefinitionAsync(string agentId, CancellationToken cancellationToken = default);
    Task SaveDefinitionsAsync(AgentDefinitionsDocument document, CancellationToken cancellationToken = default);
}

public interface IAgentRunner
{
    Task<AgentRunResult> RunAsync(AgentRunRequest request, CancellationToken cancellationToken = default);
}
