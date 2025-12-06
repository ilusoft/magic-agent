using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using PRQXCommon.Core.Authorization;

namespace MagicAgent.Api.Controllers;

[ApiController]
[Route("api/agents/{agentId}/runs")]
public class AgentRunsController(
    IAgentRunner agentRunner,
    IAgentDiagnosticsStore diagnosticsStore,
    IAgentDefinitionsProvider definitionsProvider,
    IAgentDefinitionValueResolver definitionValueResolver) : ControllerBase
{
    private readonly IAgentRunner _agentRunner =
        agentRunner ?? throw new ArgumentNullException(nameof(agentRunner));

    private readonly IAgentDiagnosticsStore _diagnosticsStore =
        diagnosticsStore ?? throw new ArgumentNullException(nameof(diagnosticsStore));

    private readonly IAgentDefinitionsProvider _definitionsProvider =
        definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));

    private readonly IAgentDefinitionValueResolver _definitionValueResolver =
        definitionValueResolver ?? throw new ArgumentNullException(nameof(definitionValueResolver));

    [HttpPost]
    public async Task<IActionResult> RunAsync(
        string agentId,
        [FromBody] RunAgentRequest? request,
        CancellationToken cancellationToken)
    {
        try
        {
            if (await ShouldStreamAsync(agentId, cancellationToken).ConfigureAwait(false))
            {
                await using var streamingSink = StreamingAgentRunProgressSink.Create(Response, HttpContext.RequestAborted);
                await RunInternalAsync(agentId, request, streamingSink, cancellationToken).ConfigureAwait(false);
                return new EmptyResult();
            }

            var runResult = await RunInternalAsync(agentId, request, null, cancellationToken).ConfigureAwait(false);

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

    [Authorize(Policy = PrqxPolicies.PolicyAuthOnlyAdmin)]
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

    private async Task<bool> ShouldStreamAsync(string agentId, CancellationToken cancellationToken)
    {
        if (!AcceptsEventStream())
        {
            return false;
        }

        var definition = await _definitionsProvider.GetAgentDefinitionAsync(agentId, cancellationToken).ConfigureAwait(false);

        if (definition is null)
        {
            throw new AgentNotFoundException(agentId);
        }

        definition = _definitionValueResolver.Resolve(definition);

        return definition.Streaming?.Enabled == true;
    }

    private bool AcceptsEventStream()
    {
        if (!Request.Headers.TryGetValue("Accept", out var acceptValues))
        {
            return false;
        }

        return acceptValues.Any(value =>
            value?.IndexOf("text/event-stream", StringComparison.OrdinalIgnoreCase) >= 0);
    }

    private async Task<AgentRunResult> RunInternalAsync(
        string agentId,
        RunAgentRequest? request,
        IAgentRunProgressSink? progressSink,
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
            inboundHeaders.Count > 0 ? inboundHeaders : null,
            progressSink);

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
