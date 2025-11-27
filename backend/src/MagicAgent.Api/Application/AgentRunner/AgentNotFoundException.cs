namespace MagicAgent.Api.Application.AgentRunner;

public sealed class AgentNotFoundException(string agentId)
    : InvalidOperationException($"Agent '{agentId}' was not found in configuration.")
{
    public string AgentId { get; } = agentId;
}
