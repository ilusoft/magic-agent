using System.Text.Json;
using System.Text.Json.Serialization;
using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Application.Expressions;
using MagicAgent.Api.Infrastructure.AgentRunner;
using Microsoft.Extensions.Logging;
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
using Serilog.Events;
using Serilog.Extensions.Logging;

Log.Logger = new LoggerConfiguration()
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .CreateBootstrapLogger();

var builder = WebApplication.CreateBuilder(args);

try
{
    Log.Information("Starting Bootstrapping!!");
    builder.Host.AddPrqxConfiguration(builderType: BuilderType.WebAppBff,
        sc =>
        {
            sc.AddPrqxOption<AzureAdSettings>();
            sc.AddPrqxOption<BffSettings>();
        });

    Log.Logger = BuildConfiguredLogger(builder.Configuration);

    builder.Logging.ClearProviders();
    builder.Logging.AddSerilog(Log.Logger, dispose: true);
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

    builder.Services.AddHttpContextAccessor();
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

    Log.Information("Starting Services!!");

    app.UsePrqxConfiguration();
    app.UsePrqxExceptionHandler();
    app.UsePrqxHealthChecks();
    app.UsePrqxSwagger();

    app.UseRouting();
    app.UseCors(CorsConstants.PolicyAdmin);
    app.UsePrqxAuthorization();
    app.MapControllers();

    Log.Information("App ready to run!!");

    app.Run();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Application failed to start.");
}
finally
{
    Log.CloseAndFlush();
}

static Serilog.ILogger BuildConfiguredLogger(IConfiguration configuration)
{
    var loggingSection = configuration.GetSection("Logging:LogLevel");
    var defaultLevel = ParseLogEventLevel(loggingSection["Default"], LogEventLevel.Information);

    var loggerConfig = new LoggerConfiguration()
        .MinimumLevel.Is(defaultLevel)
        .Enrich.FromLogContext()
        .WriteTo.Console();

    foreach (var child in loggingSection.GetChildren())
    {
        var category = child.Key;
        if (string.Equals(category, "Default", StringComparison.OrdinalIgnoreCase))
        {
            continue;
        }

        var level = ParseLogEventLevel(child.Value, defaultLevel);
        loggerConfig.MinimumLevel.Override(category, level);
    }

    return loggerConfig.CreateLogger();
}

static LogEventLevel ParseLogEventLevel(string? configuredLevel, LogEventLevel fallback)
{
    if (string.IsNullOrWhiteSpace(configuredLevel))
    {
        return fallback;
    }

    if (Enum.TryParse<Microsoft.Extensions.Logging.LogLevel>(configuredLevel, ignoreCase: true, out var microsoftLevel))
    {
        return microsoftLevel switch
        {
            Microsoft.Extensions.Logging.LogLevel.Trace => LogEventLevel.Verbose,
            Microsoft.Extensions.Logging.LogLevel.Debug => LogEventLevel.Debug,
            Microsoft.Extensions.Logging.LogLevel.Information => LogEventLevel.Information,
            Microsoft.Extensions.Logging.LogLevel.Warning => LogEventLevel.Warning,
            Microsoft.Extensions.Logging.LogLevel.Error => LogEventLevel.Error,
            Microsoft.Extensions.Logging.LogLevel.Critical => LogEventLevel.Fatal,
            Microsoft.Extensions.Logging.LogLevel.None => LogEventLevel.Fatal,
            _ => fallback
        };
    }

    if (Enum.TryParse<LogEventLevel>(configuredLevel, ignoreCase: true, out var serilogLevel))
    {
        return serilogLevel;
    }

    return fallback;
}

public partial class Program;
