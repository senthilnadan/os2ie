from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .models import AbstractTransition, ExecutableDSTT
from .catalog import build_catalog


# ---------------------------------------------------------------------------
# Outcome types — returned by CreateTransitionHandler, never cross a service
# boundary.
# ---------------------------------------------------------------------------

@dataclass
class EscapeToShell:
    """Shell fallback succeeded — an executable transition was produced."""
    executable_dstt: ExecutableDSTT
    transition_id: str
    abstract_tool: str


@dataclass
class Escalation:
    """All recovery paths exhausted — surface to caller."""
    reason: str                          # "not_mappable_after_shell_fallback"
    transition_id: str                   # escalation locator
    segment_index: int                   # escalation locator
    abstract_tool: str
    context: dict = field(default_factory=dict)   # state snapshot at failure point


# ---------------------------------------------------------------------------
# Shell tool entry — appended to available_tools for the fallback retry.
# Built once from the catalog so the description stays authoritative.
# ---------------------------------------------------------------------------

def _shell_tool_entry() -> dict[str, Any]:
    catalog = build_catalog()
    for tool in catalog:
        if tool["name"] == "run_shell_command":
            return tool
    raise RuntimeError("run_shell_command not found in catalog")


_SHELL_TOOL: dict[str, Any] = _shell_tool_entry()


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

        Two recovery steps, in order:
          1. Shell fallback  — retry compile with run_shell_command added to
                               available_tools. Returns EscapeToShell on success.
          2. Escalate        — return Escalation; kernel surfaces to caller.
        """

        @staticmethod
        def handle_not_mappable(
            task: str,
            state: dict[str, Any],
            abstract_transition: AbstractTransition,
            t2e: Any,                        # Transition2ExecClient
            available_tools: list[dict],
            segment_index: int = 0,
        ) -> EscapeToShell | Escalation:

            # Step 1 — shell fallback
            tools_with_shell = available_tools + [_SHELL_TOOL]
            try:
                exec_dstt, _ = t2e.compile(
                    task, state, abstract_transition, available_tools=tools_with_shell
                )
                if exec_dstt.status == "ok":
                    return EscapeToShell(
                        executable_dstt=exec_dstt,
                        transition_id=abstract_transition.id,
                        abstract_tool=abstract_transition.tool,
                    )
            except Exception:
                pass  # shell fallback call itself failed — fall through to escalation

            # Step 2 — escalate
            return Escalation(
                reason="not_mappable_after_shell_fallback",
                transition_id=abstract_transition.id,
                segment_index=segment_index,
                abstract_tool=abstract_transition.tool,
                context=dict(state),
            )
