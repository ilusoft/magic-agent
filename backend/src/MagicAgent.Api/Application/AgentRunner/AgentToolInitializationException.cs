namespace MagicAgent.Api.Application.AgentRunner;

internal sealed record ToolInitializationError(string ToolId, string ToolName, string Message, bool StopExecution);
