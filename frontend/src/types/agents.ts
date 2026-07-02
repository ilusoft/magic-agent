export type WorkflowVariableDataType =
  | "string"
  | "number"
  | "dateTime"
  | "json"
  | "boolean";

export interface AgentDefinitionsDocument {
  llmProfiles?: Record<string, AgentLlmProfileDefinition>;
  tools?: Record<string, AgentToolDefinition>;
  agents: AgentDefinition[];
}

export interface AgentLlmProfileDefinition {
  provider: string;
  endpoint?: string;
  deployment?: string;
  apiVersion?: string;
  baseUrl?: string;
  model?: string;
  apiKey?: string;
  headers?: Record<string, string>;
  temperature?: number;
  maxTokens?: number;
}

export interface AgentStepLlmConfig {
  profileId?: string;
  provider?: string;
  endpoint?: string;
  deployment?: string;
  apiVersion?: string;
  baseUrl?: string;
  model?: string;
  apiKey?: string;
  headers?: Record<string, string>;
  temperature?: number;
  maxTokens?: number;
}

export interface AgentDefinition {
  id: string;
  name: string;
  description?: string;
  defaultParameters?: Record<string, string>;
  // Deprecated: LLM config moved to document-level llmProfiles + per-step
  // llmConfig. Kept optional for the in-flight migration; phase 9 removes
  // them once configs/agents/agents.json is migrated.
  endpoint?: string;
  deployment?: string;
  apiKey?: string;
  apiVersion?: string;
  baseUrl?: string;
  model?: string;
  provider?: string;
  steps: AgentStepDefinition[];
  // Deprecated: tool configs moved to document-level tools map; steps
  // reference them by id. Kept optional for the in-flight migration.
  tools?: AgentToolDefinition[];
  viewLayout?: AgentViewLayout;
  streaming?: AgentStreamingOptions;
}

export interface AgentStepDefinition {
  name: string;
  type: string;
  parameters?: Record<string, string>;
  variableTypes?: Record<string, WorkflowVariableDataType>;
  // Deprecated: provider moved into llmConfig (or the referenced
  // profile's provider). Kept optional for the in-flight migration.
  provider?: string;
  // Deprecated: options is unused; kept optional for the in-flight
  // migration.
  options?: Record<string, string>;
  conversation?: AgentStepConversationOptions;
  // References to document-level tool ids. The full tool config
  // lives in the document's `tools` map.
  tools?: string[];
  stopOnToolError?: boolean;
  inputSource?: string;
  outcomes?: AgentStepOutcomeDefinition[];
  isStartStep?: boolean;
  // Per-step LLM override. When set, takes precedence over any
  // workflow-level LLM config (which is gone post-refactor).
  llmConfig?: AgentStepLlmConfig;
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
  allowedTools?: string[];
  actions?: AgentToolActionDefinition[];
  forwardAuthorizationHeader?: boolean;
  authorizationHeaderName?: string;
  stopOnToolInitError?: boolean;
}

export interface AgentToolActionDefinition {
  name: string;
  description?: string;
  parameters?: Record<string, string>;
}

export interface AgentToolAction {
  name: string;
  description?: string;
  parameters?: Record<string, string>;
}

export interface AgentStepOutcome {
  name: string;
  nextStep?: string | null;
  condition?: { expression?: string } | null;
  endWorkflow?: boolean;
  order?: number;
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

export interface AgentViewLayout {
  nodes?: Record<string, AgentViewLayoutNode>;
  edges?: Record<string, AgentViewLayoutEdge>;
  viewport?: AgentViewLayoutViewport;
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    stepName?: string;
    label?: string;
    type?: string;
    toolId?: string;
    [key: string]: unknown;
  };
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
}

export interface AgentStreamingOptions {
  enabled: boolean;
  mode?: string;
}

export interface LLMCallConfig {
  provider?: string;
  model?: string | null;
  endpoint?: string | null;
  baseUrl?: string | null;
  deployment?: string | null;
  apiVersion?: string | null;
  temperature?: number | string | null;
  maxTokens?: number | null;
  apiKeyFingerprint?: string | null;
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

export interface AgentIterationTrace {
  iteration: number;
  content?: string | null;
  toolCallNames: string[];
  hasToolCalls: boolean;
  timestamp: string;
}

export interface AgentStepLiveTrace {
  stepName: string;
  iterations: AgentIterationTrace[];
  toolCalls: AgentToolCall[];
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
