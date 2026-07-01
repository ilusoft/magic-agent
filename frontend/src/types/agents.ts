export type WorkflowVariableDataType =
  | "string"
  | "number"
  | "dateTime"
  | "json"
  | "boolean";

export interface AgentDefinitionsDocument {
  agents: AgentDefinition[];
}

export interface AgentDefinition {
  id: string;
  name: string;
  description?: string;
  endpoint?: string;
  deployment?: string;
  apiKey?: string;
  apiVersion?: string;
  defaultParameters: Record<string, string>;
  steps: AgentStepDefinition[];
  tools?: AgentToolDefinition[];
  ViewLayout?: AgentViewLayout;
  streaming?: AgentStreamingOptions;
}

export interface AgentStreamingOptions {
  enabled?: boolean;
  mode?: string;
}

export interface AgentViewLayout {
  nodes?: Record<string, AgentViewLayoutNode>;
  edges?: Record<string, AgentViewLayoutEdge>;
  viewport?: AgentViewLayoutViewport;
}

export type WorkflowHandlePosition = "top" | "right" | "bottom" | "left";

export interface AgentNodeHandlePlacement {
  input?: WorkflowHandlePosition;
  outcomes?: WorkflowHandlePosition;
  tools?: WorkflowHandlePosition;
}

export interface AgentViewLayoutNode {
  x: number;
  y: number;
  handles?: AgentNodeHandlePlacement;
}

export interface AgentViewLayoutEdge {
  controlPoints?: AgentViewLayoutNode[];
}

export interface AgentViewLayoutViewport {
  position: AgentViewLayoutNode;
  zoom: number;
}

export interface AgentStepDefinition {
  name: string;
  type: string;
  parameters: Record<string, string>;
  variableTypes?: Record<string, WorkflowVariableDataType>;
  conversation?: AgentStepConversationOptions;
  outcomes?: AgentStepOutcomeDefinition[];
  tools?: string[];
  isStartStep?: boolean;
}

export interface AgentStepConversationOptions {
  enabled: boolean;
}

export interface AgentStepOutcomeDefinition {
  name: string;
  nextStep?: string;
  condition?: AgentStepOutcomeConditionDefinition;
  endWorkflow?: boolean;
  order?: number;
}

export interface AgentStepOutcomeConditionDefinition {
  expression?: string;
}

export interface AgentToolDefinition {
  id: string;
  type: string;
  name?: string;
  description?: string;
  serverUrl?: string;
  protocol?: string;
  headers?: Record<string, string>;
  options?: Record<string, string>;
  actions?: AgentToolActionDefinition[];
  allowedTools?: string[];
  forwardAuthorizationHeader?: boolean;
  authorizationHeaderName?: string;
  stopOnToolInitError?: boolean;
}

export interface AgentToolActionDefinition {
  name: string;
  description?: string;
  parameters?: Record<string, string>;
}

export interface AgentMessage {
  role: string;
  content: string;
  timestamp: string;
}

export interface AgentToolCall {
  toolName?: string | null;
  invocationId?: string | null;
  result?: string | null;
  argumentsJson?: string | null;
  errorMessage?: string | null;
  errorDetails?: string | null;
  errorCode?: string | null;
}

export interface LLMCallConfig {
  provider?: string | null;
  model?: string | null;
  endpoint?: string | null;
  baseUrl?: string | null;
  deployment?: string | null;
  apiVersion?: string | null;
  temperature?: number | string | null;
  maxTokens?: number | null;
  apiKeyFingerprint?: string | null;
}

export interface AgentStepExecutionResult {
  name: string;
  type: string;
  output: string;
  input?: string | null;
  resolvedParameters?: Record<string, string>;
  parameterDebug?: Record<string, WorkflowParameterDebugInfo>;
  variableDebug?: Record<string, WorkflowVariableDebugInfo>;
  threadContext?: unknown;
  outcome?: string | null;
  nextStep?: string | null;
  endWorkflow?: boolean;
  toolInvocations?: AgentToolCall[];
  iterations?: AgentIterationTrace[];
  toolErrorDetected?: boolean;
  llmConfig?: LLMCallConfig | null;
}

/**
 * One LLM turn inside an agent step. Mirrors the
 * `AgentIterationTrace` payload emitted by the backend's
 * `agent-iteration` SSE event and persisted on
 * `AgentStepExecutionResult.Iterations`. Used by the trace panel
 * to render the model's intermediate reasoning — including turns
 * where it only requested tools and produced no user-facing text.
 */
export interface AgentIterationTrace {
  iteration: number;
  content?: string | null;
  toolCallNames: string[];
  hasToolCalls: boolean;
  timestamp: string;
}

/**
 * Live SSE trace entries captured for a single step during a run.
 * Mirrors the data the backend emits via `agent-iteration` and
 * `tool-call` events; the UI merges them with the post-run
 * `iterations` / `toolInvocations` arrays when the run finishes.
 */
export interface AgentStepLiveTrace {
  stepName: string;
  iterations: AgentIterationTrace[];
  toolCalls: AgentToolCall[];
  /**
   * When `true` the trace was already persisted to the diagnostics
   * store, so the UI can stop appending live events and render the
   * (authoritative) backend version.
   */
  persisted: boolean;
}


export interface WorkflowVariableDebugInfo {
  rawValue: string;
  convertedValue: string;
  type: WorkflowVariableDataType;
  error?: string | null;
}

export interface WorkflowParameterDebugInfo {
  originalValue: string;
  resolvedValue: string;
  placeholders: string[];
}

export interface AgentRunResult {
  agentId: string;
  status: string;
  steps: AgentStepExecutionResult[];
  conversationId?: string | null;
  completedAt: string;
}

export interface AgentWorkflowResult {
  agentId: string;
  status: string;
  lastStep?: {
    name: string;
    type: string;
    output: string;
    outcome?: string | null;
    nextStep?: string | null;
    endWorkflow?: boolean;
  } | null;
  conversationId?: string | null;
}

export interface AgentConversationDiagnostics {
  conversationId: string;
  runs: AgentRunResult[];
}
