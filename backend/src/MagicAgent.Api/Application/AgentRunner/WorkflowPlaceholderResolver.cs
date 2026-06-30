using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using MagicAgent.Api.Application.Expressions;

namespace MagicAgent.Api.Application.AgentRunner;

internal static partial class WorkflowPlaceholderResolver
{
    private const string VariablePrefix = "var.";
    private const string ParameterPrefixShort = "param.";
    private const string ParameterPrefixLong = "parameter.";
    private static readonly StringComparer Comparer = StringComparer.OrdinalIgnoreCase;
    private static readonly IReadOnlyDictionary<string, string> EmptyDictionary = new Dictionary<string, string>(Comparer);
    private static readonly Regex ExpressionEnvelopeRegex = new(
        "\\$\\{\\{(?<expr>.*?)\\}\\}",
        RegexOptions.CultureInvariant | RegexOptions.Singleline);

    private static IWorkflowExpressionEvaluator? _expressionEvaluator;

    public static void Configure(IWorkflowExpressionEvaluator evaluator)
    {
        _expressionEvaluator = evaluator ?? throw new ArgumentNullException(nameof(evaluator));
    }

    internal static WorkflowParameterResolution ResolveDictionaryWithDebug(
        IDictionary<string, string>? source,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        if (source is null || source.Count == 0)
        {
            return new WorkflowParameterResolution(
                new Dictionary<string, WorkflowExpressionValue>(Comparer),
                new Dictionary<string, WorkflowParameterDebugInfo>(Comparer));
        }

        var resolved = new Dictionary<string, WorkflowExpressionValue>(source.Count, Comparer);
        var debug = new Dictionary<string, WorkflowParameterDebugInfo>(source.Count, Comparer);

        foreach (var kvp in source)
        {
            var (value, typedValue, placeholders, expressionErrors) = ResolveStringWithDebug(kvp.Value ?? string.Empty, variables, workflowParameters, stepInput, lastStepOutput);
            resolved[kvp.Key] = typedValue;
            debug[kvp.Key] = new WorkflowParameterDebugInfo(
                kvp.Value ?? string.Empty,
                value,
                placeholders,
                expressionErrors);
        }

        return new WorkflowParameterResolution(resolved, debug);
    }

    internal static IReadOnlyDictionary<string, WorkflowExpressionValue> ResolveDictionary(
        IDictionary<string, string>? source,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        return ResolveDictionaryWithDebug(source, variables, workflowParameters, stepInput, lastStepOutput).Values;
    }

    internal static string ResolveString(
        string value,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
        => ResolveStringWithDebug(value, variables, workflowParameters, stepInput, lastStepOutput).ResolvedValue;

    private static (string ResolvedValue, WorkflowExpressionValue TypedValue, IReadOnlyList<string> Placeholders, IReadOnlyList<string> ExpressionErrors) ResolveStringWithDebug(
        string value,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        var source = value ?? string.Empty;

        if (string.IsNullOrEmpty(source))
        {
            return (source, WorkflowExpressionValue.FromString(source), Array.Empty<string>(), Array.Empty<string>());
        }

        if (TryExtractSingleExpression(source, out var singleExpressionBody))
        {
            var singleExpressionPlaceholders = new List<string>();
            var singleExpressionErrors = new List<string>();
            var (typedValue, resolvedValue) = EvaluateSingleExpression(
                singleExpressionBody,
                variables,
                workflowParameters,
                stepInput,
                lastStepOutput,
                singleExpressionPlaceholders,
                singleExpressionErrors);

            return (resolvedValue, typedValue, singleExpressionPlaceholders, singleExpressionErrors);
        }

        var parameterDictionary = workflowParameters ?? EmptyDictionary;
        var placeholderList = new List<string>();
        var placeholderSet = new HashSet<string>(Comparer);
        var expressionErrors = new List<string>();

        void RecordPlaceholder(string expression)
        {
            if (!string.IsNullOrWhiteSpace(expression) && placeholderSet.Add(expression))
            {
                placeholderList.Add(expression);
            }
        }

        var resolved = ReplaceExpressionEnvelopes(
            source,
            variables,
            workflowParameters,
            stepInput,
            lastStepOutput,
            RecordPlaceholder,
            expressionErrors);

        resolved = PlaceholderPatternRegex.Replace(resolved, match =>
        {
            var expression = match.Groups["expr"].Value.Trim();

            if (string.IsNullOrEmpty(expression))
            {
                return match.Value;
            }

            if (Comparer.Equals(expression, "input"))
            {
                RecordPlaceholder(expression);
                return stepInput ?? string.Empty;
            }

            if (Comparer.Equals(expression, "lastOutput"))
            {
                RecordPlaceholder(expression);
                return lastStepOutput ?? string.Empty;
            }

            if (TryResolveWorkflowParameter(expression, parameterDictionary, out var parameterValue))
            {
                RecordPlaceholder(expression);
                return parameterValue ?? string.Empty;
            }

            // Date presets (``{{ today }}``, ``{{ dd-mm-yyyy }}``,
            // etc.) sit between the special identifiers above and
            // the variable lookup below. They exist so workflow
            // authors who reach for the legacy ``{{ … }}`` syntax
            // still get a working current-date substitution — the
            // model was previously hallucinating against the
            // literal ``dd-mm-yyyy`` placeholder text because the
            // legacy path didn't know what to do with it.
            if (TryResolveDatePreset(expression, out var presetValue))
            {
                RecordPlaceholder(expression);
                return presetValue;
            }

            var originalExpression = expression;
            if (expression.StartsWith(VariablePrefix, StringComparison.OrdinalIgnoreCase))
            {
                expression = expression[VariablePrefix.Length..];
            }

            if (variables.TryGetValue(expression, out var variableValue))
            {
                RecordPlaceholder(originalExpression);
                return variableValue ?? string.Empty;
            }

            return match.Value;
        });

        var placeholders = placeholderList.Count == 0
            ? Array.Empty<string>()
            : placeholderList.ToArray();

        return (resolved, WorkflowExpressionValue.FromString(resolved), placeholders, expressionErrors);
    }

    private static string ReplaceExpressionEnvelopes(
        string source,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput,
        Action<string> recordPlaceholder,
        List<string> expressionErrors)
    {
        if (string.IsNullOrEmpty(source))
        {
            return source;
        }

        var evaluator = _expressionEvaluator;

        if (evaluator is null)
        {
            return source;
        }

        var builder = new StringBuilder(source.Length);
        var cursor = 0;

        while (cursor < source.Length)
        {
            var start = source.IndexOf("${{", cursor, StringComparison.Ordinal);
            if (start < 0)
            {
                builder.Append(source, cursor, source.Length - cursor);
                break;
            }

            builder.Append(source, cursor, start - cursor);

            var end = source.IndexOf("}}", start + 3, StringComparison.Ordinal);
            if (end < 0)
            {
                builder.Append(source, start, source.Length - start);
                break;
            }

            var expressionBody = source.Substring(start + 3, end - start - 3).Trim();

            if (string.IsNullOrEmpty(expressionBody))
            {
                builder.Append(source, start, end - start + 2);
                cursor = end + 2;
                continue;
            }

            if (TryParseJsonLiteral(expressionBody, out var jsonLiteral))
            {
                builder.Append(jsonLiteral?.ToJsonString() ?? string.Empty);
                cursor = end + 2;
                continue;
            }

            var evalContext = BuildExpressionContext(variables, workflowParameters, stepInput, lastStepOutput);
            var result = evaluator.Evaluate(expressionBody, evalContext);

            if (result.Success)
            {
                foreach (var reference in result.ReferencedIdentifiers ?? [])
                {
                    recordPlaceholder(reference);
                }

                builder.Append(result.Value?.ToDisplayString() ?? string.Empty);
            }
            else
            {
                if (!string.IsNullOrEmpty(result.ErrorMessage))
                {
                    expressionErrors.Add($"{expressionBody}: {result.ErrorMessage}");
                }

                builder.Append(source, start, end - start + 2);
            }

            cursor = end + 2;
        }

        return builder.ToString();
    }

    private static bool TryParseJsonLiteral(string expressionBody, out JsonNode? jsonNode)
    {
        jsonNode = null;

        if (string.IsNullOrWhiteSpace(expressionBody))
        {
            return false;
        }

        var trimmed = expressionBody.Trim();
        if (!(trimmed.StartsWith("{", StringComparison.Ordinal) || trimmed.StartsWith("[", StringComparison.Ordinal)))
        {
            return false;
        }

        try
        {
            jsonNode = JsonNode.Parse(trimmed);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool TryExtractSingleExpression(string source, out string expressionBody)
    {
        expressionBody = string.Empty;

        if (string.IsNullOrWhiteSpace(source))
        {
            return false;
        }

        var trimmed = source.Trim();

        if (!trimmed.StartsWith("${{", StringComparison.Ordinal) || !trimmed.EndsWith("}}", StringComparison.Ordinal))
        {
            return false;
        }

        var body = trimmed[3..^2].Trim();

        if (string.IsNullOrEmpty(body))
        {
            return false;
        }

        expressionBody = body;

        var prefixWhitespace = source.Length - source.TrimStart().Length;
        var suffixWhitespace = source.Length - source.TrimEnd().Length;
        var trimmedLength = source.Length - prefixWhitespace - suffixWhitespace;

        return trimmedLength == trimmed.Length;
    }

    private static (WorkflowExpressionValue TypedValue, string ResolvedValue) EvaluateSingleExpression(
        string expressionBody,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput,
        List<string> placeholders,
        List<string> expressionErrors)
    {
        if (TryParseJsonLiteral(expressionBody, out var jsonLiteral))
        {
            var resolvedJson = jsonLiteral?.ToJsonString() ?? string.Empty;
            return (WorkflowExpressionValue.FromJson(jsonLiteral), resolvedJson);
        }

        var evaluator = _expressionEvaluator;

        if (evaluator is null)
        {
            var literal = $"${{ {{ {expressionBody} }} }}";
            return (WorkflowExpressionValue.FromString(literal), literal);
        }

        var evalContext = BuildExpressionContext(variables, workflowParameters, stepInput, lastStepOutput);
        var result = evaluator.Evaluate(expressionBody, evalContext);

        if (result.Success && result.Value is not null)
        {
            foreach (var reference in result.ReferencedIdentifiers ?? [])
            {
                if (!string.IsNullOrWhiteSpace(reference))
                {
                    placeholders.Add(reference);
                }
            }

            return (result.Value, result.Value.ToDisplayString());
        }

        if (!string.IsNullOrEmpty(result.ErrorMessage))
        {
            expressionErrors.Add($"{expressionBody}: {result.ErrorMessage}");
        }

        var fallbackLiteral = $"${{ {{ {expressionBody} }} }}";
        return (WorkflowExpressionValue.FromString(fallbackLiteral), fallbackLiteral);
    }

    private static WorkflowExpressionContext BuildExpressionContext(
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        var variableValues = variables?.ToDictionary(
            kvp => kvp.Key,
            kvp => WorkflowExpressionValue.FromString(kvp.Value),
            Comparer) ?? new Dictionary<string, WorkflowExpressionValue>(Comparer);

        var parameterValues = workflowParameters?.ToDictionary(
            kvp => kvp.Key,
            kvp => WorkflowExpressionValue.FromString(kvp.Value),
            Comparer) ?? new Dictionary<string, WorkflowExpressionValue>(Comparer);

        return new WorkflowExpressionContext(
            variableValues,
            parameterValues,
            runtimeState: new Dictionary<string, WorkflowExpressionValue>(Comparer),
            stepInput,
            lastStepOutput);
    }

    private static bool TryResolveWorkflowParameter(
        string expression,
        IReadOnlyDictionary<string, string> workflowParameters,
        out string? value)
    {
        value = null;

        if (workflowParameters.Count == 0)
        {
            return false;
        }

        string parameterKey;

        if (expression.StartsWith(ParameterPrefixShort, StringComparison.OrdinalIgnoreCase))
        {
            parameterKey = expression[ParameterPrefixShort.Length..];
        }
        else if (expression.StartsWith(ParameterPrefixLong, StringComparison.OrdinalIgnoreCase))
        {
            parameterKey = expression[ParameterPrefixLong.Length..];
        }
        else
        {
            return false;
        }

        if (string.IsNullOrWhiteSpace(parameterKey))
        {
            return false;
        }

        if (workflowParameters.TryGetValue(parameterKey, out var parameterValue))
        {
            value = parameterValue ?? string.Empty;
            return true;
        }

        return false;
    }

    /// <summary>
    /// Try to resolve a small set of date-preset keywords that
    /// authors reach for inside the legacy <c>{{ … }}</c> syntax
    /// (e.g. <c>{{ today }}</c>, <c>{{ dd-mm-yyyy }}</c>). Mirrors
    /// the Python backend's <c>_resolve_date_preset</c> so a
    /// workflow authored against either backend behaves
    /// identically.
    /// </summary>
    /// <remarks>
    /// The preset layer is purely additive — anything that
    /// isn't a recognised preset falls through to the normal
    /// variable lookup. We also accept the human-friendly format
    /// tokens <c>dd-mm-yyyy</c>, <c>yyyy-mm-dd</c>, <c>mm/dd/yyyy</c>,
    /// etc., which the <c>now()</c> helper also accepts. The .NET
    /// <see cref="DateTimeOffset.ToString(string)"/> method
    /// understands these natively, so no alias translation is
    /// required.
    /// </remarks>
    private static bool TryResolveDatePreset(string expression, out string value)
    {
        value = string.Empty;
        if (string.IsNullOrWhiteSpace(expression))
        {
            return false;
        }

        var trimmed = expression.Trim();
        var localNow = DateTimeOffset.Now;
        var utcNow = DateTimeOffset.UtcNow;

        switch (trimmed.ToLowerInvariant())
        {
            // Word presets
            case "today":
            case "currentdate":
                value = localNow.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                return true;
            case "now":
            case "nowutc":
            case "currentdatetime":
                value = utcNow.ToString("O", CultureInfo.InvariantCulture);
                return true;
            case "nowlocal":
                value = localNow.ToString("O", CultureInfo.InvariantCulture);
                return true;

            // Common date-format placeholders. The agent
            // author wrote ``Current Date Time : dd-mm-yyyy``
            // into the web-search agent's system prompt and the
            // model was hallucinating against the literal
            // string; the preset now turns the placeholder into
            // a working current-date substitution.
            case "dd-mm-yyyy":
                value = localNow.ToString("dd-MM-yyyy", CultureInfo.InvariantCulture);
                return true;
            case "yyyy-mm-dd":
                value = localNow.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
                return true;
            case "mm-dd-yyyy":
                value = localNow.ToString("MM-dd-yyyy", CultureInfo.InvariantCulture);
                return true;
            case "dd/mm/yyyy":
                value = localNow.ToString("dd/MM/yyyy", CultureInfo.InvariantCulture);
                return true;
            case "yyyy/mm/dd":
                value = localNow.ToString("yyyy/MM/dd", CultureInfo.InvariantCulture);
                return true;
            case "mm/dd/yyyy":
                value = localNow.ToString("MM/dd/yyyy", CultureInfo.InvariantCulture);
                return true;
        }

        return false;
    }

    [GeneratedRegex("\\{\\{(?<expr>[^{}]+)\\}\\}", RegexOptions.CultureInvariant)]
    private static partial Regex PlaceholderPattern();

    private static Regex PlaceholderPatternRegex => PlaceholderPattern();

    internal sealed record WorkflowParameterResolution(
        IReadOnlyDictionary<string, WorkflowExpressionValue> Values,
        IReadOnlyDictionary<string, WorkflowParameterDebugInfo> Debug);

    // WorkflowParameterDebugInfo is defined elsewhere
}