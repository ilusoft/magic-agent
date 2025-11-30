import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Wrench,
} from "lucide-react";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { NodeProps } from "reactflow";
import { Handle, Position } from "reactflow";

import type { WorkflowHandlePosition, WorkflowNodeData } from "./types";

const HANDLE_OPTIONS: {
  value: WorkflowHandlePosition;
  label: string;
  icon: typeof ArrowUp;
}[] = [
  { value: "top", label: "Top", icon: ArrowUp },
  { value: "right", label: "Right", icon: ArrowRight },
  { value: "bottom", label: "Bottom", icon: ArrowDown },
  { value: "left", label: "Left", icon: ArrowLeft },
];

const HANDLE_POSITION_MAP: Record<WorkflowHandlePosition, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
};

const DEFAULT_INPUT_POSITION: WorkflowHandlePosition = "left";

export function WorkflowToolNode({
  data,
  selected,
}: NodeProps<WorkflowNodeData>) {
  const baseClass = clsx(
    "relative flex items-center gap-3 rounded-lg border px-4 py-3 text-sm shadow-sm transition-shadow",
    selected ? "ring-2 ring-primary" : "ring-1 ring-transparent",
    "border-slate-200 bg-slate-50 text-slate-900"
  );
  const canEditHandles = typeof data.onHandlePlacementChange === "function";
  const inputPlacement = data.handlePlacement?.input ?? DEFAULT_INPUT_POSITION;
  const [menuState, setMenuState] = useState<null | {
    x: number;
    y: number;
  }>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const handleContextMenu = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (!canEditHandles) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      setMenuState({ x: event.clientX, y: event.clientY });
    },
    [canEditHandles]
  );

  useEffect(() => {
    if (!menuState) {
      return;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (menuRef.current && menuRef.current.contains(event.target as Node)) {
        return;
      }

      setMenuState(null);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuState(null);
      }
    };

    window.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [menuState]);

  useEffect(() => {
    if (!canEditHandles) {
      setMenuState(null);
    }
  }, [canEditHandles]);

  const handlePlacementChange = useCallback(
    (position: WorkflowHandlePosition) => {
      data.onHandlePlacementChange?.("input", position);
      setMenuState(null);
    },
    [data]
  );

  const menu = useMemo(() => {
    if (!canEditHandles || !menuState) {
      return null;
    }

    return createPortal(
      <div
        className="relative"
        style={{
          position: "fixed",
          top: menuState.y,
          left: menuState.x,
          zIndex: 1200,
        }}
        onContextMenu={(event) => event.preventDefault()}
      >
        <div
          ref={(node) => {
            menuRef.current = node;
          }}
          className="min-w-[160px] rounded-lg border border-border bg-card p-2 text-sm shadow-xl"
        >
          <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-foreground/60">
            Input handle position
          </p>
          <div className="flex flex-col gap-1">
            {HANDLE_OPTIONS.map((option) => {
              const Icon = option.icon;
              const isActive = inputPlacement === option.value;

              return (
                <button
                  key={option.value}
                  type="button"
                  className={clsx(
                    "flex items-center gap-2 rounded px-2 py-1.5 text-left",
                    isActive
                      ? "text-primary"
                      : "text-foreground/80 hover:bg-muted"
                  )}
                  onClick={() => handlePlacementChange(option.value)}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>,
      document.body
    );
  }, [canEditHandles, handlePlacementChange, inputPlacement, menuState]);

  return (
    <>
      <div className={baseClass} onContextMenu={handleContextMenu}>
        <Handle
          id="input"
          type="target"
          position={HANDLE_POSITION_MAP[inputPlacement]}
        />
        <Handle id="output" type="source" position={Position.Right} />

        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-600">
          <Wrench className="h-5 w-5" />
        </span>
        <div className="flex flex-col">
          <span className="text-base font-semibold leading-tight text-foreground">
            {data.label}
          </span>
          <span className="text-xs uppercase tracking-wide text-foreground/70">
            Tool
          </span>
        </div>
      </div>
      {menu}
    </>
  );
}
