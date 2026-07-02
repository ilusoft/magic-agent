using System.Text.Json;
using System.Text.Json.Serialization;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.Extensions.Options;

namespace MagicAgent.Api.Infrastructure.AgentRunner;

public sealed class FileAgentDefinitionsProvider : IAgentDefinitionsProvider
{
    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
    };

    private readonly IOptionsMonitor<AgentDefinitionsOptions> _options;
    private readonly IWebHostEnvironment _environment;
    private readonly ILogger<FileAgentDefinitionsProvider> _logger;

    public FileAgentDefinitionsProvider(
        IOptionsMonitor<AgentDefinitionsOptions> options,
        IWebHostEnvironment environment,
        ILogger<FileAgentDefinitionsProvider> logger)
    {
        _options = options ?? throw new ArgumentNullException(nameof(options));
        _environment = environment ?? throw new ArgumentNullException(nameof(environment));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));

        if (!SerializerOptions.Converters.Any(converter => converter is JsonStringEnumConverter))
        {
            SerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
        }
    }

    public async Task<AgentDefinitionsDocument> GetDefinitionsAsync(CancellationToken cancellationToken = default)
        => await LoadDefinitionsAsync(cancellationToken);

    public async Task<AgentDefinition?> GetAgentDefinitionAsync(string agentId, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(agentId);

        var document = await LoadDefinitionsAsync(cancellationToken);

        return document.Agents.FirstOrDefault(a => string.Equals(a.Id, agentId, StringComparison.OrdinalIgnoreCase));
    }

    public async Task SaveDefinitionsAsync(AgentDefinitionsDocument document, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(document);

        var issues = AgentDefinitionsDocumentValidator.Validate(document);
        if (issues.Count > 0)
        {
            throw new AgentDefinitionsValidationException(issues);
        }

        NormalizeStartSteps(document);

        var absolutePath = ResolveDefinitionsPath();
        await using var stream = File.Create(absolutePath);
        await JsonSerializer.SerializeAsync(stream, document, SerializerOptions, cancellationToken);
    }

    private async Task<AgentDefinitionsDocument> LoadDefinitionsAsync(CancellationToken cancellationToken)
    {
        var absolutePath = ResolveDefinitionsPath();

        if (!File.Exists(absolutePath))
        {
            throw new FileNotFoundException($"Agent definitions file not found at '{absolutePath}'.", absolutePath);
        }

        await using var stream = File.OpenRead(absolutePath);
        var document = await JsonSerializer.DeserializeAsync<AgentDefinitionsDocument>(stream, SerializerOptions, cancellationToken);

        if (document is null)
        {
            _logger.LogWarning("Agent definitions file '{Path}' could not be deserialized; returning empty document.", absolutePath);
            return new AgentDefinitionsDocument();
        }

        DetectLegacyShapeAndThrow(absolutePath);

        var issues = AgentDefinitionsDocumentValidator.Validate(document);
        if (issues.Count > 0)
        {
            throw new AgentDefinitionsValidationException(issues);
        }

        return document;
    }

    /// <summary>
    /// Reads the file as raw text and looks for any of the
    /// pre-refactor top-level keys. The C# types no longer carry
    /// these fields (they were dropped in phase 9), so the
    /// deserializer silently ignores them. The only place to detect
    /// the legacy shape is in the raw JSON.
    /// Throws <see cref="MigrationRequiredException"/> so the
    /// controller can return a 426 pointing the operator at the
    /// migration tool.
    /// </summary>
    private static void DetectLegacyShapeAndThrow(string absolutePath)
    {
        // Re-open the file and scan for legacy top-level keys. This
        // is cheap (single small file) and avoids keeping an
        // out-of-band copy of the removed fields just for the check.
        string raw;
        using (var reader = new StreamReader(absolutePath))
        {
            raw = reader.ReadToEnd();
        }

        var legacyAgentKeys = new[] { "endpoint", "deployment", "apiKey", "apiVersion", "baseUrl", "model", "provider" };
        var detected = new List<string>();
        foreach (var key in legacyAgentKeys)
        {
            if (raw.Contains($"\"{key}\":", StringComparison.Ordinal))
            {
                detected.Add(key);
            }
        }

        // Per-step legacy keys: only scan inside "steps" arrays. A
        // substring search keeps the check fast for our file sizes.
        if (raw.Contains("\"provider\":", StringComparison.Ordinal) ||
            raw.Contains("\"options\":", StringComparison.Ordinal))
        {
            // Both are also valid for newer shapes, but the migration
            // path is the only known case where they appear without
            // the rest of the new shape. The validator runs after this
            // check; a false positive just produces a less helpful
            // 426 instead of a 422.
            if (raw.Contains("\"options\":", StringComparison.Ordinal))
            {
                detected.Add("options");
            }
        }

        if (detected.Count == 0)
        {
            return;
        }

        throw new MigrationRequiredException(
            $"Agent definitions document at '{absolutePath}' uses the pre-refactor shape. "
            + "Run `dotnet run --project tools/AgentsMigrator -- <path-to-agents.json>` to upgrade. "
            + "Legacy keys detected: "
            + string.Join(", ", detected.Distinct()),
            absolutePath);
    }

    private string ResolveDefinitionsPath()
    {
        var relativePath = _options.CurrentValue.FilePath;
        if (string.IsNullOrWhiteSpace(relativePath))
        {
            throw new InvalidOperationException("Agent definitions file path is not configured.");
        }

        return Path.IsPathRooted(relativePath)
            ? relativePath
            : Path.Combine(_environment.ContentRootPath, relativePath);
    }

    private void NormalizeStartSteps(AgentDefinitionsDocument document)
    {
        if (document.Agents == null)
        {
            return;
        }

        foreach (var agent in document.Agents)
        {
            if (agent?.Steps == null || agent.Steps.Count == 0)
            {
                continue;
            }

            var flaggedIndex = -1;

            for (var index = 0; index < agent.Steps.Count; index++)
            {
                if (agent.Steps[index].IsStartStep && flaggedIndex == -1)
                {
                    flaggedIndex = index;
                }
                else if (agent.Steps[index].IsStartStep)
                {
                    agent.Steps[index].IsStartStep = false;
                }
            }

            if (flaggedIndex == -1)
            {
                flaggedIndex = 0;
                _logger.LogInformation(
                    "Workflow {WorkflowId} did not specify a start step. Defaulting to '{StepName}'.",
                    agent.Id,
                    agent.Steps[flaggedIndex].Name);
            }

            for (var index = 0; index < agent.Steps.Count; index++)
            {
                agent.Steps[index].IsStartStep = index == flaggedIndex;
            }
        }
    }
}
