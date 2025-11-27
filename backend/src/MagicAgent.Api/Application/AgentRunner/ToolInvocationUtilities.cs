using System.Globalization;
using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;

namespace MagicAgent.Api.Application.AgentRunner;

internal static class ToolInvocationUtilities
{
    internal static ToolInvocationAnalysis Analyze(AgentRunResponse? runResponse)
    {
        var invocations = ExtractToolInvocations(runResponse);
        var errors = ExtractToolErrors(invocations);
        var toolCalls = MapToolInvocations(invocations);

        return new ToolInvocationAnalysis(invocations, errors, toolCalls);
    }

    internal static AgentStepExecutionResult CreateErrorResult(AgentStepDefinition step, ToolInvocationAnalysis analysis)
    {
        var errorText = string.Join(Environment.NewLine, analysis.Errors.Select(e => $"[{e.ToolName}] {e.Message}"));

        return new AgentStepExecutionResult(step.Name, step.Type, errorText)
        {
            Outcome = "error",
            EndWorkflow = step.StopOnToolError,
            ToolInvocations = analysis.ToolCalls,
            ToolErrorDetected = true,
        };
    }

    private static List<ToolInvocationRecord> ExtractToolInvocations(AgentRunResponse? runResponse)
    {
        if (runResponse is null)
        {
            return [];
        }

        if (runResponse.Messages is not { Count: > 0 })
        {
            return [];
        }

        var functionCallMetadata = BuildFunctionCallMetadata(runResponse.Messages);
        var invocations = new List<ToolInvocationRecord>();

        foreach (var message in runResponse.Messages)
        {
            if (message is null || !ChatRole.Tool.Equals(message.Role))
            {
                continue;
            }

            invocations.Add(CreateToolInvocationFromMessage(message, functionCallMetadata));
        }

        return invocations.Count > 0 ? invocations : [];
    }

    private static List<ToolExecutionError> ExtractToolErrors(List<ToolInvocationRecord> toolInvocations)
    {
        if (toolInvocations.Count == 0)
        {
            return [];
        }

        var errors = new List<ToolExecutionError>();

        foreach (var invocation in toolInvocations)
        {
            if (invocation.Error is null)
            {
                continue;
            }

            var message = !string.IsNullOrWhiteSpace(invocation.Error.Message)
                ? invocation.Error.Message!
                : !string.IsNullOrWhiteSpace(invocation.Error.Details)
                    ? invocation.Error.Details!
                    : "Tool execution failed.";

            errors.Add(new ToolExecutionError(
                invocation.ToolName ?? string.Empty,
                invocation.InvocationId ?? string.Empty,
                message,
                invocation.Error.Code));
        }

        return errors;
    }

    private static List<AgentToolCall> MapToolInvocations(List<ToolInvocationRecord> toolInvocations)
    {
        if (toolInvocations.Count == 0)
        {
            return [];
        }

        var calls = new List<AgentToolCall>(toolInvocations.Count);

        foreach (var invocation in toolInvocations)
        {
            calls.Add(new AgentToolCall(
                invocation.ToolName,
                invocation.InvocationId,
                invocation.ResultText,
                invocation.ArgumentsJson,
                invocation.Error?.Message,
                invocation.Error?.Details,
                invocation.Error?.Code));
        }

        return calls;
    }

    private static bool TryGetToolInvocations(object? source, out IReadOnlyList<ToolInvocationRecord> invocations)
    {
        invocations = [];

        if (source is null)
        {
            return false;
        }

        if (source is IEnumerable<KeyValuePair<string, object?>> pairs)
        {
            foreach (var pair in pairs)
            {
                if (IsToolInvocationsKey(pair.Key) && TryGetToolInvocations(pair.Value, out invocations))
                {
                    return true;
                }
            }

            return false;
        }

        if (source is System.Collections.IDictionary legacyDict)
        {
            foreach (System.Collections.DictionaryEntry entry in legacyDict)
            {
                var key = entry.Key?.ToString();
                if (IsToolInvocationsKey(key) && TryGetToolInvocations(entry.Value, out invocations))
                {
                    return true;
                }
            }

            return false;
        }

        if (source is string jsonText)
        {
            if (string.IsNullOrWhiteSpace(jsonText))
            {
                return false;
            }

            try
            {
                return TryGetToolInvocationsFromElement(JsonSerializer.Deserialize<JsonElement>(jsonText), out invocations);
            }
            catch
            {
                return false;
            }
        }

        if (TryConvertToJsonElement(source, out var jsonElement))
        {
            return TryGetToolInvocationsFromElement(jsonElement, out invocations);
        }

        if (source is IEnumerable<object?> enumerable)
        {
            try
            {
                var serializedElement = JsonSerializer.SerializeToElement(enumerable);
                return TryGetToolInvocationsFromElement(serializedElement, out invocations);
            }
            catch
            {
                return false;
            }
        }

        return false;
    }

    private static bool IsToolInvocationsKey(string? key) =>
        key is not null && (key.Equals("toolInvocations", StringComparison.OrdinalIgnoreCase) ||
            key.Equals("tool_invocations", StringComparison.OrdinalIgnoreCase));

    private static bool TryGetToolInvocationsFromElement(JsonElement element, out IReadOnlyList<ToolInvocationRecord> invocations)
    {
        invocations = [];

        if (element.ValueKind == JsonValueKind.Undefined || element.ValueKind == JsonValueKind.Null)
        {
            return false;
        }

        JsonElement arrayElement;

        if (element.ValueKind == JsonValueKind.Array)
        {
            arrayElement = element;
        }
        else if (element.ValueKind == JsonValueKind.Object)
        {
            if (element.TryGetProperty("toolInvocations", out var property) && property.ValueKind == JsonValueKind.Array)
            {
                arrayElement = property;
            }
            else if (element.TryGetProperty("tool_invocations", out property) && property.ValueKind == JsonValueKind.Array)
            {
                arrayElement = property;
            }
            else
            {
                var single = CreateInvocationFromJsonObject(element);
                if (single is not null)
                {
                    invocations = [ single ];
                    return true;
                }

                return false;
            }
        }
        else
        {
            return false;
        }

        var results = new List<ToolInvocationRecord>(arrayElement.GetArrayLength());

        foreach (var item in arrayElement.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
            {
                continue;
            }

            var record = CreateInvocationFromJsonObject(item);
            if (record is not null)
            {
                results.Add(record);
            }
        }

        if (results.Count == 0)
        {
            return false;
        }

        invocations = results;
        return true;
    }

    private static ToolInvocationRecord? CreateInvocationFromJsonObject(JsonElement element)
    {
        string? toolName = ReadStringProperty(element, "toolName") ?? ReadStringProperty(element, "name");
        string? invocationId = ReadStringProperty(element, "id") ?? ReadStringProperty(element, "callId");
        string? resultText = ReadContentText(element);

        ToolInvocationErrorRecord? error = null;
        if (element.TryGetProperty("error", out var errorElement) && errorElement.ValueKind == JsonValueKind.Object)
        {
            error = new ToolInvocationErrorRecord(
                Message: ReadStringProperty(errorElement, "message"),
                Details: ReadStringProperty(errorElement, "details"),
                Code: ReadStringProperty(errorElement, "code"));
        }

        if (toolName is null && invocationId is null && resultText is null && error is null)
        {
            return null;
        }

        string? argumentsJson = null;

        ExtractToolInvocationMetadata(element, ref toolName, ref invocationId, ref argumentsJson, ref resultText);

        return new ToolInvocationRecord(toolName, invocationId, resultText, argumentsJson, error);
    }

    private static bool TryConvertToJsonElement(object source, out JsonElement element)
    {
        element = default;

        if (source is JsonElement jsonElement)
        {
            element = jsonElement;
            return true;
        }

        if (source is JsonDocument document)
        {
            element = document.RootElement;
            return true;
        }

        if (source is string json && !string.IsNullOrWhiteSpace(json))
        {
            try
            {
                element = JsonSerializer.Deserialize<JsonElement>(json);
                return true;
            }
            catch
            {
                return false;
            }
        }

        try
        {
            element = JsonSerializer.SerializeToElement(source);
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static string? ReadStringProperty(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var value))
        {
            return null;
        }

        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString(),
            JsonValueKind.Number => value.TryGetInt64(out var longValue) ? longValue.ToString(CultureInfo.InvariantCulture) : value.ToString(),
            JsonValueKind.True or JsonValueKind.False => value.GetBoolean().ToString(),
            JsonValueKind.Object or JsonValueKind.Array => JsonSerializer.Serialize(value),
            _ => null,
        };
    }

    private static string? ReadContentText(JsonElement element)
    {
        if (element.TryGetProperty("result", out var result))
        {
            return SerializeContent(result);
        }

        if (element.TryGetProperty("response", out var response))
        {
            return SerializeContent(response);
        }

        if (element.TryGetProperty("content", out var content))
        {
            return SerializeContent(content);
        }

        return null;
    }

    private static string? SerializeContent(JsonElement element)
    {
        return element.ValueKind switch
        {
            JsonValueKind.String => element.GetString(),
            JsonValueKind.Undefined or JsonValueKind.Null => null,
            _ => JsonSerializer.Serialize(element),
        };
    }

    internal sealed class ToolInvocationAnalysis
    {
        internal ToolInvocationAnalysis(
            IReadOnlyList<ToolInvocationRecord> rawInvocations,
            IReadOnlyList<ToolExecutionError> errors,
            List<AgentToolCall> toolCalls)
        {
            RawInvocations = rawInvocations;
            Errors = errors;
            ToolCalls = toolCalls;
        }

        internal IReadOnlyList<ToolInvocationRecord> RawInvocations { get; }

        internal IReadOnlyList<ToolExecutionError> Errors { get; }

        internal List<AgentToolCall> ToolCalls { get; }

        internal bool HasErrors => Errors.Count > 0;
    }

    private static ToolInvocationRecord CreateToolInvocationFromMessage(
        ChatMessage message,
        Dictionary<string, (string? ToolName, string? ArgumentsJson)> functionCallMetadata)
    {
        string? resultText = string.IsNullOrWhiteSpace(message.Text) ? null : message.Text;
        string? toolName = null;
        string? invocationId = null;
        string? argumentsJson = null;

        if (message.Contents is { Count: > 0 })
        {
            var serializedContents = JsonSerializer.Serialize(message.Contents);

            try
            {
                using var document = JsonDocument.Parse(serializedContents);
                ExtractToolInvocationMetadata(document.RootElement, ref toolName, ref invocationId, ref argumentsJson, ref resultText);
            }
            catch
            {
                // Ignore parsing failures and fall back to serialized contents.
            }

            resultText ??= serializedContents;
        }
        else if (!string.IsNullOrWhiteSpace(message.Text))
        {
            try
            {
                using var document = JsonDocument.Parse(message.Text);
                ExtractToolInvocationMetadata(document.RootElement, ref toolName, ref invocationId, ref argumentsJson, ref resultText);
            }
            catch
            {
                // message.Text is not JSON—leave as-is.
            }
        }

        if (invocationId is not null && functionCallMetadata.TryGetValue(invocationId, out var metadata))
        {
            toolName ??= metadata.ToolName;
            argumentsJson ??= metadata.ArgumentsJson;
        }

        return new ToolInvocationRecord(toolName, invocationId, resultText, argumentsJson, null);
    }

    private static Dictionary<string, (string? ToolName, string? ArgumentsJson)> BuildFunctionCallMetadata(
        IEnumerable<ChatMessage?> messages)
    {
        var metadata = new Dictionary<string, (string? ToolName, string? ArgumentsJson)>(StringComparer.OrdinalIgnoreCase);

        foreach (var message in messages)
        {
            if (message is null || !ChatRole.Assistant.Equals(message.Role) || message.Contents is not { Count: > 0 })
            {
                continue;
            }

            foreach (var content in message.Contents)
            {
                try
                {
                    var serialized = JsonSerializer.Serialize(content);
                    using var document = JsonDocument.Parse(serialized);
                    var root = document.RootElement;

                    var typeName = GetStringPropertyIgnoreCase(root, "$type");
                    if (!string.Equals(typeName, "functionCall", StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    var callId = GetStringPropertyIgnoreCase(root, "CallId");
                    if (string.IsNullOrWhiteSpace(callId))
                    {
                        continue;
                    }

                    var toolName = GetStringPropertyIgnoreCase(root, "Name");
                    string? argumentsJson = null;

                    if (TryGetPropertyIgnoreCase(root, "Arguments", out var argumentsElement) &&
                        argumentsElement.ValueKind is not JsonValueKind.Null and not JsonValueKind.Undefined)
                    {
                        argumentsJson = argumentsElement.GetRawText();
                    }

                    metadata[callId] = (toolName, argumentsJson);
                }
                catch
                {
                    // Ignore malformed content entries.
                }
            }
        }

        return metadata;
    }

    private static string? GetStringPropertyIgnoreCase(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            return null;
        }

        foreach (var property in element.EnumerateObject())
        {
            if (property.NameEquals(propertyName) || property.Name.Equals(propertyName, StringComparison.OrdinalIgnoreCase))
            {
                return property.Value.ValueKind switch
                {
                    JsonValueKind.String => property.Value.GetString(),
                    JsonValueKind.Number => property.Value.GetRawText(),
                    JsonValueKind.True or JsonValueKind.False => property.Value.GetBoolean().ToString(),
                    _ => property.Value.GetRawText(),
                };
            }
        }

        return null;
    }

    private static bool TryGetPropertyIgnoreCase(JsonElement element, string propertyName, out JsonElement value)
    {
        value = default;

        if (element.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        foreach (var property in element.EnumerateObject())
        {
            if (property.NameEquals(propertyName) || property.Name.Equals(propertyName, StringComparison.OrdinalIgnoreCase))
            {
                value = property.Value;
                return true;
            }
        }

        return false;
    }

    private static void ExtractToolInvocationMetadata(
        JsonElement element,
        ref string? toolName,
        ref string? invocationId,
        ref string? argumentsJson,
        ref string? resultText)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            if (string.IsNullOrWhiteSpace(resultText))
            {
                var candidateResult = ReadContentText(element);
                if (!string.IsNullOrWhiteSpace(candidateResult))
                {
                    resultText = candidateResult;
                }
            }

            foreach (var property in element.EnumerateObject())
            {
                var propertyName = property.Name;
                var propertyNameLower = propertyName.ToLowerInvariant();

                if (toolName is null && property.Value.ValueKind == JsonValueKind.String &&
                    (propertyNameLower is "toolname" or "name" or "tool"))
                {
                    toolName = property.Value.GetString();
                }

                if (invocationId is null &&
                    (propertyNameLower is "invocationid" or "callid" or "id" or "toolcallid"))
                {
                    if (property.Value.ValueKind == JsonValueKind.String)
                    {
                        invocationId = property.Value.GetString();
                    }
                    else if (property.Value.ValueKind == JsonValueKind.Number)
                    {
                        invocationId = property.Value.GetRawText();
                    }
                }

                if (argumentsJson is null &&
                    (propertyNameLower is "arguments" or "args" or "parameters" or "input" or "payload"))
                {
                    if (property.Value.ValueKind is JsonValueKind.Object or JsonValueKind.Array or JsonValueKind.String or JsonValueKind.Number or JsonValueKind.True or JsonValueKind.False)
                    {
                        var raw = property.Value.GetRawText();
                        if (!string.IsNullOrWhiteSpace(raw) && raw != "null")
                        {
                            argumentsJson = raw;
                        }
                    }
                }

                ExtractToolInvocationMetadata(property.Value, ref toolName, ref invocationId, ref argumentsJson, ref resultText);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in element.EnumerateArray())
            {
                ExtractToolInvocationMetadata(item, ref toolName, ref invocationId, ref argumentsJson, ref resultText);
            }
        }
    }

    internal sealed record ToolInvocationRecord(
        string? ToolName,
        string? InvocationId,
        string? ResultText,
        string? ArgumentsJson,
        ToolInvocationErrorRecord? Error);

    internal sealed record ToolInvocationErrorRecord(string? Message, string? Details, string? Code);

    internal sealed record ToolExecutionError(string ToolName, string ToolCallId, string Message, string? Code = null);
}
