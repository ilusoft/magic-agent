using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;

namespace MagicAgent.Api.Tests;

public class AzureOpenAiChatClientFactoryTests
{
    [Fact]
    public void Missing_Endpoint_Throws()
    {
        var factory = new AzureOpenAiChatClientFactory();
        var profile = new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Deployment = "gpt-5-mini",
            ApiKey = "key",
        };

        var act = () => factory.Create(profile);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*endpoint*");
    }

    [Fact]
    public void Missing_Deployment_Throws()
    {
        var factory = new AzureOpenAiChatClientFactory();
        var profile = new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Endpoint = "https://test.openai.azure.com/",
            ApiKey = "key",
        };

        var act = () => factory.Create(profile);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*deployment*");
    }

    [Fact]
    public void Missing_ApiKey_Throws()
    {
        var factory = new AzureOpenAiChatClientFactory();
        var profile = new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Endpoint = "https://test.openai.azure.com/",
            Deployment = "gpt-5-mini",
        };

        var act = () => factory.Create(profile);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*apiKey*");
    }

    [Fact]
    public void Provider_Is_Azure_OpenAi()
    {
        new AzureOpenAiChatClientFactory().Provider.Should().Be("azure-openai");
    }
}
