const envDefault =
  typeof import.meta !== "undefined" &&
  typeof import.meta.env?.VITE_WORKFLOW_DEBUG_LOGGING !== "undefined"
    ? import.meta.env.VITE_WORKFLOW_DEBUG_LOGGING === "true"
    : false;

export function isWorkflowDebugLoggingEnabled(): boolean {
  if (typeof window === "undefined") {
    return envDefault;
  }

  const override = window.__MAGIC_AGENT_DEBUG_WORKFLOW;

  if (typeof override === "boolean") {
    return override;
  }

  return envDefault;
}

declare global {
  interface Window {
    __MAGIC_AGENT_DEBUG_WORKFLOW?: boolean;
  }
}
