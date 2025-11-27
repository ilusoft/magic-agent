using System;
using System.Collections.Generic;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc;

namespace MagicAgent.Api.Controllers;

[ApiController]
[Route("api/agents/{agentId}/runs")]
public class AgentRunsController(
    IAgentRunner agentRunner,
    IAgentDiagnosticsStore diagnosticsStore) : ControllerBase
{
    private readonly IAgentRunner _agentRunner =
        agentRunner ?? throw new ArgumentNullException(nameof(agentRunner));

    private readonly IAgentDiagnosticsStore _diagnosticsStore =
        diagnosticsStore ?? throw new ArgumentNullException(nameof(diagnosticsStore));

    [HttpPost]
    public async Task<IActionResult> RunAsync(
        string agentId,
        [FromBody] RunAgentRequest? request,
        CancellationToken cancellationToken)
    {
        try
        {
            var runResult = await RunInternalAsync(agentId, request, cancellationToken);

            var lastStep = runResult.Steps.Count > 0 ? runResult.Steps.Last() : null;

            var summary = new AgentWorkflowResult(
                runResult.AgentId,
                runResult.Status,
                lastStep,
                runResult.ConversationId);

            return Ok(summary);
        }
        catch (AgentNotFoundException)
        {
            return NotFound();
        }
    }

    [HttpGet("{conversationId}/debug")]
    public async Task<IActionResult> GetConversationDiagnosticsAsync(
        string conversationId,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(conversationId))
        {
            return BadRequest();
        }

        var runs = await _diagnosticsStore.GetRunsAsync(conversationId, cancellationToken);

        if (runs is null || runs.Count == 0)
        {
            return NotFound();
        }

        var diagnostics = new AgentConversationDiagnostics(
            conversationId,
            runs ?? []);

        return Ok(diagnostics);
    }

    private async Task<AgentRunResult> RunInternalAsync(
        string agentId,
        RunAgentRequest? request,
        CancellationToken cancellationToken)
    {
        var inboundHeaders = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var header in Request.Headers)
        {
            var headerValue = header.Value.ToString();

            if (string.IsNullOrWhiteSpace(headerValue))
            {
                continue;
            }

            inboundHeaders[header.Key] = headerValue;
        }

        var runRequest = new AgentRunRequest(
            agentId,
            request?.Input,
            request?.ConversationId,
            inboundHeaders.Count > 0 ? inboundHeaders : null);

        return await _agentRunner.RunAsync(runRequest, cancellationToken);
    }

    public sealed record RunAgentRequest(string? Input, string? ConversationId);

    public sealed record AgentWorkflowResult(
        string AgentId,
        string Status,
        AgentStepExecutionResult? LastStep,
        string? ConversationId);

    public sealed record AgentConversationDiagnostics(
        string ConversationId,
        IReadOnlyList<AgentRunResult> Runs);
}
