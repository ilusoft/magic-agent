using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace MagicAgent.Api.Application.AgentRunner;

public interface IAgentDefinitionValueResolver
{
    AgentDefinition Resolve(AgentDefinition definition);
}

internal sealed partial class AgentDefinitionConfigurationResolver(
    IConfiguration configuration,
    ILogger<AgentDefinitionConfigurationResolver> logger)
    : IAgentDefinitionValueResolver
{
    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);
    private static readonly Regex PlaceholderPatternRegex = PlaceholderPattern();
    private readonly IConfiguration _configuration = configuration ?? throw new ArgumentNullException(nameof(configuration));
    private readonly ILogger<AgentDefinitionConfigurationResolver> _logger = logger ?? throw new ArgumentNullException(nameof(logger));

    public AgentDefinition Resolve(AgentDefinition definition)
    {
        ArgumentNullException.ThrowIfNull(definition);

        var node = JsonSerializer.SerializeToNode(definition, SerializerOptions);
        if (node is null)
        {
            return definition;
        }

        var missingKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        ResolvePlaceholders(node, missingKeys);
        LogMissingConfigurationKeys(missingKeys);

        return node.Deserialize<AgentDefinition>(SerializerOptions) ?? definition;
    }

    private JsonNode? ResolvePlaceholders(JsonNode? node, ISet<string> missingKeys)
    {
        switch (node)
        {
            case null:
                return null;
            case JsonValue value when value.TryGetValue(out string? textValue) && textValue is not null:
                var resolved = ReplacePlaceholders(textValue, missingKeys);
                return ReferenceEquals(resolved, textValue)
                    ? value
                    : JsonValue.Create(resolved);
            case JsonObject obj:
                foreach (var property in obj.ToList())
                {
                    var resolvedProperty = ResolvePlaceholders(property.Value, missingKeys);
                    if (!ReferenceEquals(resolvedProperty, property.Value))
                    {
                        obj[property.Key] = resolvedProperty;
                    }
                }
                return obj;
            case JsonArray array:
                for (var i = 0; i < array.Count; i++)
                {
                    var current = array[i];
                    var resolvedItem = ResolvePlaceholders(current, missingKeys);
                    if (!ReferenceEquals(resolvedItem, current))
                    {
                        array[i] = resolvedItem;
                    }
                }
                return array;
            default:
                return node;
        }
    }

    private string ReplacePlaceholders(string value, ISet<string> missingKeys)
    {
        var replaced = PlaceholderPatternRegex.Replace(value, match =>
        {
            var key = match.Groups["key"].Value.Trim();
            if (string.IsNullOrEmpty(key))
            {
                return match.Value;
            }

            var resolved = _configuration[key];
            if (string.IsNullOrEmpty(resolved))
            {
                missingKeys.Add(key);
                return match.Value;
            }

            return resolved;
        });

        return replaced;
    }

    private void LogMissingConfigurationKeys(IEnumerable<string> keys)
    {
        foreach (var key in keys)
        {
            _logger.LogWarning("Configuration value for key '{Key}' was not found while resolving agent definitions.", key);
        }
    }

    [GeneratedRegex("\\{(?<key>[^{}]+)\\}", RegexOptions.CultureInvariant)]
    private static partial Regex PlaceholderPattern();
}
