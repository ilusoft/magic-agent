using System.Collections.Generic;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;

namespace MagicAgent.Api.Tests;

public class StepChatClientResolverTests
{
    [Fact]
    public void Resolves_ProfileId_To_Azure_Factory_And_Emits_LLMCallConfig()
    {
        var document = new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["azure-gpt5"] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://test.openai.azure.com/",
                    Deployment = "gpt-5-mini",
                    ApiVersion = "2024-12-01-preview",
                    ApiKey = "test-api-key-12345678",
                    Temperature = 0.3,
                },
            },
        };

        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
            LlmConfig = new AgentStepLlmConfig { ProfileId = "azure-gpt5" },
        };

        var resolver = new StepChatClientResolver(new IChatClientFactory[]
        {
            new AzureOpenAiChatClientFactory(),
            new OpenAiCompatibleChatClientFactory(),
        });

        var (client, callConfig) = resolver.Resolve(document, workflow, step);

        client.Should().NotBeNull();
        callConfig.Provider.Should().Be("azure-openai");
        callConfig.Endpoint.Should().Be("https://test.openai.azure.com/");
        callConfig.Deployment.Should().Be("gpt-5-mini");
        callConfig.ApiVersion.Should().Be("2024-12-01-preview");
        callConfig.Model.Should().BeNull();
        callConfig.BaseUrl.Should().BeNull();
        callConfig.Temperature.Should().Be(0.3);
        callConfig.MaxTokens.Should().BeNull();
        callConfig.ApiKeyFingerprint.Should().Be("***5678");
    }

    [Fact]
    public void Resolves_ProfileId_To_OpenAiCompatible_Factory()
    {
        var document = new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["qwen-local"] = new AgentLlmProfileDefinition
                {
                    Provider = "openai-compatible",
                    BaseUrl = "http://127.0.0.1:8000/v1",
                    Model = "Qwen-35B",
                    ApiKey = "qwen-key-1234",
                },
            },
        };

        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
            LlmConfig = new AgentStepLlmConfig { ProfileId = "qwen-local" },
        };

        var resolver = new StepChatClientResolver(new IChatClientFactory[]
        {
            new AzureOpenAiChatClientFactory(),
            new OpenAiCompatibleChatClientFactory(),
        });

        var (client, callConfig) = resolver.Resolve(document, workflow, step);

        client.Should().NotBeNull();
        callConfig.Provider.Should().Be("openai-compatible");
        callConfig.BaseUrl.Should().Be("http://127.0.0.1:8000/v1");
        callConfig.Model.Should().Be("Qwen-35B");
        callConfig.Endpoint.Should().BeNull();
        callConfig.Deployment.Should().BeNull();
        callConfig.ApiKeyFingerprint.Should().Be("***1234");
    }

    [Fact]
    public void Inline_Overrides_Override_Profile_Fields()
    {
        var document = new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["azure-gpt5"] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://test.openai.azure.com/",
                    Deployment = "gpt-5-mini",
                    ApiKey = "profile-key-1234",
                    Temperature = 0.7,
                },
            },
        };

        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
            LlmConfig = new AgentStepLlmConfig
            {
                ProfileId = "azure-gpt5",
                Temperature = 0.2,
                Deployment = "gpt-5-mini-override",
            },
        };

        var resolver = new StepChatClientResolver(new IChatClientFactory[]
        {
            new AzureOpenAiChatClientFactory(),
        });

        var (_, callConfig) = resolver.Resolve(document, workflow, step);

        callConfig.Deployment.Should().Be("gpt-5-mini-override");
        callConfig.Temperature.Should().Be(0.2);
        callConfig.Endpoint.Should().Be("https://test.openai.azure.com/");
        callConfig.ApiKeyFingerprint.Should().Be("***1234");
    }

    [Fact]
    public void Missing_ProfileId_Throws_LlmProfileNotFoundException()
    {
        var document = new AgentDefinitionsDocument();
        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
            LlmConfig = new AgentStepLlmConfig { ProfileId = "does-not-exist" },
        };

        var resolver = new StepChatClientResolver(new IChatClientFactory[]
        {
            new AzureOpenAiChatClientFactory(),
        });

        var act = () => resolver.Resolve(document, workflow, step);

        act.Should().Throw<LlmProfileNotFoundException>()
            .Where(ex => ex.ProfileId == "does-not-exist" && ex.StepName == "chat");
    }

    [Fact]
    public void Env_Var_Fallback_When_No_LlmConfig_And_No_Profiles()
    {
        var document = new AgentDefinitionsDocument();
        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
        };

        var originalEndpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT");
        var originalDeployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT");
        var originalApiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_APIKEY");

        try
        {
            Environment.SetEnvironmentVariable("AZURE_OPENAI_ENDPOINT", "https://env-var.openai.azure.com/");
            Environment.SetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT", "env-var-deployment");
            Environment.SetEnvironmentVariable("AZURE_OPENAI_APIKEY", "env-var-key-12345678");

            var resolver = new StepChatClientResolver(new IChatClientFactory[]
            {
                new AzureOpenAiChatClientFactory(),
                new OpenAiCompatibleChatClientFactory(),
            });

            var (client, callConfig) = resolver.Resolve(document, workflow, step);

            client.Should().NotBeNull();
            callConfig.Provider.Should().Be("azure-openai");
            callConfig.Endpoint.Should().Be("https://env-var.openai.azure.com/");
            callConfig.Deployment.Should().Be("env-var-deployment");
            callConfig.ApiKeyFingerprint.Should().Be("***5678");
        }
        finally
        {
            Environment.SetEnvironmentVariable("AZURE_OPENAI_ENDPOINT", originalEndpoint);
            Environment.SetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT", originalDeployment);
            Environment.SetEnvironmentVariable("AZURE_OPENAI_APIKEY", originalApiKey);
        }
    }

    [Fact]
    public void Unknown_Provider_Throws_With_Helpful_Message()
    {
        var document = new AgentDefinitionsDocument();
        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
            LlmConfig = new AgentStepLlmConfig
            {
                Provider = "some-future-provider",
                Endpoint = "https://example.com",
            },
        };

        var resolver = new StepChatClientResolver(new IChatClientFactory[]
        {
            new AzureOpenAiChatClientFactory(),
            new OpenAiCompatibleChatClientFactory(),
        });

        var act = () => resolver.Resolve(document, workflow, step);

        act.Should().Throw<InvalidOperationException>()
            .WithMessage("*some-future-provider*");
    }

    [Fact]
    public void Resolver_Is_Case_Insensitive_For_Provider_Names()
    {
        var document = new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["Qwen-Local"] = new AgentLlmProfileDefinition
                {
                    Provider = "OPENAI-COMPATIBLE",
                    BaseUrl = "http://127.0.0.1:8000/v1",
                    Model = "Qwen-35B",
                    ApiKey = "key-1234",
                },
            },
        };

        var workflow = new AgentDefinition { Id = "test-workflow" };
        var step = new AgentStepDefinition
        {
            Name = "chat",
            Type = "agent",
            LlmConfig = new AgentStepLlmConfig { ProfileId = "QWEN-LOCAL" },
        };

        var resolver = new StepChatClientResolver(new IChatClientFactory[]
        {
            new AzureOpenAiChatClientFactory(),
            new OpenAiCompatibleChatClientFactory(),
        });

        var (_, callConfig) = resolver.Resolve(document, workflow, step);

        callConfig.Provider.Should().Be("openai-compatible");
    }
}

public class LLMCallConfigFingerprintTests
{
    [Theory]
    [InlineData(null, null)]
    [InlineData("", null)]
    [InlineData("abc", "***abc")]
    [InlineData("abcd", "***abcd")]
    [InlineData("abcdefgh", "***efgh")]
    [InlineData("a-very-long-api-key-12345678", "***5678")]
    public void Fingerprint_Strips_To_Last4(string? input, string? expected)
    {
        LLMCallConfig.FingerprintApiKey(input).Should().Be(expected);
    }
}
