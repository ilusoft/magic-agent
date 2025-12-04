import type { LucideIcon } from "lucide-react";
import {
  Bot,
  Megaphone,
  RefreshCcw,
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
  "agent",
  "echo",
  "setVariables",
  "resetConversation",
];

export const STEP_TYPE_VISUALS: Record<StepType, StepTypeVisualConfig> = {
  agent: {
    type: "agent",
    icon: Bot,
    label: "Agent",
    toolboxLabel: "Agent Step",
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
  setVariables: {
    type: "setVariables",
    icon: VariableIcon,
    label: "Variables",
    toolboxLabel: "Variable Block",
    nodeClass: "border-emerald-200 bg-emerald-50 text-emerald-900",
    iconWrapperClass: "bg-emerald-100 text-emerald-600",
    handleColor: "rgb(16 185 129)",
  },
  resetConversation: {
    type: "resetConversation",
    icon: RefreshCcw,
    label: "Reset Conversation",
    toolboxLabel: "Reset Conversation",
    nodeClass: "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-900",
    iconWrapperClass: "bg-fuchsia-100 text-fuchsia-600",
    handleColor: "rgb(217 70 239)",
  },
};

export const DEFAULT_STEP_VISUAL: StepTypeVisualConfig = {
  type: "agent",
  icon: Bot,
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
