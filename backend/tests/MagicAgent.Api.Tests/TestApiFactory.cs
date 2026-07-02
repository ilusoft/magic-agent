using System.Collections.Generic;
using MagicAgent.Api.Application.AgentRunner;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;

namespace MagicAgent.Api.Tests;

public sealed class TestApiFactory : WebApplicationFactory<Program>
{
    public TestApiFactory()
    {
        TestProvider = new TestAgentDefinitionsProvider();
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureTestServices(services =>
        {
            services.RemoveAll<IAgentDefinitionsProvider>();
            services.RemoveAll<IAgentDefinitionValueResolver>();

            services.AddSingleton<IAgentDefinitionsProvider>(_ => TestProvider);
            services.AddSingleton<IAgentDefinitionValueResolver, PassthroughAgentDefinitionValueResolver>();
        });
    }

    /// <summary>
    /// Exposed so cascade-delete integration tests can seed the
    /// document with a referenced tool or profile before exercising
    /// the per-section PUT endpoints.
    /// </summary>
    public TestAgentDefinitionsProvider TestProvider { get; }

    public sealed class TestAgentDefinitionsProvider : IAgentDefinitionsProvider
    {
        private static readonly AgentDefinition TestAgentDefinition = new()
        {
            Id = "chat-agent",
            Name = "Test Chat Agent",
            Description = "Integration test agent",
            DefaultParameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["model"] = "test-model",
            },
            Steps = new List<AgentStepDefinition>
            {
                new()
                {
                    Name = "fallback-echo",
                    Type = "echo",
                    Parameters = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
                    {
                        ["message"] = "[agent-framework-fallback] {{input}}",
                    },
                    VariableTypes = new Dictionary<string, WorkflowVariableDataType>(StringComparer.OrdinalIgnoreCase),
                    Outcomes = new List<AgentStepOutcomeDefinition>
                    {
                        new()
                        {
                            Name = "complete",
                            NextStep = null,
                            Condition = null,
                            EndWorkflow = true,
                            Order = 1,
                        },
                    },
                    IsStartStep = true,
                },
            },
        };

        private AgentDefinitionsDocument _document = new()
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
            Tools = new Dictionary<string, AgentToolDefinition>(StringComparer.OrdinalIgnoreCase),
            Agents = new List<AgentDefinition> { TestAgentDefinition },
        };

        /// <summary>
        /// Replace the current document. Used by the cascade-delete
        /// integration tests to seed a document with a referenced
        /// tool or profile before exercising the PUT endpoints.
        /// </summary>
        public void SetDocument(AgentDefinitionsDocument document) => _document = document;

        public Task<AgentDefinitionsDocument> GetDefinitionsAsync(CancellationToken cancellationToken = default)
            => Task.FromResult(_document);

        public Task<AgentDefinition?> GetAgentDefinitionAsync(string agentId, CancellationToken cancellationToken = default)
        {
            var definition = string.Equals(agentId, TestAgentDefinition.Id, StringComparison.OrdinalIgnoreCase)
                ? TestAgentDefinition
                : null;

            return Task.FromResult(definition);
        }

        public Task SaveDefinitionsAsync(AgentDefinitionsDocument document, CancellationToken cancellationToken = default)
        {
            _document = document;
            return Task.CompletedTask;
        }
    }

    private sealed class PassthroughAgentDefinitionValueResolver : IAgentDefinitionValueResolver
    {
        public AgentDefinition Resolve(AgentDefinition definition) => definition;
    }
}
