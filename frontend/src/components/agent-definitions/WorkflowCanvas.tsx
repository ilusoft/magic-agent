import { useCallback, useEffect, useRef } from "react";
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
  onNodeDoubleClick: NodeMouseHandler;
  onEdgeClick: EdgeMouseHandler;
  onEdgeMouseEnter: EdgeMouseHandler;
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
  onNodeDoubleClick,
  onEdgeClick,
  onEdgeMouseEnter,
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

  useEffect(() => {
    const revisionChanged =
      viewportRevision !== undefined &&
      viewportRevision !== lastViewportRevisionRef.current;

    if (initialFitRef.current && !revisionChanged) {
      return;
    }

    if (initialViewport) {
      initialFitRef.current = true;
      reactFlow.setViewport({
        x: initialViewport.position.x,
        y: initialViewport.position.y,
        zoom: initialViewport.zoom,
      });
    } else {
      initialFitRef.current = true;
      reactFlow.fitView({ padding: 0.2, duration: 0 });
    }

    if (viewportRevision !== undefined) {
      lastViewportRevisionRef.current = viewportRevision;
    }
  }, [initialViewport, reactFlow, viewportRevision]);

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
        reactFlow.fitView({
          nodes: [latestNode],
          padding: 0.3,
          duration: 400,
        });
        return;
      }

      const { zoom } = reactFlow.getViewport();
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

      onViewportChange({
        position: { x: viewport.x, y: viewport.y },
        zoom: viewport.zoom,
      });
    },
    [onViewportChange]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      nodesConnectable={false}
      elementsSelectable={false}
      snapToGrid={snapEnabled}
      snapGrid={[SNAP_GRID_SIZE, SNAP_GRID_SIZE]}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeDoubleClick={onNodeDoubleClick}
      onEdgeClick={onEdgeClick}
      onEdgeMouseEnter={onEdgeMouseEnter}
      onNodeDragStop={onNodeDragStop}
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
