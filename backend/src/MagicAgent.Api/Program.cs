using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Infrastructure.AgentRunner;

var builder = WebApplication.CreateBuilder(args);

const string FrontendCorsPolicy = "FrontendCorsPolicy";

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddHealthChecks();
builder.Services.AddCors(options =>
{
    options.AddPolicy(FrontendCorsPolicy, policy =>
    {
        policy.WithOrigins(
                "http://localhost:5173",
                "https://localhost:7169")
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});

builder.Services.Configure<AgentDefinitionsOptions>(builder.Configuration.GetSection("AgentDefinitions"));
builder.Services.AddSingleton<IAgentDefinitionsProvider, FileAgentDefinitionsProvider>();
builder.Services.AddSingleton<IAgentDefinitionValueResolver, AgentDefinitionConfigurationResolver>();
builder.Services.AddSingleton<IAgentConversationStore, InMemoryAgentConversationStore>();
builder.Services.AddSingleton<IAgentDiagnosticsStore, InMemoryAgentDiagnosticsStore>();
builder.Services.AddSingleton<IAgentRunner, DefaultAgentRunner>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();

app.UseCors(FrontendCorsPolicy);

app.MapHealthChecks("/health");
app.MapControllers();

app.Run();

public partial class Program;
