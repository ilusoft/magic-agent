import type { LucideIcon } from "lucide-react";
import {
  ArrowRightLeft,
  Megaphone,
  MessageSquare,
  Variable as VariableIcon,
} from "lucide-react";

import type { StepType } from "./types";

export interface StepTypeVisualConfig {
  type: StepType;
  icon: LucideIcon;
  label: string;
  toolboxLabel: string;
  nodeClass: string;
  iconWrapperClass: string;
  handleColor: string;
}

export const STEP_TYPE_ORDER: StepType[] = [
  "chat",
  "echo",
  "pass-through",
  "setVariables",
];

export const STEP_TYPE_VISUALS: Record<StepType, StepTypeVisualConfig> = {
  chat: {
    type: "chat",
    icon: MessageSquare,
    label: "Chat",
    toolboxLabel: "Chat Step",
    nodeClass: "border-sky-200 bg-sky-50 text-sky-900",
    iconWrapperClass: "bg-sky-100 text-sky-600",
    handleColor: "rgb(59 130 246)",
  },
  echo: {
    type: "echo",
    icon: Megaphone,
    label: "Echo",
    toolboxLabel: "Echo Step",
    nodeClass: "border-amber-200 bg-amber-50 text-amber-900",
    iconWrapperClass: "bg-amber-100 text-amber-600",
    handleColor: "rgb(245 158 11)",
  },
  "pass-through": {
    type: "pass-through",
    icon: ArrowRightLeft,
    label: "Pass-through",
    toolboxLabel: "Pass-through Step",
    nodeClass: "border-violet-200 bg-violet-50 text-violet-900",
    iconWrapperClass: "bg-violet-100 text-violet-600",
    handleColor: "rgb(139 92 246)",
  },
  setVariables: {
    type: "setVariables",
    icon: VariableIcon,
    label: "Variables",
    toolboxLabel: "Variable Block",
    nodeClass: "border-emerald-200 bg-emerald-50 text-emerald-900",
    iconWrapperClass: "bg-emerald-100 text-emerald-600",
    handleColor: "rgb(16 185 129)",
  },
};

export const DEFAULT_STEP_VISUAL: StepTypeVisualConfig = {
  type: "chat",
  icon: MessageSquare,
  label: "Step",
  toolboxLabel: "Step",
  nodeClass: "border-border bg-card text-foreground",
  iconWrapperClass: "bg-muted text-foreground/70",
  handleColor: "rgb(30 64 175)",
};

export function getStepTypeVisual(type?: StepType): StepTypeVisualConfig {
  if (!type) {
    return DEFAULT_STEP_VISUAL;
  }

  return STEP_TYPE_VISUALS[type] ?? DEFAULT_STEP_VISUAL;
}
