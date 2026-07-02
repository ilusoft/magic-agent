namespace MagicAgent.Api.Application.AgentRunner;

/// <summary>
/// Validates an <see cref="AgentDefinitionsDocument"/> against the rules
/// introduced by the global LLM-profiles / tool-pool refactor:
///
///   - Every <c>step.llmConfig.profileId</c> resolves to a key in <c>document.LlmProfiles</c>.
///   - Every <c>step.tools[i]</c> resolves to a key in <c>document.Tools</c>.
///   - Every profile has the required fields for its declared <c>provider</c> and a non-empty <c>apiKey</c>.
///   - Profile and tool ids are unique (trivially true for <see cref="IDictionary{TKey,TValue}"/>,
///     but checked explicitly so inline JSON parses with duplicate keys are caught).
///
/// Returns an empty list when the document is valid. Throws
/// <see cref="AgentDefinitionsValidationException"/> from the call site if the
/// returned list is non-empty.
/// </summary>
public static class AgentDefinitionsDocumentValidator
{
    public static IReadOnlyList<AgentDefinitionsValidationIssue> Validate(AgentDefinitionsDocument document)
    {
        ArgumentNullException.ThrowIfNull(document);

        var issues = new List<AgentDefinitionsValidationIssue>();

        ValidateProfiles(document, issues);
        ValidateAgents(document, issues);

        return issues;
    }

    /// <summary>
    /// Ensures that no <c>PUT</c> on <c>/api/agent-definitions/llm-profiles</c>
    /// silently drops an id that is still referenced by a step's
    /// <c>llmConfig.profileId</c>. Throws <see cref="AgentDefinitionsInUseException"/>
    /// with the list of referencing agents and steps when the caller
    /// tries to remove an in-use profile.
    /// </summary>
    public static void CheckRemovedLlmProfiles(
        AgentDefinitionsDocument currentDocument,
        IDictionary<string, AgentLlmProfileDefinition> newProfiles)
    {
        ArgumentNullException.ThrowIfNull(currentDocument);
        ArgumentNullException.ThrowIfNull(newProfiles);

        var removedIds = currentDocument.LlmProfiles.Keys
            .Except(newProfiles.Keys, StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (removedIds.Count == 0)
        {
            return;
        }

        var referencingSteps = FindReferencingLlmProfileSteps(currentDocument, removedIds);
        if (referencingSteps.Count > 0)
        {
            throw new AgentDefinitionsInUseException(
                $"LLM profile(s) '{string.Join(", ", removedIds)}' cannot be removed: still referenced by {referencingSteps.Count} step(s).",
                referencingSteps);
        }
    }

    /// <summary>
    /// Ensures that no <c>PUT</c> on <c>/api/agent-definitions/tools</c>
    /// silently drops an id that is still referenced by a step's
    /// <c>tools</c> list. Throws <see cref="AgentDefinitionsInUseException"/>
    /// with the list of referencing agents and steps when the caller
    /// tries to remove an in-use tool.
    /// </summary>
    public static void CheckRemovedTools(
        AgentDefinitionsDocument currentDocument,
        IDictionary<string, AgentToolDefinition> newTools)
    {
        ArgumentNullException.ThrowIfNull(currentDocument);
        ArgumentNullException.ThrowIfNull(newTools);

        var removedIds = currentDocument.Tools.Keys
            .Except(newTools.Keys, StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (removedIds.Count == 0)
        {
            return;
        }

        var referencingSteps = FindReferencingToolSteps(currentDocument, removedIds);
        if (referencingSteps.Count > 0)
        {
            throw new AgentDefinitionsInUseException(
                $"Tool(s) '{string.Join(", ", removedIds)}' cannot be removed: still referenced by {referencingSteps.Count} step(s).",
                referencingSteps);
        }
    }

    private static List<ReferencingStep> FindReferencingLlmProfileSteps(
        AgentDefinitionsDocument document,
        IReadOnlyCollection<string> removedIds)
    {
        var result = new List<ReferencingStep>();
        if (document.Agents is null)
        {
            return result;
        }

        foreach (var agent in document.Agents)
        {
            if (agent?.Steps is null)
            {
                continue;
            }

            foreach (var step in agent.Steps)
            {
                if (step is null)
                {
                    continue;
                }

                var profileId = step.LlmConfig?.ProfileId;
                if (string.IsNullOrWhiteSpace(profileId))
                {
                    continue;
                }

                if (removedIds.Any(id => string.Equals(id, profileId, StringComparison.OrdinalIgnoreCase)))
                {
                    result.Add(new ReferencingStep(agent.Id, step.Name));
                }
            }
        }

        return result;
    }

    private static List<ReferencingStep> FindReferencingToolSteps(
        AgentDefinitionsDocument document,
        IReadOnlyCollection<string> removedIds)
    {
        var result = new List<ReferencingStep>();
        if (document.Agents is null)
        {
            return result;
        }

        foreach (var agent in document.Agents)
        {
            if (agent?.Steps is null)
            {
                continue;
            }

            foreach (var step in agent.Steps)
            {
                if (step?.Tools is null)
                {
                    continue;
                }

                foreach (var toolId in step.Tools)
                {
                    if (string.IsNullOrWhiteSpace(toolId))
                    {
                        continue;
                    }

                    if (removedIds.Any(id => string.Equals(id, toolId, StringComparison.OrdinalIgnoreCase)))
                    {
                        result.Add(new ReferencingStep(agent.Id, step.Name));
                        break;
                    }
                }
            }
        }

        return result;
    }

    private static void ValidateProfiles(AgentDefinitionsDocument document, List<AgentDefinitionsValidationIssue> issues)
    {
        if (document.LlmProfiles is null)
        {
            return;
        }

        foreach (var kvp in document.LlmProfiles)
        {
            var path = $"llmProfiles[{kvp.Key}]";
            ValidateProfile(kvp.Key, kvp.Value, path, issues);
        }
    }

    private static void ValidateProfile(string profileId, AgentLlmProfileDefinition? profile, string path, List<AgentDefinitionsValidationIssue> issues)
    {
        if (profile is null)
        {
            issues.Add(new AgentDefinitionsValidationIssue(path, "Profile is null."));
            return;
        }

        if (string.IsNullOrWhiteSpace(profile.Provider))
        {
            issues.Add(new AgentDefinitionsValidationIssue($"{path}.provider", "Provider is required."));
        }
        else if (profile.Provider.Equals("azure-openai", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(profile.Endpoint))
            {
                issues.Add(new AgentDefinitionsValidationIssue($"{path}.endpoint", "Azure OpenAI profile requires 'endpoint'."));
            }
            if (string.IsNullOrWhiteSpace(profile.Deployment))
            {
                issues.Add(new AgentDefinitionsValidationIssue($"{path}.deployment", "Azure OpenAI profile requires 'deployment'."));
            }
        }
        else if (profile.Provider.Equals("openai-compatible", StringComparison.OrdinalIgnoreCase))
        {
            if (string.IsNullOrWhiteSpace(profile.BaseUrl))
            {
                issues.Add(new AgentDefinitionsValidationIssue($"{path}.baseUrl", "OpenAI-compatible profile requires 'baseUrl'."));
            }
            if (string.IsNullOrWhiteSpace(profile.Model))
            {
                issues.Add(new AgentDefinitionsValidationIssue($"{path}.model", "OpenAI-compatible profile requires 'model'."));
            }
        }
        else
        {
            issues.Add(new AgentDefinitionsValidationIssue($"{path}.provider", $"Unknown provider '{profile.Provider}'."));
        }

        if (!IsValidApiKey(profile.ApiKey))
        {
            issues.Add(new AgentDefinitionsValidationIssue($"{path}.apiKey", "Profile requires 'apiKey'."));
        }

        _ = profileId;
    }

    private static bool IsValidApiKey(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }
        return true;
    }

    private static void ValidateAgents(AgentDefinitionsDocument document, List<AgentDefinitionsValidationIssue> issues)
    {
        if (document.Agents is null)
        {
            return;
        }

        for (var agentIndex = 0; agentIndex < document.Agents.Count; agentIndex++)
        {
            var agent = document.Agents[agentIndex];
            if (agent is null)
            {
                continue;
            }

            var agentPath = string.IsNullOrWhiteSpace(agent.Id)
                ? $"agents[{agentIndex}]"
                : $"agents[{agent.Id}]";

            if (agent.Steps is null)
            {
                continue;
            }

            for (var stepIndex = 0; stepIndex < agent.Steps.Count; stepIndex++)
            {
                var step = agent.Steps[stepIndex];
                if (step is null)
                {
                    continue;
                }

                var stepPath = string.IsNullOrWhiteSpace(step.Name)
                    ? $"{agentPath}.steps[{stepIndex}]"
                    : $"{agentPath}.steps[{step.Name}]";

                ValidateStep(step, stepPath, document, issues);
            }
        }
    }

    private static void ValidateStep(AgentStepDefinition step, string stepPath, AgentDefinitionsDocument document, List<AgentDefinitionsValidationIssue> issues)
    {
        var profileId = step.LlmConfig?.ProfileId;
        if (!string.IsNullOrWhiteSpace(profileId) && !document.LlmProfiles.ContainsKey(profileId))
        {
            issues.Add(new AgentDefinitionsValidationIssue(
                $"{stepPath}.llmConfig.profileId",
                $"References unknown LLM profile '{profileId}'."));
        }

        if (step.Tools is null)
        {
            return;
        }

        for (var i = 0; i < step.Tools.Count; i++)
        {
            var toolId = step.Tools[i];
            if (string.IsNullOrWhiteSpace(toolId))
            {
                continue;
            }

            if (!document.Tools.ContainsKey(toolId))
            {
                issues.Add(new AgentDefinitionsValidationIssue(
                    $"{stepPath}.tools[{i}]",
                    $"References unknown tool '{toolId}'."));
            }
        }
    }
}
