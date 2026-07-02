using System.Text.Json;
using System.Text.Json.Serialization;
using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Application.Expressions;
using MagicAgent.Api.Controllers;
using MagicAgent.Api.Infrastructure.AgentRunner;
using Serilog;
using Serilog.Events;

Log.Logger = new LoggerConfiguration()
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .CreateBootstrapLogger();

var builder = WebApplication.CreateBuilder(args);

try
{
    Log.Information("Starting Bootstrapping!!");

    Log.Logger = BuildConfiguredLogger(builder.Configuration);

    builder.Logging.ClearProviders();
    builder.Logging.AddSerilog(Log.Logger, dispose: true);

    builder.Services
        .AddControllers(options =>
        {
            options.Filters.Add<AgentDefinitionsExceptionFilter>();
        })
        .AddJsonOptions(options =>
        {
            if (!options.JsonSerializerOptions.Converters.Any(converter => converter is JsonStringEnumConverter))
            {
                options.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
            }
        });

    builder.Services.AddHttpContextAccessor();

    builder.Services.AddCors(options =>
    {
        var allowedOrigins = builder.Configuration.GetValue<string>("AllowedOrigins", "");
        var origins = allowedOrigins
            .Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(o => !string.IsNullOrEmpty(o))
            .ToArray();

        if (origins.Length > 0)
        {
            options.AddDefaultPolicy(policy =>
            {
                policy.WithOrigins(origins)
                      .AllowAnyHeader()
                      .AllowAnyMethod();
            });
        }
        else
        {
            options.AddDefaultPolicy(policy =>
            {
                policy.AllowAnyOrigin()
                      .AllowAnyHeader()
                      .AllowAnyMethod();
            });
        }
    });

    builder.Services.Configure<AgentDefinitionsOptions>(builder.Configuration.GetSection("AgentDefinitions"));
    builder.Services.AddSingleton<IAgentDefinitionsProvider, FileAgentDefinitionsProvider>();
    builder.Services.AddSingleton<IAgentDefinitionValueResolver, AgentDefinitionConfigurationResolver>();
    builder.Services.AddSingleton<IAgentConversationStore, InMemoryAgentConversationStore>();
    builder.Services.AddSingleton<IAgentDiagnosticsStore, InMemoryAgentDiagnosticsStore>();
    builder.Services.AddSingleton<IAgentRunProgressSink, NoOpAgentRunProgressSink>();
    builder.Services.AddSingleton<IAgentRunner, DefaultAgentRunner>();

    builder.Services.AddSingleton<IChatClientFactory, AzureOpenAiChatClientFactory>();
    builder.Services.AddSingleton<IChatClientFactory, OpenAiCompatibleChatClientFactory>();
    builder.Services.AddSingleton<StepChatClientResolver>();

    builder.Services.AddWorkflowExpressionServices();

    var app = builder.Build();

    Log.Information("Starting Services!!");


    app.UseRouting();
    app.UseCors();
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

    if (Enum.TryParse<LogLevel>(configuredLevel, ignoreCase: true, out var microsoftLevel))
    {
        return microsoftLevel switch
        {
          LogLevel.Trace => LogEventLevel.Verbose,
            LogLevel.Debug => LogEventLevel.Debug,
            LogLevel.Information => LogEventLevel.Information,
            LogLevel.Warning => LogEventLevel.Warning,
            LogLevel.Error => LogEventLevel.Error,
            LogLevel.Critical => LogEventLevel.Fatal,
            LogLevel.None => LogEventLevel.Fatal,
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
