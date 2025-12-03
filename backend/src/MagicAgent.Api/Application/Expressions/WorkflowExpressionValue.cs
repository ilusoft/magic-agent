using System;
using System.Globalization;
using System.Text.Json.Nodes;

namespace MagicAgent.Api.Application.Expressions;

/// <summary>
/// Represents a strongly typed value produced by the workflow expression engine.
/// </summary>
public sealed class WorkflowExpressionValue
{
    private WorkflowExpressionValue(
        WorkflowExpressionValueKind kind,
        string? stringValue = null,
        double? numberValue = null,
        bool? booleanValue = null,
        JsonNode? jsonValue = null,
        DateTimeOffset? dateTimeValue = null)
    {
        Kind = kind;
        StringValue = stringValue;
        NumberValue = numberValue;
        BooleanValue = booleanValue;
        JsonValue = jsonValue;
        DateTimeValue = dateTimeValue;
    }

    public WorkflowExpressionValueKind Kind { get; }

    public string? StringValue { get; }

    public double? NumberValue { get; }

    public bool? BooleanValue { get; }

    public JsonNode? JsonValue { get; }

    public DateTimeOffset? DateTimeValue { get; }

    public static WorkflowExpressionValue FromString(string? value) =>
        new(WorkflowExpressionValueKind.String, stringValue: value ?? string.Empty);

    public static WorkflowExpressionValue FromNumber(double value) =>
        new(WorkflowExpressionValueKind.Number, numberValue: value);

    public static WorkflowExpressionValue FromBoolean(bool value) =>
        new(WorkflowExpressionValueKind.Boolean, booleanValue: value);

    public static WorkflowExpressionValue FromJson(JsonNode? value) =>
        new(WorkflowExpressionValueKind.Json, jsonValue: value?.DeepClone());

    public static WorkflowExpressionValue Null() =>
        new(WorkflowExpressionValueKind.Null);

    public static WorkflowExpressionValue FromDateTime(DateTimeOffset value) =>
        new(WorkflowExpressionValueKind.DateTime, dateTimeValue: value);

    /// <summary>
    /// Returns a culture-aware string representation suitable for placeholder substitution.
    /// </summary>
    public string ToDisplayString(IFormatProvider? formatProvider = null)
    {
        formatProvider ??= CultureInfo.InvariantCulture;

        return Kind switch
        {
            WorkflowExpressionValueKind.String => StringValue ?? string.Empty,
            WorkflowExpressionValueKind.Number => (NumberValue ?? 0).ToString(formatProvider),
            WorkflowExpressionValueKind.Boolean => (BooleanValue ?? false).ToString(formatProvider),
            WorkflowExpressionValueKind.Json => JsonValue?.ToJsonString() ?? string.Empty,
            WorkflowExpressionValueKind.DateTime => (DateTimeValue ?? DateTimeOffset.MinValue).ToString("O", formatProvider),
            _ => string.Empty,
        };
    }
}
