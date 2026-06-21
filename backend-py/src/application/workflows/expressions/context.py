"""Expression context for evaluating workflow expressions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExpressionContext(BaseModel):
    """Context for evaluating workflow expressions.

    Contains variables, parameters, input, runtime state, and last
    output that can be referenced in expressions using ``var.*``,
    ``param.*``, ``input``, ``lastOutput``, and the runtime-state
    keys (``output``, ``stepName``, ``stepType``).

    The ``runtime_state`` keys mirror what the .NET backend exposes
    through ``StepOutcomeResolver.BuildRuntimeState`` so the same
    ``agents.json`` file yields the same identifiers in both
    backends.
    """

    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow variables set by previous steps",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the current run",
    )
    input: Any = Field(
        default=None,
        description="Original user input",
    )
    last_output: Any = Field(
        default=None,
        description="Output from the last executed step (exposed as lastOutput)",
    )
    runtime_state: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Per-step runtime identifiers (output, stepName, stepType) "
            "exposed as top-level identifiers. Mirrors the .NET "
            "WorkflowExpressionContext.RuntimeState so outcome "
            "conditions and placeholders behave the same on both "
            "backends."
        ),
    )
    step_outputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Outputs from all previous steps by step ID",
    )

    def get_variable(self, name: str) -> Any:
        """Get a variable value by name.

        Args:
            name: Variable name

        Returns:
            Variable value or None
        """
        return self.variables.get(name)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable value.

        Args:
            name: Variable name
            value: Value to set
        """
        self.variables[name] = value

    def get_parameter(self, name: str) -> Any:
        """Get a parameter value by name.

        Args:
            name: Parameter name

        Returns:
            Parameter value or None
        """
        return self.parameters.get(name)

    def get_step_output(self, step_id: str) -> Any:
        """Get output from a specific step.

        Args:
            step_id: Step identifier

        Returns:
            Step output or None
        """
        return self.step_outputs.get(step_id)

    def set_step_output(self, step_id: str, output: Any) -> None:
        """Set output for a specific step.

        Args:
            step_id: Step identifier
            output: Output value
        """
        self.step_outputs[step_id] = output
        self.last_output = output