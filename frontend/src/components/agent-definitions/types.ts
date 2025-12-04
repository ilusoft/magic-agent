import type { Edge, Node } from "reactflow";
import type {
  AgentNodeHandlePlacement,
  AgentViewLayoutNode,
  WorkflowHandlePosition,
  WorkflowVariableDataType,
} from "../../types/agents";

export type {
  WorkflowHandlePosition,
  WorkflowVariableDataType,
} from "../../types/agents";

export type NodeKind =
  | "start"
  | "step"
  | "placeholder"
  | "termination"
  | "tool"
  | "variable"
  | "empty";

export interface WorkflowNodeData {
  label: string;
  kind: NodeKind;
  stepName?: string;
  stepType?: StepType;
  handlePlacement?: AgentNodeHandlePlacement;
  onHandlePlacementChange?: (
    handle: keyof AgentNodeHandlePlacement,
    position: WorkflowHandlePosition
  ) => void;
  toolId?: string;
  outcomeName?: string;
  hasSavedPosition?: boolean;
}

export type WorkflowEdgeKind = "outcome" | "tool";

export interface WorkflowEdgeData {
  kind: WorkflowEdgeKind;
  outcomeName?: string;
  sourceStep?: string;
  toolId?: string;
  order?: number;
  controlPoints?: AgentViewLayoutNode[];
  snapEnabled?: boolean;
  onControlPointChange?: (
    edgeId: string,
    index: number,
    position: AgentViewLayoutNode
  ) => void;
  onAddControlPoint?: (
    edgeId: string,
    index: number,
    position: AgentViewLayoutNode
  ) => void;
  onRemoveControlPoint?: (edgeId: string, index: number) => void;
  showHandle?: boolean;
}

export type WorkflowNode = Node<WorkflowNodeData>;
export type WorkflowEdge = Edge<WorkflowEdgeData>;

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface KeyValueEntry {
  id: string;
  key: string;
  value: string;
  dataType?: WorkflowVariableDataType;
}

export type StepType = "agent" | "echo" | "setVariables" | "resetConversation";

export const STEP_TYPE_OPTIONS: StepType[] = [
  "agent",
  "echo",
  "setVariables",
  "resetConversation",
];

export interface StepFormState {
  name: string;
  type: StepType;
  conversationEnabled: boolean;
  parameters: KeyValueEntry[];
  tools: string[];
  variableTypes?: Record<string, WorkflowVariableDataType>;
}

export interface OutcomeFormState {
  sourceStep: string;
  name: string;
  nextStep: string;
  endWorkflow: boolean;
  expression: string;
  order: string;
  executeByDefault: boolean;
}

export interface ExpressionValidationState {
  status: "idle" | "pending" | "valid" | "invalid";
  message?: string | null;
}

export interface ExpressionValidationContextValue {
  type?: WorkflowVariableDataType;
  value?: string | null;
}

export interface ExpressionValidationContextPayload {
  variables?: Record<string, ExpressionValidationContextValue>;
  parameters?: Record<string, ExpressionValidationContextValue>;
  runtimeState?: Record<string, ExpressionValidationContextValue>;
  stepInput?: ExpressionValidationContextValue;
  lastStepOutput?: ExpressionValidationContextValue;
}

export interface ToolFormState {
  id: string;
  type: string;
  name: string;
  serverUrl: string;
  description: string;
  allowedTools: string;
  forwardAuthorizationHeader: boolean;
  authorizationHeaderName: string;
  stopOnToolInitError: boolean;
}

export interface WorkflowFormState {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  deployment: string;
  apiKey: string;
  defaultParameters: KeyValueEntry[];
  streamingEnabled: boolean;
  streamingMode: string;
}
