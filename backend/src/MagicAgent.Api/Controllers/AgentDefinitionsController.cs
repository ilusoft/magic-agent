using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc;

namespace MagicAgent.Api.Controllers;

[ApiController]
public class AgentDefinitionsController(IAgentDefinitionsProvider definitionsProvider) : ControllerBase
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
        definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));

    // Old route — kept for the legacy frontend and the migration tool.
    [HttpGet("api/agents/definitions")]
    public async Task<ActionResult<AgentDefinitionsDocument>> GetDefinitionsLegacyAsync(
        CancellationToken cancellationToken)
    {
        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        return Ok(document);
    }

    [HttpPut("api/agents/definitions")]
    public async Task<IActionResult> SaveDefinitionsLegacyAsync(
        [FromBody] AgentDefinitionsDocument document,
        CancellationToken cancellationToken)
    {
        if (document is null)
        {
            return BadRequest();
        }

        await _definitionsProvider.SaveDefinitionsAsync(document, cancellationToken);
        return NoContent();
    }

    // New route — whole-document GET/PUT alongside the per-section
    // endpoints (llm-profiles, tools, agents). Frontend is migrated
    // to this route in phase 8.
    [HttpGet("api/agent-definitions")]
    public async Task<ActionResult<AgentDefinitionsDocument>> GetDefinitionsAsync(
        CancellationToken cancellationToken)
    {
        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        return Ok(document);
    }

    [HttpPut("api/agent-definitions")]
    public async Task<IActionResult> SaveDefinitionsAsync(
        [FromBody] AgentDefinitionsDocument document,
        CancellationToken cancellationToken)
    {
        if (document is null)
        {
            return BadRequest();
        }

        await _definitionsProvider.SaveDefinitionsAsync(document, cancellationToken);
        return NoContent();
    }
}
