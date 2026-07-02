import type { AgentDefinition } from "@/types/agents";

export function renameStepReferences(
  agent: AgentDefinition,
  originalName: string,
  nextName: string
) {
  if (!originalName || !nextName || originalName === nextName) {
    return;
  }

  agent.steps.forEach((step) => {
    step.outcomes?.forEach((outcome) => {
      if (outcome.nextStep === originalName) {
        outcome.nextStep = nextName;
      }
    });
  });

  const oldNodeId = `${agent.id}-${originalName}`;
  const newNodeId = `${agent.id}-${nextName}`;

  if (agent.viewLayout?.nodes) {
    moveLayoutEntry(agent.viewLayout.nodes, oldNodeId, newNodeId);
    moveLayoutEntry(agent.viewLayout.nodes, originalName, nextName);
  }

  if (agent.viewLayout?.edges) {
    renameLayoutEdgeKeys(agent.viewLayout.edges, oldNodeId, newNodeId);
  }
}

function moveLayoutEntry<T>(
  collection: Record<string, T>,
  oldKey: string,
  newKey: string
) {
  if (!collection || oldKey === newKey || !(oldKey in collection)) {
    return;
  }

  collection[newKey] = collection[oldKey];
  delete collection[oldKey];
}

function renameLayoutEdgeKeys(
  edges: Record<string, { controlPoints?: { x: number; y: number }[] }>,
  oldNodeId: string,
  newNodeId: string
) {
  if (!edges || oldNodeId === newNodeId) {
    return;
  }

  Object.entries(edges).forEach(([edgeId, layout]) => {
    if (!edgeId.includes(oldNodeId)) {
      return;
    }

    const updatedKey = edgeId.split(oldNodeId).join(newNodeId);

    if (updatedKey === edgeId) {
      return;
    }

    edges[updatedKey] = layout;
    delete edges[edgeId];
  });
}
