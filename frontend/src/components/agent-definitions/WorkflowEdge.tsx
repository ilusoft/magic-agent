import {
  BaseEdge,
  EdgeLabelRenderer,
  type EdgeProps,
  useReactFlow,
} from "reactflow";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { AgentViewLayoutNode } from "../../types/agents";
import type { WorkflowEdgeData } from "./types";

const HANDLE_SIZE = 14;

export const WorkflowGraphEdge = memo(
  ({
    id,
    sourceX,
    sourceY,
    targetX,
    targetY,
    markerEnd,
    label,
    style,
    data,
  }: EdgeProps<WorkflowEdgeData>) => {
    const reactFlow = useReactFlow();
    const fallbackControlPoint = useMemo(
      () => ({
        x: (sourceX + targetX) / 2,
        y: (sourceY + targetY) / 2,
      }),
      [sourceX, sourceY, targetX, targetY]
    );

    const controlPoints = useMemo(() => {
      if (data?.controlPoints && data.controlPoints.length > 0) {
        return data.controlPoints;
      }

      return [fallbackControlPoint];
    }, [data?.controlPoints, fallbackControlPoint]);

    const [dragPoint, setDragPoint] = useState<{
      index: number;
      position: AgentViewLayoutNode;
    } | null>(null);
    const latestPositionRef = useRef<AgentViewLayoutNode>(fallbackControlPoint);
    const latestIndexRef = useRef<number>(0);
    const moveListenerRef = useRef<((event: PointerEvent) => void) | null>(
      null
    );
    const upListenerRef = useRef<((event: PointerEvent) => void) | null>(null);
    const [menuState, setMenuState] = useState<null | {
      index: number;
      client: { x: number; y: number };
      flowPosition: AgentViewLayoutNode;
    }>(null);
    const menuRef = useRef<HTMLDivElement | null>(null);

    const effectiveControlPoints = useMemo(() => {
      if (dragPoint) {
        const next = [...controlPoints];
        next[dragPoint.index] = dragPoint.position;
        return next;
      }

      return controlPoints;
    }, [controlPoints, dragPoint]);

    useEffect(() => {
      if (!dragPoint) {
        latestPositionRef.current = fallbackControlPoint;
        latestIndexRef.current = 0;
      }
    }, [dragPoint, fallbackControlPoint]);

    const cleanupListeners = useCallback(() => {
      if (moveListenerRef.current) {
        window.removeEventListener("pointermove", moveListenerRef.current);
        moveListenerRef.current = null;
      }

      if (upListenerRef.current) {
        window.removeEventListener("pointerup", upListenerRef.current);
        upListenerRef.current = null;
      }
    }, []);

    const stopDragging = useCallback(() => {
      cleanupListeners();
      setDragPoint(null);

      if (
        data?.onControlPointChange &&
        typeof latestIndexRef.current === "number"
      ) {
        data.onControlPointChange(
          id,
          latestIndexRef.current,
          latestPositionRef.current
        );
      }
    }, [cleanupListeners, data, id]);

    useEffect(
      () => () => {
        cleanupListeners();
      },
      [cleanupListeners]
    );

    const handlePointerDown = useCallback(
      (event: ReactPointerEvent<HTMLDivElement>, index: number) => {
        if (event.button !== 0) {
          return;
        }

        event.preventDefault();
        event.stopPropagation();

        const initial = reactFlow.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
        setDragPoint({ index, position: initial });
        latestPositionRef.current = initial;
        latestIndexRef.current = index;

        const handleMove = (moveEvent: PointerEvent) => {
          moveEvent.preventDefault();
          const projected = reactFlow.screenToFlowPosition({
            x: moveEvent.clientX,
            y: moveEvent.clientY,
          });
          latestPositionRef.current = projected;
          latestIndexRef.current = index;
          setDragPoint({ index, position: projected });
        };

        const handleUp = () => {
          stopDragging();
        };

        moveListenerRef.current = handleMove;
        upListenerRef.current = handleUp;

        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
      },
      [reactFlow, stopDragging]
    );

    const extendedPoints = useMemo(() => {
      return [
        { x: sourceX, y: sourceY },
        ...effectiveControlPoints,
        { x: targetX, y: targetY },
      ];
    }, [sourceX, sourceY, targetX, targetY, effectiveControlPoints]);

    const path = useMemo(() => {
      if (extendedPoints.length < 2) {
        return "";
      }

      const [, ...rest] = extendedPoints;
      return rest.reduce(
        (acc, point) => `${acc} L ${point.x},${point.y}`,
        `M ${extendedPoints[0].x},${extendedPoints[0].y}`
      );
    }, [extendedPoints]);

    const labelPosition = useMemo(() => {
      if (extendedPoints.length < 2) {
        return { x: sourceX, y: sourceY };
      }

      const midIndex = Math.floor((extendedPoints.length - 1) / 2);
      const start = extendedPoints[midIndex];
      const end = extendedPoints[midIndex + 1];

      return {
        x: (start.x + end.x) / 2,
        y: (start.y + end.y) / 2,
      };
    }, [extendedPoints, sourceX, sourceY]);

    const handleContextMenu = useCallback(
      (event: React.MouseEvent<HTMLDivElement>, index: number) => {
        event.preventDefault();
        event.stopPropagation();

        const flowPosition = reactFlow.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });

        setMenuState({
          index,
          client: { x: event.clientX, y: event.clientY },
          flowPosition,
        });
      },
      [reactFlow]
    );

    useEffect(() => {
      const handlePointerDownOutside = (event: PointerEvent) => {
        if (event.button !== 0) {
          return;
        }

        if (menuRef.current?.contains(event.target as Node)) {
          return;
        }

        setMenuState(null);
      };

      window.addEventListener("pointerdown", handlePointerDownOutside);

      return () => {
        window.removeEventListener("pointerdown", handlePointerDownOutside);
      };
    }, []);

    const handleAddPoint = useCallback(() => {
      if (!data?.onAddControlPoint || !menuState) {
        return;
      }

      data.onAddControlPoint(id, menuState.index + 1, menuState.flowPosition);
      setMenuState(null);
    }, [data, id, menuState]);

    const handleRemovePoint = useCallback(() => {
      if (!data?.onRemoveControlPoint || !menuState) {
        return;
      }

      data.onRemoveControlPoint(id, menuState.index);
      setMenuState(null);
    }, [data, id, menuState]);

    return (
      <>
        <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} />

        {label ? (
          <EdgeLabelRenderer>
            <div
              style={{
                position: "absolute",
                transform: `translate(-50%, -50%) translate(${labelPosition.x}px, ${labelPosition.y}px)`,
                pointerEvents: "none",
                backgroundColor: "rgba(0, 0, 0, 0.04)",
                padding: "2px 6px",
                borderRadius: 9999,
                fontSize: 11,
                fontWeight: 600,
                color: "hsl(var(--foreground))",
              }}
            >
              {label}
            </div>
          </EdgeLabelRenderer>
        ) : null}

        {data?.showHandle
          ? effectiveControlPoints.map((point, index) => (
              <EdgeLabelRenderer key={`handle-${index}`}>
                <div
                  style={{
                    position: "absolute",
                    transform: `translate(-50%, -50%) translate(${point.x}px, ${point.y}px)`,
                    pointerEvents: "all",
                  }}
                >
                  <div
                    role="button"
                    aria-label="Move edge"
                    onPointerDown={(event) => handlePointerDown(event, index)}
                    onContextMenu={(event) => handleContextMenu(event, index)}
                    style={{
                      width: HANDLE_SIZE,
                      height: HANDLE_SIZE,
                      borderRadius: "9999px",
                      border: "1.5px solid hsl(var(--primary))",
                      backgroundColor: "hsl(var(--background))",
                      boxShadow: "0 4px 8px rgba(0, 0, 0, 0.15)",
                      cursor: dragPoint ? "grabbing" : "grab",
                    }}
                  />
                </div>
              </EdgeLabelRenderer>
            ))
          : null}

        {menuState
          ? createPortal(
              <div
                ref={(node) => {
                  menuRef.current = node;
                }}
                style={{
                  position: "fixed",
                  top: menuState.client.y,
                  left: menuState.client.x,
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 6,
                  boxShadow: "0 8px 16px rgba(0,0,0,0.15)",
                  padding: 4,
                  zIndex: 1000,
                  minWidth: 140,
                }}
                onClick={(event) => event.stopPropagation()}
              >
                <button
                  type="button"
                  onClick={handleAddPoint}
                  className="block w-full rounded px-3 py-1 text-left text-sm hover:bg-muted"
                >
                  Add segment
                </button>
                <button
                  type="button"
                  onClick={handleRemovePoint}
                  className="block w-full rounded px-3 py-1 text-left text-sm hover:bg-muted"
                  disabled={effectiveControlPoints.length <= 1}
                >
                  Remove segment
                </button>
              </div>,
              document.body
            )
          : null}
      </>
    );
  }
);

WorkflowGraphEdge.displayName = "WorkflowGraphEdge";
