using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace MagicAgent.Tools.AgentsMigrator;

/// <summary>
/// One-shot migration tool that converts the pre-refactor
/// <c>agents.json</c> shape (per-agent <c>endpoint</c>/<c>deployment</c>/
/// <c>apiKey</c>/<c>apiVersion</c> + per-step <c>provider</c>/<c>options</c>)
/// into the new top-level shape with reusable LLM profiles and a
/// global tool pool.
///
/// Run with:
///
/// <code>dotnet run --project tools/AgentsMigrator -- configs/agents/agents.json</code>
///
/// Use <c>--dry-run</c> to print a diff without writing. The tool is
/// idempotent: running it on an already-migrated document is a no-op.
/// </summary>
public static class Program
{
    public static int Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("Usage: dotnet run --project tools/AgentsMigrator -- <path-to-agents.json> [--dry-run]");
            return 2;
        }

        var path = args[0];
        var dryRun = args.Length >= 2 && args[1] == "--dry-run";

        if (!File.Exists(path))
        {
            Console.Error.WriteLine($"File not found: {path}");
            return 2;
        }

        var originalJson = File.ReadAllText(path);
        var originalNode = JsonNode.Parse(originalJson, new JsonNodeOptions { PropertyNameCaseInsensitive = true })
            ?? throw new InvalidOperationException("Failed to parse agents.json");

        if (IsAlreadyMigrated(originalNode))
        {
            Console.WriteLine("[ok] document is already migrated (top-level llmProfiles/tools present)");
            return 0;
        }

        var (migratedNode, summary) = Migrate(originalNode);

        var originalSerialized = originalNode.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
        var migratedSerialized = migratedNode.ToJsonString(new JsonSerializerOptions { WriteIndented = true });

        if (dryRun)
        {
            Console.WriteLine("=== DRY RUN — no files were written ===");
            Console.WriteLine();
            PrintSummary(summary);
            Console.WriteLine();
            Console.WriteLine("New document:");
            Console.WriteLine(migratedSerialized);
            return 0;
        }

        if (originalSerialized == migratedSerialized)
        {
            Console.WriteLine("[ok] no changes needed");
            return 0;
        }

        File.Copy(path, path + ".bak", overwrite: true);
        File.WriteAllText(path, migratedSerialized, new UTF8Encoding(false));

        Console.WriteLine($"[ok] wrote {path}");
        Console.WriteLine($"[ok] backup at {path}.bak");
        PrintSummary(summary);
        return 0;
    }

    private static bool IsAlreadyMigrated(JsonNode node)
    {
        if (node is not JsonObject obj)
        {
            return false;
        }

        return obj.ContainsKey("llmProfiles") || obj.ContainsKey("tools");
    }

    private static (JsonNode Migrated, MigrationSummary Summary) Migrate(JsonNode original)
    {
        if (original is not JsonObject rootObj)
        {
            throw new InvalidOperationException("Expected a JSON object at the root.");
        }

        var agents = rootObj["agents"]?.AsArray()
            ?? throw new InvalidOperationException("Expected an 'agents' array.");

        var profiles = new Dictionary<string, JsonObject>(StringComparer.OrdinalIgnoreCase);
        var tools = new Dictionary<string, JsonObject>(StringComparer.OrdinalIgnoreCase);
        var profileIdByAgent = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var toolIdsByAgent = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        var summary = new MigrationSummary();

        foreach (var agentNode in agents)
        {
            if (agentNode is not JsonObject agent)
            {
                continue;
            }

            var agentId = agent["id"]?.GetValue<string>()
                ?? throw new InvalidOperationException("Agent is missing 'id'.");

            var profileId = ResolveProfileIdForAgent(agent, profiles, summary);
            profileIdByAgent[agentId] = profileId;

            var toolIds = new List<string>();
            if (agent["tools"] is JsonArray agentTools)
            {
                foreach (var toolNode in agentTools)
                {
                    if (toolNode is not JsonObject toolObj)
                    {
                        continue;
                    }

                    var toolId = toolObj["id"]?.GetValue<string>();
                    if (string.IsNullOrWhiteSpace(toolId))
                    {
                        continue;
                    }

                    if (!tools.ContainsKey(toolId))
                    {
                        tools[toolId] = NormalizeToolJson(toolObj);
                        summary.AddedTools.Add(toolId);
                    }

                    toolIds.Add(toolId);
                }
            }

            toolIdsByAgent[agentId] = toolIds;
        }

        foreach (var agentNode in agents)
        {
            if (agentNode is not JsonObject agent)
            {
                continue;
            }

            var agentId = agent["id"]?.GetValue<string>()
                ?? throw new InvalidOperationException("Agent is missing 'id'.");
            var profileId = profileIdByAgent[agentId];

            agent.Remove("endpoint");
            agent.Remove("deployment");
            agent.Remove("apiKey");
            agent.Remove("apiVersion");
            agent.Remove("baseUrl");
            agent.Remove("model");
            agent.Remove("provider");
            agent.Remove("tools");
            agent.Remove("llm");
            agent.Remove("systemPrompt");
            summary.LegacyKeysRemoved += 9;

            // LLM-related keys lifted out of defaultParameters.
            if (agent["defaultParameters"] is JsonObject defaultParams)
            {
                foreach (var key in LlmKeysToLift)
                {
                    if (defaultParams.ContainsKey(key))
                    {
                        defaultParams.Remove(key);
                        summary.LegacyKeysRemoved++;
                    }
                }

                if (defaultParams.Count == 0)
                {
                    agent.Remove("defaultParameters");
                }
            }

            // Rename ViewLayout -> viewLayout to match the C# [JsonPropertyName].
            if (agent["ViewLayout"] is JsonObject viewLayout)
            {
                var viewLayoutJson = viewLayout.ToJsonString();
                agent.Remove("ViewLayout");
                agent["viewLayout"] = JsonNode.Parse(viewLayoutJson) as JsonObject;
            }

            // Per-step cleanup.
            if (agent["steps"] is JsonArray steps)
            {
                foreach (var stepNode in steps)
                {
                    if (stepNode is not JsonObject step)
                    {
                        continue;
                    }

                    step.Remove("provider");
                    step.Remove("options");

                    if (step["type"]?.GetValue<string>() == "agent")
                    {
                        step["llmConfig"] = new JsonObject
                        {
                            ["profileId"] = profileId,
                        };
                    }
                }
            }
        }

        var newRoot = new JsonObject
        {
            ["llmProfiles"] = new JsonObject(),
            ["tools"] = new JsonObject(),
        };

        foreach (var (_, profileJson) in profiles)
        {
            var profileId = (string)profileJson["_profileId"]!;
            var cleanProfile = (JsonObject)profileJson.DeepClone();
            cleanProfile.Remove("_profileId");
            ((JsonObject)newRoot["llmProfiles"]!)[profileId] = cleanProfile;
        }

        foreach (var (id, toolJson) in tools)
        {
            ((JsonObject)newRoot["tools"]!)[id] = toolJson;
        }

        // Build the new agents array by cloning each modified agent
        // (they were edited in place above; cloning avoids the
        // "node already has a parent" error when adding them to a
        // new container).
        var newAgents = new JsonArray();
        foreach (var agentNode in agents)
        {
            newAgents.Add(agentNode.DeepClone());
        }
        newRoot["agents"] = newAgents;

        return (newRoot, summary);
    }

    private static readonly string[] LlmKeysToLift = new[]
    {
        "apiKey", "api_key", "endpoint", "deployment", "model", "baseUrl", "base_url",
        "apiVersion", "api_version", "temperature", "maxTokens", "max_tokens",
    };

    private static string ResolveProfileIdForAgent(
        JsonObject agent,
        Dictionary<string, JsonObject> profiles,
        MigrationSummary summary)
    {
        var profileJson = ExtractLlmProfileJson(agent);

        if (profileJson is null)
        {
            throw new InvalidOperationException(
                $"Agent '{agent["id"]?.GetValue<string>()}' has no LLM config to migrate.");
        }

        var canonical = CanonicalizeProfile(profileJson);
        var fingerprint = HashProfile(canonical);

        if (profiles.TryGetValue(fingerprint, out var existing))
        {
            return (string)existing["_profileId"]!;
        }

        var agentId = agent["id"]?.GetValue<string>() ?? "agent";
        var baseId = agentId + "-default";
        var profileId = baseId;
        var suffix = 2;
        while (profiles.Values.Any(p => (string?)p["_profileId"] == profileId))
        {
            profileId = $"{baseId}-{suffix++}";
        }

        var profile = new JsonObject
        {
            ["_profileId"] = profileId,
        };
        foreach (var kvp in canonical)
        {
            profile[kvp.Key] = kvp.Value?.DeepClone();
        }

        profiles[fingerprint] = profile;
        summary.AddedProfiles.Add((profileId, profile["provider"]?.GetValue<string>()));
        return profileId;
    }

    private static JsonObject? ExtractLlmProfileJson(JsonObject agent)
    {
        var profile = new JsonObject();

        // Top-level fields on the agent.
        string[] scalarKeys = { "provider", "endpoint", "deployment", "apiKey", "apiVersion", "baseUrl", "model" };
        foreach (var key in scalarKeys)
        {
            if (agent[key] is JsonValue value)
            {
                profile[key] = value.DeepClone();
            }
        }

        // Legacy "llm" sub-block.
        if (agent["llm"] is JsonObject legacyLlm)
        {
            foreach (var kvp in legacyLlm)
            {
                profile[kvp.Key] = kvp.Value?.DeepClone();
            }
        }

        // LLM-related keys lifted from defaultParameters.
        if (agent["defaultParameters"] is JsonObject defaultParams)
        {
            foreach (var key in LlmKeysToLift)
            {
                if (defaultParams[key] is JsonValue value && !profile.ContainsKey(key))
                {
                    profile[key] = value.DeepClone();
                }
            }
        }

        if (profile.Count == 0)
        {
            return null;
        }

        // Infer the provider from the available fields when it wasn't
        // declared explicitly. ``baseUrl`` is the openai-compatible
        // signal; ``endpoint`` is the Azure signal.
        if (!profile.ContainsKey("provider") || profile["provider"] is JsonValue v && v.GetValue<string>() is null)
        {
            if (profile.ContainsKey("baseUrl"))
            {
                profile["provider"] = "openai-compatible";
            }
            else
            {
                profile["provider"] = "azure-openai";
            }
        }

        return profile;
    }

    private static SortedDictionary<string, JsonNode?> CanonicalizeProfile(JsonObject profile)
    {
        var result = new SortedDictionary<string, JsonNode?>(StringComparer.Ordinal);
        string[] orderedKeys = { "provider", "endpoint", "deployment", "apiVersion", "baseUrl", "model", "apiKey", "headers", "temperature", "maxTokens" };
        foreach (var key in orderedKeys)
        {
            var value = profile[key];
            if (value is null || value is JsonValue jsonValue && jsonValue.GetValue<object>() is null)
            {
                continue;
            }
            result[key] = value;
        }
        return result;
    }

    private static string HashProfile(SortedDictionary<string, JsonNode?> profile)
    {
        var sb = new StringBuilder();
        foreach (var kvp in profile)
        {
            sb.Append(kvp.Key);
            sb.Append('=');
            sb.Append(kvp.Value?.ToJsonString());
            sb.Append(';');
        }

        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(sb.ToString()));
        return Convert.ToHexString(bytes);
    }

    private static JsonObject NormalizeToolJson(JsonObject tool)
    {
        var clone = (JsonObject)tool.DeepClone();
        if (clone["type"] is JsonValue && string.Equals(clone["type"]?.GetValue<string>(), "mcp-http", StringComparison.OrdinalIgnoreCase))
        {
            clone["type"] = "mcp";
        }
        return clone;
    }

    private static void PrintSummary(MigrationSummary summary)
    {
        if (summary.AddedProfiles.Count > 0)
        {
            Console.WriteLine("[ok] added profiles:");
            foreach (var (id, provider) in summary.AddedProfiles)
            {
                Console.WriteLine($"     - {id} (provider={provider ?? "<unknown>"})");
            }
        }

        if (summary.AddedTools.Count > 0)
        {
            Console.WriteLine("[ok] added tools:");
            foreach (var id in summary.AddedTools)
            {
                Console.WriteLine($"     - {id}");
            }
        }

        Console.WriteLine($"[ok] dropped {summary.LegacyKeysRemoved} legacy key(s) from agent definitions");
        Console.WriteLine("[ok] dropped per-step provider/options and rewired each agent step to its profile");
    }

    private sealed class MigrationSummary
    {
        public List<(string Id, string? Provider)> AddedProfiles { get; } = new();
        public List<string> AddedTools { get; } = new();
        public int LegacyKeysRemoved { get; set; }
    }
}
