using System;
using System.Collections.Generic;
using System.Linq;
using MagicAgent.Api.Application.Expressions;

namespace MagicAgent.Api.Application.AgentRunner;

internal static class StepOutcomeResolver
{
    internal static StepOutcomeResolution ResolveNextStep(
        AgentDefinition definition,
        IDictionary<string, AgentStepDefinition> stepLookup,
        AgentStepDefinition currentStep,
        string? stepInput,
        string? output,
        string? lastOutput,
        IReadOnlyDictionary<string, WorkflowExpressionValue> variables,
        IReadOnlyDictionary<string, WorkflowExpressionValue> parameters,
        IWorkflowExpressionEvaluator expressionEvaluator,
        ILogger logger)
    {
        ArgumentNullException.ThrowIfNull(definition);
        ArgumentNullException.ThrowIfNull(stepLookup);
        ArgumentNullException.ThrowIfNull(currentStep);
        ArgumentNullException.ThrowIfNull(expressionEvaluator);
        ArgumentNullException.ThrowIfNull(logger);

        var normalizedOutput = output ?? string.Empty;

        if (currentStep.Outcomes is not { Count: > 0 })
        {
            return new StepOutcomeResolution(null, GetSequentialNextStep(definition, currentStep), false);
        }

        var orderedOutcomes = currentStep.Outcomes
            .Select((outcome, index) => outcome is null
                ? null
                : new
                {
                    Outcome = outcome,
                    OutcomeOrder = outcome.Order ?? int.MaxValue,
                    Index = index,
                })
            .Where(wrapper => wrapper is not null)
            .Select(wrapper => wrapper!)
            .OrderBy(wrapper => wrapper.OutcomeOrder)
            .ThenBy(wrapper => wrapper.Index)
            .Select(wrapper => wrapper.Outcome)
            .ToList();

        var runtimeState = BuildRuntimeState(currentStep, normalizedOutput);
        var expressionContext = new WorkflowExpressionContext(variables, parameters, runtimeState, stepInput, lastOutput);

        foreach (var outcome in orderedOutcomes)
        {
            if (!EvaluateOutcomeCondition(definition, currentStep, outcome, expressionContext, expressionEvaluator, logger))
            {
                continue;
            }

            return ResolveOutcome(definition, stepLookup, currentStep, outcome, logger);
        }

        logger.LogWarning(
            "No outcomes matched for agent {AgentId} step {StepName} and no default outcome was defined. Workflow will terminate.",
            definition.Id,
            currentStep.Name);

        return new StepOutcomeResolution(null, null, true);
    }

    private static StepOutcomeResolution ResolveOutcome(
        AgentDefinition definition,
        IDictionary<string, AgentStepDefinition> stepLookup,
        AgentStepDefinition currentStep,
        AgentStepOutcomeDefinition outcome,
        ILogger logger)
    {
        if (outcome.EndWorkflow)
        {
            if (!string.IsNullOrWhiteSpace(outcome.NextStep))
            {
                logger.LogWarning(
                    "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} marks the workflow as complete but specifies next step '{NextStep}'. The next step will be ignored.",
                    outcome.Name,
                    definition.Id,
                    currentStep.Name,
                    outcome.NextStep);
            }

            return new StepOutcomeResolution(outcome.Name, null, true);
        }

        var requestedNextStep = outcome.NextStep;
        string? resolvedNextStep;

        if (!string.IsNullOrWhiteSpace(requestedNextStep))
        {
            if (string.Equals(requestedNextStep, currentStep.Name, StringComparison.OrdinalIgnoreCase))
            {
                logger.LogWarning(
                    "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} references the same step and would cause a loop. Execution will stop.",
                    outcome.Name,
                    definition.Id,
                    currentStep.Name);
                resolvedNextStep = null;
            }
            else if (stepLookup.TryGetValue(requestedNextStep!, out var nextStepDefinition))
            {
                resolvedNextStep = nextStepDefinition.Name;
            }
            else
            {
                logger.LogWarning(
                    "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} references unknown next step '{NextStep}'. Falling back to sequential flow.",
                    outcome.Name,
                    definition.Id,
                    currentStep.Name,
                    requestedNextStep);
                resolvedNextStep = GetSequentialNextStep(definition, currentStep);
            }
        }
        else
        {
            resolvedNextStep = GetSequentialNextStep(definition, currentStep);
        }

        return new StepOutcomeResolution(outcome.Name, resolvedNextStep, false);
    }

    private static bool EvaluateOutcomeCondition(
        AgentDefinition definition,
        AgentStepDefinition step,
        AgentStepOutcomeDefinition outcome,
        WorkflowExpressionContext context,
        IWorkflowExpressionEvaluator evaluator,
        ILogger logger)
    {
        var condition = outcome.Condition;
        var expression = condition?.Expression;

        if (string.IsNullOrWhiteSpace(expression))
        {
            return true;
        }

        var result = evaluator.Evaluate(expression, context);

        if (!result.Success)
        {
            logger.LogWarning(
                "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} failed to evaluate expression '{Expression}': {Error}.",
                outcome.Name,
                definition.Id,
                step.Name,
                expression,
                result.ErrorMessage ?? "unknown error");
            return false;
        }

        var boolean = CoerceBoolean(result.Value);

        if (result.Value.Kind != WorkflowExpressionValueKind.Boolean)
        {
            logger.LogDebug(
                "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} expression '{Expression}' returned {Kind}; interpreted as {Boolean}.",
                outcome.Name,
                definition.Id,
                step.Name,
                expression,
                result.Value.Kind,
                boolean);
        }

        return boolean;
    }

    private static string? GetSequentialNextStep(AgentDefinition definition, AgentStepDefinition currentStep)
    {
        if (definition.Steps.Count == 0)
        {
            return null;
        }

        for (var index = 0; index < definition.Steps.Count; index++)
        {
            var candidate = definition.Steps[index];
            if (!string.Equals(candidate.Name, currentStep.Name, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (index + 1 < definition.Steps.Count)
            {
                return definition.Steps[index + 1].Name;
            }

            break;
        }

        return null;
    }

    private static IReadOnlyDictionary<string, WorkflowExpressionValue> BuildRuntimeState(
        AgentStepDefinition step,
        string output)
    {
        var state = new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase)
        {
            ["output"] = WorkflowExpressionValue.FromString(output),
            ["stepName"] = WorkflowExpressionValue.FromString(step.Name),
            ["stepType"] = WorkflowExpressionValue.FromString(step.Type ?? string.Empty),
        };

        return state;
    }

    private static bool CoerceBoolean(WorkflowExpressionValue value)
    {
        return value.Kind switch
        {
            WorkflowExpressionValueKind.Boolean => value.BooleanValue ?? false,
            WorkflowExpressionValueKind.Number => Math.Abs(value.NumberValue ?? 0d) > double.Epsilon,
            WorkflowExpressionValueKind.String => !string.IsNullOrWhiteSpace(value.StringValue),
            WorkflowExpressionValueKind.Json => value.JsonValue is not null,
            _ => false,
        };
    }

    internal readonly record struct StepOutcomeResolution(string? Outcome, string? NextStep, bool EndWorkflow);
}
