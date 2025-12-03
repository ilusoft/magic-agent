using System.Collections.Generic;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using MagicAgent.Api.Application.Expressions.Parsing;
using Microsoft.Extensions.Logging;

namespace MagicAgent.Api.Application.Expressions;

internal sealed class WorkflowExpressionEvaluator : IWorkflowExpressionEvaluator
{
    private readonly IWorkflowHelperRegistry _helperRegistry;
    private readonly ILogger<WorkflowExpressionEvaluator> _logger;

    public WorkflowExpressionEvaluator(
        IWorkflowHelperRegistry helperRegistry,
        ILogger<WorkflowExpressionEvaluator> logger)
    {
        _helperRegistry = helperRegistry ?? throw new ArgumentNullException(nameof(helperRegistry));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public WorkflowExpressionResult Evaluate(
        string expression,
        WorkflowExpressionContext context,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(expression))
        {
            return WorkflowExpressionResult.FromValue(WorkflowExpressionValue.FromString(string.Empty));
        }

        try
        {
            var root = WorkflowExpressionParser.Parse(expression);
            var evaluator = new EvaluationState(context, _helperRegistry, cancellationToken);
            var value = evaluator.Evaluate(root);
            return WorkflowExpressionResult.FromValue(value, evaluator.ReferencedIdentifiers);
        }
        catch (WorkflowExpressionParseException parseEx)
        {
            return WorkflowExpressionResult.FromError(parseEx.Message, "parse_error");
        }
        catch (WorkflowExpressionEvaluationException evalEx)
        {
            _logger.LogDebug(evalEx, "Expression evaluation error: {Message}", evalEx.Message);
            return WorkflowExpressionResult.FromError(evalEx.Message, evalEx.ErrorCode);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled error evaluating expression '{Expression}'.", expression);
            return WorkflowExpressionResult.FromError("Expression evaluation failed.", "evaluation_error");
        }
    }

    private sealed class EvaluationState
    {
        private static readonly JsonDocumentOptions DocumentOptions = new()
        {
            AllowTrailingCommas = true,
            CommentHandling = JsonCommentHandling.Skip,
        };

        private readonly WorkflowExpressionContext _context;
        private readonly IWorkflowHelperRegistry _helperRegistry;
        private readonly CancellationToken _cancellationToken;
        private readonly List<string> _references = new();
        private readonly HashSet<string> _referenceSet = new(StringComparer.OrdinalIgnoreCase);

        internal EvaluationState(
            WorkflowExpressionContext context,
            IWorkflowHelperRegistry helperRegistry,
            CancellationToken cancellationToken)
        {
            _context = context ?? throw new ArgumentNullException(nameof(context));
            _helperRegistry = helperRegistry ?? throw new ArgumentNullException(nameof(helperRegistry));
            _cancellationToken = cancellationToken;
        }

        internal IReadOnlyList<string> ReferencedIdentifiers => _references;

        internal WorkflowExpressionValue Evaluate(WorkflowExpressionNode node)
        {
            _cancellationToken.ThrowIfCancellationRequested();

            return node switch
            {
                LiteralExpressionNode literal => ConvertLiteral(literal),
                IdentifierExpressionNode identifier => ResolveIdentifier(identifier.Name),
                UnaryExpressionNode unary => EvaluateUnary(unary),
                BinaryExpressionNode binary => EvaluateBinary(binary),
                ConditionalExpressionNode conditional => EvaluateConditional(conditional),
                FunctionCallExpressionNode function => EvaluateFunction(function),
                MemberAccessExpressionNode member => EvaluateMemberAccess(member),
                IndexAccessExpressionNode index => EvaluateIndexAccess(index),
                _ => throw new WorkflowExpressionEvaluationException("Unsupported expression node.", "unsupported_node"),
            };
        }

        private bool TryConvertToNumber(WorkflowExpressionValue value, out double number)
        {
            try
            {
                number = ToNumber(value);
                return true;
            }
            catch
            {
                number = 0d;
                return false;
            }
        }

        private WorkflowExpressionValue ConvertLiteral(LiteralExpressionNode literal)
        {
            return literal.ValueKind switch
            {
                WorkflowExpressionValueKind.Number => WorkflowExpressionValue.FromNumber(Convert.ToDouble(literal.Value, CultureInfo.InvariantCulture)),
                WorkflowExpressionValueKind.Boolean => WorkflowExpressionValue.FromBoolean(Convert.ToBoolean(literal.Value, CultureInfo.InvariantCulture)),
                WorkflowExpressionValueKind.Json => WorkflowExpressionValue.FromJson(literal.Value as JsonNode),
                WorkflowExpressionValueKind.Null => WorkflowExpressionValue.Null(),
                _ => WorkflowExpressionValue.FromString(literal.Value?.ToString() ?? string.Empty),
            };
        }

        private WorkflowExpressionValue ResolveIdentifier(string name)
        {
            if (string.Equals(name, "input", StringComparison.OrdinalIgnoreCase))
            {
                RecordReference(name);
                return WorkflowExpressionValue.FromString(_context.StepInput ?? string.Empty);
            }

            if (string.Equals(name, "lastOutput", StringComparison.OrdinalIgnoreCase))
            {
                RecordReference(name);
                return WorkflowExpressionValue.FromString(_context.LastStepOutput ?? string.Empty);
            }

            if (_context.RuntimeState.TryGetValue(name, out var runtimeValue))
            {
                RecordReference($"state.{name}");
                return runtimeValue;
            }

            if (_context.Variables.TryGetValue(name, out var variableValue))
            {
                RecordReference($"var.{name}");
                return variableValue;
            }

            if (_context.Parameters.TryGetValue(name, out var parameterValue))
            {
                RecordReference($"param.{name}");
                return parameterValue;
            }

            return WorkflowExpressionValue.Null();
        }

        private WorkflowExpressionValue EvaluateUnary(UnaryExpressionNode unary)
        {
            var operand = Evaluate(unary.Operand);

            return unary.Operator switch
            {
                WorkflowExpressionTokenKind.Plus => WorkflowExpressionValue.FromNumber(ToNumber(operand)),
                WorkflowExpressionTokenKind.Minus => WorkflowExpressionValue.FromNumber(-ToNumber(operand)),
                WorkflowExpressionTokenKind.Bang => WorkflowExpressionValue.FromBoolean(!ToBoolean(operand)),
                _ => throw new WorkflowExpressionEvaluationException($"Unsupported unary operator '{unary.Operator}'.", "unsupported_unary"),
            };
        }

        private WorkflowExpressionValue EvaluateBinary(BinaryExpressionNode binary)
        {
            var left = Evaluate(binary.Left);
            var right = Evaluate(binary.Right);

            return binary.Operator switch
            {
                WorkflowExpressionTokenKind.Plus => EvaluateAddition(left, right),
                WorkflowExpressionTokenKind.Minus => WorkflowExpressionValue.FromNumber(ToNumber(left) - ToNumber(right)),
                WorkflowExpressionTokenKind.Star => WorkflowExpressionValue.FromNumber(ToNumber(left) * ToNumber(right)),
                WorkflowExpressionTokenKind.Slash => WorkflowExpressionValue.FromNumber(ToNumber(left) / ToNumber(right)),
                WorkflowExpressionTokenKind.Percent => WorkflowExpressionValue.FromNumber(ToNumber(left) % ToNumber(right)),
                WorkflowExpressionTokenKind.Caret => WorkflowExpressionValue.FromNumber(Math.Pow(ToNumber(left), ToNumber(right))),
                WorkflowExpressionTokenKind.Equals => WorkflowExpressionValue.FromBoolean(AreEqual(left, right)),
                WorkflowExpressionTokenKind.NotEquals => WorkflowExpressionValue.FromBoolean(!AreEqual(left, right)),
                WorkflowExpressionTokenKind.LessThan => WorkflowExpressionValue.FromBoolean(ToNumber(left) < ToNumber(right)),
                WorkflowExpressionTokenKind.LessThanOrEqual => WorkflowExpressionValue.FromBoolean(ToNumber(left) <= ToNumber(right)),
                WorkflowExpressionTokenKind.GreaterThan => WorkflowExpressionValue.FromBoolean(ToNumber(left) > ToNumber(right)),
                WorkflowExpressionTokenKind.GreaterThanOrEqual => WorkflowExpressionValue.FromBoolean(ToNumber(left) >= ToNumber(right)),
                WorkflowExpressionTokenKind.AndAnd => WorkflowExpressionValue.FromBoolean(ToBoolean(left) && ToBoolean(right)),
                WorkflowExpressionTokenKind.OrOr => WorkflowExpressionValue.FromBoolean(ToBoolean(left) || ToBoolean(right)),
                _ => throw new WorkflowExpressionEvaluationException($"Unsupported binary operator '{binary.Operator}'.", "unsupported_binary"),
            };
        }

        private WorkflowExpressionValue EvaluateAddition(WorkflowExpressionValue left, WorkflowExpressionValue right)
        {
            if (TryConvertToNumber(left, out var leftNumber) && TryConvertToNumber(right, out var rightNumber))
            {
                return WorkflowExpressionValue.FromNumber(leftNumber + rightNumber);
            }

            return WorkflowExpressionValue.FromString(left.ToDisplayString() + right.ToDisplayString());
        }

        private WorkflowExpressionValue EvaluateConditional(ConditionalExpressionNode conditional)
        {
            var conditionValue = Evaluate(conditional.Condition);
            return ToBoolean(conditionValue)
                ? Evaluate(conditional.WhenTrue)
                : Evaluate(conditional.WhenFalse);
        }

        private WorkflowExpressionValue EvaluateFunction(FunctionCallExpressionNode function)
        {
            if (function.Target is not IdentifierExpressionNode identifier)
            {
                throw new WorkflowExpressionEvaluationException("Function calls must target a helper name.", "invalid_function_target");
            }

            var arguments = new List<WorkflowExpressionValue>(function.Arguments.Count);
            foreach (var argumentNode in function.Arguments)
            {
                arguments.Add(Evaluate(argumentNode));
            }

            if (_helperRegistry.TryInvoke(identifier.Name, arguments, out var helperResult, out var error, _cancellationToken) && helperResult is not null)
            {
                RecordReference(identifier.Name);
                return helperResult;
            }

            throw new WorkflowExpressionEvaluationException(error ?? $"Helper '{identifier.Name}' invocation failed.", "helper_error");
        }

        private WorkflowExpressionValue EvaluateMemberAccess(MemberAccessExpressionNode member)
        {
            WorkflowExpressionValue targetValue;

            if (member.Target is IdentifierExpressionNode identifier &&
                TryResolveScopedMember(identifier.Name, member.MemberName, out var scopedValue))
            {
                return scopedValue;
            }

            targetValue = Evaluate(member.Target);

            if (targetValue.Kind == WorkflowExpressionValueKind.String &&
                TryParseJson(targetValue.StringValue ?? string.Empty, out var parsedFromString))
            {
                targetValue = WorkflowExpressionValue.FromJson(parsedFromString);
            }

            var resolved = ResolveJsonMember(targetValue, member.MemberName);

            if (resolved is not null)
            {
                return resolved;
            }

            if (targetValue.Kind == WorkflowExpressionValueKind.Json)
            {
                return WorkflowExpressionValue.Null();
            }

            if (targetValue.Kind == WorkflowExpressionValueKind.String &&
                string.Equals(member.MemberName, "length", StringComparison.OrdinalIgnoreCase))
            {
                return WorkflowExpressionValue.FromNumber((targetValue.StringValue ?? string.Empty).Length);
            }

            if (targetValue.Kind == WorkflowExpressionValueKind.Json && targetValue.JsonValue is JsonArray array &&
                string.Equals(member.MemberName, "length", StringComparison.OrdinalIgnoreCase))
            {
                return WorkflowExpressionValue.FromNumber(array.Count);
            }

            throw new WorkflowExpressionEvaluationException($"Member '{member.MemberName}' was not found.", "member_not_found");
        }

        private WorkflowExpressionValue EvaluateIndexAccess(IndexAccessExpressionNode index)
        {
            var targetValue = Evaluate(index.Target);
            var indexValue = Evaluate(index.Index);

            if (targetValue.Kind == WorkflowExpressionValueKind.String && TryParseJson(targetValue.StringValue ?? string.Empty, out var parsedNode))
            {
                targetValue = WorkflowExpressionValue.FromJson(parsedNode);
            }

            if (targetValue.Kind == WorkflowExpressionValueKind.Json)
            {
                if (targetValue.JsonValue is JsonArray array)
                {
                    var position = (int)ToNumber(indexValue);
                    if (position < 0 || position >= array.Count)
                    {
                        throw new WorkflowExpressionEvaluationException("Index out of range.", "index_out_of_range");
                    }

                    return FromJsonNode(array[position]);
                }

                if (targetValue.JsonValue is JsonObject obj)
                {
                    var property = indexValue.ToDisplayString();
                    if (obj.TryGetPropertyValue(property, out var node))
                    {
                        return FromJsonNode(node);
                    }
                }
            }

            if (targetValue.Kind == WorkflowExpressionValueKind.String)
            {
                var str = targetValue.StringValue ?? string.Empty;
                var position = (int)ToNumber(indexValue);
                if (position < 0 || position >= str.Length)
                {
                    throw new WorkflowExpressionEvaluationException("String index out of range.", "index_out_of_range");
                }

                return WorkflowExpressionValue.FromString(str[position].ToString());
            }

            throw new WorkflowExpressionEvaluationException("Index access is only supported for arrays, objects, or strings.", "invalid_index_target");
        }

        private bool TryResolveScopedMember(string scopeName, string memberName, out WorkflowExpressionValue value)
        {
            if (string.Equals(scopeName, "var", StringComparison.OrdinalIgnoreCase))
            {
                if (_context.Variables.TryGetValue(memberName, out var variableValue) && variableValue is not null)
                {
                    value = variableValue;
                    RecordReference($"var.{memberName}");
                    return true;
                }

                value = WorkflowExpressionValue.Null();
                return true;
            }

            if (string.Equals(scopeName, "param", StringComparison.OrdinalIgnoreCase) ||
                string.Equals(scopeName, "parameter", StringComparison.OrdinalIgnoreCase))
            {
                if (_context.Parameters.TryGetValue(memberName, out var parameterValue) && parameterValue is not null)
                {
                    value = parameterValue;
                    RecordReference($"param.{memberName}");
                    return true;
                }

                value = WorkflowExpressionValue.Null();
                return true;
            }

            if (string.Equals(scopeName, "state", StringComparison.OrdinalIgnoreCase))
            {
                if (_context.RuntimeState.TryGetValue(memberName, out var runtimeValue) && runtimeValue is not null)
                {
                    value = runtimeValue;
                    RecordReference($"state.{memberName}");
                    return true;
                }

                value = WorkflowExpressionValue.Null();
                return true;
            }

            value = WorkflowExpressionValue.Null();
            return false;
        }

        private WorkflowExpressionValue? ResolveJsonMember(WorkflowExpressionValue targetValue, string memberName)
        {
            if (targetValue.Kind != WorkflowExpressionValueKind.Json || targetValue.JsonValue is null)
            {
                if (targetValue.Kind == WorkflowExpressionValueKind.String)
                {
                    if (TryParseJson(targetValue.StringValue ?? string.Empty, out var parsed))
                    {
                        targetValue = WorkflowExpressionValue.FromJson(parsed);
                    }
                    else
                    {
                        return null;
                    }
                }
                else
                {
                    return null;
                }
            }

            if (targetValue.JsonValue is JsonObject obj && obj.TryGetPropertyValue(memberName, out var node))
            {
                return FromJsonNode(node);
            }

            if (targetValue.JsonValue is JsonArray array && string.Equals(memberName, "length", StringComparison.OrdinalIgnoreCase))
            {
                return WorkflowExpressionValue.FromNumber(array.Count);
            }

            return null;
        }

        private static WorkflowExpressionValue FromJsonNode(JsonNode? node)
        {
            if (node is null)
            {
                return WorkflowExpressionValue.Null();
            }

            return node switch
            {
                JsonValue value when value.TryGetValue(out double number) => WorkflowExpressionValue.FromNumber(number),
                JsonValue value when value.TryGetValue(out bool boolean) => WorkflowExpressionValue.FromBoolean(boolean),
                JsonValue value when value.TryGetValue(out string? text) => WorkflowExpressionValue.FromString(text ?? string.Empty),
                _ => WorkflowExpressionValue.FromJson(node),
            };
        }

        private static bool TryParseJson(string text, out JsonNode? node)
        {
            node = null;

            if (string.IsNullOrWhiteSpace(text))
            {
                return false;
            }

            try
            {
                node = JsonNode.Parse(text, documentOptions: DocumentOptions);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private double ToNumber(WorkflowExpressionValue value)
        {
            return value.Kind switch
            {
                WorkflowExpressionValueKind.Number => value.NumberValue ?? 0d,
                WorkflowExpressionValueKind.Boolean => (value.BooleanValue ?? false) ? 1d : 0d,
                WorkflowExpressionValueKind.String => double.TryParse(value.StringValue, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed)
                    ? parsed
                    : throw new WorkflowExpressionEvaluationException($"Unable to convert '{value.StringValue}' to number.", "invalid_number"),
                _ => throw new WorkflowExpressionEvaluationException("Value cannot be converted to number.", "invalid_number"),
            };
        }

        private bool ToBoolean(WorkflowExpressionValue value)
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

        private bool AreEqual(WorkflowExpressionValue left, WorkflowExpressionValue right)
        {
            if (left.Kind == WorkflowExpressionValueKind.Number || right.Kind == WorkflowExpressionValueKind.Number)
            {
                return Math.Abs(ToNumber(left) - ToNumber(right)) < double.Epsilon;
            }

            if (left.Kind == WorkflowExpressionValueKind.Boolean || right.Kind == WorkflowExpressionValueKind.Boolean)
            {
                return ToBoolean(left) == ToBoolean(right);
            }

            if (left.Kind == WorkflowExpressionValueKind.Json && right.Kind == WorkflowExpressionValueKind.Json)
            {
                return left.JsonValue?.ToJsonString() == right.JsonValue?.ToJsonString();
            }

            return string.Equals(left.ToDisplayString(), right.ToDisplayString(), StringComparison.Ordinal);
        }

        private void RecordReference(string reference)
        {
            if (!string.IsNullOrWhiteSpace(reference) && _referenceSet.Add(reference))
            {
                _references.Add(reference);
            }
        }
    }
}

internal sealed class WorkflowExpressionEvaluationException : Exception
{
    public WorkflowExpressionEvaluationException(string message, string errorCode)
        : base(message)
    {
        ErrorCode = errorCode;
    }

    public string ErrorCode { get; }
}
