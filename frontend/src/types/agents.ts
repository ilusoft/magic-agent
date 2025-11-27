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
  defaultParameters: Record<string, string>;
  steps: AgentStepDefinition[];
  tools?: AgentToolDefinition[];
  ViewLayout?: AgentViewLayout;
}

export interface AgentViewLayout {
  nodes?: Record<string, AgentViewLayoutNode>;
  edges?: Record<string, AgentViewLayoutEdge>;
  viewport?: AgentViewLayoutViewport;
}

export interface AgentViewLayoutNode {
  x: number;
  y: number;
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
}

export interface AgentStepOutcomeConditionDefinition {
  type?: string;
  parameters?: Record<string, string>;
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

export interface AgentStepExecutionResult {
  name: string;
  type: string;
  output: string;
  input?: string | null;
  threadContext?: unknown;
  outcome?: string | null;
  nextStep?: string | null;
  endWorkflow?: boolean;
  toolInvocations?: AgentToolCall[];
  toolErrorDetected?: boolean;
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
