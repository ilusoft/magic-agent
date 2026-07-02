using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;

namespace MagicAgent.Api.Tests;

public class OpenAiCompatibleChatClientFactoryTests
{
    [Fact]
    public void Missing_BaseUrl_Throws()
    {
        var factory = new OpenAiCompatibleChatClientFactory();
        var profile = new AgentLlmProfileDefinition
        {
            Provider = "openai-compatible",
            Model = "Qwen-35B",
            ApiKey = "key",
        };

        var act = () => factory.Create(profile);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*baseUrl*");
    }

    [Fact]
    public void Missing_Model_Throws()
    {
        var factory = new OpenAiCompatibleChatClientFactory();
        var profile = new AgentLlmProfileDefinition
        {
            Provider = "openai-compatible",
            BaseUrl = "http://localhost:8000/v1",
            ApiKey = "key",
        };

        var act = () => factory.Create(profile);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*model*");
    }

    [Fact]
    public void Missing_ApiKey_Throws()
    {
        var factory = new OpenAiCompatibleChatClientFactory();
        var profile = new AgentLlmProfileDefinition
        {
            Provider = "openai-compatible",
            BaseUrl = "http://localhost:8000/v1",
            Model = "Qwen-35B",
        };

        var act = () => factory.Create(profile);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*apiKey*");
    }

    [Fact]
    public void Provider_Is_OpenAi_Compatible()
    {
        new OpenAiCompatibleChatClientFactory().Provider.Should().Be("openai-compatible");
    }
}
