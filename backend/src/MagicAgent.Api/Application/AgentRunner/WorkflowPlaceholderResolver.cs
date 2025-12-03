using System.Text;
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
            return new WorkflowParameterResolution(EmptyDictionary, new Dictionary<string, WorkflowParameterDebugInfo>(Comparer));
        }

        var resolved = new Dictionary<string, string>(source.Count, Comparer);
        var debug = new Dictionary<string, WorkflowParameterDebugInfo>(source.Count, Comparer);

        foreach (var kvp in source)
        {
            var (value, placeholders, expressionErrors) = ResolveStringWithDebug(kvp.Value ?? string.Empty, variables, workflowParameters, stepInput, lastStepOutput);
            resolved[kvp.Key] = value;
            debug[kvp.Key] = new WorkflowParameterDebugInfo(
                kvp.Value ?? string.Empty,
                value,
                placeholders,
                expressionErrors);
        }

        return new WorkflowParameterResolution(resolved, debug);
    }

    internal static IReadOnlyDictionary<string, string> ResolveDictionary(
        IDictionary<string, string>? source,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        return ResolveDictionaryWithDebug(source, variables, workflowParameters, stepInput, lastStepOutput).ResolvedValues;
    }

    internal static string ResolveString(
        string value,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
        => ResolveStringWithDebug(value, variables, workflowParameters, stepInput, lastStepOutput).ResolvedValue;

    private static (string ResolvedValue, IReadOnlyList<string> Placeholders, IReadOnlyList<string> ExpressionErrors) ResolveStringWithDebug(
        string value,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        var source = value ?? string.Empty;

        if (string.IsNullOrEmpty(source))
        {
            return (source, Array.Empty<string>(), Array.Empty<string>());
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

        return (resolved, placeholders, expressionErrors);
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

    [GeneratedRegex("\\{\\{(?<expr>[^{}]+)\\}\\}", RegexOptions.CultureInvariant)]
    private static partial Regex PlaceholderPattern();

    private static Regex PlaceholderPatternRegex => PlaceholderPattern();

    internal sealed record WorkflowParameterResolution(
        IReadOnlyDictionary<string, string> ResolvedValues,
        IReadOnlyDictionary<string, WorkflowParameterDebugInfo> Debug);

    // WorkflowParameterDebugInfo is defined elsewhere
}