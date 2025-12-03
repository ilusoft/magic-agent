using System;
using System.Collections.Generic;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Application.Expressions;
using MagicAgent.Api.Application.Expressions.Helpers;
using MagicAgent.Api.Application.Expressions.Parsing;
using Microsoft.Extensions.Logging.Abstractions;

namespace MagicAgent.Api.Tests;

public class ExpressionEvaluatorTests
{
    private static readonly WorkflowHelperRegistry HelperRegistry = new(new[]
    {
        typeof(MathWorkflowHelpers),
        typeof(DateWorkflowHelpers),
        typeof(StringWorkflowHelpers),
        typeof(JsonWorkflowHelpers),
    });

    private static readonly WorkflowExpressionEvaluator Evaluator =
        new(HelperRegistry, NullLogger<WorkflowExpressionEvaluator>.Instance);

    static ExpressionEvaluatorTests()
    {
        WorkflowPlaceholderResolver.Configure(Evaluator);
    }

    [Fact]
    public void Parser_AllowsExpressionsWithMemberAccessAndSpaces()
    {
        Action act = () => WorkflowExpressionParser.Parse("abs(var.value) + param.scale");
        act.Should().NotThrow();
    }

    [Theory]
    [InlineData("1 + 2 * 3", 7)]
    [InlineData("(1 + 2) * 3", 9)]
    [InlineData("-5 + 10", 5)]
    public void Evaluator_ComputesArithmeticExpressions(string expression, double expected)
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate(expression, context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.NumberValue.Should().Be(expected);
    }

    [Fact]
    public void Evaluator_ResolvesVariablesAndParameters()
    {
        var context = CreateContext(
            variables: new Dictionary<string, WorkflowExpressionValue>
            {
                ["value"] = WorkflowExpressionValue.FromString("5"),
            },
            parameters: new Dictionary<string, WorkflowExpressionValue>
            {
                ["scale"] = WorkflowExpressionValue.FromString("3"),
            },
            stepInput: "4");

        var result = Evaluator.Evaluate("(var.value + param.scale) * input", context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.NumberValue.Should().Be(32);
        result.ReferencedIdentifiers.Should().Contain(["var.value", "param.scale", "input"]);
    }

    [Fact]
    public void Evaluator_ResolvesJsonMemberAndIndexAccess()
    {
        var payload = "{\"items\":[{\"value\":10},{\"value\":20}]}";
        var context = CreateContext(
            variables: new Dictionary<string, WorkflowExpressionValue>
            {
                ["payload"] = WorkflowExpressionValue.FromString(payload),
            });

        var expression = "var.payload.items[1].value + var.payload.items.length";

        var result = Evaluator.Evaluate(expression, context);

        result.Success.Should().BeTrue();
        result.Value.NumberValue.Should().Be(22);
    }

    [Fact]
    public void Evaluator_InvokesHelpers()
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate("max(abs(-4), sqr(3))", context);

        result.Success.Should().BeTrue();
        result.Value.NumberValue.Should().Be(9);
        result.ReferencedIdentifiers.Should().Contain("max");
    }

    [Fact]
    public void Evaluator_UsesDateHelpers()
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate(
            "dayOfWeek(dateAdd('2024-01-01T00:00:00Z', 1, 'day'), 'en')",
            context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.StringValue.Should().Be("Tuesday");
    }

    [Fact]
    public void Evaluator_UsesStringHelpers_ForNumericResult()
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate("length(trim(toUpper('  hello  ')))", context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.NumberValue.Should().Be(5);
    }

    [Fact]
    public void Evaluator_UsesStringHelpers_ForSubstringAndReplace()
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate(
            "substring(replace('Magic Agent', ' ', ''), 5, 5)",
            context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.StringValue.Should().Be("Agent");
    }

    [Fact]
    public void Evaluator_UsesJsonHelpers()
    {
        var context = CreateContext();

        var expression = "jsonToString(stringToJson('{\"value\":42}'))";

        var result = Evaluator.Evaluate(expression, context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.StringValue.Should().Be("{\"value\":42}");
    }

    [Fact]
    public void Evaluator_UsesBooleanStringHelpers()
    {
        var context = CreateContext();

        var contains = Evaluator.Evaluate("contains('Magic Agent', 'Agent')", context);
        contains.Success.Should().BeTrue(contains.ErrorMessage ?? string.Empty);
        contains.Value.Kind.Should().Be(WorkflowExpressionValueKind.Boolean);
        contains.Value.BooleanValue.Should().BeTrue();

        var startsWith = Evaluator.Evaluate("startsWith('magic', 'mag')", context);
        startsWith.Success.Should().BeTrue(startsWith.ErrorMessage ?? string.Empty);
        startsWith.Value.BooleanValue.Should().BeTrue();

        var endsWith = Evaluator.Evaluate("endsWith('magic', 'ic')", context);
        endsWith.Success.Should().BeTrue(endsWith.ErrorMessage ?? string.Empty);
        endsWith.Value.BooleanValue.Should().BeTrue();

        var compare = Evaluator.Evaluate("compare('  Test ', 'test', false, true)", context);
        compare.Success.Should().BeTrue(compare.ErrorMessage ?? string.Empty);
        compare.Value.BooleanValue.Should().BeTrue();

        var isNullOrEmpty = Evaluator.Evaluate("isNullOrEmpty('')", context);
        isNullOrEmpty.Success.Should().BeTrue(isNullOrEmpty.ErrorMessage ?? string.Empty);
        isNullOrEmpty.Value.BooleanValue.Should().BeTrue();

        var isNull = Evaluator.Evaluate("isNull(null)", context);
        isNull.Success.Should().BeTrue(isNull.ErrorMessage ?? string.Empty);
        isNull.Value.BooleanValue.Should().BeTrue();
    }

    [Fact]
    public void StringToDate_Helper_ReturnsDateTimeOffset()
    {
        var result = DateWorkflowHelpers.StringToDate("2024-05-01T09:10:11Z");

        result.Should().Be(DateTimeOffset.Parse("2024-05-01T09:10:11Z"));
    }

    [Fact]
    public void Evaluator_ReturnsDateTimeValue_FromStringToDate()
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate("stringToDate('2023-12-31T23:59:59Z')", context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.Kind.Should().Be(WorkflowExpressionValueKind.DateTime);
        result.Value.DateTimeValue.Should().Be(DateTimeOffset.Parse("2023-12-31T23:59:59Z"));
    }

    [Fact]
    public void Evaluator_EvaluatesCompoundBooleanExpressions()
    {
        var variables = new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase)
        {
            ["value1"] = WorkflowExpressionValue.FromNumber(42),
            ["value2"] = WorkflowExpressionValue.FromString("ROUTE"),
            ["date1"] = WorkflowExpressionValue.FromDateTime(DateTimeOffset.Parse("2025-02-15T00:00:00Z")),
        };

        var runtimeState = new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase)
        {
            ["output"] = WorkflowExpressionValue.FromString("ROUTE: research complete"),
        };

        var context = new WorkflowExpressionContext(
            variables,
            parameters: new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase),
            runtimeState,
            stepInput: null,
            lastStepOutput: null);

        var expression = "var.value1 > 10 && contains(state.output, var.value2) && dateDiff(stringToDate('2025-01-01T00:00:00Z'), var.date1, 'days') > 0";

        var result = Evaluator.Evaluate(expression, context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.Kind.Should().Be(WorkflowExpressionValueKind.Boolean);
        result.Value.BooleanValue.Should().BeTrue();

        var falseExpression = "var.value1 > 100 || contains(state.output, 'missing')";
        var falseResult = Evaluator.Evaluate(falseExpression, context);

        falseResult.Success.Should().BeTrue(falseResult.ErrorMessage ?? string.Empty);
        falseResult.Value.Kind.Should().Be(WorkflowExpressionValueKind.Boolean);
        falseResult.Value.BooleanValue.Should().BeFalse();
    }

    [Fact]
    public void Evaluator_IsNull_ReturnsTrue_ForMissingJsonProperty()
    {
        var context = CreateContext(
            variables: new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase)
            {
                ["payload"] = WorkflowExpressionValue.FromString("{\"user\":{\"name\":\"Jane\"}}"),
            });

        var result = Evaluator.Evaluate("isNull(var.payload.user.age)", context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.Kind.Should().Be(WorkflowExpressionValueKind.Boolean);
        result.Value.BooleanValue.Should().BeTrue();
    }

    [Fact]
    public void Evaluator_EvaluatesConditional()
    {
        var context = CreateContext(stepInput: "hello");

        var result = Evaluator.Evaluate("input == 'hello' ? 'match' : 'nope'", context);

        result.Success.Should().BeTrue();
        result.Value.StringValue.Should().Be("match");
    }

    [Fact]
    public void PlaceholderResolver_EvaluatesExpressions()
    {
        WorkflowPlaceholderResolver.Configure(Evaluator);

        WorkflowPlaceholderResolver.ResolveString(
                "Value=${{ 1 + 1 }}",
                new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
                null,
                null,
                null)
            .Should().Be("Value=2");

        var variables = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["value"] = "-5",
        };
        var parameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["scale"] = "2",
        };

        var source = new Dictionary<string, string>
        {
            ["message"] = "Resolved=${{ abs(var.value) + param.scale }}",
        };

        var resolution = WorkflowPlaceholderResolver.ResolveDictionaryWithDebug(
            source,
            variables,
            parameters,
            stepInput: null,
            lastStepOutput: null);

        resolution.Debug["message"].Placeholders.Should().Contain(
            ["var.value", "param.scale"],
            "placeholders: {0}; errors: {1}; resolved: {2}",
            string.Join(", ", resolution.Debug["message"].Placeholders),
            string.Join("; ", resolution.Debug["message"].ExpressionErrors),
            resolution.ResolvedValues["message"]);

        resolution.Debug["message"].ExpressionErrors.Should().BeEmpty(
            string.Join(", ", resolution.Debug["message"].ExpressionErrors));
        resolution.ResolvedValues["message"].Should().Be("Resolved=7", resolution.Debug["message"].ResolvedValue);

        WorkflowPlaceholderResolver.ResolveString(
                "Resolved=${{ abs(var.value) + param.scale }}",
                variables,
                parameters,
                null,
                null)
            .Should().Be("Resolved=7");
    }

    private static WorkflowExpressionContext CreateContext(
        IReadOnlyDictionary<string, WorkflowExpressionValue>? variables = null,
        IReadOnlyDictionary<string, WorkflowExpressionValue>? parameters = null,
        string? stepInput = null,
        string? lastStepOutput = null)
    {
        return new WorkflowExpressionContext(
            variables ?? new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase),
            parameters ?? new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase),
            runtimeState: new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase),
            stepInput,
            lastStepOutput);
    }
}
