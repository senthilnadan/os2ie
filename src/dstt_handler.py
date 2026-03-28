from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .models import AbstractTransition, ExecutableTransition


# ---------------------------------------------------------------------------
# Outcome types — returned by CreateTransitionHandler, never cross a service
# boundary.
# ---------------------------------------------------------------------------

@dataclass
class EscapeToShell:
    """Transition2Shell produced a viable shell script — transition assembled."""
    executable_transition: ExecutableTransition
    transition_id: str
    abstract_tool: str


@dataclass
class Escalation:
    """All recovery paths exhausted — surface to caller."""
    reason: str                                   # "not_capable_for_shell"
    transition_id: str                            # escalation locator
    segment_index: int                            # escalation locator
    abstract_tool: str
    context: dict = field(default_factory=dict)  # state snapshot at failure point


# ---------------------------------------------------------------------------
# Output binding helper
#
# run_shell_command produces: stdout, stderr, return_code.
# Map these to the abstract transition's output keys so the executor writes
# both grounded and abstract keys into state.
#
# Binding strategy:
#   - stdout      → first output key  (primary result)
#   - return_code → second output key (if present)
#   - stderr      → unmapped (always available in state as "stderr")
# ---------------------------------------------------------------------------

_SHELL_OUTPUTS = ["stdout", "return_code", "stderr"]


def _bind_shell_outputs(abstract_outputs: list[str]) -> dict[str, str]:
    binding: dict[str, str] = {}
    for shell_key, abstract_key in zip(_SHELL_OUTPUTS, abstract_outputs):
        if shell_key != abstract_key:
            binding[shell_key] = abstract_key
    return binding


# ---------------------------------------------------------------------------
# DSTTHandler
# ---------------------------------------------------------------------------

class DSTTHandler:
    """
    Namespace for DSTT runtime recovery handlers.

    Each inner class owns one failure mode at one stage of execution.
    The kernel calls the appropriate handler and acts on the outcome type.
    """

    class CreateTransitionHandler:
        """
        Recovery handler for compile-time failures — when transition2exec
        returns not_mappable and no executable transition was produced.

        Calls Transition2Shell with decomposed intent hints (never the full
        AbstractTransition object). On not_capable → Escalation.
        On ok → assembles ExecutableTransition with run_shell_command and
        returns EscapeToShell.
        """

        @staticmethod
        def handle_not_mappable(
            task: str,
            state: dict[str, Any],
            abstract_transition: AbstractTransition,
            t2s: Any,                   # Transition2ShellClient
            segment_index: int = 0,
        ) -> EscapeToShell | Escalation:

            # Call Transition2Shell — decomposed intent hints, no full transition
            try:
                result = t2s.compile(
                    task=task,
                    intent=abstract_transition.tool,
                    inputs=abstract_transition.inputs,
                    outputs=abstract_transition.outputs,
                    context=state,
                )
            except Exception as e:
                return Escalation(
                    reason=f"transition2shell call failed: {e}",
                    transition_id=abstract_transition.id,
                    segment_index=segment_index,
                    abstract_tool=abstract_transition.tool,
                    context=dict(state),
                )

            if result.status == "not_capable":
                return Escalation(
                    reason=result.reason or "not_capable_for_shell",
                    transition_id=abstract_transition.id,
                    segment_index=segment_index,
                    abstract_tool=abstract_transition.tool,
                    context=dict(state),
                )

            # Assemble ExecutableTransition — CreateTransitionHandler's responsibility
            executable_transition = ExecutableTransition(
                id=abstract_transition.id,
                tool="run_shell_command",
                inputs={"command": result.script_description},
                outputs={},
                output_binding=_bind_shell_outputs(abstract_transition.outputs),
            )
            return EscapeToShell(
                executable_transition=executable_transition,
                transition_id=abstract_transition.id,
                abstract_tool=abstract_transition.tool,
            )
