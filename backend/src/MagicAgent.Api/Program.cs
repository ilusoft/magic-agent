using System.Text.Json;
using System.Text.Json.Serialization;
using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Application.Expressions;
using MagicAgent.Api.Infrastructure.AgentRunner;
using PRQXCommon.Core.Authentication;
using PRQXCommon.Core.Authorization;
using PRQXCommon.Core.Bff;
using PRQXCommon.Core.Configuration;
using PRQXCommon.Core.Cors;
using PRQXCommon.Core.Enums;
using PRQXCommon.Core.HealthCheck;
using PRQXCommon.Core.Logging;
using PRQXCommon.Core.Swagger;
using PRQXCommon.Core.Versioning;
using Serilog;

var builder = WebApplication.CreateBuilder(args);
Log.Debug("Starting Bootstrapping!!");
builder.Host.AddPrqxConfiguration(builderType: BuilderType.WebAppBff,
    sc =>
    {
        sc.AddPrqxOption<AzureAdSettings>();
        sc.AddPrqxOption<BffSettings>();
    });

builder.Host.AddPrqxLogging(BuilderType.WebAppBff);
builder.Services.AddPrqxHealthChecks();
builder.Services.AddPrqxApiVersioning();
builder.Services.AddPrqxSwagger("Magic Agent API");
builder.Services.AddPrqxCors();

builder.Services
    .AddControllers()
    .AddJsonOptions(options =>
    {
        if (!options.JsonSerializerOptions.Converters.Any(converter => converter is JsonStringEnumConverter))
        {
            options.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
        }
    });

builder.Services.AddPrqxAuthentication();
builder.Services.AddPrqxAuthorization(BuilderType.WebAppBff);

builder.Services.Configure<AgentDefinitionsOptions>(builder.Configuration.GetSection("AgentDefinitions"));
builder.Services.AddSingleton<IAgentDefinitionsProvider, FileAgentDefinitionsProvider>();
builder.Services.AddSingleton<IAgentDefinitionValueResolver, AgentDefinitionConfigurationResolver>();
builder.Services.AddSingleton<IAgentConversationStore, InMemoryAgentConversationStore>();
builder.Services.AddSingleton<IAgentDiagnosticsStore, InMemoryAgentDiagnosticsStore>();
builder.Services.AddSingleton<IAgentRunProgressSink, NoOpAgentRunProgressSink>();
builder.Services.AddSingleton<IAgentRunner, DefaultAgentRunner>();
builder.Services.AddWorkflowExpressionServices();

var app = builder.Build();

Log.Debug("Starting Services!!");

app.UsePrqxConfiguration();
app.UsePrqxExceptionHandler();
app.UsePrqxHealthChecks();
app.UsePrqxSwagger();

app.UseRouting();
app.UseCors(CorsConstants.PolicyAdmin);
app.UsePrqxAuthorization();
app.MapControllers();

Log.Debug("App ready to run!!");

app.Run();

public partial class Program;
