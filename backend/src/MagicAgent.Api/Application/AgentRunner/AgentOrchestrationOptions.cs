using System.Runtime.Serialization;
using System.Text.Json.Serialization;

namespace MagicAgent.Api.Application.AgentRunner;

public sealed class AgentDefinitionsOptions
{
    public string FilePath { get; init; } = "Configurations/agents.json";
}

[JsonConverter(typeof(JsonStringEnumConverter))]
public enum WorkflowVariableDataType
{
    [EnumMember(Value = "string")]
    String,

    [EnumMember(Value = "number")]
    Number,

    [EnumMember(Value = "dateTime")]
    DateTime,

    [EnumMember(Value = "json")]
    Json,

    [EnumMember(Value = "boolean")]
    Boolean,
}

public sealed class AgentDefinitionsDocument
{
    [JsonPropertyName("llmProfiles")]
    public IDictionary<string, AgentLlmProfileDefinition> LlmProfiles { get; set; }
        = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("tools")]
    public IDictionary<string, AgentToolDefinition> Tools { get; set; }
        = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("agents")]
    public IList<AgentDefinition> Agents { get; set; } = [];
}

public sealed class AgentDefinition
{
    [JsonPropertyName("id")]
    public required string Id { get; init; }
    [JsonPropertyName("name")]
    public string Name { get; init; } = "";
    [JsonPropertyName("description")]
    public string? Description { get; init; }
    [JsonPropertyName("defaultParameters")]
    public IDictionary<string, string> DefaultParameters { get; init; }
        = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    [JsonPropertyName("steps")]
    public IList<AgentStepDefinition> Steps { get; init; } = [];
    [JsonPropertyName("viewLayout")]
    public AgentViewLayout? ViewLayout { get; init; }
    [JsonPropertyName("streaming")]
    public AgentStreamingOptions? Streaming { get; init; }
}

public sealed class AgentStreamingOptions
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; init; }

    [JsonPropertyName("mode")]
    public string Mode { get; init; } = "sse";
}

public sealed class AgentViewLayout
{
    [JsonPropertyName("nodes")]
    public IDictionary<string, AgentViewLayoutNode> Nodes { get; init; } = new Dictionary<string, AgentViewLayoutNode>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("edges")]
    public IDictionary<string, AgentViewLayoutEdge> Edges { get; init; } = new Dictionary<string, AgentViewLayoutEdge>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("viewport")]
    public AgentViewLayoutViewport? Viewport { get; init; }
}

public sealed class AgentViewLayoutNode
{
    [JsonPropertyName("x")]
    public double X { get; init; }

    [JsonPropertyName("y")]
    public double Y { get; init; }

    [JsonPropertyName("handles")]
    public AgentNodeHandlePlacement? Handles { get; init; }
}

public sealed class AgentNodeHandlePlacement
{
    [JsonPropertyName("input")]
    [JsonConverter(typeof(JsonStringEnumConverter<WorkflowHandlePosition>))]
    public WorkflowHandlePosition? Input { get; init; }

    [JsonPropertyName("outcomes")]
    [JsonConverter(typeof(JsonStringEnumConverter<WorkflowHandlePosition>))]
    public WorkflowHandlePosition? Outcomes { get; init; }

    [JsonPropertyName("tools")]
    [JsonConverter(typeof(JsonStringEnumConverter<WorkflowHandlePosition>))]
    public WorkflowHandlePosition? Tools { get; init; }
}

public enum WorkflowHandlePosition
{
    [JsonPropertyName("top")]
    Top,

    [JsonPropertyName("right")]
    Right,

    [JsonPropertyName("bottom")]
    Bottom,

    [JsonPropertyName("left")]
    Left,
}

public sealed class AgentViewLayoutEdge
{
    [JsonPropertyName("controlPoints")]
    public IList<AgentViewLayoutNode> ControlPoints { get; init; } = [];
}

public sealed class AgentViewLayoutViewport
{
    [JsonPropertyName("position")]
    public AgentViewLayoutNode Position { get; init; } = new AgentViewLayoutNode();

    [JsonPropertyName("zoom")]
    public double Zoom { get; init; }
}

public sealed class AgentStepDefinition
{
    [JsonPropertyName("name")]
    public required string Name { get; init; }
    [JsonPropertyName("type")]
    public required string Type { get; init; }
    [JsonPropertyName("parameters")]
    public IDictionary<string, string> Parameters { get; init; }
        = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    [JsonPropertyName("variableTypes")]
    public IDictionary<string, WorkflowVariableDataType> VariableTypes { get; init; }
        = new Dictionary<string, WorkflowVariableDataType>(StringComparer.OrdinalIgnoreCase);
    [JsonPropertyName("conversation")]
    public AgentStepConversationOptions? Conversation { get; init; }
    [JsonPropertyName("tools")]
    public IList<string> Tools { get; init; } = [];
    [JsonPropertyName("stopOnToolError")]
    public bool StopOnToolError { get; init; }
    [JsonPropertyName("inputSource")]
    public string InputSource { get; init; } = "usePrevious";

    [JsonPropertyName("llmConfig")]
    public AgentStepLlmConfig? LlmConfig { get; init; }

    [JsonPropertyName("outcomes")]
    public IList<AgentStepOutcomeDefinition> Outcomes { get; init; } = [];

    [JsonIgnore]
    public bool IsStartStep { get; set; }
}

public sealed class AgentStepConversationOptions
{
    [JsonPropertyName("enabled")]
    public bool Enabled { get; init; }
}

public sealed class AgentStepOutcomeDefinition
{
    [JsonPropertyName("name")]
    public required string Name { get; init; }

    [JsonPropertyName("nextStep")]
    public string? NextStep { get; init; }

    [JsonPropertyName("condition")]
    public AgentStepOutcomeConditionDefinition? Condition { get; init; }

    [JsonPropertyName("endWorkflow")]
    public bool EndWorkflow { get; init; }

    [JsonPropertyName("order")]
    public int? Order { get; init; }
}

public sealed class AgentStepOutcomeConditionDefinition
{
    [JsonPropertyName("expression")]
    public string? Expression { get; init; }
}

public sealed class AgentToolDefinition
{
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    [JsonPropertyName("type")]
    public required string Type { get; init; }

    [JsonPropertyName("name")]
    public string Name { get; init; } = string.Empty;

    [JsonPropertyName("description")]
    public string? Description { get; init; }

    [JsonPropertyName("serverUrl")]
    public string? ServerUrl { get; init; }

    [JsonPropertyName("protocol")]
    public string Protocol { get; init; } = "auto";

    [JsonPropertyName("headers")]
    public IDictionary<string, string> Headers { get; init; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("options")]
    public IDictionary<string, string> Options { get; init; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("actions")]
    public IList<AgentToolActionDefinition> Actions { get; init; } = [];

    [JsonPropertyName("allowedTools")]
    public IList<string> AllowedTools { get; init; } = [];

    [JsonPropertyName("forwardAuthorizationHeader")]
    public bool ForwardAuthorizationHeader { get; init; }

    [JsonPropertyName("authorizationHeaderName")]
    public string AuthorizationHeaderName { get; init; } = "Authorization";

    [JsonPropertyName("stopOnToolInitError")]
    public bool StopOnToolInitError { get; init; }
}

public sealed class AgentToolActionDefinition
{
    [JsonPropertyName("name")]
    public required string Name { get; init; }

    [JsonPropertyName("description")]
    public string? Description { get; init; }

    [JsonPropertyName("parameters")]
    public IDictionary<string, string> Parameters { get; init; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
}

public sealed class AgentLlmProfileDefinition
{
    [JsonPropertyName("provider")]
    public string Provider { get; init; } = "azure-openai";

    [JsonPropertyName("endpoint")]
    public string? Endpoint { get; init; }

    [JsonPropertyName("deployment")]
    public string? Deployment { get; init; }

    [JsonPropertyName("apiVersion")]
    public string? ApiVersion { get; init; }

    [JsonPropertyName("baseUrl")]
    public string? BaseUrl { get; init; }

    [JsonPropertyName("model")]
    public string? Model { get; init; }

    [JsonPropertyName("apiKey")]
    public string? ApiKey { get; init; }

    [JsonPropertyName("headers")]
    public IDictionary<string, string> Headers { get; init; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("temperature")]
    public double? Temperature { get; init; }

    [JsonPropertyName("maxTokens")]
    public int? MaxTokens { get; init; }
}

public sealed class AgentStepLlmConfig
{
    [JsonPropertyName("profileId")]
    public string? ProfileId { get; init; }

    [JsonPropertyName("provider")]
    public string? Provider { get; init; }

    [JsonPropertyName("endpoint")]
    public string? Endpoint { get; init; }

    [JsonPropertyName("deployment")]
    public string? Deployment { get; init; }

    [JsonPropertyName("apiVersion")]
    public string? ApiVersion { get; init; }

    [JsonPropertyName("baseUrl")]
    public string? BaseUrl { get; init; }

    [JsonPropertyName("model")]
    public string? Model { get; init; }

    [JsonPropertyName("apiKey")]
    public string? ApiKey { get; init; }

    [JsonPropertyName("headers")]
    public IDictionary<string, string> Headers { get; init; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("temperature")]
    public double? Temperature { get; init; }

    [JsonPropertyName("maxTokens")]
    public int? MaxTokens { get; init; }
}

public sealed record LLMCallConfig(
    string Provider,
    string? Model,
    string? Endpoint,
    string? BaseUrl,
    string? Deployment,
    string? ApiVersion,
    double? Temperature,
    int? MaxTokens,
    string? ApiKeyFingerprint)
{
    /// <summary>
    /// Returns a short, non-reversible identifier for an API key (e.g. "***2S").
    /// Mirrors <c>backend-py/src/application/agents/run_result.py:_fingerprint_api_key</c>.
    /// </summary>
    public static string? FingerprintApiKey(string? apiKey)
    {
        if (string.IsNullOrEmpty(apiKey))
        {
            return null;
        }

        if (apiKey.Length <= 4)
        {
            return $"***{apiKey}";
        }

        return $"***{apiKey[^4..]}";
    }
}

