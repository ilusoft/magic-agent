using System.IO;
using System.Linq;
using System.Text.Json;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Logging;
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

        return document;
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
