import { renderHook, act } from "@testing-library/react";
import type { ChangeEvent } from "react";
import { describe, it, expect, vi } from "vitest";

import type { AgentDefinitionsDocument } from "../../../../types/agents";
import type { StepFormState, WorkflowNode } from "../../types";
import { useWorkflowAgentContext } from "../useWorkflowAgentContext";
import { useStepDialogState } from "../useStepDialogState";
import { useStepForm } from "../useStepForm";
import { useStepDialogOpeners } from "../useStepDialogOpeners";
import { useStepPersistence } from "../useStepPersistence";

const createDocument = (): AgentDefinitionsDocument => ({
  agents: [
    {
      id: "agent-1",
      name: "Primary Agent",
      defaultParameters: { systemPrompt: "Hello" },
      steps: [
        {
          name: "Existing Step",
          type: "agent",
          parameters: { message: "Hi" },
          conversation: { enabled: true },
          outcomes: [],
          tools: ["tool-1"],
        },
      ],
      tools: [
        { id: "tool-1", type: "rest", name: "Tool One" },
        { id: "tool-2", type: "rest" },
      ],
      ViewLayout: {},
    },
  ],
});

describe("useWorkflowAgentContext", () => {
  it("returns agent context with derived data", () => {
    const document = createDocument();
    const { result } = renderHook(() =>
      useWorkflowAgentContext({
        draftDocument: document,
        activeWorkflowId: "agent-1",
      })
    );

    expect(result.current.agent?.id).toBe("agent-1");
    expect(result.current.availableTools).toEqual([
      { id: "tool-1", label: "Tool One" },
      { id: "tool-2", label: "tool-2" },
    ]);
    expect(result.current.workflowParameters).toHaveLength(1);
  });

  it("falls back when context is missing", () => {
    const { result } = renderHook(() =>
      useWorkflowAgentContext({ draftDocument: null, activeWorkflowId: null })
    );

    expect(result.current.agent).toBeNull();
    expect(result.current.availableTools).toEqual([]);
    expect(result.current.workflowParameters).toEqual([]);
  });

  it("returns empty tool list when agent is missing", () => {
    const document = createDocument();

    const { result } = renderHook(() =>
      useWorkflowAgentContext({
        draftDocument: document,
        activeWorkflowId: "non-existent",
      })
    );

    expect(result.current.agent).toBeNull();
    expect(result.current.availableTools).toEqual([]);
  });
});

describe("useStepDialogState", () => {
  it("tracks open state and title", () => {
    const { result } = renderHook(() => useStepDialogState());

    expect(result.current.open).toBe(false);
    expect(result.current.title).toBe("Configure Step");

    act(() => {
      result.current.openDialog({ mode: "create" });
    });

    expect(result.current.open).toBe(true);
    expect(result.current.title).toBe("Create Step");

    act(() => {
      result.current.reset();
    });

    expect(result.current.open).toBe(false);
  });

  it("derives edit title from workflow node", () => {
    const { result } = renderHook(() => useStepDialogState());
    const node = {
      data: { label: "Label", kind: "step", stepName: "Step A" },
    } as WorkflowNode;

    act(() => {
      result.current.openDialog({ mode: "edit", target: node });
    });

    expect(result.current.title).toContain("Step A");
  });
});

describe("useStepForm", () => {
  const buildStepForm = (): StepFormState => ({
    name: "Example",
    type: "agent",
    conversationEnabled: true,
    parameters: [],
    tools: [],
  });

  it("updates step type and parameters when type changes", () => {
    const { result } = renderHook(() => useStepForm());

    act(() => {
      result.current.setStepFormState(buildStepForm());
    });

    act(() => {
      result.current.handleFieldChange("type")({
        target: { value: "setVariables" },
      } as ChangeEvent<HTMLInputElement>);
    });

    expect(result.current.stepForm?.type).toBe("setVariables");
    expect(
      result.current.stepForm?.parameters.every(
        (entry) => entry.dataType === "string"
      )
    ).toBe(true);
    expect(result.current.stepForm?.conversationEnabled).toBe(false);
    expect(result.current.stepForm?.tools).toEqual([]);
  });

  it("supports parameter add/remove operations", () => {
    const { result } = renderHook(() => useStepForm());

    act(() => {
      result.current.setStepFormState(buildStepForm());
    });

    act(() => {
      result.current.handleAddParameter();
    });

    expect(result.current.stepForm?.parameters).toHaveLength(1);

    const entryId = result.current.stepForm?.parameters[0].id as string;

    act(() => {
      result.current.handleParameterChange(
        entryId,
        "key"
      )({
        target: { value: "foo" },
      } as ChangeEvent<HTMLInputElement>);
      result.current.handleParameterChange(
        entryId,
        "value"
      )({
        target: { value: "bar" },
      } as ChangeEvent<HTMLInputElement>);
    });

    expect(result.current.stepForm?.parameters[0]).toMatchObject({
      key: "foo",
      value: "bar",
    });

    act(() => {
      result.current.handleRemoveParameter(entryId);
    });

    expect(result.current.stepForm?.parameters).toHaveLength(0);
  });

  it("toggles tools on and off", () => {
    const { result } = renderHook(() => useStepForm());

    act(() => {
      result.current.setStepFormState(buildStepForm());
    });

    act(() => {
      result.current.handleToolToggle("alpha")({
        target: { checked: true },
      } as ChangeEvent<HTMLInputElement>);
    });

    expect(result.current.stepForm?.tools).toEqual(["alpha"]);

    act(() => {
      result.current.handleToolToggle("alpha")({
        target: { checked: false },
      } as ChangeEvent<HTMLInputElement>);
    });

    expect(result.current.stepForm?.tools).toEqual([]);
  });
});

describe("useStepDialogOpeners", () => {
  it("populates form state when editing an existing step", () => {
    const document = createDocument();
    const workflowNode = {
      data: { label: "Existing", kind: "step", stepName: "Existing Step" },
    } as WorkflowNode;
    const setStepFormState = vi.fn();
    const setStepFormError = vi.fn();
    const setStepOriginalName = vi.fn();
    const openDialog = vi.fn();

    const { result } = renderHook(() =>
      useStepDialogOpeners({
        draftDocument: document,
        activeWorkflowId: "agent-1",
        agent: document.agents[0],
        setStepFormState,
        setStepFormError,
        setStepOriginalName,
        openDialog,
      })
    );

    act(() => {
      result.current.openForEditing(workflowNode);
    });

    expect(setStepFormState).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Existing Step", type: "agent" })
    );
    expect(setStepFormError).toHaveBeenCalledWith(null);
    expect(openDialog).toHaveBeenCalledWith({
      mode: "edit",
      target: workflowNode,
    });
  });

  it("initializes default form state for new reset steps", () => {
    const document = createDocument();
    const setStepFormState = vi.fn();
    const setStepFormError = vi.fn();
    const setStepOriginalName = vi.fn();
    const openDialog = vi.fn();

    const { result } = renderHook(() =>
      useStepDialogOpeners({
        draftDocument: document,
        activeWorkflowId: "agent-1",
        agent: document.agents[0],
        setStepFormState,
        setStepFormError,
        setStepOriginalName,
        openDialog,
      })
    );

    act(() => {
      result.current.openForResetCreation();
    });

    expect(setStepFormState).toHaveBeenCalledWith(
      expect.objectContaining({ type: "resetConversation" })
    );
    expect(openDialog).toHaveBeenCalledWith({ mode: "create" });
  });

  it("handles missing workflow context gracefully", () => {
    const setStepFormState = vi.fn();
    const setStepFormError = vi.fn();
    const setStepOriginalName = vi.fn();
    const openDialog = vi.fn();
    const workflowNode = {
      data: { label: "Placeholder", kind: "placeholder" },
    } as WorkflowNode;

    const { result } = renderHook(() =>
      useStepDialogOpeners({
        draftDocument: null,
        activeWorkflowId: null,
        agent: null,
        setStepFormState,
        setStepFormError,
        setStepOriginalName,
        openDialog,
      })
    );

    act(() => {
      result.current.openForEditing(workflowNode);
    });

    expect(setStepFormState).toHaveBeenCalledWith(null);
    expect(setStepFormError).toHaveBeenCalledWith(
      "Unable to locate workflow for editing."
    );
  });
});

describe("useStepPersistence", () => {
  const buildStepFormState = (
    overrides?: Partial<StepFormState>
  ): StepFormState => ({
    name: "New Step",
    type: "agent",
    conversationEnabled: true,
    parameters: [],
    tools: [],
    ...overrides,
  });

  it("persists steps with validation and prevents duplicates", () => {
    const document = createDocument();
    const applyDocumentUpdate = vi.fn(
      (updater: (draft: AgentDefinitionsDocument) => void) => {
        updater(document);
      }
    );

    const { result } = renderHook(() =>
      useStepPersistence({ applyDocumentUpdate })
    );

    const success = result.current.persistStepWithValidation({
      draftDocument: document,
      activeWorkflowId: "agent-1",
      mode: "create",
      stepForm: buildStepFormState(),
      stepOriginalName: null,
    });

    expect(success.success).toBe(true);
    expect(document.agents[0].steps).toHaveLength(2);

    const duplicate = result.current.persistStepWithValidation({
      draftDocument: document,
      activeWorkflowId: "agent-1",
      mode: "create",
      stepForm: buildStepFormState(),
      stepOriginalName: null,
    });

    expect(duplicate.success).toBe(false);
    expect(duplicate.error).toMatch(/already exists/);
  });

  it("guards deletes when context is missing", () => {
    const document = createDocument();
    const applyDocumentUpdate = vi.fn();
    const { result } = renderHook(() =>
      useStepPersistence({ applyDocumentUpdate })
    );

    const outcome = result.current.deleteStepWithValidation({
      draftDocument: document,
      activeWorkflowId: null,
      stepOriginalName: null,
    });

    expect(outcome.success).toBe(false);
    expect(outcome.error).toMatch(/missing context/);
  });

  it("deletes steps when validation passes", () => {
    const document = createDocument();
    const applyDocumentUpdate = vi.fn(
      (updater: (draft: AgentDefinitionsDocument) => void) => {
        updater(document);
      }
    );

    const { result } = renderHook(() =>
      useStepPersistence({ applyDocumentUpdate })
    );

    const outcome = result.current.deleteStepWithValidation({
      draftDocument: document,
      activeWorkflowId: "agent-1",
      stepOriginalName: "Existing Step",
    });

    expect(outcome.success).toBe(true);
    expect(
      document.agents[0].steps.some((step) => step.name === "Existing Step")
    ).toBe(false);
  });

  it("preserves start flag when editing start step", () => {
    const document = createDocument();
    document.agents[0].steps[0].isStartStep = true;

    const applyDocumentUpdate = vi.fn(
      (updater: (draft: AgentDefinitionsDocument) => void) => {
        updater(document);
      }
    );

    const { result } = renderHook(() =>
      useStepPersistence({ applyDocumentUpdate })
    );

    const outcome = result.current.persistStepWithValidation({
      draftDocument: document,
      activeWorkflowId: "agent-1",
      mode: "edit",
      stepForm: {
        name: "Existing Step",
        type: "agent",
        conversationEnabled: true,
        parameters: [],
        tools: [],
      },
      stepOriginalName: "Existing Step",
    });

    expect(outcome.success).toBe(true);
    expect(document.agents[0].steps[0].isStartStep).toBe(true);
  });
});
