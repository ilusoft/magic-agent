using System.Text.Json;
using System.Text.Json.Serialization;
using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Application.Expressions;
using MagicAgent.Api.Infrastructure.AgentRunner;
using PRQXCommon.Core;
using PRQXCommon.Core.Authentication;
using PRQXCommon.Core.Authorization;
using PRQXCommon.Core.Configuration;
using PRQXCommon.Core.Cors;
using PRQXCommon.Core.Enums;

var builder = WebApplication.CreateBuilder(args);

builder.Host.AddPrqxConfiguration(builderType: BuilderType.WebAppBackend,
    sc =>
    {
        sc.AddPrqxOption<AzureAdSettings>();
    });

builder.Services
    .AddControllers()
    .AddJsonOptions(options =>
    {
        if (!options.JsonSerializerOptions.Converters.Any(converter => converter is JsonStringEnumConverter))
        {
            options.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
        }
    });
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHealthChecks();
builder.Services.AddPrqxCors();
builder.Services.AddPrqxAuthentication();
builder.Services.AddPrqxAuthorization(BuilderType.WebAppBackend);

builder.Services.Configure<AgentDefinitionsOptions>(builder.Configuration.GetSection("AgentDefinitions"));
builder.Services.AddSingleton<IAgentDefinitionsProvider, FileAgentDefinitionsProvider>();
builder.Services.AddSingleton<IAgentDefinitionValueResolver, AgentDefinitionConfigurationResolver>();
builder.Services.AddSingleton<IAgentConversationStore, InMemoryAgentConversationStore>();
builder.Services.AddSingleton<IAgentDiagnosticsStore, InMemoryAgentDiagnosticsStore>();
builder.Services.AddSingleton<IAgentRunProgressSink, NoOpAgentRunProgressSink>();
builder.Services.AddSingleton<IAgentRunner, DefaultAgentRunner>();
builder.Services.AddWorkflowExpressionServices();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseCors(CorsConstants.PolicyBackend);

app.MapHealthChecks("/health");
app.MapControllers();

app.Run();

public partial class Program;
