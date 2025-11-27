using System.Net;
using System.Net.Http.Json;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Mvc.Testing;

namespace MagicAgent.Api.Tests;

public class ApiIntegrationTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ApiIntegrationTests(WebApplicationFactory<Program> factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task Health_Get_ReturnsOkStatus()
    {
        var response = await _client.GetAsync("/api/health");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact]
    public async Task AgentRun_Post_ReturnsAgentFrameworkFallback()
    {
        var response = await _client.PostAsJsonAsync("/api/agents/chat-agent/runs", new { input = "hello there" });

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var runResult = await response.Content.ReadFromJsonAsync<AgentRunResult>();

        runResult.Should().NotBeNull();
        runResult!.AgentId.Should().Be("chat-agent");
        runResult.Status.Should().Be("completed");
        runResult.Steps.Should().ContainSingle()
            .Which.Output.Should().Contain("[agent-framework-fallback]");

        runResult.CompletedAt.Should().NotBe(default);
    }

    [Fact]
    public async Task AgentRun_Post_WithUnknownAgent_ReturnsNotFound()
    {
        var response = await _client.PostAsJsonAsync("/api/agents/missing/runs", new { input = "ping" });

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
    }
}
