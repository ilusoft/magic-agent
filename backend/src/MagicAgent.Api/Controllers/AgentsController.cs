using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc;

namespace MagicAgent.Api.Controllers;

[ApiController]
[Route("api/agent-definitions/agents")]
public class AgentsController(IAgentDefinitionsProvider definitionsProvider) : ControllerBase
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
        definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));

    [HttpGet]
    public async Task<ActionResult<IList<AgentDefinition>>> GetAgentsAsync(
        CancellationToken cancellationToken)
    {
        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        return Ok(document.Agents);
    }

    [HttpPut]
    public async Task<IActionResult> PutAgentsAsync(
        [FromBody] IList<AgentDefinition>? agents,
        CancellationToken cancellationToken)
    {
        if (agents is null)
        {
            return BadRequest();
        }

        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        document.Agents = new List<AgentDefinition>(agents);

        var issues = AgentDefinitionsDocumentValidator.Validate(document);
        if (issues.Count > 0)
        {
            throw new AgentDefinitionsValidationException(issues);
        }

        await _definitionsProvider.SaveDefinitionsAsync(document, cancellationToken);
        return NoContent();
    }
}
