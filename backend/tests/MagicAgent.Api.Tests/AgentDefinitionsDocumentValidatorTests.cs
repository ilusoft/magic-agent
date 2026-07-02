using System.Collections.Generic;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;

namespace MagicAgent.Api.Tests;

public class AgentDefinitionsDocumentValidatorTests
{
    [Fact]
    public void Accepts_Well_Formed_Document()
    {
        var document = BuildValidDocument();

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().BeEmpty();
    }

    [Fact]
    public void Rejects_Step_Referencing_Missing_Profile()
    {
        var document = BuildValidDocument();
        document.Agents[0].Steps[0] = ReplaceStep(document.Agents[0].Steps[0], llmConfig: new AgentStepLlmConfig { ProfileId = "does-not-exist" });

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i =>
            i.Path == "agents[translator].steps[chat].llmConfig.profileId" &&
            i.Message.Contains("does-not-exist"));
    }

    [Fact]
    public void Rejects_Step_Referencing_Missing_Tool()
    {
        var document = BuildValidDocument();
        document.Agents[0].Steps[0] = ReplaceStep(document.Agents[0].Steps[0], tools: new List<string> { "nonexistent-tool" });

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i =>
            i.Path == "agents[translator].steps[chat].tools[0]" &&
            i.Message.Contains("nonexistent-tool"));
    }

    [Fact]
    public void Rejects_Azure_Profile_Missing_Endpoint()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Deployment = "gpt-5-mini",
            ApiKey = "key",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i =>
            i.Path == "llmProfiles[azure-gpt5].endpoint" &&
            i.Message.Contains("endpoint"));
    }

    [Fact]
    public void Rejects_Azure_Profile_Missing_Deployment()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Endpoint = "https://test.openai.azure.com/",
            ApiKey = "key",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i =>
            i.Path == "llmProfiles[azure-gpt5].deployment" &&
            i.Message.Contains("deployment"));
    }

    [Fact]
    public void Rejects_OpenAiCompatible_Profile_Missing_BaseUrl()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "openai-compatible",
            Model = "Qwen-35B",
            ApiKey = "key",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i => i.Path == "llmProfiles[azure-gpt5].baseUrl");
    }

    [Fact]
    public void Rejects_OpenAiCompatible_Profile_Missing_Model()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "openai-compatible",
            BaseUrl = "http://localhost:8000/v1",
            ApiKey = "key",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i => i.Path == "llmProfiles[azure-gpt5].model");
    }

    [Fact]
    public void Rejects_Profile_With_Empty_ApiKey()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "azure-openai",
            Endpoint = "https://test.openai.azure.com/",
            Deployment = "gpt-5-mini",
            ApiKey = "",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i => i.Path == "llmProfiles[azure-gpt5].apiKey");
    }

    [Fact]
    public void Rejects_Unknown_Provider()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "some-future-provider",
            Endpoint = "https://test.openai.azure.com/",
            Deployment = "gpt-5-mini",
            ApiKey = "key",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i =>
            i.Path == "llmProfiles[azure-gpt5].provider" &&
            i.Message.Contains("some-future-provider"));
    }

    [Fact]
    public void Rejects_Profile_With_Empty_Provider()
    {
        var document = BuildValidDocument();
        document.LlmProfiles["azure-gpt5"] = new AgentLlmProfileDefinition
        {
            Provider = "",
            Endpoint = "https://test.openai.azure.com/",
            Deployment = "gpt-5-mini",
            ApiKey = "key",
        };

        var issues = AgentDefinitionsDocumentValidator.Validate(document);

        issues.Should().Contain(i => i.Path == "llmProfiles[azure-gpt5].provider");
    }

    private static AgentDefinitionsDocument BuildValidDocument()
    {
        return new AgentDefinitionsDocument
        {
            LlmProfiles = new Dictionary<string, AgentLlmProfileDefinition>(StringComparer.OrdinalIgnoreCase)
            {
                ["azure-gpt5"] = new AgentLlmProfileDefinition
                {
                    Provider = "azure-openai",
                    Endpoint = "https://test.openai.azure.com/",
                    Deployment = "gpt-5-mini",
                    ApiKey = "test-key-1234",
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
                            LlmConfig = new AgentStepLlmConfig { ProfileId = "azure-gpt5" },
                        },
                    },
                },
            },
        };
    }

    private static AgentStepDefinition ReplaceStep(
        AgentStepDefinition original,
        AgentStepLlmConfig? llmConfig = null,
        IList<string>? tools = null)
    {
        return new AgentStepDefinition
        {
            Name = original.Name,
            Type = original.Type,
            Parameters = original.Parameters,
            VariableTypes = original.VariableTypes,
            LlmConfig = llmConfig ?? original.LlmConfig,
            Conversation = original.Conversation,
            Tools = tools ?? original.Tools,
            StopOnToolError = original.StopOnToolError,
            InputSource = original.InputSource,
            Outcomes = original.Outcomes,
            IsStartStep = original.IsStartStep,
        };
    }
}
