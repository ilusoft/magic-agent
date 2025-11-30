import { useCallback, useEffect, useMemo, useState } from "react";
import { ReactFlowProvider, type EdgeTypes } from "reactflow";
import type { EdgeMouseHandler, NodeMouseHandler, NodeTypes } from "reactflow";
import "reactflow/dist/style.css";
import type { AgentDefinitionsDocument } from "../types/agents";
import { StepDialog } from "../components/agent-definitions/StepDialog";
import { ToolDialog } from "../components/agent-definitions/ToolDialog";
import { OutcomeDialog } from "../components/agent-definitions/OutcomeDialog";
import {
  WORKFLOW_EDGE_TYPE,
  buildWorkflowGraph,
} from "../components/agent-definitions/workflowGraph";
import { WorkflowStepNode } from "../components/agent-definitions/WorkflowStepNode";
import { WorkflowToolNode } from "../components/agent-definitions/WorkflowToolNode";
import type {
  WorkflowEdge,
  WorkflowGraph,
  WorkflowNode,
} from "../components/agent-definitions/types";
import { WorkflowStepSelectorDialog } from "../components/agent-definitions/OutcomeCreationPrompt";
import { useWorkflowActions } from "../components/agent-definitions/hooks/useWorkflowActions";
import { useAgentDefinitionsDocument } from "../components/agent-definitions/hooks/useAgentDefinitionsDocument";
import { useWorkflowSelection } from "../components/agent-definitions/hooks/useWorkflowSelection";
import { useStepSelectionFlow } from "../components/agent-definitions/hooks/useStepSelectionFlow";
import { WorkflowDialog } from "../components/agent-definitions/WorkflowDialog";
import { WorkflowGraphEdge } from "../components/agent-definitions/WorkflowEdge";
import { WorkflowHeader } from "../components/agent-definitions/WorkflowHeader";
import { WorkflowCanvas } from "../components/agent-definitions/WorkflowCanvas";
import { useWorkflowCanvas } from "../components/agent-definitions/hooks/useWorkflowCanvas";
import { WorkflowAgentTabs } from "../components/agent-definitions/WorkflowAgentTabs";
import { WorkflowJsonEditor } from "../components/agent-definitions/WorkflowJsonEditor";
import { WorkflowBuilderPanel } from "../components/agent-definitions/WorkflowBuilderPanel";
import { Plus } from "lucide-react";
import { useWorkflowDialogs } from "../components/agent-definitions/hooks/useWorkflowDialogs";
import { isWorkflowDebugLoggingEnabled } from "../components/agent-definitions/utils/workflowDebug";

const EMPTY_WORKFLOW_GRAPH: WorkflowGraph = { nodes: [], edges: [] };

interface AgentDefinitionsViewProps {
  definitions: AgentDefinitionsDocument | null;
  loading: boolean;
  error: string | null;
  onReload: () => Promise<void>;
  onDefinitionsUpdated: (document: AgentDefinitionsDocument) => void;
  apiBaseUrl: string;
}

export function AgentDefinitionsView({
  definitions,
  loading,
  error,
  onReload,
  onDefinitionsUpdated,
  apiBaseUrl,
}: AgentDefinitionsViewProps) {
  const {
    draftDocument,
    jsonDraft,
    jsonError,
    isSaving,
    isDirty,
    successMessage,
    documentRevision,
    handleReload,
    handleJsonDraftChange,
    applyDocumentUpdate,
    handleSave,
  } = useAgentDefinitionsDocument({
    definitions,
    apiBaseUrl,
    onReload,
    onDefinitionsUpdated,
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [viewportRevision, setViewportRevision] = useState(0);
  const workflowDebugLogging = isWorkflowDebugLoggingEnabled();

  useEffect(() => {
    if (!showAdvanced) {
      setViewportRevision((previous) => previous + 1);
    }
  }, [showAdvanced]);

  const {
    activeWorkflowId,
    setActiveWorkflowId,
    isWorkflowDialogOpen,
    workflowForm,
    workflowFormError,
    workflowDialogMode,
    openWorkflowDialog,
    openWorkflowDialogForEdit,
    handleWorkflowFieldChange,
    handleStreamingToggle,
    handleAddDefaultParameter,
    handleDefaultParameterChange,
    handleRemoveDefaultParameter,
    handleWorkflowSubmit,
    handleWorkflowDialogClose,
    handleRemoveWorkflow,
    handleWorkflowKeyDown,
  } = useWorkflowSelection({ draftDocument, applyDocumentUpdate });

  const activeAgent = useMemo(() => {
    if (!draftDocument || !activeWorkflowId) {
      return null;
    }

    return (
      draftDocument.agents.find((agent) => agent.id === activeWorkflowId) ??
      null
    );
  }, [activeWorkflowId, draftDocument, documentRevision]);

  const graph: WorkflowGraph = useMemo(() => {
    if (!activeAgent) {
      return EMPTY_WORKFLOW_GRAPH;
    }

    return buildWorkflowGraph(activeAgent);
  }, [activeAgent, documentRevision]);

  useEffect(() => {
    if (!workflowDebugLogging || !activeAgent) {
      return;
    }

    const steps = activeAgent.steps.map((step) => ({
      name: step.name,
      isStartStep: Boolean(step.isStartStep),
    }));

    console.info("[AgentDefinitionsView] active agent updated", {
      workflowId: activeAgent.id,
      documentRevision,
      steps,
    });
  }, [workflowDebugLogging, activeAgent, documentRevision]);

  const {
    nodes,
    edges,
    handleNodesChange,
    onEdgesChange,
    handleNodeDragStop,
    handleEdgeMouseEnter,
    handlePaneClick,
    snapEnabled,
    setSnapEnabled,
    setActiveEdgeId,
    setNodePosition,
    initialViewport,
    handleViewportChange,
    graphSignature,
  } = useWorkflowCanvas({
    graph,
    activeWorkflowId,
    applyDocumentUpdate,
    viewport: activeAgent?.ViewLayout?.viewport ?? null,
  });

  useEffect(() => {
    if (!workflowDebugLogging) {
      return;
    }

    const startEdge = graph.edges.find(
      (edge) => edge.data?.sourceStep === "start"
    );

    console.info("[AgentDefinitionsView] graph signature updated", {
      workflowId: activeWorkflowId,
      graphSignature,
      startEdgeTarget: startEdge?.target,
      documentRevision,
    });
  }, [
    workflowDebugLogging,
    graphSignature,
    graph,
    activeWorkflowId,
    documentRevision,
  ]);

  const nodeTypes = useMemo<NodeTypes>(
    () => ({
      step: WorkflowStepNode,
      placeholder: WorkflowStepNode,
      tool: WorkflowToolNode,
    }),
    []
  );

  const edgeTypes = useMemo<EdgeTypes>(
    () => ({
      [WORKFLOW_EDGE_TYPE]: WorkflowGraphEdge,
    }),
    []
  );

  const {
    stepDialogProps,
    openStepDialogForNode,
    openStepDialogForCreation,
    openEchoStepDialogForCreation,
    openVariableStepDialogForCreation,
    toolDialogProps,
    openToolDialogForNode,
    openToolDialogForCreation,
    outcomeDialogProps,
    openOutcomeDialogForEdge,
    openOutcomeDialogForCreation,
  } = useWorkflowDialogs({
    draftDocument,
    activeWorkflowId,
    applyDocumentUpdate,
  });

  const { stepNames, setStartStep } = useWorkflowActions({
    activeAgent,
    activeWorkflowId,
    applyDocumentUpdate,
  });

  const {
    stepSelection,
    handleAddOutcome,
    handleAddTermination,
    handleAddStart,
    handleStepSelectionCancel,
    handleStepSelectionConfirm,
  } = useStepSelectionFlow({
    stepNames,
    openStepDialogForCreation,
    setStartStep,
    openOutcomeDialogForCreation,
  });

  const handleNodeClick = useCallback<NodeMouseHandler>(
    (_event, node) => {
      const workflowNode = node as WorkflowNode;

      if (workflowNode.data.kind === "placeholder") {
        openStepDialogForNode(workflowNode);
      }
    },
    [openStepDialogForNode]
  );

  const handleNodeDoubleClick = useCallback<NodeMouseHandler>(
    (_event, node) => {
      const workflowNode = node as WorkflowNode;

      if (
        workflowNode.data.kind === "step" ||
        workflowNode.data.kind === "placeholder"
      ) {
        openStepDialogForNode(workflowNode);
      }

      if (workflowNode.data.kind === "tool") {
        openToolDialogForNode(workflowNode);
      }
    },
    [openStepDialogForNode, openToolDialogForNode]
  );

  const handleEdgeClick = useCallback<EdgeMouseHandler>(
    (_event, edge) => {
      setActiveEdgeId(edge.id);
    },
    [setActiveEdgeId]
  );

  const handleEdgeDoubleClick = useCallback<EdgeMouseHandler>(
    (_event, edge) => {
      const workflowEdge = edge as WorkflowEdge;

      if (workflowEdge.data?.sourceStep === "start") {
        handleAddStart();
        return;
      }

      if (workflowEdge.data?.kind === "outcome") {
        openOutcomeDialogForEdge(workflowEdge);
      }
    },
    [handleAddStart, openOutcomeDialogForEdge]
  );

  const toolboxDisabled = !activeAgent;

  const handleSnapToggle = useCallback(() => {
    setSnapEnabled((previous) => !previous);
  }, [setSnapEnabled]);

  const saveDisabled =
    loading || isSaving || !isDirty || jsonError !== null || !draftDocument;

  return (
    <ReactFlowProvider>
      <div className="space-y-4 pb-6">
        <WorkflowHeader
          loading={loading}
          showAdvanced={showAdvanced}
          isSaving={isSaving}
          saveDisabled={saveDisabled}
          onReload={handleReload}
          onToggleAdvanced={() => setShowAdvanced((previous) => !previous)}
          onSave={handleSave}
        />

        {error ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {jsonError && !showAdvanced ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            {jsonError}
          </p>
        ) : null}

        {successMessage ? (
          <p className="rounded-md border border-emerald-300/40 bg-emerald-100/40 p-3 text-sm text-emerald-700">
            {successMessage}
          </p>
        ) : null}

        {!draftDocument || draftDocument.agents.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-4 text-sm text-foreground/70">
            <p>No workflows defined yet. Use the button below to create one.</p>
            <div className="mt-3 flex justify-start">
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-card text-foreground/80 transition-colors hover:bg-muted"
                onClick={openWorkflowDialog}
                title="New Workflow"
              >
                <Plus className="h-4 w-4" />
                <span className="sr-only">New Workflow</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <WorkflowAgentTabs
              agents={draftDocument.agents}
              activeWorkflowId={activeWorkflowId}
              onSelect={setActiveWorkflowId}
              onKeyDown={handleWorkflowKeyDown}
              onEdit={openWorkflowDialogForEdit}
              onRemove={handleRemoveWorkflow}
              onCreate={openWorkflowDialog}
            />

            {showAdvanced ? (
              <WorkflowJsonEditor
                value={jsonDraft}
                error={jsonError}
                onChange={handleJsonDraftChange}
              />
            ) : (
              <WorkflowBuilderPanel
                disabled={toolboxDisabled}
                onAddStep={openStepDialogForCreation}
                onAddEchoStep={openEchoStepDialogForCreation}
                onAddVariableStep={openVariableStepDialogForCreation}
                onAddOutcome={handleAddOutcome}
                onAddTool={openToolDialogForCreation}
                onAddStart={handleAddStart}
                onAddTermination={handleAddTermination}
              >
                <WorkflowCanvas
                  key={graphSignature}
                  nodes={nodes}
                  edges={edges}
                  nodeTypes={nodeTypes}
                  edgeTypes={edgeTypes}
                  snapEnabled={snapEnabled}
                  onToggleSnap={handleSnapToggle}
                  onNodesChange={handleNodesChange}
                  onEdgesChange={onEdgesChange}
                  onNodeClick={handleNodeClick}
                  onNodeDoubleClick={handleNodeDoubleClick}
                  onEdgeClick={handleEdgeClick}
                  onEdgeDoubleClick={handleEdgeDoubleClick}
                  onEdgeMouseEnter={handleEdgeMouseEnter}
                  onNodeDragStop={handleNodeDragStop}
                  onPaneClick={handlePaneClick}
                  onNodePositionRequest={setNodePosition}
                  initialViewport={initialViewport}
                  viewportRevision={viewportRevision}
                  onViewportChange={handleViewportChange}
                  activeWorkflowId={activeWorkflowId}
                />
              </WorkflowBuilderPanel>
            )}
          </div>
        )}

        <WorkflowStepSelectorDialog
          open={stepSelection !== null}
          steps={stepNames}
          title={stepSelection?.title ?? ""}
          description={stepSelection?.description ?? ""}
          confirmLabel={stepSelection?.confirmLabel}
          onCancel={handleStepSelectionCancel}
          onConfirm={handleStepSelectionConfirm}
        />

        <StepDialog {...stepDialogProps} />

        <ToolDialog {...toolDialogProps} />

        <OutcomeDialog {...outcomeDialogProps} />

        <WorkflowDialog
          open={isWorkflowDialogOpen}
          title={
            workflowDialogMode === "create"
              ? "Create Workflow"
              : "Edit Workflow"
          }
          workflowForm={workflowForm}
          workflowFormError={workflowFormError}
          onClose={handleWorkflowDialogClose}
          onSubmit={handleWorkflowSubmit}
          onFieldChange={handleWorkflowFieldChange}
          mode={workflowDialogMode}
          onAddDefaultParameter={handleAddDefaultParameter}
          onDefaultParameterChange={handleDefaultParameterChange}
          onRemoveDefaultParameter={handleRemoveDefaultParameter}
          onStreamingToggle={handleStreamingToggle}
        />
      </div>
    </ReactFlowProvider>
  );
}
