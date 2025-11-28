namespace MagicAgent.Api.Application.AgentRunner;

internal static class StepOutcomeResolver
{
    internal static StepOutcomeResolution ResolveNextStep(
        AgentDefinition definition,
        IDictionary<string, AgentStepDefinition> stepLookup,
        AgentStepDefinition currentStep,
        string? output,
        ILogger logger)
    {
        ArgumentNullException.ThrowIfNull(definition);
        ArgumentNullException.ThrowIfNull(stepLookup);
        ArgumentNullException.ThrowIfNull(currentStep);
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

        var defaultOutcome = orderedOutcomes.FirstOrDefault(IsDefaultOutcome);

        var conditionalOutcomes = orderedOutcomes
            .Where(outcome => !IsDefaultOutcome(outcome))
            .ToList();

        foreach (var outcome in conditionalOutcomes)
        {
            if (!EvaluateOutcomeCondition(definition, currentStep, outcome, normalizedOutput, logger))
            {
                continue;
            }

            return ResolveOutcome(definition, stepLookup, currentStep, outcome, logger);
        }

        if (defaultOutcome is not null)
        {
            logger.LogInformation(
                "No conditional outcomes matched for agent {AgentId} step {StepName}. Applying default outcome '{OutcomeName}'.",
                definition.Id,
                currentStep.Name,
                defaultOutcome.Name);

            return ResolveOutcome(definition, stepLookup, currentStep, defaultOutcome, logger);
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
        string output,
        ILogger logger)
    {
        var condition = outcome.Condition;

        if (condition is null)
        {
            return true;
        }

        var conditionType = string.IsNullOrWhiteSpace(condition.Type) ? "always" : condition.Type.Trim();
        var parameters = condition.Parameters ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var comparison = GetStringComparison(parameters);

        switch (conditionType.ToLowerInvariant())
        {
            case "always":
                return true;
            case "contains":
                if (!parameters.TryGetValue("value", out var containsValue))
                {
                    logger.LogWarning(
                        "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} missing 'value' parameter for 'contains' condition.",
                        outcome.Name,
                        definition.Id,
                        step.Name);
                    return false;
                }

                return output.IndexOf(containsValue, comparison) >= 0;
            case "equals":
                if (!parameters.TryGetValue("value", out var equalsValue))
                {
                    logger.LogWarning(
                        "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} missing 'value' parameter for 'equals' condition.",
                        outcome.Name,
                        definition.Id,
                        step.Name);
                    return false;
                }

                return string.Equals(output, equalsValue, comparison);
            case "startswith":
                if (!parameters.TryGetValue("value", out var startsWithValue))
                {
                    logger.LogWarning(
                        "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} missing 'value' parameter for 'startsWith' condition.",
                        outcome.Name,
                        definition.Id,
                        step.Name);
                    return false;
                }

                return output.StartsWith(startsWithValue, comparison);
            case "endswith":
                if (!parameters.TryGetValue("value", out var endsWithValue))
                {
                    logger.LogWarning(
                        "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} missing 'value' parameter for 'endsWith' condition.",
                        outcome.Name,
                        definition.Id,
                        step.Name);
                    return false;
                }

                return output.EndsWith(endsWithValue, comparison);
            case "notempty":
                return !string.IsNullOrWhiteSpace(output);
            case "empty":
                return string.IsNullOrWhiteSpace(output);
            default:
                logger.LogWarning(
                    "Outcome '{OutcomeName}' for agent {AgentId} step {StepName} has unsupported condition type '{ConditionType}'.",
                    outcome.Name,
                    definition.Id,
                    step.Name,
                    condition.Type);
                return false;
        }
    }

    private static StringComparison GetStringComparison(IDictionary<string, string> parameters)
    {
        if (parameters.TryGetValue("caseSensitive", out var caseSensitiveValue) &&
            bool.TryParse(caseSensitiveValue, out var caseSensitive) &&
            caseSensitive)
        {
            return StringComparison.Ordinal;
        }

        return StringComparison.OrdinalIgnoreCase;
    }

    private static bool IsDefaultOutcome(AgentStepOutcomeDefinition? outcome)
    {
        if (outcome is null)
        {
            return false;
        }

        var conditionType = outcome.Condition?.Type;

        return !string.IsNullOrWhiteSpace(conditionType) &&
            string.Equals(conditionType.Trim(), "always", StringComparison.OrdinalIgnoreCase);
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

    internal readonly record struct StepOutcomeResolution(string? Outcome, string? NextStep, bool EndWorkflow);
}
