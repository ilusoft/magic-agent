using System;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Channels;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace MagicAgent.Api.Application.AgentRunner;

internal sealed class StreamingAgentRunProgressSink : IAgentRunProgressSink, IAsyncDisposable
{
    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpResponse _response;
    private readonly Channel<string> _events;
    private readonly CancellationToken _abortToken;
    private readonly Task _pumpTask;

    private StreamingAgentRunProgressSink(HttpResponse response, CancellationToken abortToken)
    {
        _response = response ?? throw new ArgumentNullException(nameof(response));
        _abortToken = abortToken;
        _events = Channel.CreateUnbounded<string>(new UnboundedChannelOptions
        {
            SingleReader = true,
            SingleWriter = false,
        });

        _pumpTask = Task.Run(PumpAsync);
    }

    internal static StreamingAgentRunProgressSink Create(HttpResponse response, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(response);

        response.StatusCode = StatusCodes.Status200OK;
        response.Headers.CacheControl = "no-cache";
        response.Headers["X-Accel-Buffering"] = "no";
        response.Headers["Connection"] = "keep-alive";
        response.ContentType = "text/event-stream";

        return new StreamingAgentRunProgressSink(response, cancellationToken);
    }

    public async ValueTask StepStartingAsync(string agentId, string stepName, string stepType, int iteration, CancellationToken cancellationToken)
    {
        await EnqueueAsync("step-start", new
        {
            agentId,
            stepName,
            stepType,
            iteration,
        }, cancellationToken).ConfigureAwait(false);
    }

    public async ValueTask StepCompletedAsync(string agentId, AgentStepExecutionResult stepResult, TimeSpan elapsed, CancellationToken cancellationToken)
    {
        await EnqueueAsync("step-complete", new
        {
            agentId,
            step = stepResult,
            elapsedMs = elapsed.TotalMilliseconds,
        }, cancellationToken).ConfigureAwait(false);
    }

    public async ValueTask RunCompletedAsync(AgentRunResult runResult, CancellationToken cancellationToken)
    {
        await EnqueueAsync("run-complete", runResult, cancellationToken).ConfigureAwait(false);
        _events.Writer.TryComplete();
    }

    public async ValueTask IterationAsync(
        string agentId,
        string stepName,
        AgentIterationTrace trace,
        CancellationToken cancellationToken)
    {
        await EnqueueAsync("agent-iteration", new
        {
            agentId,
            stepName,
            iteration = trace.Iteration,
            content = trace.Content,
            toolCallNames = trace.ToolCallNames,
            hasToolCalls = trace.HasToolCalls,
            timestamp = trace.Timestamp,
        }, cancellationToken).ConfigureAwait(false);
    }

    public async ValueTask ToolCallAsync(
        string agentId,
        string stepName,
        AgentToolCall toolCall,
        CancellationToken cancellationToken)
    {
        await EnqueueAsync("tool-call", new
        {
            agentId,
            stepName,
            toolCall,
        }, cancellationToken).ConfigureAwait(false);
    }

    public async ValueTask DisposeAsync()
    {
        _events.Writer.TryComplete();
        try
        {
            await _pumpTask.ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
        }
    }

    private async Task PumpAsync()
    {
        try
        {
            await foreach (var payload in _events.Reader.ReadAllAsync(_abortToken).ConfigureAwait(false))
            {
                await _response.WriteAsync(payload, _abortToken).ConfigureAwait(false);
                await _response.Body.FlushAsync(_abortToken).ConfigureAwait(false);
            }
        }
        catch (OperationCanceledException)
        {
        }
    }

    private ValueTask EnqueueAsync(string eventName, object payload, CancellationToken cancellationToken)
    {
        if (_abortToken.IsCancellationRequested)
        {
            return ValueTask.CompletedTask;
        }

        var json = JsonSerializer.Serialize(payload, SerializerOptions);
        var builder = new StringBuilder();
        builder.Append("event: ").Append(eventName).Append('\n');
        builder.Append("data: ").Append(json).Append("\n\n");
        return _events.Writer.WriteAsync(builder.ToString(), cancellationToken);
    }
}
