import type { Edge, Node } from "reactflow";
import type { AgentViewLayoutNode } from "../../types/agents";

export type NodeKind =
  | "start"
  | "step"
  | "placeholder"
  | "termination"
  | "tool"
  | "empty";

export interface WorkflowNodeData {
  label: string;
  kind: NodeKind;
  stepName?: string;
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
}

export type StepType = "chat" | "echo" | "pass-through";

export const STEP_TYPE_OPTIONS: StepType[] = ["chat", "echo", "pass-through"];

export interface StepFormState {
  name: string;
  type: StepType;
  conversationEnabled: boolean;
  parameters: KeyValueEntry[];
  tools: string[];
}

export interface OutcomeFormState {
  sourceStep: string;
  name: string;
  nextStep: string;
  endWorkflow: boolean;
  conditionType: string;
  conditionParameters: KeyValueEntry[];
  order: string;
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
}
