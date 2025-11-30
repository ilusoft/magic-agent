import type { CSSProperties } from "react";
import type {
  AgentDefinition,
  AgentViewLayoutEdge,
  AgentViewLayoutNode,
} from "../../types/agents";
import type {
  WorkflowEdge,
  WorkflowGraph,
  WorkflowNode,
  StepType,
} from "./types";
import { isWorkflowDebugLoggingEnabled } from "./utils/workflowDebug";

export const WORKFLOW_EDGE_TYPE = "workflowEdge";

const VERTICAL_SPACING = 160;
const HORIZONTAL_SPACING = 220;

const START_NODE_STYLE: CSSProperties = {
  backgroundColor: "rgba(34, 197, 94, 0.15)",
  border: "2px solid rgba(34, 197, 94, 0.4)",
  color: "rgb(22, 101, 52)",
  width: 50,
  height: 50,
  borderRadius: "9999px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 600,
  textAlign: "center",
  padding: 12,
};

const TERMINATION_NODE_STYLE: CSSProperties = {
  backgroundColor: "rgba(239, 68, 68, 0.12)",
  border: "2px solid rgba(239, 68, 68, 0.4)",
  color: "rgb(153, 27, 27)",
  width: 50,
  height: 50,
  borderRadius: "9999px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 600,
  textAlign: "center",
  padding: 12,
};

const START_NODE_WIDTH =
  typeof START_NODE_STYLE.width === "number" ? START_NODE_STYLE.width : 50;
const START_NODE_HEIGHT =
  typeof START_NODE_STYLE.height === "number" ? START_NODE_STYLE.height : 50;
const TERMINATION_NODE_WIDTH =
  typeof TERMINATION_NODE_STYLE.width === "number"
    ? TERMINATION_NODE_STYLE.width
    : 50;
const TERMINATION_NODE_HEIGHT =
  typeof TERMINATION_NODE_STYLE.height === "number"
    ? TERMINATION_NODE_STYLE.height
    : 50;

export function buildWorkflowGraph(agent: AgentDefinition): WorkflowGraph {
  const nodes: WorkflowNode[] = [];
  const edges: WorkflowEdge[] = [];
  const workflowDebugLogging = isWorkflowDebugLoggingEnabled();

  if (!agent.steps || agent.steps.length === 0) {
    nodes.push({
      id: `${agent.id}-empty`,
      position: { x: 0, y: 0 },
      data: { label: "No steps defined", kind: "empty" },
      type: "input",
    });

    return { nodes, edges };
  }

  const stepNames = new Set(agent.steps.map((step) => step.name));
  const stepPositions = new Map(
    agent.steps.map((step, index) => [step.name, index])
  );
  const stepByName = new Map(agent.steps.map((step) => [step.name, step]));
  const incomingByStep = new Map<string, number[]>();
  const stepColumns = new Map<string, number>();
  const layoutPositions: Record<string, AgentViewLayoutNode> =
    agent.ViewLayout?.nodes ?? {};
  const layoutEdges: Record<string, AgentViewLayoutEdge> =
    agent.ViewLayout?.edges ?? {};
  const nodeIds = new Set<string>();
  const placeholderNodes = new Map<string, string>();
  const terminationNodes = new Map<string, string>();

  agent.steps.forEach((step) => {
    const sourceIndex = stepPositions.get(step.name);

    if (sourceIndex === undefined) {
      return;
    }

    if (!Array.isArray(step.outcomes)) {
      return;
    }

    step.outcomes.forEach((outcome) => {
      if (!outcome.nextStep) {
        return;
      }

      const entries = incomingByStep.get(outcome.nextStep);

      if (entries) {
        entries.push(sourceIndex);
      } else {
        incomingByStep.set(outcome.nextStep, [sourceIndex]);
      }
    });
  });

  const startNodeId = `${agent.id}-start`;
  const startPosition =
    layoutPositions[startNodeId] ??
    layoutPositions["start"] ??
    layoutPositions[agent.id];
  const resolvedStartPosition = startPosition
    ? { x: startPosition.x, y: startPosition.y }
    : { x: 0, y: 0 };
  const startNodeHasSavedPosition = Boolean(startPosition);

  if (workflowDebugLogging) {
    console.log("[WorkflowGraph] Start node layout", {
      agentId: agent.id,
      startNodeId,
      availableKeys: Object.keys(layoutPositions).filter(
        (key) => key.includes("start") || key === agent.id
      ),
      chosenPosition: resolvedStartPosition,
    });
  }

  nodes.push({
    id: startNodeId,
    position: resolvedStartPosition,
    data: {
      label: "Start",
      kind: "start",
      hasSavedPosition: startNodeHasSavedPosition,
    },
    type: "input",
    style: START_NODE_STYLE,
    width: START_NODE_WIDTH,
    height: START_NODE_HEIGHT,
  });
  nodeIds.add(startNodeId);

  const flaggedStartStep = agent.steps.find((step) => step.isStartStep);
  const fallbackStartStep = flaggedStartStep ?? agent.steps[0];
  const desiredStartTargetStepName = fallbackStartStep?.name ?? null;

  if (workflowDebugLogging) {
    console.log("[WorkflowGraph] desired start edge", {
      workflowId: agent.id,
      desiredStartTargetStepName,
    });
  }

  agent.steps.forEach((step, index) => {
    const nodeId = `${agent.id}-${step.name}`;

    if (!nodeIds.has(nodeId)) {
      const savedLayoutNode =
        layoutPositions[nodeId] ?? layoutPositions[step.name];
      const hasSavedPosition = Boolean(savedLayoutNode);
      const targetIndex = stepPositions.get(step.name) ?? index;
      const incoming = incomingByStep.get(step.name) ?? [];
      const requiresOffset = incoming.some(
        (sourceIndex) => sourceIndex < targetIndex - 1
      );
      const column = savedLayoutNode
        ? savedLayoutNode.x / HORIZONTAL_SPACING
        : requiresOffset
        ? 2
        : 1;
      const clampedColumn = Number.isFinite(column) && column >= 0 ? column : 1;
      const defaultX = HORIZONTAL_SPACING * clampedColumn;
      const defaultY = index * VERTICAL_SPACING;
      const position = savedLayoutNode
        ? { x: savedLayoutNode.x, y: savedLayoutNode.y }
        : { x: defaultX, y: defaultY };

      nodes.push({
        id: nodeId,
        position,
        data: {
          label: step.name,
          kind: "step",
          stepName: step.name,
          stepType: step.type as StepType,
          handlePlacement: savedLayoutNode?.handles,
          hasSavedPosition,
        },
        type: "step",
      });
      nodeIds.add(nodeId);
      stepColumns.set(step.name, position.x / HORIZONTAL_SPACING);
    }
    if (Array.isArray(step.tools) && step.tools.length > 0) {
      step.tools.forEach((toolId) => {
        const trimmedToolId = toolId?.trim();

        if (!trimmedToolId) {
          return;
        }

        const toolNodeId = `${agent.id}-tool-${trimmedToolId}`;

        const edgeId = `${nodeId}-tool-${trimmedToolId}`;
        const layoutEdge = layoutEdges[edgeId];

        edges.push({
          id: edgeId,
          source: nodeId,
          sourceHandle: "tools",
          target: toolNodeId,
          type: WORKFLOW_EDGE_TYPE,
          data: {
            kind: "tool",
            sourceStep: step.name,
            toolId: trimmedToolId,
            controlPoints: layoutEdge?.controlPoints,
          },
          style: {
            strokeDasharray: "4 4",
            strokeWidth: 1.5,
          },
        });
      });
    }
  });

  if (desiredStartTargetStepName) {
    const targetNodeId = `${agent.id}-${desiredStartTargetStepName}`;
    const edgeId = `${startNodeId}-${targetNodeId}`;
    const layoutEdge = layoutEdges[edgeId];

    if (nodeIds.has(targetNodeId)) {
      edges.push({
        id: edgeId,
        source: startNodeId,
        target: targetNodeId,
        targetHandle: "input",
        type: WORKFLOW_EDGE_TYPE,
        label: "start",
        data: {
          kind: "outcome",
          outcomeName: "start",
          sourceStep: "start",
          controlPoints: layoutEdge?.controlPoints,
        },
      });
    }
  }

  agent.steps.forEach((step) => {
    const nodeId = `${agent.id}-${step.name}`;

    if (!Array.isArray(step.outcomes)) {
      return;
    }

    step.outcomes.forEach((outcome, outcomeIndex) => {
      const normalizedOrder =
        typeof outcome.order === "number" && outcome.order > 0
          ? outcome.order
          : outcomeIndex + 1;
      const outcomeLabelParts: string[] = [];

      if (normalizedOrder) {
        outcomeLabelParts.push(String(normalizedOrder));
      }

      if (outcome.name) {
        outcomeLabelParts.push(outcome.name);
      }

      const outcomeLabel = outcomeLabelParts.length
        ? outcomeLabelParts.join(" - ")
        : "outcome";

      let targetId: string;

      if (outcome.nextStep) {
        const normalizedTarget = `${agent.id}-${outcome.nextStep}`;

        if (!stepNames.has(outcome.nextStep)) {
          if (!placeholderNodes.has(outcome.nextStep)) {
            placeholderNodes.set(outcome.nextStep, normalizedTarget);
            const savedLayoutNode =
              layoutPositions[normalizedTarget] ??
              layoutPositions[outcome.nextStep];
            const hasSavedPosition = Boolean(savedLayoutNode);
            nodes.push({
              id: normalizedTarget,
              position: savedLayoutNode
                ? { x: savedLayoutNode.x, y: savedLayoutNode.y }
                : {
                    x: HORIZONTAL_SPACING * 2,
                    y:
                      (placeholderNodes.size + terminationNodes.size) *
                      VERTICAL_SPACING,
                  },
              data: {
                label: `${outcome.nextStep} (missing)`,
                kind: "placeholder",
                stepName: outcome.nextStep,
                hasSavedPosition,
              },
              type: "step",
            });
            nodeIds.add(normalizedTarget);
          }
        } else if (!nodeIds.has(normalizedTarget)) {
          const stepIndex = stepPositions.get(outcome.nextStep) ?? 0;
          const savedPosition =
            layoutPositions[normalizedTarget] ??
            layoutPositions[outcome.nextStep];
          const hasSavedPosition = Boolean(savedPosition);
          const column = savedPosition
            ? savedPosition.x / HORIZONTAL_SPACING
            : stepColumns.get(outcome.nextStep) ?? 1;
          const position = savedPosition
            ? { x: savedPosition.x, y: savedPosition.y }
            : {
                x: HORIZONTAL_SPACING * column,
                y: stepIndex * VERTICAL_SPACING,
              };
          const targetStep = stepByName.get(outcome.nextStep);
          nodes.push({
            id: normalizedTarget,
            position,
            data: {
              label: `${outcome.nextStep}`,
              kind: "step",
              stepName: outcome.nextStep,
              stepType: targetStep?.type as StepType | undefined,
              handlePlacement: savedPosition?.handles,
              hasSavedPosition,
            },
            type: "step",
          });
          nodeIds.add(normalizedTarget);
          stepColumns.set(outcome.nextStep, position.x / HORIZONTAL_SPACING);
        }

        targetId = normalizedTarget;
      } else {
        const endKey = outcome.name ?? `end-${outcomeIndex}`;

        if (!terminationNodes.has(endKey)) {
          const terminationId = `${agent.id}-termination-${endKey}`;
          terminationNodes.set(endKey, terminationId);
          const savedPosition =
            layoutPositions[terminationId] ?? layoutPositions[endKey];
          const hasSavedPosition = Boolean(savedPosition);
          nodes.push({
            id: terminationId,
            position: savedPosition ?? {
              x: HORIZONTAL_SPACING * 2.5,
              y: terminationNodes.size * VERTICAL_SPACING,
            },
            data: {
              label: "End",
              kind: "termination",
              hasSavedPosition,
            },
            type: "output",
            style: TERMINATION_NODE_STYLE,
            width: TERMINATION_NODE_WIDTH,
            height: TERMINATION_NODE_HEIGHT,
          });
          nodeIds.add(terminationId);
        }

        targetId = terminationNodes.get(endKey) as string;
      }

      const edgeId = `${nodeId}-${outcome.name ?? outcomeIndex}`;
      const layoutEdge = layoutEdges[edgeId];

      edges.push({
        id: edgeId,
        source: nodeId,
        sourceHandle: "outcomes",
        target: targetId,
        targetHandle: nodeIds.has(targetId) ? "input" : undefined,
        type: WORKFLOW_EDGE_TYPE,
        label: outcomeLabel,
        data: {
          kind: "outcome",
          outcomeName: outcome.name ?? undefined,
          sourceStep: step.name,
          order: normalizedOrder,
          controlPoints: layoutEdge?.controlPoints,
        },
      });
    });
  });

  if (Array.isArray(agent.tools) && agent.tools.length > 0) {
    agent.tools.forEach((tool, index) => {
      const nodeId = `${agent.id}-tool-${tool.id}`;

      if (nodeIds.has(nodeId)) {
        return;
      }

      const savedLayoutNode =
        layoutPositions[nodeId] ?? layoutPositions[tool.id];
      const hasSavedPosition = Boolean(savedLayoutNode);
      nodes.push({
        id: nodeId,
        position: savedLayoutNode
          ? { x: savedLayoutNode.x, y: savedLayoutNode.y }
          : {
              x: HORIZONTAL_SPACING * 3.5,
              y: index * VERTICAL_SPACING,
            },
        data: {
          label: tool.name ?? tool.id,
          kind: "tool",
          toolId: tool.id,
          hasSavedPosition,
          handlePlacement: savedLayoutNode?.handles,
        },
        type: "tool",
      });
      nodeIds.add(nodeId);
    });
  }

  return { nodes, edges };
}
