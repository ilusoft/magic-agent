using System.Text.RegularExpressions;

namespace MagicAgent.Api.Application.AgentRunner;

internal static partial class WorkflowPlaceholderResolver
{
    private const string VariablePrefix = "var.";
    private const string ParameterPrefixShort = "param.";
    private const string ParameterPrefixLong = "parameter.";
    private static readonly StringComparer Comparer = StringComparer.OrdinalIgnoreCase;
    private static readonly IReadOnlyDictionary<string, string> EmptyDictionary = new Dictionary<string, string>(Comparer);

    internal static IReadOnlyDictionary<string, string> ResolveDictionary(
        IDictionary<string, string>? source,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        if (source is null || source.Count == 0)
        {
            return EmptyDictionary;
        }

        var resolved = new Dictionary<string, string>(source.Count, Comparer);

        foreach (var kvp in source)
        {
            resolved[kvp.Key] = ResolveString(kvp.Value, variables, workflowParameters, stepInput, lastStepOutput);
        }

        return resolved;
    }

    internal static string ResolveString(
        string value,
        IReadOnlyDictionary<string, string> variables,
        IReadOnlyDictionary<string, string>? workflowParameters,
        string? stepInput,
        string? lastStepOutput)
    {
        if (string.IsNullOrEmpty(value))
        {
            return value;
        }

        var parameterDictionary = workflowParameters ?? EmptyDictionary;

        return PlaceholderPatternRegex.Replace(value, match =>
        {
            var expression = match.Groups["expr"].Value.Trim();

            if (string.IsNullOrEmpty(expression))
            {
                return match.Value;
            }

            if (Comparer.Equals(expression, "input"))
            {
                return stepInput ?? string.Empty;
            }

            if (Comparer.Equals(expression, "lastOutput"))
            {
                return lastStepOutput ?? string.Empty;
            }

            if (TryResolveWorkflowParameter(expression, parameterDictionary, out var parameterValue))
            {
                return parameterValue ?? string.Empty;
            }

            if (expression.StartsWith(VariablePrefix, StringComparison.OrdinalIgnoreCase))
            {
                expression = expression[VariablePrefix.Length..];
            }

            if (variables.TryGetValue(expression, out var variableValue))
            {
                return variableValue ?? string.Empty;
            }

            return match.Value;
        });
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
}