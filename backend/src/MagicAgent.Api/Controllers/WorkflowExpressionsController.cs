using System.Text.Json.Serialization;
using MagicAgent.Api.Application.Expressions;
using Microsoft.AspNetCore.Mvc;

namespace MagicAgent.Api.Controllers;

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
            return BadRequest(new ExpressionValidationResponse(false, "Expression is required.", "missing_expression", null));
        }

        var context = new WorkflowExpressionContext();
        var result = _expressionEvaluator.Evaluate(request.Expression, context);

        if (!result.Success)
        {
            return Ok(new ExpressionValidationResponse(false, result.ErrorMessage ?? "Expression evaluation failed.", result.ErrorCode, result.Value.Kind));
        }

        if (result.Value.Kind != WorkflowExpressionValueKind.Boolean)
        {
            return Ok(new ExpressionValidationResponse(false, "Expression must evaluate to a Boolean value.", "non_boolean", result.Value.Kind));
        }

        return Ok(new ExpressionValidationResponse(true, null, null, WorkflowExpressionValueKind.Boolean));
    }

    public sealed record ExpressionValidationRequest(
        [property: JsonPropertyName("expression")] string Expression);

    public sealed record ExpressionValidationResponse(
        [property: JsonPropertyName("success")] bool Success,
        [property: JsonPropertyName("error")] string? Error,
        [property: JsonPropertyName("errorCode")] string? ErrorCode,
        [property: JsonPropertyName("resultKind")] WorkflowExpressionValueKind? ResultKind);
}
// new file