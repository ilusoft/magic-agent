using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using MagicAgent.Api.Application.Expressions;
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
  IAgentRunProgressSink progressSink,
  ILogger<DefaultAgentRunner> logger,
  IWorkflowExpressionEvaluator expressionEvaluator,
  StepChatClientResolver chatClientResolver) : IAgentRunner
{
    private readonly IAgentDefinitionsProvider _definitionsProvider =
      definitionsProvider ?? throw new ArgumentNullException(nameof(definitionsProvider));
    private readonly IAgentDefinitionValueResolver _definitionValueResolver =
      definitionValueResolver ?? throw new ArgumentNullException(nameof(definitionValueResolver));
    private readonly IAgentConversationStore _conversationStore =
      conversationStore ?? throw new ArgumentNullException(nameof(conversationStore));
    private readonly IAgentDiagnosticsStore _diagnosticsStore =
      diagnosticsStore ?? throw new ArgumentNullException(nameof(diagnosticsStore));
    private readonly IAgentRunProgressSink _progressSink =
      progressSink ?? throw new ArgumentNullException(nameof(progressSink));
    private readonly ILogger<DefaultAgentRunner> _logger =
      logger ?? throw new ArgumentNullException(nameof(logger));
    private readonly IWorkflowExpressionEvaluator _expressionEvaluator =
      expressionEvaluator ?? throw new ArgumentNullException(nameof(expressionEvaluator));
    private readonly StepChatClientResolver _chatClientResolver =
      chatClientResolver ?? throw new ArgumentNullException(nameof(chatClientResolver));
    private const int MaxWorkflowSteps = 100;
    private static readonly JsonSerializerOptions PassThroughSerializerOptions = new(JsonSerializerDefaults.Web);

    public async Task<AgentRunResult> RunAsync(AgentRunRequest request, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(request);

        if (string.IsNullOrWhiteSpace(request.AgentId))
        {
            throw new ArgumentException("AgentId must be provided.", nameof(request));
        }

        var progressSink = request.ProgressSink ?? _progressSink;

        var document = await _definitionsProvider.GetDefinitionsAsync(cancellationToken);
        var definition = document.Agents.FirstOrDefault(a => string.Equals(a.Id, request.AgentId, StringComparison.OrdinalIgnoreCase))
            ?? throw new AgentNotFoundException(request.AgentId);

        definition = _definitionValueResolver.Resolve(definition);

        var parameters = new Dictionary<string, string>(definition.DefaultParameters, StringComparer.OrdinalIgnoreCase);

        if (!string.IsNullOrWhiteSpace(request.Input))
        {
            parameters["input"] = request.Input!;
        }

        var stepResults = new List<AgentStepExecutionResult>();
        var conversationId = request.ConversationId;
        JsonElement? sharedThreadState = null;
        var pendingInput = request.Input;
        var lastStepOutput = pendingInput;
        var workflowVariables = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var workflowVariableStates = new Dictionary<string, WorkflowVariableState>(StringComparer.OrdinalIgnoreCase);

        var toolBuilder = new AgentToolBuilder(_logger);
        await using var toolContext = await toolBuilder.BuildAsync(document, definition, request.Headers, cancellationToken).ConfigureAwait(false);

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
                var failedRun = new AgentRunResult(definition.Id, "failed", stepResults, conversationId, DateTimeOffset.UtcNow);
                return await CompleteRunAsync(failedRun, progressSink, cancellationToken).ConfigureAwait(false);
            }

            if (definition.Steps.Count == 0)
            {
                var failedResult = new AgentStepExecutionResult("tool-initialization", "diagnostic", "One or more tools failed to initialize.")
                {
                    ToolErrorDetected = true,
                };

                stepResults.Add(failedResult);
                var failedRun = new AgentRunResult(definition.Id, "failed", stepResults, conversationId, DateTimeOffset.UtcNow);
                return await CompleteRunAsync(failedRun, progressSink, cancellationToken).ConfigureAwait(false);
            }
        }

        if (definition.Steps.Count == 0)
        {
            var emptyRun = new AgentRunResult(definition.Id, "completed", stepResults, conversationId, DateTimeOffset.UtcNow);
            return await CompleteRunAsync(emptyRun, progressSink, cancellationToken).ConfigureAwait(false);
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

            _logger.LogDebug(
                "[Workflow] Agent {AgentId} starting step {StepName} (type: {StepType}, iteration: {Iteration}).",
                definition.Id,
                stepDefinition.Name,
                stepDefinition.Type,
                executedSteps);

            await progressSink.StepStartingAsync(
                definition.Id,
                stepDefinition.Name,
                stepDefinition.Type,
                executedSteps,
                cancellationToken).ConfigureAwait(false);

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

            var stepStopwatch = Stopwatch.StartNew();

            var parameterResolution = WorkflowPlaceholderResolver.ResolveDictionaryWithDebug(
                stepDefinition.Parameters,
                workflowVariables,
                parameters,
                stepInput,
                lastStepOutput);
            var resolvedParameters = parameterResolution.Values;

            // resolvedOptions is forwarded to every step as an empty
            // dictionary so the call site below stays stable even
            // though the legacy ``step.Options`` field was removed in
            // the global profiles/tools refactor. Future step types
            // that need their own options bag can add it to
            // ``AgentStepDefinition`` and surface it here.
            var resolvedOptions = WorkflowPlaceholderResolver.ResolveDictionary(
                null,
                workflowVariables,
                parameters,
                stepInput,
                lastStepOutput);

            var (executionResult, updatedConversationId, updatedThreadState, stepThreadContext) = await ExecuteStepAsync(
              document,
              definition,
              stepDefinition,
              stepInput,
              parameters,
              conversationId,
              stepTools,
              sharedThreadState,
              resolvedParameters,
              resolvedOptions,
              parameterResolution.Debug,
              workflowVariables,
              workflowVariableStates,
              progressSink,
              cancellationToken).ConfigureAwait(false);

            stepStopwatch.Stop();
            var elapsed = stepStopwatch.Elapsed;

            conversationId = updatedConversationId;
            pendingInput = DetermineNextStepInput(stepDefinition, stepInput, executionResult.Output);
            lastStepOutput = executionResult.Output;
            sharedThreadState = updatedThreadState;

            var expressionVariables = BuildVariableExpressionValues(workflowVariables, workflowVariableStates);
            var expressionParameters = BuildParameterExpressionValues(parameters);

            var outcomeResolution = StepOutcomeResolver.ResolveNextStep(
                definition,
                stepLookup,
                stepDefinition,
                stepInput,
                executionResult.Output,
                lastStepOutput,
                expressionVariables,
                expressionParameters,
                _expressionEvaluator,
                _logger);

            var enrichedResult = executionResult with
            {
                Input = stepInput,
                ThreadContext = stepThreadContext,
                Outcome = outcomeResolution.Outcome,
                NextStep = outcomeResolution.NextStep,
                EndWorkflow = outcomeResolution.EndWorkflow,
            };

            stepResults.Add(enrichedResult);

            await progressSink.StepCompletedAsync(
                definition.Id,
                enrichedResult,
                elapsed,
                cancellationToken).ConfigureAwait(false);
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
        return await CompleteRunAsync(runResult, progressSink, cancellationToken).ConfigureAwait(false);
    }

    private async Task<(AgentStepExecutionResult Result, string? ConversationId, JsonElement? ThreadState, JsonElement? StepThreadContext)> ExecuteStepAsync(
      AgentDefinitionsDocument document,
      AgentDefinition definition,
      AgentStepDefinition step,
      string? input,
      IDictionary<string, string> parameters,
      string? conversationId,
      IReadOnlyList<AITool> tools,
      JsonElement? threadState,
      IReadOnlyDictionary<string, WorkflowExpressionValue> resolvedParameters,
      IReadOnlyDictionary<string, WorkflowExpressionValue> resolvedOptions,
      IReadOnlyDictionary<string, WorkflowParameterDebugInfo> parameterDebug,
      IDictionary<string, string> workflowVariables,
      IDictionary<string, WorkflowVariableState> workflowVariableStates,
      IAgentRunProgressSink progressSink,
      CancellationToken cancellationToken)
    {
        if (step.Type.Equals("agent", StringComparison.OrdinalIgnoreCase))
        {
            return await ExecuteAgentStepAsync(
              document,
              definition,
              step,
              input,
              parameters,
              conversationId,
              tools,
              threadState,
              resolvedParameters,
              resolvedOptions,
              parameterDebug,
              progressSink,
              cancellationToken);
        }

        if (step.Type.Equals("echo", StringComparison.OrdinalIgnoreCase))
        {
            var message = resolvedParameters.TryGetValue("message", out var value)
                ? WorkflowExpressionValueConverter.ToStringValue(value)
                : string.Empty;
            return (
                new AgentStepExecutionResult(step.Name, step.Type, message)
                {
                    ResolvedParameters = MaterializeResolvedValues(resolvedParameters),
                    ParameterDebug = parameterDebug,
                },
                conversationId,
                threadState,
                threadState);
        }

        if (step.Type.Equals("setVariables", StringComparison.OrdinalIgnoreCase))
        {
            var assigned = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var assignedDebug = new Dictionary<string, WorkflowVariableDebugInfo>(StringComparer.OrdinalIgnoreCase);
            var declaredTypes = step.VariableTypes ?? new Dictionary<string, WorkflowVariableDataType>(StringComparer.OrdinalIgnoreCase);

            foreach (var kvp in resolvedParameters)
            {
                var typedValue = kvp.Value ?? WorkflowExpressionValue.FromString(string.Empty);
                var resolvedValue = ResolveVariableAssignmentValue(WorkflowExpressionValueConverter.ToStringValue(typedValue), conversationId);
                var targetType = declaredTypes.TryGetValue(kvp.Key, out var declaredType)
                    ? declaredType
                    : WorkflowVariableDataType.String;

                var state = ConvertWorkflowVariableValue(typedValue, resolvedValue, targetType);

                workflowVariables[kvp.Key] = state.ConvertedValue;
                workflowVariableStates[kvp.Key] = state;
                assigned[kvp.Key] = state.ConvertedValue;
                assignedDebug[kvp.Key] = new WorkflowVariableDebugInfo(
                    state.RawValue,
                    state.ConvertedValue,
                    state.Type,
                    state.Error);
            }

            return (
                new AgentStepExecutionResult(step.Name, step.Type, input ?? string.Empty)
                {
                    ResolvedParameters = assigned,
                    VariableDebug = assignedDebug,
                    ParameterDebug = parameterDebug,
                },
                conversationId,
                threadState,
                threadState);
        }

        var fallbackOutput = JsonSerializer.Serialize(step.Parameters);
        return (
            new AgentStepExecutionResult(step.Name, step.Type, fallbackOutput)
            {
                ResolvedParameters = MaterializeResolvedValues(resolvedParameters),
                ParameterDebug = parameterDebug,
            },
            conversationId,
            threadState,
            threadState);
    }

    private static string ResolveVariableAssignmentValue(string? value, string? conversationId)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        const string presetPrefix = "$preset:";

        if (!value.StartsWith(presetPrefix, StringComparison.OrdinalIgnoreCase))
        {
            return value;
        }

        var presetKey = value[presetPrefix.Length..].Trim();

        if (string.IsNullOrEmpty(presetKey))
        {
            return string.Empty;
        }

        var localNow = DateTimeOffset.Now;

        if (presetKey.Equals("CurrentDate", StringComparison.OrdinalIgnoreCase))
        {
            return localNow.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        }

        if (presetKey.Equals("LocalDateTime", StringComparison.OrdinalIgnoreCase))
        {
            return localNow.ToString("O", CultureInfo.InvariantCulture);
        }

        if (presetKey.Equals("UtcDateTime", StringComparison.OrdinalIgnoreCase))
        {
            return localNow.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);
        }

        if (presetKey.Equals("DayOfTheWeek", StringComparison.OrdinalIgnoreCase))
        {
            return localNow.ToString("dddd", CultureInfo.InvariantCulture);
        }

        if (presetKey.Equals("ConversationId", StringComparison.OrdinalIgnoreCase))
        {
            return conversationId ?? string.Empty;
        }

        return value;
    }

    private static WorkflowVariableState ConvertWorkflowVariableValue(
        WorkflowExpressionValue typedValue,
        string rawValue,
        WorkflowVariableDataType targetType)
    {
        typedValue ??= WorkflowExpressionValue.FromString(rawValue ?? string.Empty);
        rawValue ??= string.Empty;

        string converted = rawValue;
        string? error = null;
        var effectiveType = targetType;

        switch (targetType)
        {
            case WorkflowVariableDataType.Number:
                if (WorkflowExpressionValueConverter.TryConvertToNumber(typedValue, out var numericValue))
                {
                    converted = numericValue.ToString(CultureInfo.InvariantCulture);
                }
                else if (double.TryParse(rawValue, NumberStyles.Float, CultureInfo.InvariantCulture, out numericValue))
                {
                    converted = numericValue.ToString(CultureInfo.InvariantCulture);
                }
                else
                {
                    error = "Unable to parse number. Stored original string.";
                    effectiveType = WorkflowVariableDataType.String;
                }
                break;

            case WorkflowVariableDataType.DateTime:
                if (WorkflowExpressionValueConverter.TryConvertToDateTime(typedValue, out var dateTimeValue))
                {
                    converted = dateTimeValue.ToString("O", CultureInfo.InvariantCulture);
                }
                else if (DateTimeOffset.TryParse(rawValue, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out dateTimeValue))
                {
                    converted = dateTimeValue.ToString("O", CultureInfo.InvariantCulture);
                }
                else
                {
                    error = "Unable to parse date/time. Stored original string.";
                    effectiveType = WorkflowVariableDataType.String;
                }
                break;

            case WorkflowVariableDataType.Json:
                var (jsonConverted, jsonError) = WorkflowExpressionValueConverter.ConvertToJsonString(typedValue);
                converted = jsonConverted;
                error = jsonError;
                break;

            case WorkflowVariableDataType.Boolean:
                if (typedValue.Kind == WorkflowExpressionValueKind.Boolean)
                {
                    converted = (typedValue.BooleanValue ?? false) ? "true" : "false";
                }
                else if (bool.TryParse(rawValue, out var booleanValue))
                {
                    converted = booleanValue ? "true" : "false";
                    error = null;
                }
                else
                {
                    error = "Enter either true or false.";
                }
                break;

            case WorkflowVariableDataType.String:
            default:
                converted = rawValue;
                break;
        }

        return new WorkflowVariableState(rawValue, converted, effectiveType, error);
    }

    private sealed record WorkflowVariableState(
        string RawValue,
        string ConvertedValue,
        WorkflowVariableDataType Type,
        string? Error);

    private static IReadOnlyDictionary<string, WorkflowExpressionValue> BuildParameterExpressionValues(IDictionary<string, string> parameters)
    {
        if (parameters.Count == 0)
        {
            return new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase);
        }

        var map = new Dictionary<string, WorkflowExpressionValue>(parameters.Count, StringComparer.OrdinalIgnoreCase);
        foreach (var kvp in parameters)
        {
            map[kvp.Key] = WorkflowExpressionValue.FromString(kvp.Value);
        }

        return map;
    }

    private static IReadOnlyDictionary<string, WorkflowExpressionValue> BuildVariableExpressionValues(
        IDictionary<string, string> rawVariables,
        IDictionary<string, WorkflowVariableState> states)
    {
        if (rawVariables.Count == 0 && states.Count == 0)
        {
            return new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase);
        }

        var map = new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase);

        foreach (var kvp in rawVariables)
        {
            map[kvp.Key] = WorkflowExpressionValue.FromString(kvp.Value);
        }

        foreach (var kvp in states)
        {
            map[kvp.Key] = ConvertStateToExpressionValue(kvp.Value);
        }

        return map;
    }

    private static WorkflowExpressionValue ConvertStateToExpressionValue(WorkflowVariableState state)
    {
        var value = state.ConvertedValue ?? string.Empty;

        return state.Type switch
        {
            WorkflowVariableDataType.Number => double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var number)
                ? WorkflowExpressionValue.FromNumber(number)
                : WorkflowExpressionValue.FromString(value),
            WorkflowVariableDataType.Boolean => bool.TryParse(value, out var boolean)
                ? WorkflowExpressionValue.FromBoolean(boolean)
                : WorkflowExpressionValue.FromString(value),
            WorkflowVariableDataType.Json => TryParseJson(value, out var node)
                ? WorkflowExpressionValue.FromJson(node)
                : WorkflowExpressionValue.FromString(value),
            WorkflowVariableDataType.DateTime => DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out var dateTime)
                ? WorkflowExpressionValue.FromDateTime(dateTime)
                : WorkflowExpressionValue.FromString(value),
            _ => WorkflowExpressionValue.FromString(value),
        };
    }

    private static bool TryParseJson(string value, out JsonNode? node)
    {
        node = null;

        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        try
        {
            node = JsonNode.Parse(value);
            return node is not null;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static IReadOnlyDictionary<string, string> MaterializeResolvedValues(
        IReadOnlyDictionary<string, WorkflowExpressionValue> values)
    {
        if (values.Count == 0)
        {
            return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }

        var materialized = new Dictionary<string, string>(values.Count, StringComparer.OrdinalIgnoreCase);
        foreach (var (key, value) in values)
        {
            materialized[key] = WorkflowExpressionValueConverter.ToStringValue(value);
        }

        return materialized;
    }

    private async Task<(AgentStepExecutionResult Result, string? ConversationId, JsonElement? ThreadState, JsonElement? StepThreadContext)> ExecuteAgentStepAsync(
      AgentDefinitionsDocument document,
      AgentDefinition definition,
      AgentStepDefinition step,
      string? input,
      IDictionary<string, string> parameters,
      string? conversationId,
      IReadOnlyList<AITool> tools,
      JsonElement? threadState,
      IReadOnlyDictionary<string, WorkflowExpressionValue> resolvedParameters,
      IReadOnlyDictionary<string, WorkflowExpressionValue> resolvedOptions,
      IReadOnlyDictionary<string, WorkflowParameterDebugInfo> parameterDebug,
      IAgentRunProgressSink progressSink,
      CancellationToken cancellationToken)
    {
        var instructions = resolvedParameters.TryGetValue("systemPrompt", out var systemPromptValue)
            ? WorkflowExpressionValueConverter.ToStringValue(systemPromptValue)
            : definition.Description ?? "You are a helpful assistant.";

        if (string.IsNullOrWhiteSpace(instructions))
        {
            instructions = definition.Description ?? "You are a helpful assistant.";
        }

        var userMessage = resolvedParameters.TryGetValue("message", out var configuredMessage)
            ? WorkflowExpressionValueConverter.ToStringValue(configuredMessage)
            : input;

        if (string.IsNullOrWhiteSpace(userMessage))
        {
            userMessage = input;
        }

        if (string.IsNullOrWhiteSpace(userMessage))
        {
            throw new InvalidOperationException("Agent step requires an input message.");
        }

        var (chatClient, llmCallConfig) = _chatClientResolver.Resolve(document, definition, step);
        var chatOptions = BuildChatOptions(llmCallConfig);

        if (tools is not null && tools.Count > 0)
        {
            chatOptions.Tools = tools.ToList();
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
            var agent = CreateAgentFromChatClient(chatClient, definition, chatOptions, instructions);
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

            var agentRunStopwatch = Stopwatch.StartNew();
            var runResponse = await agent.RunAsync(requestMessages, agentThread, options: null, cancellationToken: cancellationToken);
            agentRunStopwatch.Stop();

            var toolAnalysis = ToolInvocationUtilities.Analyze(runResponse);
            LogToolInvocations(definition.Id, step, toolAnalysis, agentRunStopwatch.Elapsed);

            var iterationTraces = BuildIterationTraces(runResponse);
            await EmitAgentTraceAsync(progressSink, definition.Id, step.Name, iterationTraces, toolAnalysis.ToolCalls, cancellationToken).ConfigureAwait(false);

            JsonElement? serializedThread = null;

            if (toolAnalysis.HasErrors)
            {

                serializedThread = agentThread.Serialize();

                if (step.StopOnToolError)
                {
                    var errorResult = ToolInvocationUtilities.CreateErrorResult(step, toolAnalysis) with
                    {
                        Iterations = iterationTraces,
                        LlmConfig = llmCallConfig,
                    };
                    return (errorResult, activeConversationId, serializedThread, threadState);
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
                Iterations = iterationTraces,
                ToolErrorDetected = toolAnalysis.HasErrors,
                ResolvedParameters = MaterializeResolvedValues(resolvedParameters),
                ParameterDebug = parameterDebug,
                LlmConfig = llmCallConfig,
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

            return (
                new AgentStepExecutionResult(step.Name, step.Type, fallback)
                {
                    ResolvedParameters = MaterializeResolvedValues(resolvedParameters),
                    ParameterDebug = parameterDebug,
                    LlmConfig = llmCallConfig,
                },
                conversationContext.ConversationId ?? conversationId,
                threadState,
                threadState);
        }
    }

    private static AIAgent CreateAgentFromChatClient(
        IChatClient chatClient,
        AgentDefinition definition,
        ChatOptions chatOptions,
        string instructions)
    {
        var agentOptions = new ChatClientAgentOptions
        {
            Instructions = instructions,
            Name = definition.Name,
            Description = definition.Description,
            ChatOptions = chatOptions,
        };

        return chatClient.CreateAIAgent(agentOptions);
    }

    private static ChatOptions BuildChatOptions(LLMCallConfig llmCallConfig)
    {
        var options = new ChatOptions();
        if (llmCallConfig.Temperature.HasValue)
        {
            options.Temperature = (float)llmCallConfig.Temperature.Value;
        }
        if (llmCallConfig.MaxTokens.HasValue)
        {
            options.MaxOutputTokens = llmCallConfig.MaxTokens;
        }
        return options;
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

    private async Task<AgentRunResult> CompleteRunAsync(
        AgentRunResult runResult,
        IAgentRunProgressSink progressSink,
        CancellationToken cancellationToken)
    {
        if (!string.IsNullOrWhiteSpace(runResult.ConversationId))
        {
            await _diagnosticsStore.SaveRunAsync(runResult.ConversationId!, runResult, cancellationToken).ConfigureAwait(false);
        }

        await progressSink.RunCompletedAsync(runResult, cancellationToken).ConfigureAwait(false);
        return runResult;
    }

    /// <summary>
    /// Walk the assistant messages of <paramref name="runResponse"/> and
    /// build one <see cref="AgentIterationTrace"/> per LLM turn.
    /// Captures the assistant's text (when present) and the names of
    /// the tools it requested on that turn so the operator can see
    /// how the model reasoned through intermediate steps instead of
    /// only seeing the final assistant message.
    /// </summary>
    private static List<AgentIterationTrace> BuildIterationTraces(AgentRunResponse? runResponse)
    {
        if (runResponse?.Messages is not { Count: > 0 } messages)
        {
            return [];
        }

        var traces = new List<AgentIterationTrace>();
        var iterationIndex = 0;

        foreach (var message in messages)
        {
            if (message is null || !ChatRole.Assistant.Equals(message.Role))
            {
                continue;
            }

            var toolCallNames = new List<string>();
            string? content = null;

            if (message.Contents is { Count: > 0 })
            {
                var textBuilder = new StringBuilder();
                foreach (var contentPart in message.Contents)
                {
                    switch (contentPart)
                    {
                        case FunctionCallContent functionCall:
                            if (!string.IsNullOrWhiteSpace(functionCall.Name))
                            {
                                toolCallNames.Add(functionCall.Name!);
                            }
                            break;

                        case TextContent textContent:
                            if (!string.IsNullOrEmpty(textContent.Text))
                            {
                                textBuilder.Append(textContent.Text);
                            }
                            break;
                    }
                }

                if (textBuilder.Length > 0)
                {
                    content = textBuilder.ToString();
                }
            }

            if (content is null && !string.IsNullOrWhiteSpace(message.Text))
            {
                content = message.Text;
            }

            traces.Add(new AgentIterationTrace(
                iterationIndex,
                content,
                toolCallNames,
                toolCallNames.Count > 0,
                DateTimeOffset.UtcNow));

            iterationIndex++;
        }

        return traces;
    }

    private static async ValueTask EmitAgentTraceAsync(
        IAgentRunProgressSink sink,
        string agentId,
        string stepName,
        IReadOnlyList<AgentIterationTrace> iterations,
        IReadOnlyList<AgentToolCall> toolCalls,
        CancellationToken cancellationToken)
    {
        for (var i = 0; i < iterations.Count; i++)
        {
            await sink.IterationAsync(agentId, stepName, iterations[i], cancellationToken).ConfigureAwait(false);
        }

        for (var i = 0; i < toolCalls.Count; i++)
        {
            await sink.ToolCallAsync(agentId, stepName, toolCalls[i], cancellationToken).ConfigureAwait(false);
        }
    }

    private void LogToolInvocations(
        string agentId,
        AgentStepDefinition step,
        ToolInvocationUtilities.ToolInvocationAnalysis analysis,
        TimeSpan elapsed)
    {
        if (analysis.ToolCalls.Count == 0)
        {
            _logger.LogDebug(
                "Agent {AgentId} step {StepName} completed with no MCP tool invocations in {ElapsedMs} ms.",
                agentId,
                step.Name,
                elapsed.TotalMilliseconds);
            return;
        }

        foreach (var call in analysis.ToolCalls)
        {
            _logger.LogDebug(
                "Agent {AgentId} step {StepName} invoked MCP tool {ToolName} (InvocationId={InvocationId}) in {ElapsedMs} ms. Args={Arguments} Result={Result} ErrorMessage={ErrorMessage} ErrorDetails={ErrorDetails} ErrorCode={ErrorCode}",
                agentId,
                step.Name,
                call.ToolName ?? "(unknown)",
                call.InvocationId ?? "(none)",
                elapsed.TotalMilliseconds,
                TruncateForLog(call.ArgumentsJson),
                TruncateForLog(call.Result),
                call.ErrorMessage ?? "(none)",
                TruncateForLog(call.ErrorDetails),
                call.ErrorCode ?? "(none)");
        }
    }

    private static string TruncateForLog(string? value, int maxLength = 500)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return "(empty)";
        }

        return value.Length <= maxLength
            ? value
            : $"{value[..maxLength]}...(+{value.Length - maxLength} chars)";
    }
}