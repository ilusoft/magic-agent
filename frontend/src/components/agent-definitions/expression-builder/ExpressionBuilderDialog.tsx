import { Sigma } from "lucide-react";
import {
  type ChangeEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { DialogShell } from "../DialogShell";

interface WorkflowHelperParameterDescriptor {
  name: string;
  type: string;
  description?: string | null;
  optional: boolean;
}

interface WorkflowHelperDescriptor {
  name: string;
  returnType: string;
  description?: string | null;
  parameters: WorkflowHelperParameterDescriptor[];
}

function buildHelpersUrl(apiBaseUrl: string): string {
  const normalized = apiBaseUrl.endsWith("/")
    ? apiBaseUrl.slice(0, -1)
    : apiBaseUrl;
  return `${normalized}/api/workflows/helpers`;
}

function insertTextAtSelection(
  textarea: HTMLTextAreaElement,
  text: string
): { nextValue: string; caret: number } {
  const { selectionStart = 0, selectionEnd = 0, value } = textarea;
  const nextValue =
    value.slice(0, selectionStart) + text + value.slice(selectionEnd);
  const caret = selectionStart + text.length;
  return { nextValue, caret };
}

function wrapWithExpressionEnvelope(text: string): string {
  return `\$\{\{ ${text ?? ""} \}}`;
}

function isWrappedExpression(text: string): boolean {
  const trimmed = text.trim();
  return trimmed.startsWith("${{") && trimmed.endsWith("}}");
}

function unwrapExpressionEnvelope(text: string): string {
  const match = text.match(/^\s*\$\{\{\s*(.*)\s*\}\}\s*$/s);
  return match ? match[1] ?? "" : text;
}

export interface ExpressionBuilderButtonProps {
  value?: string;
  onApply: (value: string) => void;
  apiBaseUrl: string;
  renderTrigger?: (controls: { open: () => void }) => ReactNode;
  mode?: "embedded" | "direct";
}

export function ExpressionBuilderButton({
  value,
  onApply,
  apiBaseUrl,
  renderTrigger,
  mode = "embedded",
}: ExpressionBuilderButtonProps) {
  const [open, setOpen] = useState(false);
  const [expression, setExpression] = useState(value ?? "");
  const [helpers, setHelpers] = useState<WorkflowHelperDescriptor[]>([]);
  const [helpersError, setHelpersError] = useState<string | null>(null);
  const [loadingHelpers, setLoadingHelpers] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const pendingCaretRef = useRef<number | null>(null);
  const isDirectExpression = mode === "direct";

  useEffect(() => {
    if (open) {
      setExpression(value ?? "");
    }
  }, [open, value]);

  useEffect(() => {
    if (!open || helpers.length > 0) {
      return;
    }

    const abortController = new AbortController();

    async function loadHelpers() {
      setLoadingHelpers(true);
      setHelpersError(null);

      try {
        const response = await fetch(buildHelpersUrl(apiBaseUrl), {
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`Failed to load helpers (${response.status})`);
        }

        const payload = (await response.json()) as WorkflowHelperDescriptor[];
        setHelpers(payload ?? []);
      } catch (error) {
        if (abortController.signal.aborted) {
          return;
        }

        const message =
          error instanceof Error ? error.message : "Unable to load helpers.";
        setHelpersError(message);
      } finally {
        if (!abortController.signal.aborted) {
          setLoadingHelpers(false);
        }
      }
    }

    void loadHelpers();

    return () => abortController.abort();
  }, [apiBaseUrl, helpers.length, open]);

  const helperCategories = useMemo(() => {
    return helpers.reduce<Record<string, WorkflowHelperDescriptor[]>>(
      (acc, helper) => {
        const type = helper.returnType || "value";

        if (!acc[type]) {
          acc[type] = [];
        }

        acc[type].push(helper);
        return acc;
      },
      {}
    );
  }, [helpers]);

  const helperTypes = useMemo(
    () => Object.keys(helperCategories),
    [helperCategories]
  );
  const [activeHelperType, setActiveHelperType] = useState<string | null>(null);

  useEffect(() => {
    if (helperTypes.length === 0) {
      setActiveHelperType(null);
      return;
    }

    if (!activeHelperType || !helperCategories[activeHelperType]) {
      setActiveHelperType(helperTypes[0]);
    }
  }, [activeHelperType, helperCategories, helperTypes]);

  const activeHelpers = activeHelperType
    ? helperCategories[activeHelperType] ?? []
    : [];

  const handleInsertHelper = useCallback((helper: WorkflowHelperDescriptor) => {
    const callSignature = `${helper.name}(${helper.parameters
      .map((param) => param.name ?? "value")
      .join(", ")})`;

    const textarea = textareaRef.current;
    if (!textarea) {
      setExpression((previous) => `${previous}${callSignature}`);
      return;
    }

    const { nextValue, caret } = insertTextAtSelection(textarea, callSignature);
    pendingCaretRef.current = caret;
    setExpression(nextValue);
  }, []);

  const handleWrapSelection = useCallback(() => {
    const textarea = textareaRef.current;
    setExpression((current) => {
      if (!textarea) {
        if (isWrappedExpression(current)) {
          return current;
        }
        return wrapWithExpressionEnvelope(current);
      }

      const { selectionStart = 0, selectionEnd = 0 } = textarea;
      const hasSelection = selectionStart !== selectionEnd;

      if (!hasSelection) {
        if (isWrappedExpression(current)) {
          return current;
        }
        const wrapped = wrapWithExpressionEnvelope(current);
        pendingCaretRef.current = wrapped.length;
        return wrapped;
      }

      const before = current.slice(0, selectionStart);
      const selection = current.slice(selectionStart, selectionEnd);
      const after = current.slice(selectionEnd);
      const wrapped = wrapWithExpressionEnvelope(selection);
      pendingCaretRef.current = selectionStart + wrapped.length;
      return `${before}${wrapped}${after}`;
    });
  }, []);

  const handleUnwrapSelection = useCallback(() => {
    const textarea = textareaRef.current;
    setExpression((current) => {
      if (!textarea) {
        return unwrapExpressionEnvelope(current);
      }

      const { selectionStart = 0, selectionEnd = 0 } = textarea;
      const hasSelection = selectionStart !== selectionEnd;

      if (!hasSelection) {
        if (!isWrappedExpression(current)) {
          return current;
        }
        const unwrapped = unwrapExpressionEnvelope(current);
        pendingCaretRef.current = unwrapped.length;
        return unwrapped;
      }

      const before = current.slice(0, selectionStart);
      const selection = current.slice(selectionStart, selectionEnd);
      const after = current.slice(selectionEnd);

      if (!isWrappedExpression(selection)) {
        return current;
      }

      const unwrapped = unwrapExpressionEnvelope(selection);
      pendingCaretRef.current = selectionStart + unwrapped.length;
      return `${before}${unwrapped}${after}`;
    });
  }, []);

  useEffect(() => {
    if (pendingCaretRef.current == null) {
      return;
    }

    const caret = pendingCaretRef.current;
    pendingCaretRef.current = null;

    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(caret, caret);
    });
  }, [expression]);

  const applyExpression = useCallback(() => {
    onApply(expression);
    setOpen(false);
  }, [expression, onApply]);

  const toggleDialog = () => setOpen((previous) => !previous);
  const openDialog = () => setOpen(true);

  const trigger = renderTrigger ? (
    renderTrigger({ open: openDialog })
  ) : (
    <button
      type="button"
      className="rounded-md border border-border px-2 py-1 text-xs text-foreground/70 hover:bg-muted"
      title="Open expression builder"
      onClick={toggleDialog}
    >
      <Sigma className="h-3.5 w-3.5" />
    </button>
  );

  return (
    <>
      {trigger}
      {open ? (
        <DialogShell
          title="Expression Builder"
          open={open}
          onClose={() => {
            setOpen(false);
            setExpression(value ?? "");
          }}
          contentClassName="max-w-5xl w-full max-h-[90vh]"
        >
          <div className="flex flex-col gap-2 text-sm">
            <p className="text-xs text-foreground/60">
              {isDirectExpression ? (
                <>
                  {
                    "This field expects a raw expression that evaluates to a boolean. Enter the expression directly without wrapping it in "
                  }
                  <code className="rounded bg-muted px-1 text-[11px]">
                    {"${{ … }}"}
                  </code>
                  {
                    ". You can combine comparisons (==, !=, >, >=, <, <=) with logical operators such as "
                  }
                  <code className="rounded bg-muted px-1 text-[11px]">&&</code>
                  {" and "}
                  <code className="rounded bg-muted px-1 text-[11px]">||</code>
                  {". For dates, helpers like "}
                  <code className="rounded bg-muted px-1 text-[11px]">
                    stringToDate()
                  </code>
                  {" or "}
                  <code className="rounded bg-muted px-1 text-[11px]">
                    dateDiff()
                  </code>
                  {" let you build boolean comparisons."}
                </>
              ) : (
                <>
                  {"Write expressions using "}
                  <code className="rounded bg-muted px-1 text-[11px]">
                    {"${{ … }}"}
                  </code>
                  {
                    " syntax. Insert helper functions or reference workflow data using the tips below."
                  }
                </>
              )}
            </p>

            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase text-foreground/60">
                Expression
              </label>
              <textarea
                ref={textareaRef}
                className="h-48 w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                value={expression}
                onChange={(event: ChangeEvent<HTMLTextAreaElement>) =>
                  setExpression(event.target.value)
                }
                placeholder="abs(var.value) + param.scale"
              />
            </div>

            <div className="grid gap-4 lg:grid-cols-[2fr_1fr] items-stretch">
              <div className="flex h-full flex-col space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase text-foreground/60">
                    Helper functions
                  </span>
                  {loadingHelpers ? (
                    <span className="text-[11px] text-foreground/60">
                      Loading…
                    </span>
                  ) : null}
                </div>

                {helpersError ? (
                  <p className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
                    {helpersError}
                  </p>
                ) : helpers.length === 0 ? (
                  <p className="text-xs text-foreground/60">
                    {loadingHelpers
                      ? "Loading helpers…"
                      : "No helpers available."}
                  </p>
                ) : (
                  <div className="flex-1 rounded-md border border-border/60 bg-card/60 p-3">
                    <div className="flex flex-wrap gap-2">
                      {helperTypes.map((type) => (
                        <button
                          key={type}
                          type="button"
                          className={`rounded-md border px-2 py-1 text-[11px] font-semibold uppercase ${
                            activeHelperType === type
                              ? "border-primary text-primary"
                              : "border-border/70 text-foreground/70"
                          }`}
                          onClick={() => setActiveHelperType(type)}
                        >
                          {`Returns ${type}`}
                        </button>
                      ))}
                    </div>

                    <div className="mt-3 max-h-72 overflow-y-auto space-y-1 pr-1">
                      {activeHelpers.length === 0 ? (
                        <p className="text-xs text-foreground/60">
                          No helpers available for this type.
                        </p>
                      ) : (
                        activeHelpers.map((helper) => (
                          <div key={helper.name}>
                            <div className="flex flex-wrap gap-1">
                              <button
                                type="button"
                                className="rounded-md border border-border/70 bg-background px-2 py-1 text-[11px] font-semibold text-foreground/80 hover:bg-muted my-1"
                                onClick={() => handleInsertHelper(helper)}
                                title={
                                  helper.description ?? `Insert ${helper.name}`
                                }
                              >
                                {helper.name}
                              </button>
                              {helper.description ? (
                                <p className="ml-4 text-[11px] text-foreground/60 py-2">
                                  {helper.description}
                                </p>
                              ) : null}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className="flex h-full flex-col space-y-2">
                {!isDirectExpression ? (
                  <div className="flex flex-nowrap items-center justify-between gap-2">
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-1 text-[11px] font-semibold text-primary hover:bg-primary/10"
                      onClick={handleWrapSelection}
                    >
                      Wrap selection with {"${{ … }}"}
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-border px-3 py-1 text-[11px] font-semibold text-foreground/80 hover:bg-muted"
                      onClick={handleUnwrapSelection}
                    >
                      Unwrap selection
                    </button>
                  </div>
                ) : null}
                <div className="flex-1 rounded-md border border-dashed border-border/70 bg-muted/40 p-3 text-xs text-foreground/70">
                  <p className="font-semibold text-foreground/80">Tips</p>
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    <li>
                      Reference workflow parameters with
                      <code className="ml-1 rounded bg-muted px-1 text-[11px]">
                        {"param.someKey"}
                      </code>
                      .
                    </li>
                    <li>
                      Use
                      <code className="ml-1 rounded bg-muted px-1 text-[11px]">
                        {"var.variableName"}
                      </code>
                      for previously set variables.
                    </li>
                    <li>
                      <code className="rounded bg-muted px-1 text-[11px]">
                        input
                      </code>
                      {" and "}
                      <code className="rounded bg-muted px-1 text-[11px]">
                        lastOutput
                      </code>
                      {" are always available."}
                    </li>
                    {isDirectExpression ? (
                      <li>
                        {"Combine comparisons (e.g. "}
                        <code className="rounded bg-muted px-1 text-[11px]">
                          var.score &gt; 10
                        </code>
                        {", "}
                        <code className="rounded bg-muted px-1 text-[11px]">
                          var.date &gt; stringToDate('2025-01-02')
                        </code>
                        {") with logical operators such as "}
                        <code className="rounded bg-muted px-1 text-[11px]">
                          &&
                        </code>
                        {" or "}
                        <code className="rounded bg-muted px-1 text-[11px]">
                          ||
                        </code>
                        {" to build boolean expressions."}
                      </li>
                    ) : null}
                    {!isDirectExpression ? (
                      <li>
                        Use the wrap / unwrap controls alongside the helper list
                        to quickly add or remove the expression envelope.
                      </li>
                    ) : null}
                  </ul>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded-md border border-border px-3 py-1.5 text-sm text-foreground/70 hover:bg-muted"
                onClick={() => {
                  setOpen(false);
                  setExpression(value ?? "");
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
                onClick={applyExpression}
              >
                Apply expression
              </button>
            </div>
          </div>
        </DialogShell>
      ) : null}
    </>
  );
}
