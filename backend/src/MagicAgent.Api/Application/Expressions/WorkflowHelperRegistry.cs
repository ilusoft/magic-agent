using System.Collections.Concurrent;
using System.Globalization;
using System.Reflection;
using System.Text.Json.Nodes;

namespace MagicAgent.Api.Application.Expressions;

public sealed class WorkflowHelperRegistry : IWorkflowHelperRegistry
{
    private readonly ConcurrentDictionary<string, HelperInvoker> _helpers;
    private readonly IReadOnlyList<WorkflowHelperDescriptor> _descriptors;

    public WorkflowHelperRegistry(IEnumerable<Type> helperTypes)
    {
        if (helperTypes is null)
        {
            throw new ArgumentNullException(nameof(helperTypes));
        }

        var helpers = new List<HelperInvoker>();

        foreach (var type in helperTypes)
        {
            if (type is null || !type.IsClass || !(type.IsAbstract && type.IsSealed))
            {
                continue;
            }

            foreach (var method in type.GetMethods(BindingFlags.Public | BindingFlags.Static))
            {
                var attribute = method.GetCustomAttribute<WorkflowHelperAttribute>();
                if (attribute is null)
                {
                    continue;
                }

                helpers.Add(CreateInvoker(attribute, method));
            }
        }

        _helpers = new ConcurrentDictionary<string, HelperInvoker>(StringComparer.OrdinalIgnoreCase);
        foreach (var helper in helpers)
        {
            _helpers.TryAdd(helper.Name, helper);
        }

        _descriptors = helpers
            .Select(h => new WorkflowHelperDescriptor(h.Name, h.ReturnType, h.Description, h.Parameters))
            .ToArray();
    }

    public IReadOnlyList<WorkflowHelperDescriptor> GetDescriptors() => _descriptors;

    public bool TryInvoke(
        string helperName,
        IReadOnlyList<WorkflowExpressionValue> arguments,
        out WorkflowExpressionValue? result,
        out string? errorMessage,
        CancellationToken cancellationToken = default)
    {
        result = null;
        errorMessage = null;

        if (string.IsNullOrWhiteSpace(helperName))
        {
            errorMessage = "Helper name must be provided.";
            return false;
        }

        if (!_helpers.TryGetValue(helperName, out var invoker))
        {
            errorMessage = $"Helper '{helperName}' was not found.";
            return false;
        }

        try
        {
            result = invoker.Invoke(arguments, cancellationToken);
            return true;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            errorMessage = ex.Message;
            return false;
        }
    }

    private static HelperInvoker CreateInvoker(WorkflowHelperAttribute attribute, MethodInfo method)
    {
        var parameters = method.GetParameters();
        var metadataAttributes = method.GetCustomAttributes<WorkflowHelperParameterAttribute>().ToList();

        var descriptors = parameters
            .Select(p =>
            {
                var metadata = metadataAttributes.FirstOrDefault(attr =>
                    string.Equals(attr.ParameterName, p.Name, StringComparison.OrdinalIgnoreCase));

                var name = metadata?.DisplayName ?? p.Name ?? "param";
                var type = metadata?.Type ?? MapParameterType(p.ParameterType);
                var description = metadata?.Description;
                var optional = metadata?.IsOptional ?? p.IsOptional;

                return new WorkflowHelperParameterDescriptor(name, type, description, optional);
            })
            .ToArray();

        return new HelperInvoker(
            attribute.Name,
            attribute.Description,
            attribute.ReturnType,
            descriptors,
            method);
    }

    private static WorkflowExpressionValueKind MapParameterType(Type type)
    {
        if (type == typeof(double) || type == typeof(float) || type == typeof(decimal))
        {
            return WorkflowExpressionValueKind.Number;
        }

        if (type == typeof(bool))
        {
            return WorkflowExpressionValueKind.Boolean;
        }

        if (type == typeof(string))
        {
            return WorkflowExpressionValueKind.String;
        }

        return WorkflowExpressionValueKind.Json;
    }

    private sealed record HelperInvoker(
        string Name,
        string? Description,
        WorkflowExpressionValueKind ReturnType,
        IReadOnlyList<WorkflowHelperParameterDescriptor> Parameters,
        MethodInfo MethodInfo)
    {
        public WorkflowExpressionValue Invoke(
            IReadOnlyList<WorkflowExpressionValue> arguments,
            CancellationToken cancellationToken)
        {
            var parameterInfos = MethodInfo.GetParameters();
            var coercedArgs = new object?[parameterInfos.Length];

            for (var i = 0; i < parameterInfos.Length; i++)
            {
                var expected = parameterInfos[i];
                WorkflowExpressionValue? provided = i < arguments.Count ? arguments[i] : null;

                coercedArgs[i] = ConvertArgument(expected.ParameterType, provided);
            }

            var result = MethodInfo.Invoke(null, coercedArgs);

            return ReturnType switch
            {
                WorkflowExpressionValueKind.Number => WorkflowExpressionValue.FromNumber(Convert.ToDouble(result, CultureInfo.InvariantCulture)),
                WorkflowExpressionValueKind.Boolean => WorkflowExpressionValue.FromBoolean(Convert.ToBoolean(result, CultureInfo.InvariantCulture)),
                WorkflowExpressionValueKind.Json => WorkflowExpressionValue.FromJson(result switch
                {
                    JsonNode node => node,
                    string s when !string.IsNullOrWhiteSpace(s) => JsonNode.Parse(s),
                    _ => null,
                }),
                WorkflowExpressionValueKind.Null => WorkflowExpressionValue.Null(),
                WorkflowExpressionValueKind.DateTime => result is DateTimeOffset dto
                    ? WorkflowExpressionValue.FromDateTime(dto)
                    : WorkflowExpressionValue.FromDateTime(Convert.ToDateTime(result, CultureInfo.InvariantCulture)),
                _ => WorkflowExpressionValue.FromString(result?.ToString()),
            };
        }

        private static object? ConvertArgument(Type expectedType, WorkflowExpressionValue? provided)
        {
            if (provided is null)
            {
                return expectedType.IsValueType ? Activator.CreateInstance(expectedType) : null;
            }

            if (expectedType == typeof(double) || expectedType == typeof(float) || expectedType == typeof(decimal))
            {
                var number = provided.Kind switch
                {
                    WorkflowExpressionValueKind.Number => provided.NumberValue ?? 0d,
                    WorkflowExpressionValueKind.Boolean => (provided.BooleanValue ?? false) ? 1d : 0d,
                    WorkflowExpressionValueKind.String => double.TryParse(provided.StringValue, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed)
                        ? parsed
                        : 0d,
                    _ => 0d,
                };

                if (expectedType == typeof(float))
                {
                    return (float)number;
                }

                if (expectedType == typeof(decimal))
                {
                    return Convert.ToDecimal(number, CultureInfo.InvariantCulture);
                }

                return number;
            }

            if (expectedType == typeof(int))
            {
                return (int)Math.Round(provided.NumberValue ?? 0d, MidpointRounding.ToEven);
            }

            if (expectedType == typeof(bool))
            {
                return provided.Kind switch
                {
                    WorkflowExpressionValueKind.Boolean => provided.BooleanValue ?? false,
                    WorkflowExpressionValueKind.Number => Math.Abs(provided.NumberValue ?? 0d) > double.Epsilon,
                    WorkflowExpressionValueKind.String => bool.TryParse(provided.StringValue, out var parsed) && parsed,
                    _ => false,
                };
            }

            if (expectedType == typeof(WorkflowExpressionValue))
            {
                return provided;
            }

            if (expectedType == typeof(JsonNode))
            {
                if (provided.Kind == WorkflowExpressionValueKind.Json)
                {
                    return provided.JsonValue;
                }

                if (!string.IsNullOrWhiteSpace(provided.StringValue))
                {
                    return JsonNode.Parse(provided.StringValue!);
                }

                return null;
            }

            if (expectedType == typeof(string))
            {
                return provided.ToDisplayString();
            }

            return provided.ToDisplayString();
        }
    }
}
