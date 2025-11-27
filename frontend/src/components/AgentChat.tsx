import { useEffect, useMemo, useRef } from "react";
import type { AgentMessage } from "../types/agents";

interface AgentChatProps {
  conversation: AgentMessage[];
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  isRunning: boolean;
  runError: string | null;
  disableSend: boolean;
}

export function AgentChat({
  conversation,
  input,
  onInputChange,
  onSend,
  isRunning,
  runError,
  disableSend,
}: AgentChatProps) {
  const displayedMessages = useMemo(() => {
    return [...conversation];
  }, [conversation]);

  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = scrollContainerRef.current;

    if (!container) {
      return;
    }

    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [displayedMessages, isRunning]);

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto pr-1">
        {displayedMessages.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-foreground/70">
            Start a conversation to see the transcript here.
          </div>
        ) : (
          <ul className="space-y-3 pb-4">
            {displayedMessages.map((message, index) => (
              <li
                key={`${index}-${message.role}-${message.timestamp}`}
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`flex max-w-xl flex-col gap-1 rounded-lg border border-border px-3 py-2 text-sm shadow-sm ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : message.role === "system"
                      ? "bg-muted text-foreground"
                      : "bg-card text-foreground"
                  }`}
                >
                  <span
                    className={`text-xs font-semibold uppercase ${
                      message.role === "user"
                        ? "text-primary-foreground/80 text-right"
                        : "text-foreground/60"
                    }`}
                  >
                    {message.role === "system"
                      ? "system (workflow)"
                      : message.role}
                  </span>
                  <div className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm">
                    {message.content}
                  </div>
                  <span
                    className={`text-[11px] ${
                      message.role === "user"
                        ? "text-primary-foreground/70 text-right"
                        : "text-foreground/50"
                    }`}
                  >
                    {new Date(message.timestamp).toLocaleString()}
                  </span>
                </div>
              </li>
            ))}

            {isRunning ? (
              <li className="flex justify-start">
                <TypingIndicator />
              </li>
            ) : null}
          </ul>
        )}
      </div>

      <div className="mt-4 border-t border-border pt-4">
        <label className="mb-2 block text-sm font-medium text-foreground/80">
          Message
        </label>
        <textarea
          className="h-24 w-full resize-none rounded-md border border-border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          placeholder="Ask the agent something…"
        />

        {runError ? (
          <p className="mt-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-sm text-destructive">
            {runError}
          </p>
        ) : null}

        <div className="mt-3 flex justify-end">
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-70"
            onClick={onSend}
            disabled={disableSend || isRunning}
          >
            {isRunning ? "Running…" : "Send message"}
          </button>
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-muted px-3 py-2">
      <span className="sr-only">Agent is responding</span>
      {[0, 1, 2].map((dot) => (
        <span
          key={dot}
          className="h-2 w-2 rounded-full bg-foreground/50 animate-bounce"
          style={{ animationDelay: `${dot * 0.15}s` }}
        />
      ))}
    </div>
  );
}
