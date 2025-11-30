import { useCallback, useEffect, useMemo, useRef } from "react";
import ReactFlow, {
  Background,
  ControlButton,
  Controls,
  MiniMap,
  type OnEdgesChange,
  type OnNodesChange,
  type OnMoveEnd,
  useReactFlow,
} from "reactflow";
import type {
  EdgeMouseHandler,
  NodeDragHandler,
  NodeMouseHandler,
} from "reactflow";
import clsx from "clsx";
import type { AgentViewLayoutViewport } from "../../types/agents";
import type {
  WorkflowEdge,
  WorkflowEdgeData,
  WorkflowNode,
  WorkflowNodeData,
} from "./types";
import { SNAP_GRID_SIZE } from "./hooks/useWorkflowCanvas";
import { Grid3x3, SquareIcon } from "lucide-react";

export interface WorkflowCanvasProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  nodeTypes: any;
  edgeTypes: any;
  snapEnabled: boolean;
  onToggleSnap: () => void;
  onNodesChange: OnNodesChange;
  onEdgesChange?: OnEdgesChange;
  onNodeClick?: NodeMouseHandler;
  onNodeDoubleClick: NodeMouseHandler;
  onEdgeClick: EdgeMouseHandler;
  onEdgeDoubleClick?: EdgeMouseHandler;
  onEdgeMouseEnter: EdgeMouseHandler;
  onNodeDragStart?: NodeDragHandler;
  onNodeDragStop: NodeDragHandler;
  onPaneClick: () => void;
  onNodePositionRequest?: (
    node: WorkflowNode,
    position: { x: number; y: number }
  ) => void;
  initialViewport?: AgentViewLayoutViewport | null;
  viewportRevision?: number;
  onViewportChange?: (viewport: AgentViewLayoutViewport) => void;
  activeWorkflowId: string | null;
}

export function WorkflowCanvas({
  nodes,
  edges,
  nodeTypes,
  edgeTypes,
  snapEnabled,
  onToggleSnap,
  onNodesChange,
  onEdgesChange,
  onNodeClick,
  onNodeDoubleClick,
  onEdgeClick,
  onEdgeDoubleClick,
  onEdgeMouseEnter,
  onNodeDragStart,
  onNodeDragStop,
  onPaneClick,
  onNodePositionRequest,
  initialViewport,
  viewportRevision,
  onViewportChange,
  activeWorkflowId,
}: WorkflowCanvasProps) {
  const reactFlow = useReactFlow<WorkflowNodeData, WorkflowEdgeData>();
  const autoPlacementBaselineIdsRef = useRef<Set<string>>(new Set());
  const baselineCapturedRef = useRef(false);
  const initialFitRef = useRef(false);
  const lastViewportRevisionRef = useRef<number | null>(null);
  const focusRequestRef = useRef<number | null>(null);
  const placementIndexRef = useRef(0);
  const workflowRef = useRef<string | null>(null);
  const lastEdgesSignatureRef = useRef<string>("");
  const lastAppliedViewportSignatureRef = useRef<string | null>(null);
  const skipNextViewportPersistRef = useRef(false);
  const isDraggingNodeRef = useRef(false);
  const nodeDragSuppressClickRef = useRef(false);
  const nodeDragSuppressFrameRef = useRef<number | null>(null);
  const nodeDragStartPositionRef = useRef<
    Map<string, { x: number; y: number }>
  >(new Map());
  const CLICK_MOVE_THRESHOLD = 2;

  useEffect(() => {
    return () => {
      if (nodeDragSuppressFrameRef.current !== null) {
        cancelAnimationFrame(nodeDragSuppressFrameRef.current);
        nodeDragSuppressFrameRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (workflowRef.current === (activeWorkflowId ?? null)) {
      return;
    }

    workflowRef.current = activeWorkflowId ?? null;
    autoPlacementBaselineIdsRef.current = new Set();
    baselineCapturedRef.current = false;
    placementIndexRef.current = 0;
    initialFitRef.current = false;
  }, [activeWorkflowId]);

  const nodesReady = nodes.length > 0;
  const initialViewportTransform = useMemo(() => {
    if (!initialViewport) {
      return undefined;
    }

    return {
      x: initialViewport.position.x,
      y: initialViewport.position.y,
      zoom: initialViewport.zoom,
    };
  }, [initialViewport]);

  useEffect(() => {
    if (!nodesReady) {
      return;
    }

    const revisionChanged =
      viewportRevision !== undefined &&
      viewportRevision !== lastViewportRevisionRef.current;
    const viewportSignature = initialViewport
      ? `${initialViewport.position.x}:${initialViewport.position.y}:${initialViewport.zoom}`
      : "fit";
    const viewportChanged =
      viewportSignature !== lastAppliedViewportSignatureRef.current;

    if (!revisionChanged && !viewportChanged && initialFitRef.current) {
      return;
    }

    if (initialViewportTransform) {
      skipNextViewportPersistRef.current = true;
      reactFlow.setViewport(initialViewportTransform);
    } else {
      skipNextViewportPersistRef.current = true;
      reactFlow.fitView({ padding: 0.2, duration: 0 });
    }

    initialFitRef.current = true;
    lastAppliedViewportSignatureRef.current = viewportSignature;

    if (viewportRevision !== undefined) {
      lastViewportRevisionRef.current = viewportRevision;
    }
  }, [
    activeWorkflowId,
    initialViewportTransform,
    nodesReady,
    reactFlow,
    viewportRevision,
  ]);

  useEffect(() => {
    if (nodes.length === 0) {
      return;
    }

    if (!baselineCapturedRef.current) {
      autoPlacementBaselineIdsRef.current = new Set(
        nodes.map((node) => node.id)
      );
      baselineCapturedRef.current = true;
      return;
    }

    const allowedKinds = new Set(["step", "tool", "start", "termination"]);
    const currentIds = new Set(nodes.map((node) => node.id));

    autoPlacementBaselineIdsRef.current.forEach((id) => {
      if (!currentIds.has(id)) {
        autoPlacementBaselineIdsRef.current.delete(id);
      }
    });

    const targetNode = nodes.find((node) => {
      if (autoPlacementBaselineIdsRef.current.has(node.id)) {
        return false;
      }

      if (node.data?.hasSavedPosition) {
        autoPlacementBaselineIdsRef.current.add(node.id);
        return false;
      }

      return allowedKinds.has(node.data?.kind);
    });

    if (!targetNode) {
      return;
    }

    autoPlacementBaselineIdsRef.current.add(targetNode.id);

    if (onNodePositionRequest) {
      const { x: viewportX, y: viewportY, zoom } = reactFlow.getViewport();
      const topLeft = {
        x: -viewportX / zoom,
        y: -viewportY / zoom,
      };
      const nextIndex = placementIndexRef.current;
      placementIndexRef.current = (placementIndexRef.current + 1) % 4;
      const desiredPosition = {
        x: topLeft.x + 120,
        y: topLeft.y + 120 + nextIndex * 140,
      };
      onNodePositionRequest(targetNode, desiredPosition);
    }

    const focusNewNode = () => {
      const latestNode = reactFlow.getNode(targetNode.id);

      if (latestNode) {
        skipNextViewportPersistRef.current = true;
        reactFlow.fitView({
          nodes: [latestNode],
          padding: 0.3,
          duration: 400,
        });
        return;
      }

      const { zoom } = reactFlow.getViewport();
      skipNextViewportPersistRef.current = true;
      reactFlow.setCenter(targetNode.position.x, targetNode.position.y, {
        zoom,
        duration: 400,
      });
    };

    focusRequestRef.current = window.requestAnimationFrame(focusNewNode);

    return () => {
      if (focusRequestRef.current !== null) {
        cancelAnimationFrame(focusRequestRef.current);
        focusRequestRef.current = null;
      }
    };
  }, [nodes, onNodePositionRequest, reactFlow]);

  useEffect(() => {
    const signature = JSON.stringify(
      edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        label: edge.label,
        type: edge.type,
        data: edge.data
          ? {
              kind: edge.data.kind,
              outcomeName: edge.data.outcomeName,
              sourceStep: edge.data.sourceStep,
              toolId: edge.data.toolId,
              showHandle: edge.data.showHandle,
              controlPoints: edge.data.controlPoints,
            }
          : undefined,
      }))
    );

    if (signature === lastEdgesSignatureRef.current) {
      return;
    }

    lastEdgesSignatureRef.current = signature;
    reactFlow.setEdges(edges);
  }, [edges, reactFlow]);

  const handleViewportChangeInternal = useCallback<OnMoveEnd>(
    (_event, viewport) => {
      if (!viewport || !onViewportChange) {
        return;
      }

      if (skipNextViewportPersistRef.current) {
        skipNextViewportPersistRef.current = false;
        return;
      }

      onViewportChange({
        position: { x: viewport.x, y: viewport.y },
        zoom: viewport.zoom,
      });
    },
    [onViewportChange]
  );

  const scheduleNodeClickRelease = useCallback(() => {
    nodeDragSuppressClickRef.current = true;

    if (nodeDragSuppressFrameRef.current !== null) {
      cancelAnimationFrame(nodeDragSuppressFrameRef.current);
    }

    nodeDragSuppressFrameRef.current = window.requestAnimationFrame(() => {
      nodeDragSuppressClickRef.current = false;
      nodeDragSuppressFrameRef.current = null;
    });
  }, []);

  const handleNodeDragStartInternal = useCallback<NodeDragHandler>(
    (event, node, dragHandle) => {
      isDraggingNodeRef.current = true;
      const position = node.position ?? node.positionAbsolute ?? { x: 0, y: 0 };
      nodeDragStartPositionRef.current.set(node.id, {
        x: position.x,
        y: position.y,
      });

      if (onNodeDragStart) {
        onNodeDragStart(event, node, dragHandle);
      }
    },
    [onNodeDragStart]
  );

  const handleNodeDragStopInternal = useCallback<NodeDragHandler>(
    (event, node, dragHandle) => {
      isDraggingNodeRef.current = false;
      const startPosition = nodeDragStartPositionRef.current.get(node.id);
      nodeDragStartPositionRef.current.delete(node.id);
      const currentPosition = node.position ??
        node.positionAbsolute ?? {
          x: 0,
          y: 0,
        };
      const deltaX = Math.abs(
        currentPosition.x - (startPosition?.x ?? currentPosition.x)
      );
      const deltaY = Math.abs(
        currentPosition.y - (startPosition?.y ?? currentPosition.y)
      );
      const movedSignificantly =
        deltaX > CLICK_MOVE_THRESHOLD || deltaY > CLICK_MOVE_THRESHOLD;

      if (!movedSignificantly) {
        return;
      }

      scheduleNodeClickRelease();
      onNodeDragStop(event, node, dragHandle);
    },
    [onNodeDragStop, scheduleNodeClickRelease]
  );

  const handleNodeClickInternal = useCallback<NodeMouseHandler>(
    (event, node) => {
      if (!onNodeClick) {
        return;
      }

      if (nodeDragSuppressClickRef.current || isDraggingNodeRef.current) {
        return;
      }

      onNodeClick(event, node);
    },
    [onNodeClick]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      defaultViewport={initialViewportTransform}
      nodesConnectable={false}
      snapToGrid={snapEnabled}
      snapGrid={[SNAP_GRID_SIZE, SNAP_GRID_SIZE]}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClickInternal}
      onNodeDoubleClick={onNodeDoubleClick}
      onEdgeClick={onEdgeClick}
      onEdgeDoubleClick={onEdgeDoubleClick}
      onEdgeMouseEnter={onEdgeMouseEnter}
      onNodeDragStart={handleNodeDragStartInternal}
      onNodeDragStop={handleNodeDragStopInternal}
      onPaneClick={onPaneClick}
      onMoveEnd={handleViewportChangeInternal}
    >
      <MiniMap pannable zoomable />
      <Controls>
        <ControlButton
          onClick={onToggleSnap}
          title={snapEnabled ? "Disable snap to grid" : "Enable snap to grid"}
          aria-label={
            snapEnabled ? "Disable snap to grid" : "Enable snap to grid"
          }
          className={clsx(
            "transition-colors",
            snapEnabled ? "text-primary" : "text-foreground"
          )}
        >
          {snapEnabled ? (
            <Grid3x3 className="h-4 w-4" />
          ) : (
            <SquareIcon className="h-4 w-4" />
          )}
        </ControlButton>
      </Controls>
      <Background gap={16} color="hsl(var(--muted-foreground))" />
    </ReactFlow>
  );
}
