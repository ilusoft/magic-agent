using System.Collections.Generic;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.Extensions.Logging.Abstractions;

namespace MagicAgent.Api.Tests;

public class AgentToolBuilderTests
{
    [Fact]
    public async Task Collects_Tool_Ids_Across_All_Steps_Deduplicated()
    {
        var document = new AgentDefinitionsDocument
        {
            Tools = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["tavily-mcp"] = new AgentToolDefinition
                {
                    Id = "tavily-mcp",
                    Type = "unsupported-type",
                    ServerUrl = "https://example.com",
                },
            },
        };

        var workflow = new AgentDefinition
        {
            Id = "test-workflow",
            Steps = new List<AgentStepDefinition>
            {
                new() { Name = "step1", Type = "agent", Tools = new List<string> { "tavily-mcp" } },
                new() { Name = "step2", Type = "agent", Tools = new List<string> { "tavily-mcp" } },
                new() { Name = "step3", Type = "agent", Tools = new List<string>() },
            },
        };

        var builder = new AgentToolBuilder(NullLogger.Instance);
        var toolContext = await builder.BuildAsync(document, workflow, null, CancellationToken.None);

        toolContext.InitializationErrors.Should().BeEmpty();
        toolContext.Tools.Should().BeEmpty();
    }

    [Fact]
    public async Task Skips_Steps_With_Unknown_Tool_Ids()
    {
        var document = new AgentDefinitionsDocument
        {
            Tools = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase),
        };

        var workflow = new AgentDefinition
        {
            Id = "test-workflow",
            Steps = new List<AgentStepDefinition>
            {
                new() { Name = "step1", Type = "agent", Tools = new List<string> { "ghost-tool" } },
            },
        };

        var builder = new AgentToolBuilder(NullLogger.Instance);
        var toolContext = await builder.BuildAsync(document, workflow, null, CancellationToken.None);

        toolContext.InitializationErrors.Should().BeEmpty();
        toolContext.Tools.Should().BeEmpty();
    }

    [Fact]
    public async Task Returns_Empty_Context_When_No_Steps_Reference_Any_Tool()
    {
        var document = new AgentDefinitionsDocument
        {
            Tools = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["tavily-mcp"] = new AgentToolDefinition
                {
                    Id = "tavily-mcp",
                    Type = "mcp",
                    ServerUrl = "https://example.com",
                },
            },
        };

        var workflow = new AgentDefinition
        {
            Id = "test-workflow",
            Steps = new List<AgentStepDefinition>
            {
                new() { Name = "step1", Type = "agent", Tools = new List<string>() },
                new() { Name = "step2", Type = "agent", Tools = null! },
            },
        };

        var builder = new AgentToolBuilder(NullLogger.Instance);
        var toolContext = await builder.BuildAsync(document, workflow, null, CancellationToken.None);

        toolContext.InitializationErrors.Should().BeEmpty();
        toolContext.Tools.Should().BeEmpty();
    }

    [Fact]
    public async Task Skips_Unsupported_Tool_Types_Without_Throwing()
    {
        var document = new AgentDefinitionsDocument
        {
            Tools = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["http-tool"] = new AgentToolDefinition
                {
                    Id = "http-tool",
                    Type = "http",
                    ServerUrl = "https://example.com",
                },
            },
        };

        var workflow = new AgentDefinition
        {
            Id = "test-workflow",
            Steps = new List<AgentStepDefinition>
            {
                new() { Name = "step1", Type = "agent", Tools = new List<string> { "http-tool" } },
            },
        };

        var builder = new AgentToolBuilder(NullLogger.Instance);
        var toolContext = await builder.BuildAsync(document, workflow, null, CancellationToken.None);

        toolContext.InitializationErrors.Should().BeEmpty();
        toolContext.Tools.Should().BeEmpty();
    }
}
