using System.Collections.Generic;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.Extensions.DependencyInjection;

namespace MagicAgent.Api.Tests;

public class AgentDefinitionsCascadeDeleteTests : IClassFixture<TestApiFactory>
{
    private readonly TestApiFactory _factory;

    public AgentDefinitionsCascadeDeleteTests(TestApiFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task PutTools_Removing_Referenced_Tool_Returns_409_With_Referencing_Steps()
    {
        // Seed: a tool that IS referenced by a step.
        var referencedToolId = "tavily-mcp";
        var unreferencedToolId = "ghost-tool";

        var document = BuildDocumentWithReferencedTool(
            referencedToolId,
            unreferencedToolId,
            referencingAgentId: "translator",
            referencingStepName: "search",
            stepType: "agent");

        _factory.TestProvider.SetDocument(document);

        using var client = _factory.CreateClient();
        var newTools = new Dictionary<string, AgentToolDefinition>
        {
            // Only the unreferenced tool survives.
            [unreferencedToolId] = new AgentToolDefinition
            {
                Id = unreferencedToolId,
                Type = "unsupported",
                ServerUrl = "https://example.com",
            },
        };

        var response = await client.PutAsJsonAsync("/api/agent-definitions/tools", newTools);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);

        var payload = await response.Content.ReadFromJsonAsync<JsonElement>();
        payload.GetProperty("message").GetString().Should().Contain(referencedToolId);
        var referencingSteps = payload.GetProperty("referencingSteps");
        referencingSteps.GetArrayLength().Should().Be(1);
        referencingSteps[0].GetProperty("agentId").GetString().Should().Be("translator");
        referencingSteps[0].GetProperty("stepName").GetString().Should().Be("search");
    }

    [Fact]
    public async Task PutLlmProfiles_Removing_Referenced_Profile_Returns_409_With_Referencing_Steps()
    {
        var referencedProfileId = "azure-gpt5";

        var document = BuildDocumentWithReferencedProfile(
            referencedProfileId,
            referencingAgentId: "translator",
            referencingStepName: "chat");

        _factory.TestProvider.SetDocument(document);

        using var client = _factory.CreateClient();
        var newProfiles = new Dictionary<string, AgentLlmProfileDefinition>
        {
            ["other-profile"] = new AgentLlmProfileDefinition
            {
                Provider = "azure-openai",
                Endpoint = "https://other.openai.azure.com/",
                Deployment = "other-deployment",
                ApiKey = "other-key-1234",
            },
        };

        var response = await client.PutAsJsonAsync("/api/agent-definitions/llm-profiles", newProfiles);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);

        var payload = await response.Content.ReadFromJsonAsync<JsonElement>();
        payload.GetProperty("message").GetString().Should().Contain(referencedProfileId);
        var referencingSteps = payload.GetProperty("referencingSteps");
        referencingSteps.GetArrayLength().Should().Be(1);
        referencingSteps[0].GetProperty("agentId").GetString().Should().Be("translator");
        referencingSteps[0].GetProperty("stepName").GetString().Should().Be("chat");
    }

    [Fact]
    public async Task PutTools_Removing_Unreferenced_Tool_Succeeds()
    {
        var referencedToolId = "tavily-mcp";
        var unreferencedToolId = "ghost-tool";

        var document = BuildDocumentWithReferencedTool(
            referencedToolId,
            unreferencedToolId,
            referencingAgentId: "translator",
            referencingStepName: "search",
            stepType: "agent");

        _factory.TestProvider.SetDocument(document);

        using var client = _factory.CreateClient();
        var newTools = new Dictionary<string, AgentToolDefinition>
        {
            // Keep the referenced tool; drop the unreferenced one.
            [referencedToolId] = new AgentToolDefinition
            {
                Id = referencedToolId,
                Type = "unsupported",
                ServerUrl = "https://example.com",
            },
        };

        var response = await client.PutAsJsonAsync("/api/agent-definitions/tools", newTools);

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);

        // Verify the server-side state actually changed.
        var getResponse = await client.GetAsync("/api/agent-definitions/tools");
        getResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        var current = await getResponse.Content.ReadFromJsonAsync<JsonElement>();
        current.EnumerateObject().Select(p => p.Name).Should().BeEquivalentTo(new[] { referencedToolId });
    }

    [Fact]
    public async Task PutLlmProfiles_Removing_Unreferenced_Profile_Succeeds()
    {
        var referencedProfileId = "azure-gpt5";
        var unreferencedProfileId = "stale-profile";

        var document = new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                [referencedProfileId] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://test.openai.azure.com/",
                    Deployment = "gpt-5-mini",
                    ApiKey = "key-1234",
                },
                [unreferencedProfileId] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://stale.openai.azure.com/",
                    Deployment = "stale",
                    ApiKey = "stale-key-1234",
                },
            },
            Agents = new List<AgentDefinition>
            {
                new()
                {
                    Id = "translator",
                    Steps = new List<AgentStepDefinition>
                    {
                        new()
                        {
                            Name = "chat",
                            Type = "agent",
                            LlmConfig = new AgentStepLlmConfig { ProfileId = referencedProfileId },
                        },
                    },
                },
            },
        };

        _factory.TestProvider.SetDocument(document);

        using var client = _factory.CreateClient();
        var newProfiles = new Dictionary<string, AgentLlmProfileDefinition>
        {
            [referencedProfileId] = document.LlmProfiles[referencedProfileId],
        };

        var response = await client.PutAsJsonAsync("/api/agent-definitions/llm-profiles", newProfiles);

        response.StatusCode.Should().Be(HttpStatusCode.NoContent);
    }

    [Fact]
    public async Task PutLlmProfiles_With_Invalid_Profile_Returns_422()
    {
        var document = new AgentDefinitionsDocument();
        _factory.TestProvider.SetDocument(document);

        using var client = _factory.CreateClient();
        var newProfiles = new Dictionary<string, AgentLlmProfileDefinition>
        {
            ["broken"] = new AgentLlmProfileDefinition
            {
                Provider = "azure-openai",
                // Missing endpoint, deployment, apiKey.
            },
        };

        var response = await client.PutAsJsonAsync("/api/agent-definitions/llm-profiles", newProfiles);

        response.StatusCode.Should().Be(HttpStatusCode.UnprocessableEntity);
        var payload = await response.Content.ReadFromJsonAsync<JsonElement>();
        var issues = payload.GetProperty("issues");
        issues.GetArrayLength().Should().BeGreaterThan(0);
    }

    private static AgentDefinitionsDocument BuildDocumentWithReferencedTool(
        string referencedToolId,
        string unreferencedToolId,
        string referencingAgentId,
        string referencingStepName,
        string stepType)
    {
        return new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["test-azure"] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://test.openai.azure.com/",
                    Deployment = "test-deployment",
                    ApiKey = "test-api-key-12345678",
                },
            },
            Tools = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                [referencedToolId] = new AgentToolDefinition
                {
                    Id = referencedToolId,
                    Type = "unsupported",
                    ServerUrl = "https://example.com",
                },
                [unreferencedToolId] = new AgentToolDefinition
                {
                    Id = unreferencedToolId,
                    Type = "unsupported",
                    ServerUrl = "https://example.com",
                },
            },
            Agents = new List<AgentDefinition>
            {
                new()
                {
                    Id = referencingAgentId,
                    Steps = new List<AgentStepDefinition>
                    {
                        new()
                        {
                            Name = referencingStepName,
                            Type = stepType,
                            Tools = new List<string> { referencedToolId },
                        },
                    },
                },
            },
        };
    }

    private static AgentDefinitionsDocument BuildDocumentWithReferencedProfile(
        string referencedProfileId,
        string referencingAgentId,
        string referencingStepName)
    {
        return new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                [referencedProfileId] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://test.openai.azure.com/",
                    Deployment = "test-deployment",
                    ApiKey = "test-api-key-12345678",
                },
            },
            Agents = new List<AgentDefinition>
            {
                new()
                {
                    Id = referencingAgentId,
                    Steps = new List<AgentStepDefinition>
                    {
                        new()
                        {
                            Name = referencingStepName,
                            Type = "agent",
                            LlmConfig = new AgentStepLlmConfig { ProfileId = referencedProfileId },
                        },
                    },
                },
            },
        };
    }
}
