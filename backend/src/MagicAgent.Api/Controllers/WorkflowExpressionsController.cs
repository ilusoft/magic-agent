using System.Text.Json.Serialization;
using MagicAgent.Api.Application.Expressions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using PRQXCommon.Core.Authorization;

namespace MagicAgent.Api.Controllers;

[Authorize(Policy = PrqxPolicies.PolicyAuthOnlyAdmin)]
[ApiController]
[Route("api/workflows/expressions")]
public sealed class WorkflowExpressionsController(IWorkflowExpressionEvaluator expressionEvaluator) : ControllerBase
{
    private readonly IWorkflowExpressionEvaluator _expressionEvaluator =
        expressionEvaluator ?? throw new ArgumentNullException(nameof(expressionEvaluator));

    [HttpPost("validate")]
    public ActionResult<ExpressionValidationResponse> Validate([FromBody] ExpressionValidationRequest request)
    {
        if (request is null || string.IsNullOrWhiteSpace(request.Expression))
        {
            return BadRequest(new ExpressionValidationResponse(false, "Expression is required.", "missing_expression", null, Array.Empty<string>()));
        }

        var context = ExpressionValidationContextFactory.Create(request.Context);
        var result = _expressionEvaluator.Evaluate(request.Expression, context);

        if (!result.Success)
        {
            return Ok(new ExpressionValidationResponse(false, result.ErrorMessage ?? "Expression evaluation failed.", result.ErrorCode, result.Value.Kind, result.ReferencedIdentifiers));
        }

        if (result.Value.Kind != WorkflowExpressionValueKind.Boolean)
        {
            return Ok(new ExpressionValidationResponse(false, "Expression must evaluate to a Boolean value.", "non_boolean", result.Value.Kind, result.ReferencedIdentifiers));
        }

        return Ok(new ExpressionValidationResponse(true, null, null, WorkflowExpressionValueKind.Boolean, result.ReferencedIdentifiers));
    }

    public sealed record ExpressionValidationRequest(
        [property: JsonPropertyName("expression")] string Expression,
        [property: JsonPropertyName("context")] ExpressionValidationContextPayload? Context);

    public sealed record ExpressionValidationResponse(
        [property: JsonPropertyName("success")] bool Success,
        [property: JsonPropertyName("error")] string? Error,
        [property: JsonPropertyName("errorCode")] string? ErrorCode,
        [property: JsonPropertyName("resultKind")] WorkflowExpressionValueKind? ResultKind,
        [property: JsonPropertyName("referencedIdentifiers")] IReadOnlyList<string>? ReferencedIdentifiers);
}
// new file