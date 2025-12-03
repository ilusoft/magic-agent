namespace MagicAgent.Api.Application.Expressions;

/// <summary>
/// Represents the primary data kinds that workflow expressions can evaluate to.
/// </summary>
public enum WorkflowExpressionValueKind
{
    String = 0,
    Number = 1,
    Boolean = 2,
    Json = 3,
    Null = 4,
    DateTime = 5,
}
