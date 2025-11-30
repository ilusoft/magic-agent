import clsx from "clsx";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ChevronRight,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { NodeProps } from "reactflow";
import { Handle, Position } from "reactflow";

import type {
  WorkflowNodeData,
  StepType,
  WorkflowHandlePosition,
} from "./types";
import { getStepTypeVisual } from "./stepTypeVisuals";

const HANDLE_POSITION_MAP: Record<WorkflowHandlePosition, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
};

const HANDLE_OPTIONS: {
  value: WorkflowHandlePosition;
  icon: typeof ArrowUp;
  label: string;
}[] = [
  { value: "top", icon: ArrowUp, label: "Top" },
  { value: "right", icon: ArrowRight, label: "Right" },
  { value: "bottom", icon: ArrowDown, label: "Bottom" },
  { value: "left", icon: ArrowLeft, label: "Left" },
];

type HandleGroup = "input" | "outcomes" | "tools";

const HANDLE_GROUPS: { key: HandleGroup; label: string }[] = [
  { key: "input", label: "Input" },
  { key: "outcomes", label: "Outcomes" },
  { key: "tools", label: "Tools" },
];

const DEFAULT_HANDLE_PLACEMENT: Record<string, WorkflowHandlePosition> = {
  input: "top",
  outcomes: "bottom",
  tools: "right",
};

export function WorkflowStepNode({
  data,
  selected,
}: NodeProps<WorkflowNodeData>) {
  const isPlaceholder = data.kind === "placeholder";
  const visual = getStepTypeVisual(data.stepType as StepType | undefined);
  const Icon = visual.icon;
  const handlePlacement = data.handlePlacement ?? {};
  const inputPlacement =
    handlePlacement.input ?? DEFAULT_HANDLE_PLACEMENT.input;
  const outcomesPlacement =
    handlePlacement.outcomes ?? DEFAULT_HANDLE_PLACEMENT.outcomes;
  const toolsPlacement =
    handlePlacement.tools ?? DEFAULT_HANDLE_PLACEMENT.tools;
  const canEditHandles =
    !isPlaceholder && typeof data.onHandlePlacementChange === "function";
  const [menuState, setMenuState] = useState<null | {
    position: { x: number; y: number };
  }>(null);
  const [activeGroup, setActiveGroup] = useState<HandleGroup>("input");
  const menuRef = useRef<HTMLDivElement | null>(null);

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
    if (!menuState) {
      return;
    }

    setActiveGroup("input");
  }, [menuState]);

  useEffect(() => {
    if (!canEditHandles) {
      setMenuState(null);
    }
  }, [canEditHandles]);

  const handleContextMenu = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (!canEditHandles) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      setMenuState({ position: { x: event.clientX, y: event.clientY } });
    },
    [canEditHandles]
  );

  const handlePlacementChange = useCallback(
    (group: HandleGroup, position: WorkflowHandlePosition) => {
      data.onHandlePlacementChange?.(group, position);
      setMenuState(null);
    },
    [data]
  );

  const handlePlacementValues = useMemo(
    () => ({
      input: inputPlacement,
      outcomes: outcomesPlacement,
      tools: toolsPlacement,
    }),
    [inputPlacement, outcomesPlacement, toolsPlacement]
  );

  const baseClass = clsx(
    "relative flex flex-col gap-3 rounded-lg border px-4 py-3 text-sm shadow-sm transition-shadow",
    selected ? "ring-2 ring-primary" : "ring-1 ring-transparent",
    isPlaceholder
      ? "border-dashed border-border/70 text-foreground/70"
      : visual.nodeClass
  );

  const contentClass = clsx(
    "flex w-full items-center gap-3",
    isPlaceholder ? "justify-center" : "justify-start"
  );

  const menu =
    canEditHandles && menuState
      ? createPortal(
          <div
            className="relative"
            style={{
              position: "fixed",
              top: menuState.position.y,
              left: menuState.position.x,
              zIndex: 1200,
            }}
            onContextMenu={(event) => event.preventDefault()}
          >
            <div
              ref={(node) => {
                menuRef.current = node;
              }}
              className="min-w-[200px] rounded-lg border border-border bg-card p-2 text-sm shadow-xl"
            >
              <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-foreground/60">
                Handle placement
              </p>
              <div className="space-y-1">
                {HANDLE_GROUPS.map((group) => (
                  <div key={group.key} className="relative">
                    <button
                      type="button"
                      className={clsx(
                        "flex w-full items-center justify-between rounded px-2 py-1.5 text-left hover:bg-muted",
                        activeGroup === group.key && "bg-muted"
                      )}
                      onMouseEnter={() => setActiveGroup(group.key)}
                      onFocus={() => setActiveGroup(group.key)}
                    >
                      <span className="text-sm font-medium text-foreground">
                        {group.label}
                      </span>
                      <ChevronRight className="h-4 w-4 text-foreground/50" />
                    </button>

                    {activeGroup === group.key ? (
                      <div className="absolute left-full top-0 ml-1 rounded border border-border bg-card shadow-lg">
                        {HANDLE_OPTIONS.map((option) => {
                          const OptionIcon = option.icon;
                          const isActive =
                            handlePlacementValues[group.key] === option.value;

                          return (
                            <button
                              key={option.value}
                              type="button"
                              className={clsx(
                                "flex min-w-[140px] items-center gap-2 whitespace-nowrap px-3 py-1.5 text-left text-sm",
                                isActive
                                  ? "text-primary"
                                  : "text-foreground/80 hover:bg-muted"
                              )}
                              onClick={() =>
                                handlePlacementChange(group.key, option.value)
                              }
                            >
                              <OptionIcon className="h-3.5 w-3.5" />
                              {option.label}
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          </div>,
          document.body
        )
      : null;

  const contextHint = canEditHandles
    ? "Right-click to change handle placement"
    : undefined;

  return (
    <div
      className={baseClass}
      onContextMenu={handleContextMenu}
      title={contextHint}
    >
      <Handle
        id="input"
        type="target"
        position={HANDLE_POSITION_MAP[inputPlacement]}
        style={{
          background: isPlaceholder ? "rgb(30 64 175)" : visual.handleColor,
        }}
      />
      <Handle
        id="outcomes"
        type="source"
        position={HANDLE_POSITION_MAP[outcomesPlacement]}
        style={{
          background: isPlaceholder ? "rgb(30 64 175)" : visual.handleColor,
        }}
      />
      <Handle
        id="tools"
        type="source"
        position={HANDLE_POSITION_MAP[toolsPlacement]}
        style={{
          background: isPlaceholder ? "rgb(30 64 175)" : visual.handleColor,
        }}
      />

      <div className={contentClass}>
        {isPlaceholder ? (
          <span className="font-medium">{data.label}</span>
        ) : (
          <>
            <span
              className={clsx(
                "flex h-10 w-10 items-center justify-center rounded-full",
                visual.iconWrapperClass
              )}
            >
              <Icon className="h-5 w-5" />
            </span>
            <div className="flex flex-col">
              <span className="text-base font-semibold leading-tight text-foreground">
                {data.label}
              </span>
              <span className="text-xs uppercase tracking-wide text-foreground/70">
                {visual.label}
              </span>
            </div>
          </>
        )}
      </div>
      {menu}
    </div>
  );
}
