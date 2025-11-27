using Microsoft.Extensions.AI;
using ModelContextProtocol.Client;

namespace MagicAgent.Api.Application.AgentRunner;

internal sealed class AgentToolBuilder
{
    private readonly ILogger _logger;

    internal AgentToolBuilder(ILogger logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    internal async Task<AgentToolContext> BuildAsync(
        AgentDefinition definition,
        IReadOnlyDictionary<string, string>? requestHeaders,
        CancellationToken cancellationToken)
    {
        if (definition.Tools is null || definition.Tools.Count == 0)
        {
            return AgentToolContext.Empty;
        }

        var tools = new List<AITool>(definition.Tools.Count);
        var disposables = new List<IAsyncDisposable>(definition.Tools.Count);
        var toolInitializationErrors = new List<ToolInitializationError>();
        var toolsByDefinition = new Dictionary<string, IReadOnlyList<AITool>>(StringComparer.OrdinalIgnoreCase);

        foreach (var toolDefinition in definition.Tools)
        {
            if (toolDefinition is null)
            {
                continue;
            }

            if (toolDefinition.Type.Equals("mcp", StringComparison.OrdinalIgnoreCase) ||
                toolDefinition.Type.Equals("mcp-http", StringComparison.OrdinalIgnoreCase))
            {
                try
                {
                    var (mcpTools, mcpDisposables) = await BuildMcpToolsAsync(
                        definition,
                        toolDefinition,
                        requestHeaders,
                        cancellationToken).ConfigureAwait(false);

                    tools.AddRange(mcpTools);
                    disposables.AddRange(mcpDisposables);
                    toolsByDefinition[toolDefinition.Id] = mcpTools;
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to initialize MCP tool {ToolId} for agent {AgentId}.", toolDefinition.Id, definition.Id);
                    toolInitializationErrors.Add(new ToolInitializationError(
                        toolDefinition.Id,
                        toolDefinition.Name ?? toolDefinition.Id,
                        ex.Message,
                        toolDefinition.StopOnToolInitError));
                }
            }
            else
            {
                _logger.LogWarning("Unsupported tool type '{ToolType}' for agent {AgentId}.", toolDefinition.Type, definition.Id);
            }
        }

        return new AgentToolContext(tools, disposables, toolInitializationErrors, toolsByDefinition);
    }

    private async Task<(IReadOnlyList<AITool> Tools, IReadOnlyList<IAsyncDisposable> Disposables)> BuildMcpToolsAsync(
        AgentDefinition definition,
        AgentToolDefinition toolDefinition,
        IReadOnlyDictionary<string, string>? requestHeaders,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(toolDefinition.ServerUrl))
        {
            throw new InvalidOperationException($"Tool '{toolDefinition.Id}' for agent '{definition.Id}' is missing 'serverUrl'.");
        }

        var options = new HttpClientTransportOptions
        {
            Endpoint = new Uri(toolDefinition.ServerUrl, UriKind.Absolute),
            TransportMode = ParseTransportMode(toolDefinition.Protocol)
        };

        var mergedHeaders = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        if (toolDefinition.Headers is { Count: > 0 })
        {
            foreach (var kvp in toolDefinition.Headers)
            {
                mergedHeaders[kvp.Key] = kvp.Value;
            }
        }

        if (toolDefinition.ForwardAuthorizationHeader && requestHeaders is not null)
        {
            var headerName = string.IsNullOrWhiteSpace(toolDefinition.AuthorizationHeaderName)
                ? "Authorization"
                : toolDefinition.AuthorizationHeaderName;

            if (requestHeaders.TryGetValue(headerName, out var authValue) && !string.IsNullOrWhiteSpace(authValue))
            {
                mergedHeaders[headerName] = authValue;
            }
        }

        if (mergedHeaders.Count > 0)
        {
            options.AdditionalHeaders = mergedHeaders;
        }

        var transport = new HttpClientTransport(options);
        var mcpClient = await McpClient.CreateAsync(transport, cancellationToken: cancellationToken).ConfigureAwait(false);

        var allTools = await mcpClient.ListToolsAsync(cancellationToken: cancellationToken).ConfigureAwait(false);
        var toolsToExpose = new List<McpClientTool>(allTools);

        if (toolDefinition.AllowedTools is { Count: > 0 })
        {
            var allowed = new HashSet<string>(toolDefinition.AllowedTools, StringComparer.OrdinalIgnoreCase);
            toolsToExpose = [.. toolsToExpose.Where(t => allowed.Contains(t.Name))];

            var missingTools = allowed.Except(toolsToExpose.Select(t => t.Name), StringComparer.OrdinalIgnoreCase);
            foreach (var missing in missingTools)
            {
                _logger.LogWarning(
                    "Tool '{MissingTool}' requested in allowedTools for MCP tool {ToolId} on agent {AgentId} was not found on the server.",
                    missing,
                    toolDefinition.Id,
                    definition.Id);
            }
        }

        var toolLookup = new Dictionary<string, McpClientTool>(StringComparer.OrdinalIgnoreCase);
        foreach (var tool in toolsToExpose)
        {
            toolLookup[tool.Name] = tool;
        }

        var exposedTools = new List<AITool>(toolLookup.Count);

        if (toolDefinition.Actions is { Count: > 0 })
        {
            foreach (var action in toolDefinition.Actions)
            {
                if (action is null)
                {
                    continue;
                }

                var sourceToolName = action.Parameters.TryGetValue("tool", out var mappedName) ? mappedName : action.Name;

                if (!toolLookup.TryGetValue(sourceToolName, out var sourceTool))
                {
                    _logger.LogWarning(
                        "Action '{ActionName}' for MCP tool {ToolId} on agent {AgentId} references unknown tool '{SourceTool}'.",
                        action.Name,
                        toolDefinition.Id,
                        definition.Id,
                        sourceToolName);
                    continue;
                }

                var customized = sourceTool;

                if (!string.IsNullOrWhiteSpace(action.Name) &&
                    !string.Equals(action.Name, sourceTool.Name, StringComparison.OrdinalIgnoreCase))
                {
                    customized = customized.WithName(action.Name);
                }

                if (!string.IsNullOrWhiteSpace(action.Description))
                {
                    customized = customized.WithDescription(action.Description);
                }

                exposedTools.Add((AITool)customized);
            }
        }
        else
        {
            foreach (var tool in toolsToExpose)
            {
                exposedTools.Add((AITool)tool);
            }
        }

        if (exposedTools.Count == 0)
        {
            _logger.LogWarning("No tools were exposed for MCP server {ToolId} on agent {AgentId}.", toolDefinition.Id, definition.Id);
        }

        return (exposedTools, new List<IAsyncDisposable> { transport, mcpClient });
    }

    private static HttpTransportMode ParseTransportMode(string? protocol) => protocol?.Trim().ToLowerInvariant() switch
    {
        "http" or "streamable-http" => HttpTransportMode.StreamableHttp,
        "sse" => HttpTransportMode.Sse,
        _ => HttpTransportMode.AutoDetect,
    };
}

internal sealed class AgentToolContext : IAsyncDisposable
{
    internal static AgentToolContext Empty { get; } = new([], [],[],
        new Dictionary<string, IReadOnlyList<AITool>>(StringComparer.OrdinalIgnoreCase));

    internal AgentToolContext(
        IReadOnlyList<AITool> tools,
        IReadOnlyList<IAsyncDisposable> disposables,
        IReadOnlyList<ToolInitializationError> initializationErrors,
        IReadOnlyDictionary<string, IReadOnlyList<AITool>> toolsByDefinition)
    {
        Tools = tools;
        _disposables = disposables;
        InitializationErrors = initializationErrors;
        ToolsByDefinition = toolsByDefinition;
    }

    private readonly IReadOnlyList<IAsyncDisposable> _disposables;

    internal IReadOnlyList<AITool> Tools { get; }

    internal IReadOnlyDictionary<string, IReadOnlyList<AITool>> ToolsByDefinition { get; }

    internal IReadOnlyList<ToolInitializationError> InitializationErrors { get; }

    public ValueTask DisposeAsync()
    {
        return _disposables.Count == 0 ? ValueTask.CompletedTask : new ValueTask(DisposeInternalAsync());
    }

    private async Task DisposeInternalAsync()
    {
        foreach (var disposable in _disposables)
        {
            try
            {
                await disposable.DisposeAsync().ConfigureAwait(false);
            }
            catch
            {
            }
        }
    }
}
