using System.Collections.Generic;
using FluentAssertions;
using MagicAgent.Api.Application.AgentRunner;
using MagicAgent.Api.Application.Expressions;
using MagicAgent.Api.Application.Expressions.Helpers;
using Microsoft.Extensions.Logging.Abstractions;

namespace MagicAgent.Api.Tests;

public class StepOutcomeResolverTests
{
    private static readonly WorkflowExpressionEvaluator Evaluator;

    static StepOutcomeResolverTests()
    {
        var registry = new WorkflowHelperRegistry(new[]
        {
            typeof(MathWorkflowHelpers),
            typeof(DateWorkflowHelpers),
            typeof(StringWorkflowHelpers),
            typeof(JsonWorkflowHelpers),
        });

        Evaluator = new WorkflowExpressionEvaluator(registry, NullLogger<WorkflowExpressionEvaluator>.Instance);
    }

    [Fact]
    public void ResolveNextStep_SelectsFirstMatchingExpression()
    {
        var definition = CreateDefinition(
            CreateOutcomes(
            new AgentStepOutcomeDefinition
            {
                Name = "skip",
                NextStep = "Fallback",
                Order = 1,
                Condition = new AgentStepOutcomeConditionDefinition { Expression = "false" },
            },
            new AgentStepOutcomeDefinition
            {
                Name = "match",
                NextStep = "Research Agent",
                Order = 2,
                Condition = new AgentStepOutcomeConditionDefinition
                {
                    Expression = "contains(state.output, \"ROUTE: research\")",
                },
            },
            new AgentStepOutcomeDefinition
            {
                Name = "default",
                NextStep = "Escalate Risk",
                Order = 3,
            }));
        var step = definition.Steps[0];

        var stepLookup = BuildStepLookup(definition);

        var result = StepOutcomeResolver.ResolveNextStep(
            definition,
            stepLookup,
            step,
            stepInput: null,
            output: "ROUTE: research",
            lastOutput: null,
            variables: EmptyExpressions(),
            parameters: EmptyExpressions(),
            expressionEvaluator: Evaluator,
            logger: NullLogger.Instance);

        result.Outcome.Should().Be("match");
        result.NextStep.Should().Be("Research Agent");
        result.EndWorkflow.Should().BeFalse();
    }

    [Fact]
    public void ResolveNextStep_TerminatesWhenNoExpressionsMatch()
    {
        var definition = CreateDefinition(
            CreateOutcomes(
            new AgentStepOutcomeDefinition
            {
                Name = "no_match",
                NextStep = "Research Agent",
                Order = 1,
                Condition = new AgentStepOutcomeConditionDefinition
                {
                    Expression = "contains(state.output, \"ROUTE: risk\")",
                },
            }));
        var step = definition.Steps[0];

        var stepLookup = BuildStepLookup(definition);

        var result = StepOutcomeResolver.ResolveNextStep(
            definition,
            stepLookup,
            step,
            stepInput: null,
            output: "ROUTE: research",
            lastOutput: null,
            variables: EmptyExpressions(),
            parameters: EmptyExpressions(),
            expressionEvaluator: Evaluator,
            logger: NullLogger.Instance);

        result.Outcome.Should().BeNull();
        result.NextStep.Should().BeNull();
        result.EndWorkflow.Should().BeTrue();
    }

    [Fact]
    public void ResolveNextStep_UsesDefaultWhenExpressionMissing()
    {
        var definition = CreateDefinition(
            CreateOutcomes(
            new AgentStepOutcomeDefinition
            {
                Name = "always",
                NextStep = "Escalate Risk",
                Order = 5,
            }));
        var step = definition.Steps[0];

        var stepLookup = BuildStepLookup(definition);

        var result = StepOutcomeResolver.ResolveNextStep(
            definition,
            stepLookup,
            step,
            stepInput: null,
            output: string.Empty,
            lastOutput: null,
            variables: EmptyExpressions(),
            parameters: EmptyExpressions(),
            expressionEvaluator: Evaluator,
            logger: NullLogger.Instance);

        result.Outcome.Should().Be("always");
        result.NextStep.Should().Be("Escalate Risk");
        result.EndWorkflow.Should().BeFalse();
    }

    [Fact]
    public void ResolveNextStep_EvaluatesExpressionsInOrder()
    {
        var definition = CreateDefinition(
            CreateOutcomes(
            new AgentStepOutcomeDefinition
            {
                Name = "first",
                NextStep = "Research Agent",
                Order = 1,
                Condition = new AgentStepOutcomeConditionDefinition
                {
                    Expression = "contains(state.output, \"ROUTE: research\")",
                },
            },
            new AgentStepOutcomeDefinition
            {
                Name = "second",
                NextStep = "Escalate Risk",
                Order = 2,
                Condition = new AgentStepOutcomeConditionDefinition
                {
                    Expression = "contains(state.output, \"ROUTE: risk\")",
                },
            },
            new AgentStepOutcomeDefinition
            {
                Name = "default",
                NextStep = "Fallback",
                Order = 3,
            }));
        var step = definition.Steps[0];

        var stepLookup = BuildStepLookup(definition);

        var result = StepOutcomeResolver.ResolveNextStep(
            definition,
            stepLookup,
            step,
            stepInput: null,
            output: "ROUTE: research",
            lastOutput: null,
            variables: EmptyExpressions(),
            parameters: EmptyExpressions(),
            expressionEvaluator: Evaluator,
            logger: NullLogger.Instance);

        result.Outcome.Should().Be("first");
        result.NextStep.Should().Be("Research Agent");
        result.EndWorkflow.Should().BeFalse();
    }

    [Fact]
    public void ResolveNextStep_IgnoresExpressionsWithSyntaxErrors()
    {
        var definition = CreateDefinition(
            CreateOutcomes(
            new AgentStepOutcomeDefinition
            {
                Name = "invalid",
                NextStep = "Research Agent",
                Order = 1,
                Condition = new AgentStepOutcomeConditionDefinition
                {
                    Expression = " invalid expression ",
                },
            },
            new AgentStepOutcomeDefinition
            {
                Name = "valid",
                NextStep = "Escalate Risk",
                Order = 2,
                Condition = new AgentStepOutcomeConditionDefinition
                {
                    Expression = "contains(state.output, \"ROUTE: risk\")",
                },
            }));
        var step = definition.Steps[0];

        var stepLookup = BuildStepLookup(definition);

        var result = StepOutcomeResolver.ResolveNextStep(
            definition,
            stepLookup,
            step,
            stepInput: null,
            output: "ROUTE: risk",
            lastOutput: null,
            variables: EmptyExpressions(),
            parameters: EmptyExpressions(),
            expressionEvaluator: Evaluator,
            logger: NullLogger.Instance);

        result.Outcome.Should().Be("valid");
        result.NextStep.Should().Be("Escalate Risk");
        result.EndWorkflow.Should().BeFalse();
    }

    private static AgentDefinition CreateDefinition(List<AgentStepOutcomeDefinition>? initialOutcomes = null)
    {
        return new AgentDefinition
        {
            Id = "test-agent",
            Steps =
            [
                new AgentStepDefinition
                {
                    Name = "Security",
                    Type = "chat",
                    Parameters = new Dictionary<string, string>(),
                    Outcomes = initialOutcomes ?? new List<AgentStepOutcomeDefinition>(),
                },
                new AgentStepDefinition
                {
                    Name = "Research Agent",
                    Type = "chat",
                    Parameters = new Dictionary<string, string>(),
                },
                new AgentStepDefinition
                {
                    Name = "Escalate Risk",
                    Type = "echo",
                    Parameters = new Dictionary<string, string>(),
                },
                new AgentStepDefinition
                {
                    Name = "Fallback",
                    Type = "echo",
                    Parameters = new Dictionary<string, string>(),
                },
            ],
        };
    }

    private static Dictionary<string, AgentStepDefinition> BuildStepLookup(AgentDefinition definition)
    {
        var lookup = new Dictionary<string, AgentStepDefinition>(StringComparer.OrdinalIgnoreCase);
        foreach (var step in definition.Steps)
        {
            lookup[step.Name] = step;
        }

        return lookup;
    }

    private static List<AgentStepOutcomeDefinition> CreateOutcomes(params AgentStepOutcomeDefinition[] outcomes) =>
        new List<AgentStepOutcomeDefinition>(outcomes);

    private static IReadOnlyDictionary<string, WorkflowExpressionValue> EmptyExpressions() =>
        new Dictionary<string, WorkflowExpressionValue>(StringComparer.OrdinalIgnoreCase);
}