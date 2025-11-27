import clsx from "clsx";
import type { KeyboardEvent } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import type { AgentDefinition } from "../../types/agents";

interface WorkflowAgentTabsProps {
  agents: AgentDefinition[];
  activeWorkflowId: string | null;
  onSelect: (agentId: string) => void;
  onKeyDown: (
    agentId: string
  ) => (event: KeyboardEvent<HTMLDivElement>) => void;
  onEdit: (agent: AgentDefinition) => void;
  onRemove: (
    agentId: string
  ) => (event: React.MouseEvent<HTMLButtonElement>) => void;
  onCreate: () => void;
}

export function WorkflowAgentTabs({
  agents,
  activeWorkflowId,
  onSelect,
  onKeyDown,
  onEdit,
  onRemove,
  onCreate,
}: WorkflowAgentTabsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {agents.map((agent) => (
        <div key={agent.id} className="flex items-center">
          <div
            role="button"
            tabIndex={0}
            onClick={() => onSelect(agent.id)}
            onKeyDown={onKeyDown(agent.id)}
            className={clsx(
              "flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
              activeWorkflowId === agent.id
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-card text-foreground/80 hover:bg-muted/60"
            )}
            title={agent.name?.trim() ? agent.name : agent.id}
          >
            <span className="truncate">
              {agent.name?.trim() ? agent.name : agent.id}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-md border border-transparent text-foreground/70 transition-colors hover:bg-muted"
                onClick={(event) => {
                  event.stopPropagation();
                  onEdit(agent);
                }}
                title="Edit Workflow"
              >
                <Pencil className="h-3.5 w-3.5" />
                <span className="sr-only">Edit workflow</span>
              </button>
              <button
                type="button"
                className="flex h-7 w-7 items-center justify-center rounded-md border border-transparent text-foreground/70 transition-colors hover:bg-destructive/10 hover:text-destructive"
                onClick={(event) => {
                  event.stopPropagation();
                  onRemove(agent.id)(event);
                }}
                title="Remove Workflow"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span className="sr-only">Remove workflow</span>
              </button>
            </div>
          </div>
        </div>
      ))}
      <button
        type="button"
        className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-card text-foreground/80 transition-colors hover:bg-muted"
        onClick={onCreate}
        title="New Workflow"
      >
        <Plus className="h-4 w-4" />
        <span className="sr-only">New Workflow</span>
      </button>
    </div>
  );
}
