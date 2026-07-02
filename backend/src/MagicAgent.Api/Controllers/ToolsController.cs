using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc;

namespace MagicAgent.Api.Controllers;

[ApiController]
[Route("api/agent-definitions/tools")]
public class ToolsController(IAgentDefinitionsProvider definitionsProvider) : ControllerBase
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
        definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));

    [HttpGet]
    public async Task<ActionResult<IDictionary<string, AgentToolDefinition>>> GetToolsAsync(
        CancellationToken cancellationToken)
    {
        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        return Ok(document.Tools);
    }

    [HttpPut]
    public async Task<IActionResult> PutToolsAsync(
        [FromBody] IDictionary<string, AgentToolDefinition>? tools,
        CancellationToken cancellationToken)
    {
        if (tools is null)
        {
            return BadRequest();
        }

        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        AgentDefinitionsDocumentValidator.CheckRemovedTools(document, tools);

        document.Tools = new Dictionary<string, AgentToolDefinition>(
            tools,
            StringComparer.OrdinalIgnoreCase);

        var issues = AgentDefinitionsDocumentValidator.Validate(document);
        if (issues.Count > 0)
        {
            throw new AgentDefinitionsValidationException(issues);
        }

        await _definitionsProvider.SaveDefinitionsAsync(document, cancellationToken);
        return NoContent();
    }
}
