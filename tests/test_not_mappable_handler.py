"""
Unit tests for DSTTHandler.CreateTransitionHandler — Path A not_mappable pivot.

No live endpoint required. Uses StubTransition2ExecClient.

Scenarios:
  A. not_mappable → shell fallback succeeds → EscapeToShell → kernel continues
  B. not_mappable → shell fallback also not_mappable → Escalation → kernel returns escalated
  C. not_mappable mid-plan (second transition) → correct segment_index in Escalation
"""
from __future__ import annotations
import pytest
from src.dstt_handler import DSTTHandler, EscapeToShell, Escalation
from src.kernel import execute
from src.models import (
    AbstractDSTT, AbstractSegment, AbstractTransition,
    ExecutableDSTT, ExecutableSegment, ExecutableTransition,
)
from tests.stub_t2e import StubTransition2ExecClient, ok, not_mappable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abstract_dstt(*tool_names: str) -> AbstractDSTT:
    """Build a single-segment AbstractDSTT with one transition per tool name."""
    transitions = [
        AbstractTransition(id=f"t{i+1}", tool=name, inputs=[], outputs=[])
        for i, name in enumerate(tool_names)
    ]
    return AbstractDSTT(segments=[AbstractSegment(
        transitions=transitions,
        milestone=[t.id for t in transitions],
    )])


def _abstract_transition(tid: str = "t1", tool: str = "fetch_data") -> AbstractTransition:
    return AbstractTransition(id=tid, tool=tool, inputs=[], outputs=[])


def _available_tools() -> list[dict]:
    from src.catalog import build_catalog
    return [t for t in build_catalog() if t["name"] != "run_shell_command"]


# ---------------------------------------------------------------------------
# A. Shell fallback succeeds → EscapeToShell
# ---------------------------------------------------------------------------

def test_handle_not_mappable_shell_fallback_succeeds():
    """Shell fallback compile returns ok. Returns EscapeToShell.
    The handler is called after the kernel has already seen not_mappable —
    it only makes one compile call (the shell fallback retry).
    """
    shell_ok = ok([{
        "id": "t1", "tool": "run_shell_command",
        "inputs": {"command": "date"},
        "outputs": {}, "output_binding": {},
    }])
    stub = StubTransition2ExecClient([shell_ok])
    transition = _abstract_transition()

    result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
        task="run date command",
        state={},
        abstract_transition=transition,
        t2e=stub,
        available_tools=_available_tools(),
        segment_index=0,
    )

    assert isinstance(result, EscapeToShell)
    assert result.transition_id == "t1"
    assert result.abstract_tool == "fetch_data"
    assert result.executable_dstt.status == "ok"


# ---------------------------------------------------------------------------
# B. Shell fallback also not_mappable → Escalation
# ---------------------------------------------------------------------------

def test_handle_not_mappable_escalates_when_shell_also_fails():
    """Shell fallback also returns not_mappable. Returns Escalation with correct locator.
    Handler is called with one compile call remaining (the shell fallback retry).
    """
    stub = StubTransition2ExecClient([not_mappable()])
    transition = _abstract_transition(tid="t2", tool="compute_hash")

    result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
        task="compute sha256",
        state={"file_path": "/tmp/data.bin"},
        abstract_transition=transition,
        t2e=stub,
        available_tools=_available_tools(),
        segment_index=1,
    )

    assert isinstance(result, Escalation)
    assert result.reason == "not_mappable_after_shell_fallback"
    assert result.transition_id == "t2"
    assert result.segment_index == 1
    assert result.abstract_tool == "compute_hash"
    assert result.context == {"file_path": "/tmp/data.bin"}


# ---------------------------------------------------------------------------
# C. Kernel: not_mappable → shell fallback succeeds → execution continues
# ---------------------------------------------------------------------------

def test_kernel_recovers_via_shell_fallback(tmp_path):
    """
    Kernel receives not_mappable on first compile.
    Shell fallback returns run_shell_command.
    Kernel executes the shell command and completes.
    """
    shell_ok = ok([{
        "id": "t1", "tool": "run_shell_command",
        "inputs": {"command": f"echo hello > {tmp_path}/out.txt"},
        "outputs": {}, "output_binding": {},
    }])
    stub = StubTransition2ExecClient([not_mappable(), shell_ok])
    abstract_dstt = _abstract_dstt("run_echo")

    result = execute(
        task="echo hello to file",
        state={},
        abstract_dstt=abstract_dstt,
        t2e=stub,
        available_tools=_available_tools(),
    )

    assert result.status == "completed"
    assert result.execution_log[-1].tool == "run_shell_command"
    assert result.execution_log[-1].status == "ok"


# ---------------------------------------------------------------------------
# D. Kernel: not_mappable → shell fallback also fails → status=escalated
# ---------------------------------------------------------------------------

def test_kernel_escalates_when_both_attempts_fail():
    """Both compile attempts return not_mappable. Kernel returns status=escalated."""
    stub = StubTransition2ExecClient([not_mappable(), not_mappable()])
    abstract_dstt = _abstract_dstt("http_get_request")

    result = execute(
        task="fetch https://api.example.com/status",
        state={"url": "https://api.example.com/status"},
        abstract_dstt=abstract_dstt,
        t2e=stub,
        available_tools=_available_tools(),
    )

    assert result.status == "escalated"
    assert result.execution_log[-1].status == "escalated"
    assert result.execution_log[-1].error == "not_mappable_after_shell_fallback"


# ---------------------------------------------------------------------------
# E. Kernel: not_mappable on second transition preserves completed segment
# ---------------------------------------------------------------------------

def test_kernel_escalation_preserves_partial_state(tmp_path):
    """
    First transition succeeds. Second returns not_mappable (shell fallback also fails).
    segments_completed=1, partial state from first transition is preserved.
    """
    first_ok = ok([{
        "id": "t1", "tool": "exists",
        "inputs": {"file_path": str(tmp_path)},
        "outputs": {}, "output_binding": {},
    }])
    stub = StubTransition2ExecClient([first_ok, not_mappable(), not_mappable()])
    abstract_dstt = AbstractDSTT(segments=[
        AbstractSegment(
            transitions=[AbstractTransition(id="t1", tool="check_path", inputs=[], outputs=[])],
            milestone=["t1"],
        ),
        AbstractSegment(
            transitions=[AbstractTransition(id="t2", tool="send_webhook", inputs=[], outputs=[])],
            milestone=["t2"],
        ),
    ])

    result = execute(
        task="check path then send webhook",
        state={},
        abstract_dstt=abstract_dstt,
        t2e=stub,
        available_tools=_available_tools(),
    )

    assert result.status == "escalated"
    assert result.segments_completed == 1
    assert result.execution_log[0].status == "ok"
    assert result.execution_log[1].status == "escalated"
    assert result.execution_log[1].transition_id == "t2"
