using System;
using System.Text.Json.Nodes;

namespace MagicAgent.Api.Application.Expressions.Helpers;

public static class StringWorkflowHelpers
{
    [WorkflowHelper("length", ReturnType = WorkflowExpressionValueKind.Number, Description = "Returns the number of characters in the string.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    public static double Length(string value) => value?.Length ?? 0;

    [WorkflowHelper("toUpper", ReturnType = WorkflowExpressionValueKind.String, Description = "Converts the input to uppercase using invariant culture.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    public static string ToUpper(string value) => (value ?? string.Empty).ToUpperInvariant();

    [WorkflowHelper("toLower", ReturnType = WorkflowExpressionValueKind.String, Description = "Converts the input to lowercase using invariant culture.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    public static string ToLower(string value) => (value ?? string.Empty).ToLowerInvariant();

    [WorkflowHelper("substring", ReturnType = WorkflowExpressionValueKind.String, Description = "Extracts a substring starting at the specified index.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("start", Description = "Zero-based starting index.")]
    [WorkflowHelperParameter("length", Description = "Number of characters (0 means until end).", IsOptional = true)]
    public static string Substring(string value, double start, double length = 0)
    {
        var text = value ?? string.Empty;
        var startIndex = ClampIndex((int)Math.Round(start, MidpointRounding.AwayFromZero), text.Length);
        var remaining = text.Length - startIndex;
        var resolvedLength = length <= 0 ? remaining : Math.Min(remaining, (int)Math.Round(length, MidpointRounding.AwayFromZero));
        return resolvedLength <= 0 ? string.Empty : text.Substring(startIndex, resolvedLength);
    }

    [WorkflowHelper("replace", ReturnType = WorkflowExpressionValueKind.String, Description = "Replaces occurrences of a substring.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("match", Description = "Substring to replace.")]
    [WorkflowHelperParameter("replaceWith", Description = "Replacement string.")]
    public static string Replace(string value, string match, string replaceWith)
    {
        var source = value ?? string.Empty;
        var target = match ?? string.Empty;
        var replacement = replaceWith ?? string.Empty;
        return target.Length == 0 ? source : source.Replace(target, replacement, StringComparison.Ordinal);
    }

    [WorkflowHelper("indexOf", ReturnType = WorkflowExpressionValueKind.Number, Description = "Returns the index of the first occurrence of a term (or -1).")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("term", Description = "Term to search for.")]
    public static double IndexOf(string value, string term)
    {
        var source = value ?? string.Empty;
        var search = term ?? string.Empty;
        if (search.Length == 0)
        {
            return 0;
        }

        return source.IndexOf(search, StringComparison.Ordinal);
    }

    [WorkflowHelper("trim", ReturnType = WorkflowExpressionValueKind.String, Description = "Trims whitespace from both ends of the string.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    public static string Trim(string value) => (value ?? string.Empty).Trim();

    [WorkflowHelper("split", ReturnType = WorkflowExpressionValueKind.Json, Description = "Splits a string by the provided separator and returns a JSON array.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("separator", Description = "Separator to split on (defaults to comma).", IsOptional = true)]
    public static JsonArray Split(string value, string separator = ",")
    {
        var text = value ?? string.Empty;
        var token = string.IsNullOrEmpty(separator) ? "," : separator;
        var parts = text.Split(token, StringSplitOptions.None);
        var array = new JsonArray();
        foreach (var part in parts)
        {
            array.Add(part);
        }

        return array;
    }

    [WorkflowHelper("contains", ReturnType = WorkflowExpressionValueKind.Boolean, Description = "Returns true when the value contains the provided search term (case-sensitive).")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("searchValue", Description = "Substring to locate within the input.")]
    public static bool Contains(string value, string searchValue)
    {
        var source = value ?? string.Empty;
        var term = searchValue ?? string.Empty;
        return term.Length == 0 || source.IndexOf(term, StringComparison.Ordinal) >= 0;
    }

    [WorkflowHelper("startsWith", ReturnType = WorkflowExpressionValueKind.Boolean, Description = "Returns true when the value starts with the provided prefix (case-sensitive).")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("searchValue", Description = "Prefix to evaluate.")]
    public static bool StartsWith(string value, string searchValue)
    {
        var source = value ?? string.Empty;
        var prefix = searchValue ?? string.Empty;
        return source.StartsWith(prefix, StringComparison.Ordinal);
    }

    [WorkflowHelper("endsWith", ReturnType = WorkflowExpressionValueKind.Boolean, Description = "Returns true when the value ends with the provided suffix (case-sensitive).")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    [WorkflowHelperParameter("searchValue", Description = "Suffix to evaluate.")]
    public static bool EndsWith(string value, string searchValue)
    {
        var source = value ?? string.Empty;
        var suffix = searchValue ?? string.Empty;
        return source.EndsWith(suffix, StringComparison.Ordinal);
    }

    [WorkflowHelper("compare", ReturnType = WorkflowExpressionValueKind.Boolean, Description = "Compares two strings with optional trimming and case sensitivity.")]
    [WorkflowHelperParameter("value", Description = "First value to compare.")]
    [WorkflowHelperParameter("other", Description = "Second value to compare.")]
    [WorkflowHelperParameter("caseSensitive", Description = "If true, performs a case-sensitive comparison.", IsOptional = true)]
    [WorkflowHelperParameter("trimWhitespace", Description = "If true, trims both values before comparison.", IsOptional = true)]
    public static bool Compare(string value, string other, bool caseSensitive = false, bool trimWhitespace = false)
    {
        var first = value ?? string.Empty;
        var second = other ?? string.Empty;

        if (trimWhitespace)
        {
            first = first.Trim();
            second = second.Trim();
        }

        var comparison = caseSensitive ? StringComparison.Ordinal : StringComparison.OrdinalIgnoreCase;
        return string.Equals(first, second, comparison);
    }

    [WorkflowHelper("isNullOrEmpty", ReturnType = WorkflowExpressionValueKind.Boolean, Description = "Returns true when the string is null or empty.")]
    [WorkflowHelperParameter("value", Description = "Input string.")]
    public static bool IsNullOrEmpty(string value) => string.IsNullOrEmpty(value);

    [WorkflowHelper("isNull", ReturnType = WorkflowExpressionValueKind.Boolean, Description = "Returns true when the provided expression evaluates to null.")]
    [WorkflowHelperParameter("value", Description = "Value to inspect.")]
    public static bool IsNull(WorkflowExpressionValue value) => value is null || value.Kind == WorkflowExpressionValueKind.Null;

    private static int ClampIndex(int index, int length)
    {
        if (length <= 0)
        {
            return 0;
        }

        if (index < 0)
        {
            return 0;
        }

        if (index >= length)
        {
            return length;
        }

        return index;
    }
}