"""
Unit tests for DSTTHandler.CreateTransitionHandler — Path A not_mappable pivot.

No live endpoint required. Uses stubs for both Transition2ExecClient and
Transition2ShellClient.

Scenarios:
  A. not_mappable → Transition2Shell capable → EscapeToShell with run_shell_command
  B. not_mappable → Transition2Shell not_capable → Escalation
  C. Transition2Shell call fails → Escalation
  D. Kernel: EscapeToShell → execution continues with run_shell_command
  E. Kernel: Escalation → status=escalated
  F. Kernel: second transition escalates → partial state preserved
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import pytest
from src.dstt_handler import DSTTHandler, EscapeToShell, Escalation
from src.kernel import execute
from src.models import (
    AbstractDSTT, AbstractSegment, AbstractTransition,
    ExecutableDSTT, ExecutableSegment, ExecutableTransition,
    Transition2ShellResult,
)
from tests.stub_t2e import StubTransition2ExecClient, ok, not_mappable


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubTransition2ShellClient:
    """Returns queued Transition2ShellResult responses in order."""
    def __init__(self, responses: list[Transition2ShellResult]):
        self._queue = list(responses)

    def compile(self, task, intent, inputs, outputs, context) -> Transition2ShellResult:
        if not self._queue:
            raise RuntimeError("StubTransition2ShellClient: no more responses queued")
        return self._queue.pop(0)


def shell_ok(script: str = "echo hello") -> Transition2ShellResult:
    return Transition2ShellResult(status="ok", script_description=script)


def shell_not_capable(reason: str = "cannot do this with shell") -> Transition2ShellResult:
    return Transition2ShellResult(status="not_capable", reason=reason)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abstract_transition(
    tid: str = "t1",
    tool: str = "fetch_data",
    outputs: list[str] | None = None,
) -> AbstractTransition:
    return AbstractTransition(id=tid, tool=tool, inputs=[], outputs=outputs or [])


def _abstract_dstt(*tool_names: str) -> AbstractDSTT:
    transitions = [
        AbstractTransition(id=f"t{i+1}", tool=name, inputs=[], outputs=[])
        for i, name in enumerate(tool_names)
    ]
    return AbstractDSTT(segments=[AbstractSegment(
        transitions=transitions, milestone=[t.id for t in transitions],
    )])


def _available_tools() -> list[dict]:
    from src.catalog import build_catalog
    return [t for t in build_catalog() if t["name"] != "run_shell_command"]


# ---------------------------------------------------------------------------
# A. Transition2Shell capable → EscapeToShell with run_shell_command
# ---------------------------------------------------------------------------

def test_handle_not_mappable_shell_capable():
    t2s = StubTransition2ShellClient([shell_ok("date +%Y-%m-%d")])
    transition = _abstract_transition(outputs=["stdout"])

    result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
        task="get current date",
        state={},
        abstract_transition=transition,
        t2s=t2s,
        segment_index=0,
    )

    assert isinstance(result, EscapeToShell)
    assert result.executable_transition.tool == "run_shell_command"
    assert result.executable_transition.inputs["command"] == "date +%Y-%m-%d"
    assert result.executable_transition.id == "t1"


# ---------------------------------------------------------------------------
# B. Transition2Shell not_capable → Escalation
# ---------------------------------------------------------------------------

def test_handle_not_mappable_not_capable():
    t2s = StubTransition2ShellClient([shell_not_capable("HTTP request not possible")])
    transition = _abstract_transition(tid="t2", tool="http_get_request")

    result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
        task="fetch https://api.example.com",
        state={"url": "https://api.example.com"},
        abstract_transition=transition,
        t2s=t2s,
        segment_index=1,
    )

    assert isinstance(result, Escalation)
    assert result.reason == "HTTP request not possible"
    assert result.transition_id == "t2"
    assert result.segment_index == 1
    assert result.abstract_tool == "http_get_request"


# ---------------------------------------------------------------------------
# C. Transition2Shell call itself fails → Escalation
# ---------------------------------------------------------------------------

def test_handle_not_mappable_t2s_call_fails():
    class FailingT2S:
        def compile(self, **kwargs):
            raise ConnectionError("service unavailable")

    transition = _abstract_transition()
    result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
        task="some task",
        state={},
        abstract_transition=transition,
        t2s=FailingT2S(),
    )

    assert isinstance(result, Escalation)
    assert "transition2shell call failed" in result.reason


# ---------------------------------------------------------------------------
# D. Kernel: EscapeToShell → execution continues with run_shell_command
# ---------------------------------------------------------------------------

def test_kernel_escapes_to_shell(tmp_path):
    stub_t2e = StubTransition2ExecClient([not_mappable()])
    stub_t2s = StubTransition2ShellClient([shell_ok(f"echo hello > {tmp_path}/out.txt")])
    abstract_dstt = _abstract_dstt("run_echo")

    result = execute(
        task="echo hello to file",
        state={},
        abstract_dstt=abstract_dstt,
        t2e=stub_t2e,
        available_tools=_available_tools(),
        t2s=stub_t2s,
    )

    assert result.status == "completed"
    assert result.execution_log[-1].tool == "run_shell_command"
    assert result.execution_log[-1].status == "ok"


# ---------------------------------------------------------------------------
# E. Kernel: Transition2Shell not_capable → status=escalated
# ---------------------------------------------------------------------------

def test_kernel_escalates_when_not_capable():
    stub_t2e = StubTransition2ExecClient([not_mappable()])
    stub_t2s = StubTransition2ShellClient([shell_not_capable("HTTP not supported")])
    abstract_dstt = _abstract_dstt("http_get_request")

    result = execute(
        task="fetch external URL",
        state={},
        abstract_dstt=abstract_dstt,
        t2e=stub_t2e,
        available_tools=_available_tools(),
        t2s=stub_t2s,
    )

    assert result.status == "escalated"
    assert result.execution_log[-1].status == "escalated"
    assert result.execution_log[-1].error == "HTTP not supported"


# ---------------------------------------------------------------------------
# F. Kernel: second transition escalates → partial state preserved
# ---------------------------------------------------------------------------

def test_kernel_escalation_preserves_partial_state(tmp_path):
    first_ok = ok([{
        "id": "t1", "tool": "exists",
        "inputs": {"file_path": str(tmp_path)},
        "outputs": {}, "output_binding": {},
    }])
    stub_t2e = StubTransition2ExecClient([first_ok, not_mappable()])
    stub_t2s = StubTransition2ShellClient([shell_not_capable("no shell path")])
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
        task="check then webhook",
        state={},
        abstract_dstt=abstract_dstt,
        t2e=stub_t2e,
        available_tools=_available_tools(),
        t2s=stub_t2s,
    )

    assert result.status == "escalated"
    assert result.segments_completed == 1
    assert result.execution_log[0].status == "ok"
    assert result.execution_log[1].status == "escalated"
