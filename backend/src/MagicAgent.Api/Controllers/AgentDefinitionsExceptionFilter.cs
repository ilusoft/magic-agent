using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Filters;

namespace MagicAgent.Api.Controllers;

/// <summary>
/// Global exception filter that turns the two domain-specific
/// exceptions into structured HTTP responses:
///
///   * <see cref="AgentDefinitionsInUseException"/> -> 409 Conflict
///     with the list of referencing agents/steps so the UI can
///     show the user exactly which workflows need to be updated
///     before the deletion can proceed.
///   * <see cref="AgentDefinitionsValidationException"/> -> 422
///     Unprocessable Entity with the full list of validation
///     issues so the UI can display every problem at once instead
///     of one at a time.
/// </summary>
public sealed class AgentDefinitionsExceptionFilter : IExceptionFilter
{
    public void OnException(ExceptionContext context)
    {
        switch (context.Exception)
        {
            case AgentDefinitionsInUseException inUse:
                context.Result = new ObjectResult(new
                {
                    message = inUse.Message,
                    referencingSteps = inUse.ReferencingSteps.Select(s => new
                    {
                        agentId = s.AgentId,
                        stepName = s.StepName,
                    }),
                })
                {
                    StatusCode = StatusCodes.Status409Conflict,
                };
                context.ExceptionHandled = true;
                break;

            case AgentDefinitionsValidationException validation:
                context.Result = new ObjectResult(new
                {
                    message = validation.Message,
                    issues = validation.Issues,
                })
                {
                    StatusCode = StatusCodes.Status422UnprocessableEntity,
                };
                context.ExceptionHandled = true;
                break;

            case MigrationRequiredException migration:
                context.Result = new ObjectResult(new
                {
                    message = migration.Message,
                    documentPath = migration.DocumentPath,
                })
                {
                    StatusCode = StatusCodes.Status426UpgradeRequired,
                };
                context.ExceptionHandled = true;
                break;
        }
    }
}
