import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type EdgeMouseHandler,
  type NodeDragHandler,
  type OnEdgesChange,
  type OnNodesChange,
  useEdgesState,
  useNodesState,
} from "reactflow";

import type {
  AgentDefinitionsDocument,
  AgentViewLayoutViewport,
} from "../../../types/agents";
import type { WorkflowEdge, WorkflowGraph, WorkflowNode } from "../types";
import { WORKFLOW_EDGE_TYPE } from "../workflowGraph";
import { isWorkflowDebugLoggingEnabled } from "../utils/workflowDebug";

const SNAP_GRID_SIZE_VALUE = 16;

export const SNAP_GRID_SIZE = SNAP_GRID_SIZE_VALUE;

export function snapPositionToGrid(position: { x: number; y: number }) {
  return {
    x: Math.round(position.x / SNAP_GRID_SIZE_VALUE) * SNAP_GRID_SIZE_VALUE,
    y: Math.round(position.y / SNAP_GRID_SIZE_VALUE) * SNAP_GRID_SIZE_VALUE,
  };
}

export type ApplyDocumentUpdate = (
  updater: (draft: AgentDefinitionsDocument) => AgentDefinitionsDocument | void
) => void;

declare global {
  interface Window {
    __MAGIC_AGENT_DISABLE_AUTO_SNAP?: boolean;
    __MAGIC_AGENT_DEBUG_LAYOUT?: boolean;
    __MAGIC_AGENT_LAST_LAYOUT_WRITE?: unknown;
  }
}

const isBrowserEnvironment = typeof window !== "undefined";

interface UseWorkflowCanvasOptions {
  graph: WorkflowGraph;
  activeWorkflowId: string | null;
  applyDocumentUpdate: ApplyDocumentUpdate;
  viewport?: AgentViewLayoutViewport | null;
}

function snapNodePosition(node: WorkflowNode, enabled: boolean) {
  if (!enabled) {
    return node.position;
  }

  let snapped = snapPositionToGrid(node.position);

  if (
    typeof node.width === "number" &&
    Number.isFinite(node.width) &&
    node.width > 0
  ) {
    const anchorX = snapped.x + node.width / 2;
    const snappedAnchorX =
      Math.round(anchorX / SNAP_GRID_SIZE_VALUE) * SNAP_GRID_SIZE_VALUE;
    snapped = {
      ...snapped,
      x: snapped.x + (snappedAnchorX - anchorX),
    };
  }

  if (
    typeof node.height === "number" &&
    Number.isFinite(node.height) &&
    node.height > 0
  ) {
    const anchorY = snapped.y + node.height / 2;
    const snappedAnchorY =
      Math.round(anchorY / SNAP_GRID_SIZE_VALUE) * SNAP_GRID_SIZE_VALUE;
    snapped = {
      ...snapped,
      y: snapped.y + (snappedAnchorY - anchorY),
    };
  }

  return snapped;
}

function getLayoutKeysForNode(workflowNode: WorkflowNode): string[] {
  const keys = new Set<string>([workflowNode.id]);

  if (
    (workflowNode.data.kind === "step" ||
      workflowNode.data.kind === "placeholder") &&
    workflowNode.data.stepName
  ) {
    keys.add(workflowNode.data.stepName);
  }

  if (workflowNode.data.kind === "tool" && workflowNode.data.toolId) {
    keys.add(workflowNode.data.toolId);
  }

  return Array.from(keys);
}

function getNodesSignature(nodes: WorkflowNode[]): string {
  return JSON.stringify(
    nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: node.data,
      style: node.style,
      width: node.width,
      height: node.height,
      hidden: node.hidden,
      draggable: node.draggable,
      selectable: node.selectable,
      connectable: node.connectable,
    }))
  );
}

function getEdgesSignature(edges: WorkflowEdge[]): string {
  return JSON.stringify(
    edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      label: edge.label,
      data: edge.data,
      type: edge.type,
    }))
  );
}

export function useWorkflowCanvas({
  graph,
  activeWorkflowId,
  applyDocumentUpdate,
  viewport,
}: UseWorkflowCanvasOptions) {
  const [nodes, setNodes, handleNodesChange] = useNodesState(graph.nodes);
  const [edgesState, setEdgesState, handleEdgesChange] = useEdgesState(
    graph.edges
  );
  const [activeEdgeId, setActiveEdgeId] = useState<string | null>(null);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const workflowDebugLogging = isWorkflowDebugLoggingEnabled();
  const layoutLoggingEnabled =
    workflowDebugLogging ||
    (isBrowserEnvironment && Boolean(window.__MAGIC_AGENT_DEBUG_LAYOUT));
  const lastGraphNodesSignatureRef = useRef<string>("");
  const lastGraphEdgesSignatureRef = useRef<string>("");
  const dirtyNodeIdsRef = useRef<Set<string>>(new Set());
  const lastWorkflowIdRef = useRef<string | null>(null);
  const graphSignature = useMemo(() => {
    const nodesSignature = getNodesSignature(graph.nodes);
    const edgesSignature = getEdgesSignature(graph.edges);
    return `${nodesSignature}|${edgesSignature}`;
  }, [graph.edges, graph.nodes]);
  const persistNodePosition = useCallback(
    (workflowNode: WorkflowNode, position: { x: number; y: number }) => {
      if (!activeWorkflowId || workflowNode.data.kind === "empty") {
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        if (!agent.ViewLayout) {
          agent.ViewLayout = { nodes: {} };
        }

        if (!agent.ViewLayout.nodes) {
          agent.ViewLayout.nodes = {};
        }

        const layoutKeys = getLayoutKeysForNode(workflowNode);
        const allowFallbackCreation = workflowNode.data.kind === "start";
        layoutKeys.forEach((key) => {
          const isPrimaryKey = key === workflowNode.id;
          const keyExists = key in agent.ViewLayout!.nodes!;

          if (!isPrimaryKey && !keyExists && !allowFallbackCreation) {
            return;
          }

          agent.ViewLayout!.nodes![key] = {
            x: position.x,
            y: position.y,
          };
        });

        if (layoutLoggingEnabled) {
          const payload = {
            agentId: agent.id,
            nodeId: workflowNode.id,
            persistedKeys: layoutKeys,
            position,
          };
          console.info("[WorkflowCanvas] Persist node position", payload);

          if (isBrowserEnvironment) {
            window.__MAGIC_AGENT_LAST_LAYOUT_WRITE = payload;
          }
        }

        if (workflowDebugLogging) {
          console.info(
            "[WorkflowCanvas] persistNodePosition updated document",
            {
              workflowId: agent.id,
              startFlags: agent.steps.map((step) => ({
                name: step.name,
                isStartStep: step.isStartStep,
              })),
            }
          );
        }

        return draft;
      });
    },
    [activeWorkflowId, applyDocumentUpdate, workflowDebugLogging]
  );

  useEffect(() => {
    const nodesSignature = getNodesSignature(graph.nodes);
    const edgesSignature = getEdgesSignature(graph.edges);

    if (
      nodesSignature === lastGraphNodesSignatureRef.current &&
      edgesSignature === lastGraphEdgesSignatureRef.current
    ) {
      return;
    }

    if (workflowDebugLogging) {
      const startEdge = graph.edges.find(
        (edge) => edge.data?.sourceStep === "start"
      );

      console.info("[WorkflowCanvas] graph update", {
        workflowId: activeWorkflowId,
        startEdgeTarget: startEdge?.target,
      });
    }

    lastGraphNodesSignatureRef.current = nodesSignature;
    lastGraphEdgesSignatureRef.current = edgesSignature;
    setNodes(graph.nodes);
    setEdgesState(graph.edges);
  }, [graph.edges, graph.nodes, setNodes, setEdgesState]);

  useEffect(() => {
    if (lastWorkflowIdRef.current === (activeWorkflowId ?? null)) {
      return;
    }

    lastWorkflowIdRef.current = activeWorkflowId ?? null;
    lastGraphNodesSignatureRef.current = "";
    dirtyNodeIdsRef.current = new Set();
  }, [activeWorkflowId]);

  useEffect(() => {
    if (!activeWorkflowId) {
      return;
    }

    applyDocumentUpdate((draft) => {
      const agent = draft.agents.find(
        (candidate) => candidate.id === activeWorkflowId
      );

      if (!agent?.ViewLayout) {
        if (workflowDebugLogging) {
          console.info(
            "[WorkflowCanvas] layout cleanup skipped (no ViewLayout)",
            {
              workflowId: activeWorkflowId,
            }
          );
        }
        return draft;
      }

      if (workflowDebugLogging) {
        console.info("[WorkflowCanvas] layout cleanup starting", {
          workflowId: activeWorkflowId,
          startFlags: agent.steps.map((step) => ({
            name: step.name,
            isStartStep: step.isStartStep,
          })),
        });
      }

      let mutated = false;

      if (agent.ViewLayout.nodes) {
        const allowedNodeKeys = new Set<string>();
        graph.nodes.forEach((node) => {
          getLayoutKeysForNode(node).forEach((key) => allowedNodeKeys.add(key));
        });

        Object.keys(agent.ViewLayout.nodes).forEach((key) => {
          if (!allowedNodeKeys.has(key)) {
            delete agent.ViewLayout!.nodes![key];
            mutated = true;
          }
        });

        if (Object.keys(agent.ViewLayout.nodes).length === 0) {
          delete agent.ViewLayout.nodes;
          mutated = true;
        }
      }

      if (agent.ViewLayout.edges) {
        const allowedEdgeKeys = new Set(graph.edges.map((edge) => edge.id));

        Object.keys(agent.ViewLayout.edges).forEach((key) => {
          if (!allowedEdgeKeys.has(key)) {
            delete agent.ViewLayout!.edges![key];
            mutated = true;
          }
        });

        if (Object.keys(agent.ViewLayout.edges).length === 0) {
          delete agent.ViewLayout.edges;
          mutated = true;
        }
      }

      if (
        !agent.ViewLayout.nodes &&
        !agent.ViewLayout.edges &&
        !agent.ViewLayout.viewport
      ) {
        delete agent.ViewLayout;
        mutated = true;
      }

      if (workflowDebugLogging) {
        console.info("[WorkflowCanvas] layout cleanup finished", {
          workflowId: activeWorkflowId,
          mutated,
          startFlags: agent.steps.map((step) => ({
            name: step.name,
            isStartStep: step.isStartStep,
          })),
        });
      }

      return mutated ? draft : draft;
    });
  }, [
    activeWorkflowId,
    applyDocumentUpdate,
    graph.edges,
    graph.nodes,
    workflowDebugLogging,
  ]);

  const updateNodePositionState = useCallback(
    (nodeId: string, position: { x: number; y: number }) => {
      setNodes((current) =>
        current.map((existing) =>
          existing.id === nodeId ? { ...existing, position } : existing
        )
      );
    },
    [setNodes]
  );

  const setNodePosition = useCallback(
    (workflowNode: WorkflowNode, position: { x: number; y: number }) => {
      if (workflowNode.data.kind === "empty") {
        return;
      }

      const snappedPosition = snapNodePosition(
        { ...workflowNode, position },
        snapEnabled
      );

      updateNodePositionState(workflowNode.id, snappedPosition);
      persistNodePosition(workflowNode, snappedPosition);
    },
    [persistNodePosition, snapEnabled, updateNodePositionState]
  );

  const handleEdgeControlPointChange = useCallback(
    (edgeId: string, index: number, position: { x: number; y: number }) => {
      if (!activeWorkflowId) {
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        if (!agent.ViewLayout) {
          agent.ViewLayout = { nodes: {}, edges: {} };
        }

        if (!agent.ViewLayout.edges) {
          agent.ViewLayout.edges = {};
        }

        const existing = agent.ViewLayout.edges[edgeId]?.controlPoints ?? [];
        const next = [...existing];

        if (index >= next.length) {
          next.length = index + 1;
        }

        next[index] = snapEnabled ? snapPositionToGrid(position) : position;

        agent.ViewLayout.edges[edgeId] = {
          controlPoints: next.filter(
            (point): point is { x: number; y: number } => Boolean(point)
          ),
        };

        if (workflowDebugLogging) {
          console.info("[WorkflowCanvas] edge control point change persisted", {
            workflowId: agent.id,
            edgeId,
          });
        }

        return draft;
      });
    },
    [activeWorkflowId, applyDocumentUpdate, snapEnabled, workflowDebugLogging]
  );

  const handleAddEdgeControlPoint = useCallback(
    (edgeId: string, index: number, position: { x: number; y: number }) => {
      if (!activeWorkflowId) {
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        if (!agent.ViewLayout) {
          agent.ViewLayout = { nodes: {}, edges: {} };
        }

        if (!agent.ViewLayout.edges) {
          agent.ViewLayout.edges = {};
        }

        const existing = agent.ViewLayout.edges[edgeId]?.controlPoints ?? [];
        const next = [...existing];

        next.splice(
          index,
          0,
          snapEnabled ? snapPositionToGrid(position) : position
        );

        agent.ViewLayout.edges[edgeId] = {
          controlPoints: next.filter(
            (point): point is { x: number; y: number } => Boolean(point)
          ),
        };

        return draft;
      });
    },
    [activeWorkflowId, applyDocumentUpdate, snapEnabled]
  );

  const handleRemoveEdgeControlPoint = useCallback(
    (edgeId: string, index: number) => {
      if (!activeWorkflowId) {
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent || !agent.ViewLayout?.edges) {
          return draft;
        }

        const existing = agent.ViewLayout.edges[edgeId]?.controlPoints ?? [];

        if (existing.length === 0) {
          return draft;
        }

        const next = [...existing];
        next.splice(index, 1);

        if (next.length > 0) {
          agent.ViewLayout.edges[edgeId] = { controlPoints: next };
        } else {
          delete agent.ViewLayout.edges[edgeId];
        }

        return draft;
      });
    },
    [activeWorkflowId, applyDocumentUpdate]
  );

  const edgesWithHandlers = useMemo(() => {
    return edgesState.map((edge) => ({
      ...edge,
      type: edge.type ?? WORKFLOW_EDGE_TYPE,
      data: {
        ...(edge.data ?? {}),
        controlPoints: edge.data?.controlPoints,
        onControlPointChange: handleEdgeControlPointChange,
        onAddControlPoint: handleAddEdgeControlPoint,
        onRemoveControlPoint: handleRemoveEdgeControlPoint,
        showHandle: activeEdgeId === edge.id,
        snapEnabled,
      },
    }));
  }, [
    edgesState,
    handleEdgeControlPointChange,
    handleAddEdgeControlPoint,
    handleRemoveEdgeControlPoint,
    activeEdgeId,
  ]);

  const handleEdgeMouseEnter = useCallback<EdgeMouseHandler>((_event, edge) => {
    setActiveEdgeId(edge.id);
  }, []);

  const handlePaneClick = useCallback(() => {
    setActiveEdgeId(null);
  }, []);

  const handleNodeDragStop = useCallback<NodeDragHandler>(
    (_event, node) => {
      const workflowNode = node as WorkflowNode;

      if (workflowNode.data.kind === "empty") {
        return;
      }

      const targetPosition = snapNodePosition(workflowNode, snapEnabled);

      updateNodePositionState(workflowNode.id, targetPosition);
      dirtyNodeIdsRef.current.add(workflowNode.id);
      persistNodePosition(workflowNode, targetPosition);
    },
    [persistNodePosition, snapEnabled, updateNodePositionState]
  );

  const toggleActiveEdge = useCallback((edgeId: string | null) => {
    setActiveEdgeId(edgeId);
  }, []);

  const persistViewport = useCallback(
    (nextViewport: AgentViewLayoutViewport) => {
      if (!activeWorkflowId) {
        return;
      }

      applyDocumentUpdate((draft) => {
        const agent = draft.agents.find(
          (candidate) => candidate.id === activeWorkflowId
        );

        if (!agent) {
          return draft;
        }

        if (!agent.ViewLayout) {
          agent.ViewLayout = { nodes: {} };
        }

        agent.ViewLayout.viewport = {
          position: {
            x: nextViewport.position.x,
            y: nextViewport.position.y,
          },
          zoom: nextViewport.zoom,
        };

        return draft;
      });
    },
    [activeWorkflowId, applyDocumentUpdate]
  );

  return {
    nodes,
    edges: edgesWithHandlers as WorkflowEdge[],
    onEdgesChange: handleEdgesChange as OnEdgesChange,
    handleNodesChange: handleNodesChange as OnNodesChange,
    handleNodeDragStop,
    handleEdgeMouseEnter,
    handlePaneClick,
    snapEnabled,
    setSnapEnabled,
    setActiveEdgeId: toggleActiveEdge,
    setNodePosition,
    initialViewport: viewport ?? null,
    handleViewportChange: persistViewport,
    graphSignature,
  };
}
