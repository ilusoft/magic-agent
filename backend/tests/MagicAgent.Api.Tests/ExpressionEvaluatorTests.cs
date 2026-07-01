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
        typeof(ArrayWorkflowHelpers),
    });

    private static readonly WorkflowExpressionEvaluator Evaluator =
        new(HelperRegistry, NullLogger<WorkflowExpressionEvaluator>.Instance);

    public ExpressionEvaluatorTests()
    {
        WorkflowPlaceholderResolver.Configure(Evaluator);
    }

    [Fact]
    public void HelperOptionalNumberParameter_DefaultsWhenOmitted()
    {
        var arrayJson = "[1,2]";
        var result = Evaluate("addToArray(3, stringToJson(\"" + arrayJson + "\"))");

        result.Should().Be("[1,2,3]");
    }

    [Fact]
    public void HelperOptionalNumberParameter_RespectsProvidedValue()
    {
        var arrayJson = "[1,2]";
        var result = Evaluate("addToArray(3, stringToJson(\"" + arrayJson + "\"), 1)");

        result.Should().Be("[1,3,2]");
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
    public void Evaluator_UsesArrayLengthHelper()
    {
        var payload = "{\"items\":[{\"value\":10},{\"value\":20},{\"value\":30}]}";
        var context = CreateContext(
            variables: new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase)
            {
                ["payload"] = WorkflowExpressionValue.FromString(payload),
            });

        var inlineExpression = "arrayLength(stringToJson('[1,2,3,4]'))";
        var inlineResult = Evaluator.Evaluate(inlineExpression, context);

        inlineResult.Success.Should().BeTrue(inlineResult.ErrorMessage ?? string.Empty);
        inlineResult.Value.Kind.Should().Be(WorkflowExpressionValueKind.Number);
        inlineResult.Value.NumberValue.Should().Be(4);

        var variableExpression = "arrayLength(var.payload.items)";
        var variableResult = Evaluator.Evaluate(variableExpression, context);

        variableResult.Success.Should().BeTrue(variableResult.ErrorMessage ?? string.Empty);
        variableResult.Value.Kind.Should().Be(WorkflowExpressionValueKind.Number);
        variableResult.Value.NumberValue.Should().Be(3);
    }

    [Fact]
    public void Evaluator_UsesArrayHelpers()
    {
        var context = CreateContext();

        var addResult = Evaluator.Evaluate("jsonToString(addToArray('c', stringToJson('[\"a\",\"b\"]'), 1))", context);
        addResult.Success.Should().BeTrue(addResult.ErrorMessage ?? string.Empty);
        addResult.Value.StringValue.Should().Be("[\"a\",\"c\",\"b\"]");

        var removeResult = Evaluator.Evaluate("jsonToString(removeFromArray('a', stringToJson('[\"a\",\"b\",\"a\"]'), true))", context);
        removeResult.Success.Should().BeTrue(removeResult.ErrorMessage ?? string.Empty);
        removeResult.Value.StringValue.Should().Be("[\"b\"]");

        var indexResult = Evaluator.Evaluate("indexOnArray('b', stringToJson('[\"a\",\"b\",\"c\"]'))", context);
        indexResult.Success.Should().BeTrue(indexResult.ErrorMessage ?? string.Empty);
        indexResult.Value.NumberValue.Should().Be(1);

        var lastIndexResult = Evaluator.Evaluate("indexOnArray('a', stringToJson('[\"x\",\"a\",\"y\",\"a\"]'), true)", context);
        lastIndexResult.Success.Should().BeTrue(lastIndexResult.ErrorMessage ?? string.Empty);
        lastIndexResult.Value.NumberValue.Should().Be(3);

        var replaceResult = Evaluator.Evaluate("jsonToString(replaceElement('a', stringToJson('[\"a\",\"b\",\"a\"]'), 'z', true))", context);
        replaceResult.Success.Should().BeTrue(replaceResult.ErrorMessage ?? string.Empty);
        replaceResult.Value.StringValue.Should().Be("[\"z\",\"b\",\"z\"]");

        var subsetResult = Evaluator.Evaluate("jsonToString(subArray(stringToJson('[\"a\",\"b\",\"c\",\"d\"]'), 2))", context);
        subsetResult.Success.Should().BeTrue(subsetResult.ErrorMessage ?? string.Empty);
        subsetResult.Value.StringValue.Should().Be("[\"a\",\"b\"]");

        var invertedSubsetResult = Evaluator.Evaluate("jsonToString(subArray(stringToJson('[\"a\",\"b\",\"c\",\"d\"]'), 3, true))", context);
        invertedSubsetResult.Success.Should().BeTrue(invertedSubsetResult.ErrorMessage ?? string.Empty);
        invertedSubsetResult.Value.StringValue.Should().Be("[\"b\",\"c\",\"d\"]");

        var concatResult = Evaluator.Evaluate("jsonToString(concatArrays(stringToJson('[\"a\"]'), stringToJson('[\"b\",\"c\"]')))", context);
        concatResult.Success.Should().BeTrue(concatResult.ErrorMessage ?? string.Empty);
        concatResult.Value.StringValue.Should().Be("[\"a\",\"b\",\"c\"]");
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
    public void NowHelper_ReturnsParseableUtcIsoString()
    {
        var result = DateWorkflowHelpers.Now(string.Empty);

        // The default template is round-trip 'O' which produces a
        // string ``DateTimeOffset.Parse`` accepts back. The whole
        // point of the helper is that the value tracks the host's
        // wall clock — a frozen-constant regression would surface
        // here as a parse failure or an obviously old timestamp.
        var parsed = DateTimeOffset.Parse(
            result,
            System.Globalization.CultureInfo.InvariantCulture);
        parsed.Offset.Should().Be(TimeSpan.Zero);
        // Within 60 s of "now" is a generous bound that still
        // catches a frozen / hard-coded value.
        (DateTimeOffset.UtcNow - parsed).Duration().Should().BeLessThan(TimeSpan.FromSeconds(60));
    }

    [Fact]
    public void NowHelper_RespectsFormatArgument()
    {
        var result = DateWorkflowHelpers.Now("yyyy-MM-dd");

        result.Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}$");
    }

    [Fact]
    public void NowUtcHelper_BehavesAsAliasForNow()
    {
        // Both helpers must produce parseable UTC ISO strings.
        // They need not be byte-identical (call ordering can
        // produce sub-millisecond drift), but the parsed offsets
        // must be zero and the two values must agree to within
        // one second — the same property the Python tests check.
        var now = DateTimeOffset.Parse(
            DateWorkflowHelpers.Now(string.Empty),
            System.Globalization.CultureInfo.InvariantCulture);
        var nowUtc = DateTimeOffset.Parse(
            DateWorkflowHelpers.NowUtc(string.Empty),
            System.Globalization.CultureInfo.InvariantCulture);

        now.Offset.Should().Be(TimeSpan.Zero);
        nowUtc.Offset.Should().Be(TimeSpan.Zero);
        (now - nowUtc).Duration().Should().BeLessThan(TimeSpan.FromSeconds(1));
    }

    [Fact]
    public void NowLocalHelper_ReflectsHostTimezone()
    {
        var result = DateWorkflowHelpers.NowLocal(string.Empty);
        var parsed = DateTimeOffset.Parse(
            result,
            System.Globalization.CultureInfo.InvariantCulture);

        if (TimeZoneInfo.Local.GetUtcOffset(DateTimeOffset.Now) == TimeSpan.Zero)
        {
            // The host is UTC — the helper's output coincides
            // with ``Now()`` and there's nothing meaningful to
            // assert beyond the parse round-trip.
            return;
        }

        parsed.Offset.Should().Be(TimeZoneInfo.Local.GetUtcOffset(parsed));
        parsed.Offset.Should().NotBe(TimeSpan.Zero);
    }

    [Fact]
    public void NowLocalHelper_RespectsFormatArgument()
    {
        var result = DateWorkflowHelpers.NowLocal("yyyy/MM/dd HH:mm");

        result.Should().MatchRegex(@"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$");
    }

    [Fact]
    public void TodayHelper_ReturnsLocalDateAsYyyyMmDd()
    {
        var result = DateWorkflowHelpers.Today();

        result.Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}$");
        // Must agree with ``nowLocal('yyyy-MM-dd')`` — not, say,
        // a baked-in UTC date.
        DateWorkflowHelpers.NowLocal("yyyy-MM-dd").Should().Be(result);
    }

    [Fact]
    public void Evaluator_EvaluatesNowHelper()
    {
        // End-to-end: the expression parser + evaluator must
        // resolve ``now()`` to a real, parseable ISO string.
        var context = CreateContext();

        var result = Evaluator.Evaluate("now()", context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.Kind.Should().Be(WorkflowExpressionValueKind.String);
        var parsed = DateTimeOffset.Parse(
            result.Value.StringValue!,
            System.Globalization.CultureInfo.InvariantCulture);
        parsed.Offset.Should().Be(TimeSpan.Zero);
    }

    [Fact]
    public void Evaluator_EvaluatesTodayHelper()
    {
        var context = CreateContext();

        var result = Evaluator.Evaluate("today()", context);

        result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
        result.Value.Kind.Should().Be(WorkflowExpressionValueKind.String);
        result.Value.StringValue.Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}$");
    }

    [Fact]
    public void HelperRegistry_ExposesNowFamily()
    {
        // The frontend helper picker reads from this registry;
        // the new helpers must be discoverable alongside the
        // other date helpers so the UI surfaces them.
        var descriptorNames = HelperRegistry.GetDescriptors()
            .Select(d => d.Name)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        descriptorNames.Should().Contain(new[] { "now", "nowUtc", "nowLocal", "today" });
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
            resolution.Values["message"].ToDisplayString());

        resolution.Debug["message"].ExpressionErrors.Should().BeEmpty(
            string.Join(", ", resolution.Debug["message"].ExpressionErrors));
        resolution.Values["message"].ToDisplayString().Should().Be("Resolved=7", resolution.Debug["message"].ResolvedValue);

        WorkflowPlaceholderResolver.ResolveString(
                "Resolved=${{ abs(var.value) + param.scale }}",
                variables,
                parameters,
                stepInput: null,
                lastStepOutput: null);

            resolution.Debug["message"].Placeholders.Should().Contain(
                ["var.value", "param.scale"],
                "placeholders: {0}; errors: {1}; resolved: {2}",
                string.Join(", ", resolution.Debug["message"].Placeholders),
                string.Join("; ", resolution.Debug["message"].ExpressionErrors),
                resolution.Values["message"].ToDisplayString());

            resolution.Debug["message"].ExpressionErrors.Should().BeEmpty(
                string.Join(", ", resolution.Debug["message"].ExpressionErrors));
            resolution.Values["message"].ToDisplayString().Should().Be("Resolved=7", resolution.Debug["message"].ResolvedValue);

            WorkflowPlaceholderResolver.ResolveString(
                    "Resolved=${{ abs(var.value) + param.scale }}",
                    variables,
                    parameters,
                    null,
                    null)
                .Should().Be("Resolved=7");
        }

        [Fact]
        public void PlaceholderResolver_PureExpressionReturnsTypedJson()
        {
            WorkflowPlaceholderResolver.Configure(Evaluator);

            var source = new Dictionary<string, string>
            {
                ["payload"] = "${{ { \"count\": 3 } }}",
            };

            var resolution = WorkflowPlaceholderResolver.ResolveDictionaryWithDebug(
                source,
                variables: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
                workflowParameters: null,
                stepInput: null,
                lastStepOutput: null);

            resolution.Values["payload"].Kind.Should().Be(WorkflowExpressionValueKind.Json);
            resolution.Values["payload"].JsonValue!["count"]!.GetValue<int>().Should().Be(3);
            resolution.Debug["payload"].ResolvedValue.Should().Be("{\"count\":3}");
        }

        [Fact]
        public void PlaceholderResolver_MixedLiteralExpressionFallsBackToString()
        {
            WorkflowPlaceholderResolver.Configure(Evaluator);

            var source = new Dictionary<string, string>
            {
                ["message"] = "Total=${{ 2 + 3 }} items",
            };

            var resolution = WorkflowPlaceholderResolver.ResolveDictionaryWithDebug(
                source,
                variables: new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
                workflowParameters: null,
                stepInput: null,
                lastStepOutput: null);

            resolution.Values["message"].Kind.Should().Be(WorkflowExpressionValueKind.String);
            resolution.Values["message"].StringValue.Should().Be("Total=5 items");
            resolution.Debug["message"].ResolvedValue.Should().Be("Total=5 items");
        }

        private static string Evaluate(string expression)
        {
            var context = CreateContext();
            var result = Evaluator.Evaluate(expression, context);

            result.Success.Should().BeTrue(result.ErrorMessage ?? string.Empty);
            return result.Value.ToDisplayString();
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

    [Fact]
    public void PlaceholderResolver_DatePreset_TodayResolvesToLocalDate()
    {
        // Regression: ``{{ today }}`` previously fell through to
        // the variable-lookup path, missed, and was returned as
        // the literal string. The model would then hallucinate
        // against it (the original symptom on the web-search
        // agent's system prompt, where the author wrote
        // ``Current Date Time : dd-mm-yyyy``). The preset layer
        // turns it into a real current-date substitution.
        WorkflowPlaceholderResolver.Configure(Evaluator);

        var resolved = WorkflowPlaceholderResolver.ResolveString(
            "Today is {{ today }}",
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
            null,
            null,
            null);

        var datePart = resolved["Today is ".Length..];
        datePart.Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}$",
            "preset must produce a YYYY-MM-DD local date, got {0}", datePart);
        // Sanity: the value tracks the host clock. A frozen
        // constant or a stale test would surface here.
        var expected = DateTimeOffset.Now.ToString("yyyy-MM-dd",
            System.Globalization.CultureInfo.InvariantCulture);
        datePart.Should().Be(expected);
    }

    [Fact]
    public void PlaceholderResolver_DatePreset_TodayIsCaseInsensitive()
    {
        WorkflowPlaceholderResolver.Configure(Evaluator);

        var resolved = WorkflowPlaceholderResolver.ResolveString(
            "{{ TODAY }}",
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
            null,
            null,
            null);

        resolved.Should().MatchRegex(@"^\d{4}-\d{2}-\d{2}$");
    }

    [Theory]
    [InlineData("dd-mm-yyyy", "dd-MM-yyyy")]
    [InlineData("yyyy-mm-dd", "yyyy-MM-dd")]
    [InlineData("mm/dd/yyyy", "MM/dd/yyyy")]
    [InlineData("dd/mm/yyyy", "dd/MM/yyyy")]
    [InlineData("yyyy/mm/dd", "yyyy/MM/dd")]
    [InlineData("mm-dd-yyyy", "MM-dd-yyyy")]
    public void PlaceholderResolver_DatePreset_FormatTokensResolveToToday(
        string preset, string expectedNetFormat)
    {
        // The exact placeholder the user pasted into the
        // web-search agent's system prompt. ``dd-mm-yyyy`` is
        // the canonical example — the rest are common
        // alternatives so a workflow author who writes the
        // date in their own locale's convention still gets a
        // working current-date substitution.
        WorkflowPlaceholderResolver.Configure(Evaluator);

        var resolved = WorkflowPlaceholderResolver.ResolveString(
            "{{ " + preset + " }}",
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
            null,
            null,
            null);

        var expected = DateTimeOffset.Now.ToString(expectedNetFormat,
            System.Globalization.CultureInfo.InvariantCulture);
        resolved.Should().Be(expected);
    }

    [Fact]
    public void PlaceholderResolver_DatePreset_NowReturnsIsoDatetime()
    {
        WorkflowPlaceholderResolver.Configure(Evaluator);

        var resolved = WorkflowPlaceholderResolver.ResolveString(
            "{{ now }}",
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase),
            null,
            null,
            null);

        // ISO 8601 round-trip form: ``2026-06-30T23:33:50.6016540+00:00``
        DateTimeOffset.TryParse(resolved,
            System.Globalization.CultureInfo.InvariantCulture,
            System.Globalization.DateTimeStyles.RoundtripKind,
            out var parsed).Should().BeTrue(
            "preset 'now' must produce a parseable ISO 8601 string, got {0}", resolved);
        parsed.Offset.Should().Be(TimeSpan.Zero);
    }

    [Fact]
    public void PlaceholderResolver_DatePreset_DoesNotHijackVariableLookup()
    {
        // The preset layer is purely additive — a non-preset
        // key must still go through the normal variable
        // lookup. If a future change accidentally hijacks
        // arbitrary identifiers, this test catches it.
        WorkflowPlaceholderResolver.Configure(Evaluator);

        var variables = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["foo"] = "bar",
        };

        var resolved = WorkflowPlaceholderResolver.ResolveString(
            "{{ foo }}",
            variables,
            null,
            null,
            null);

        resolved.Should().Be("bar");
    }
}
