using System.Collections.Generic;

namespace MagicAgent.Api.Application.Expressions;

/// <summary>
/// Provides the data that expressions can reference during evaluation.
/// </summary>
public sealed class WorkflowExpressionContext
{
    public WorkflowExpressionContext(
        IReadOnlyDictionary<string, WorkflowExpressionValue>? variables = null,
        IReadOnlyDictionary<string, WorkflowExpressionValue>? parameters = null,
        IReadOnlyDictionary<string, WorkflowExpressionValue>? runtimeState = null,
        string? stepInput = null,
        string? lastStepOutput = null)
    {
        Variables = variables ?? new Dictionary<string, WorkflowExpressionValue>();
        Parameters = parameters ?? new Dictionary<string, WorkflowExpressionValue>();
        RuntimeState = runtimeState ?? new Dictionary<string, WorkflowExpressionValue>();
        StepInput = stepInput;
        LastStepOutput = lastStepOutput;
    }

    public IReadOnlyDictionary<string, WorkflowExpressionValue> Variables { get; }

    public IReadOnlyDictionary<string, WorkflowExpressionValue> Parameters { get; }

    public IReadOnlyDictionary<string, WorkflowExpressionValue> RuntimeState { get; }

    public string? StepInput { get; }

    public string? LastStepOutput { get; }
}
