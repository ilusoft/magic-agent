using System.Text.RegularExpressions;

namespace MagicAgent.Api.Application.AgentRunner;

internal static partial class WorkflowPlaceholderResolver
{
    private const string VariablePrefix = "var.";
    private static readonly StringComparer Comparer = StringComparer.OrdinalIgnoreCase;
    private static readonly IReadOnlyDictionary<string, string> EmptyDictionary = new Dictionary<string, string>(Comparer);

    internal static IReadOnlyDictionary<string, string> ResolveDictionary(
        IDictionary<string, string>? source,
        IReadOnlyDictionary<string, string> variables,
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
            resolved[kvp.Key] = ResolveString(kvp.Value, variables, stepInput, lastStepOutput);
        }

        return resolved;
    }

    internal static string ResolveString(
        string value,
        IReadOnlyDictionary<string, string> variables,
        string? stepInput,
        string? lastStepOutput)
    {
        if (string.IsNullOrEmpty(value))
        {
            return value;
        }

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

    [GeneratedRegex("\\{\\{(?<expr>[^{}]+)\\}\\}", RegexOptions.CultureInvariant)]
    private static partial Regex PlaceholderPattern();

    private static Regex PlaceholderPatternRegex => PlaceholderPattern();
}