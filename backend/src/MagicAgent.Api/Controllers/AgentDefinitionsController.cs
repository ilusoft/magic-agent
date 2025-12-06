using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using PRQXCommon.Core.Authorization;

namespace MagicAgent.Api.Controllers;

[Authorize(Policy = PrqxPolicies.PolicyAuthOnlyAdmin)]
[ApiController]
[Route("api/agents/definitions")]
public class AgentDefinitionsController(IAgentDefinitionsProvider definitionsProvider) : ControllerBase
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
        definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));

    [HttpGet]
    public async Task<ActionResult<AgentDefinitionsDocument>> GetDefinitionsAsync(CancellationToken cancellationToken)
    {
        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        return Ok(document);
    }

    [HttpPut]
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
