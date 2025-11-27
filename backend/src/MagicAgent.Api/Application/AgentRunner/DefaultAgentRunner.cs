using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
using ChatMessage = Microsoft.Extensions.AI.ChatMessage;
using ChatRole = Microsoft.Extensions.AI.ChatRole;

namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Default implementation that instantiates Microsoft Agent Framework agents based on JSON configuration.
/// </summary>
public sealed class DefaultAgentRunner(
  IAgentDefinitionsProvider definitionsProvider,
  IAgentDefinitionValueResolver definitionValueResolver,
  IAgentConversationStore conversationStore,
  IAgentDiagnosticsStore diagnosticsStore,
  ILogger<DefaultAgentRunner> logger) : IAgentRunner
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
      definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));
    private readonly IAgentDefinitionValueResolver _definitionValueResolver =
      definitionValueResolver ?? throw new ArgumentNullException(nameof(definitionValueResolver));
    private readonly IAgentConversationStore _conversationStore =
      conversationStore ?? throw new ArgumentNullException(nameof(conversationStore));
    private readonly IAgentDiagnosticsStore _diagnosticsStore =
      diagnosticsStore ?? throw new ArgumentNullException(nameof(diagnosticsStore));
    private readonly ILogger<DefaultAgentRunner> _logger =
      logger ?? throw new ArgumentNullException(nameof(logger));
    private const int MaxWorkflowSteps = 100;
    private static readonly JsonSerializerOptions PassThroughSerializerOptions = new(JsonSerializerDefaults.Web);

    public async Task<AgentRunResult> RunAsync(AgentRunRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (string.IsNullOrWhiteSpace(request.AgentId))
        {
            throw new ArgumentException("AgentId must be provided.", nameof(request));
        }

        var definition = await _definitionsProvider.GetAgentDefinitionAsync(request.AgentId, cancellationToken);

        definition = _definitionValueResolver.Resolve(definition ?? throw new AgentNotFoundException(request.AgentId));

        var parameters = new Dictionary<string, string>(definition.DefaultParameters, StringComparer.OrdinalIgnoreCase);

        if (!string.IsNullOrWhiteSpace(definition.Endpoint))
        {
            parameters.TryAdd("endpoint", definition.Endpoint);
        }

        if (!string.IsNullOrWhiteSpace(definition.Deployment))
        {
            parameters.TryAdd("deployment", definition.Deployment);
        }

        if (!string.IsNullOrWhiteSpace(definition.ApiKey))
        {
            parameters.TryAdd("apiKey", definition.ApiKey);
        }

        if (!string.IsNullOrWhiteSpace(request.Input))
        {
            parameters["input"] = request.Input!;
        }

        var stepResults = new List<AgentStepExecutionResult>();
        var conversationId = request.ConversationId;
        JsonElement? sharedThreadState = null;
        var pendingInput = request.Input;

        var toolBuilder = new AgentToolBuilder(_logger);
        await using var toolContext = await toolBuilder.BuildAsync(definition, request.Headers, cancellationToken).ConfigureAwait(false);

        if (toolContext.InitializationErrors.Count > 0)
        {
            _logger.LogWarning("{Count} tool(s) failed to initialize for agent {AgentId}.", toolContext.InitializationErrors.Count, definition.Id);

            var fatalErrors = toolContext.InitializationErrors.Where(e => e.StopExecution).ToList();

            if (fatalErrors.Count > 0)
            {
                var errorSummary = string.Join(Environment.NewLine, fatalErrors.Select(e => $"[fatal-tool-init] {e.ToolName}: {e.Message}"));
                var failedResult = new AgentStepExecutionResult("tool-initialization", "diagnostic", errorSummary)
                {
                    ToolErrorDetected = true,
                    EndWorkflow = true,
                };

                stepResults.Add(failedResult);
                return new AgentRunResult(definition.Id, "failed", stepResults, conversationId, DateTimeOffset.UtcNow);
            }

            if (definition.Steps.Count == 0)
            {
                var failedResult = new AgentStepExecutionResult("tool-initialization", "diagnostic", "One or more tools failed to initialize.")
                {
                    ToolErrorDetected = true,
                };

                stepResults.Add(failedResult);
                return new AgentRunResult(definition.Id, "failed", stepResults, conversationId, DateTimeOffset.UtcNow);
            }
        }

        if (definition.Steps.Count == 0)
        {
            return new AgentRunResult(definition.Id, "completed", stepResults, conversationId, DateTimeOffset.UtcNow);
        }

        var stepLookup = definition.Steps.ToDictionary(s => s.Name, StringComparer.OrdinalIgnoreCase);
        var startStep = definition.Steps.FirstOrDefault(step => step.IsStartStep) ?? definition.Steps[0];
        var currentStepName = startStep.Name;
        var executedSteps = 0;

        while (!string.IsNullOrWhiteSpace(currentStepName))
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (executedSteps++ >= MaxWorkflowSteps)
            {
                _logger.LogWarning("Workflow for agent {AgentId} exceeded maximum step count of {MaxSteps}. Execution halted.", definition.Id, MaxWorkflowSteps);
                break;
            }

            if (!stepLookup.TryGetValue(currentStepName, out var stepDefinition))
            {
                _logger.LogWarning("Step '{StepName}' referenced in workflow for agent {AgentId} was not found. Execution halted.", currentStepName, definition.Id);
                break;
            }

            var stepInput = pendingInput;

            if (!string.IsNullOrWhiteSpace(stepInput))
            {
                parameters["input"] = stepInput!;
            }
            else
            {
                parameters.Remove("input");
            }

            IReadOnlyList<AITool> stepTools = toolContext.Tools;

            if (stepDefinition.Tools is { Count: > 0 })
            {
                var requestedToolIds = new HashSet<string>(stepDefinition.Tools, StringComparer.OrdinalIgnoreCase);
                var matchedTools = new List<AITool>(requestedToolIds.Count);

                foreach (var toolId in requestedToolIds)
                {
                    if (!toolContext.ToolsByDefinition.TryGetValue(toolId, out var toolsForDefinition))
                    {
                        continue;
                    }

                    matchedTools.AddRange(toolsForDefinition);
                }

                stepTools = matchedTools;
            }

            var (executionResult, updatedConversationId, updatedThreadState, stepThreadContext) = await ExecuteStepAsync(
              definition,
              stepDefinition,
              stepInput,
              parameters,
              conversationId,
              stepTools,
              sharedThreadState,
              cancellationToken).ConfigureAwait(false);

            conversationId = updatedConversationId;
            pendingInput = DetermineNextStepInput(stepDefinition, stepInput, executionResult.Output);
            sharedThreadState = updatedThreadState;

            var outcomeResolution = StepOutcomeResolver.ResolveNextStep(definition, stepLookup, stepDefinition, executionResult.Output, _logger);

            var enrichedResult = executionResult with
            {
                Input = stepInput,
                ThreadContext = stepThreadContext,
                Outcome = outcomeResolution.Outcome,
                NextStep = outcomeResolution.NextStep,
                EndWorkflow = outcomeResolution.EndWorkflow,
            };

            stepResults.Add(enrichedResult);

            if (outcomeResolution.EndWorkflow)
            {
                currentStepName = null;
            }
            else
            {
                currentStepName = outcomeResolution.NextStep;
            }
        }

        var runResult = new AgentRunResult(definition.Id, "completed", stepResults, conversationId, DateTimeOffset.UtcNow);

        if (!string.IsNullOrWhiteSpace(runResult.ConversationId))
        {
            await _diagnosticsStore.SaveRunAsync(runResult.ConversationId!, runResult, cancellationToken).ConfigureAwait(false);
        }

        return runResult;
    }

    private async Task<(AgentStepExecutionResult Result, string? ConversationId, JsonElement? ThreadState, JsonElement? StepThreadContext)> ExecuteStepAsync(
      AgentDefinition definition,
      AgentStepDefinition step,
      string? input,
      IDictionary<string, string> parameters,
      string? conversationId,
      IReadOnlyList<AITool> tools,
      JsonElement? threadState,
      CancellationToken cancellationToken)
    {
        if (step.Type.Equals("chat", StringComparison.OrdinalIgnoreCase))
        {
            return await ExecuteChatStepAsync(
              definition,
              step,
              input,
              parameters,
              conversationId,
              tools,
              threadState,
              cancellationToken);
        }

        if (step.Type.Equals("echo", StringComparison.OrdinalIgnoreCase))
        {
            var message = step.Parameters.TryGetValue("message", out var value) ? value : string.Empty;
            return (new AgentStepExecutionResult(step.Name, step.Type, message), conversationId, threadState, threadState);
        }

        var fallbackOutput = JsonSerializer.Serialize(step.Parameters);
        return (new AgentStepExecutionResult(step.Name, step.Type, fallbackOutput), conversationId, threadState, threadState);
    }

    private async Task<(AgentStepExecutionResult Result, string? ConversationId, JsonElement? ThreadState, JsonElement? StepThreadContext)> ExecuteChatStepAsync(
      AgentDefinition definition,
      AgentStepDefinition step,
      string? input,
      IDictionary<string, string> parameters,
      string? conversationId,
      IReadOnlyList<AITool> tools,
      JsonElement? threadState,
      CancellationToken cancellationToken)
    {
        var instructions = step.Parameters.TryGetValue("systemPrompt", out var systemPrompt) ?
          systemPrompt :
          definition.Description ?? "You are a helpful assistant.";

        var userMessage = input;
        if (string.IsNullOrWhiteSpace(userMessage) && step.Parameters.TryGetValue("message", out var fallbackMessage))
        {
            userMessage = fallbackMessage;
        }

        if (string.IsNullOrWhiteSpace(userMessage))
        {
            throw new InvalidOperationException("Chat agent requires an input message.");
        }

        var conversationContext = await ConversationContext.CreateAsync(
          _conversationStore,
          step,
          conversationId,
          cancellationToken).ConfigureAwait(false);

        var previousMessages = conversationContext.PreviousMessages;
        var activeConversationId = conversationContext.ConversationId ?? conversationId;

        AgentMessage? userTranscriptMessage = null;

        try
        {
            var agent = ChatAgentFactory.CreateChatAgent(definition, step, parameters, tools);
            AgentThread agentThread;

            if (threadState.HasValue)
            {
                agentThread = agent.DeserializeThread(threadState.Value);
            }
            else
            {
                agentThread = agent.GetNewThread();
            }
            var requestMessages = BuildChatMessages(instructions, userMessage, previousMessages);

            if (!string.IsNullOrWhiteSpace(instructions) && (!conversationContext.Enabled || previousMessages.Count == 0))
            {
            }

            userTranscriptMessage = new AgentMessage("user", userMessage, DateTimeOffset.UtcNow);

            var runResponse = await agent.RunAsync(requestMessages, agentThread, options: null, cancellationToken: cancellationToken);

            var toolAnalysis = ToolInvocationUtilities.Analyze(runResponse);


            JsonElement? serializedThread = null;

            if (toolAnalysis.HasErrors)
            {

                serializedThread = agentThread.Serialize();

                if (step.StopOnToolError)
                {
                    return (ToolInvocationUtilities.CreateErrorResult(step, toolAnalysis), activeConversationId, serializedThread, threadState);
                }
            }

            var output = !string.IsNullOrWhiteSpace(runResponse.Text) ?
              runResponse.Text!
              :
              runResponse.Messages?.LastOrDefault(m => m.Role == ChatRole.Assistant)?.Text ?? string.Empty;


            await conversationContext.SaveMessagesAsync(
              [userTranscriptMessage, new AgentMessage("assistant", output, DateTimeOffset.UtcNow)],
              cancellationToken).ConfigureAwait(false);

            var stepResult = new AgentStepExecutionResult(step.Name, step.Type, output)
            {
                ToolInvocations = toolAnalysis.ToolCalls,
                ToolErrorDetected = toolAnalysis.HasErrors,
            };

            serializedThread ??= agentThread.Serialize();

            return (stepResult, conversationContext.ConversationId ?? conversationId, serializedThread, threadState);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Agent Framework execution failed for agent {AgentId} step {StepName}.", definition.Id, step.Name);

            var fallback = $"[agent-framework-fallback] {userMessage}";
            var fallbackAssistantMessage = new AgentMessage("assistant", fallback, DateTimeOffset.UtcNow);

            var userMessageForStore = userTranscriptMessage ?? new AgentMessage("user", userMessage, DateTimeOffset.UtcNow);

            await conversationContext.SaveMessagesAsync(
              [userMessageForStore, fallbackAssistantMessage],
              cancellationToken).ConfigureAwait(false);

            return (new AgentStepExecutionResult(step.Name, step.Type, fallback), conversationContext.ConversationId ?? conversationId, threadState, threadState);
        }
    }
    private static List<ChatMessage> BuildChatMessages(string? instructions, string userMessage, IEnumerable<AgentMessage>? previousMessages)
    {
        var messages = new List<ChatMessage>();

        if (!string.IsNullOrWhiteSpace(instructions))
        {
            messages.Add(new ChatMessage(ChatRole.System, instructions));
        }

        if (previousMessages is not null)
        {
            foreach (var message in previousMessages)
            {
                messages.Add(ConvertToChatMessage(message));
            }
        }

        messages.Add(new ChatMessage(ChatRole.User, userMessage));

        return messages;
    }

    private static ChatMessage ConvertToChatMessage(AgentMessage message)
    {
        var role = message.Role.ToLowerInvariant() switch
        {
            "system" => ChatRole.System,
            "assistant" => ChatRole.Assistant,
            _ => ChatRole.User,
        };

        return new ChatMessage(role, message.Content);
    }

    private static string? DetermineNextStepInput(AgentStepDefinition step, string? stepInput, string? stepOutput)
    {
        if (string.IsNullOrWhiteSpace(step?.InputSource) || string.Equals(step.InputSource, "usePrevious", StringComparison.OrdinalIgnoreCase))
        {
            return stepOutput;
        }

        if (string.Equals(step.InputSource, "passThrough", StringComparison.OrdinalIgnoreCase))
        {
            if (stepInput is null && stepOutput is null)
            {
                return null;
            }

            var payload = new PassThroughPayload(stepInput, stepOutput);
            return JsonSerializer.Serialize(payload, PassThroughSerializerOptions);
        }

        return stepOutput;
    }

    private sealed record PassThroughPayload(string? Input, string? Output);

}