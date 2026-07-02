using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc;

namespace MagicAgent.Api.Controllers;

[ApiController]
[Route("api/agent-definitions/llm-profiles")]
public class LlmProfilesController(IAgentDefinitionsProvider definitionsProvider) : ControllerBase
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
        definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));

    [HttpGet]
    public async Task<ActionResult<IDictionary<string, AgentLlmProfileDefinition>>> GetLlmProfilesAsync(
        CancellationToken cancellationToken)
    {
        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        return Ok(document.LlmProfiles);
    }

    [HttpPut]
    public async Task<IActionResult> PutLlmProfilesAsync(
        [FromBody] IDictionary<string, AgentLlmProfileDefinition>? profiles,
        CancellationToken cancellationToken)
    {
        if (profiles is null)
        {
            return BadRequest();
        }

        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        AgentDefinitionsDocumentValidator.CheckRemovedLlmProfiles(document, profiles);

        // Validate the prospective document before persisting so
        // the controller layer is the single source of truth for
        // 422 responses (the file provider also validates on save,
        // but that path isn't reached in tests with a mock provider).
        document.LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(
            profiles,
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
