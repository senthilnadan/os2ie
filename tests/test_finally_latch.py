"""
Finally latch — unit tests.

The finally latch runs after every transition dispatch + output_binding.
It verifies that all keys declared in AbstractTransition.outputs are
present in state. If any are missing, the kernel fails immediately and
the next transition never compiles.

Three tests:
  1. All declared outputs present → transition passes, execution continues.
  2. Tool returns wrong key name → declared output missing → latch fires.
  3. Tool returns partial outputs (one of two declared keys missing) → latch fires.

EscapeToShell relevance: shell commands return {stdout, stderr, return_code}.
The abstract transition declares outputs like ["moved"] or ["deleted"].
output_binding maps the shell keys to the abstract keys. The finally latch
then confirms the abstract keys landed in state — proving the binding worked.
"""
from __future__ import annotations
import pytest
from src.kernel import execute
from src.models import (
    AbstractDSTT, AbstractSegment, AbstractTransition,
    ExecutableDSTT, ExecutableSegment, ExecutableTransition,
)
from tests.stub_t2e import StubTransition2ExecClient, ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abstract_dstt(tool: str, inputs: list[str], outputs: list[str]) -> AbstractDSTT:
    return AbstractDSTT(segments=[
        AbstractSegment(
            transitions=[
                AbstractTransition(id="t1", tool=tool, inputs=inputs, outputs=outputs)
            ],
            milestone=outputs,
        )
    ])


def _grounded(tool: str, inputs: dict, outputs_keys: list[str],
              output_binding: dict | None = None) -> ExecutableDSTT:
    return ok([{
        "id": "t1",
        "tool": tool,
        "inputs": inputs,
        "outputs": {},
        "output_binding": output_binding or {},
    }])


# ---------------------------------------------------------------------------
# Test 1 — all declared outputs present → latch passes
# ---------------------------------------------------------------------------

def test_finally_latch_passes_when_outputs_present(monkeypatch):
    """Tool returns the declared output key — latch sees it in state and passes."""
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "delete_file", lambda state: {"deleted": True})

    abstract = _abstract_dstt("remove_artifact", ["file_path"], ["deleted"])
    stub = StubTransition2ExecClient([
        _grounded("delete_file", {"file_path": "/tmp/os2ie_sandbox/old.tar.gz"}, ["deleted"])
    ])

    result = execute(
        task="Remove the old artifact",
        state={"file_path": "/tmp/os2ie_sandbox/old.tar.gz"},
        abstract_dstt=abstract,
        t2e=stub,
        available_tools=[],
    )

    assert result.status == "completed"
    assert result.state["deleted"] is True
    assert "deleted" in result.milestone_reached


# ---------------------------------------------------------------------------
# Test 2 — tool returns wrong key name → declared output missing → latch fires
# ---------------------------------------------------------------------------

def test_finally_latch_auto_aliases_1to1_mismatch(monkeypatch):
    """
    Abstract transition declares output ["moved"].
    Tool returns {"result": True} — wrong key, no output_binding.
    1 declared missing, 1 unbound actual → kernel auto-aliases result→moved.
    Latch passes, declared key lands in state.
    """
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "move_file", lambda state: {"result": True})

    abstract = _abstract_dstt("move_artifact", ["source_path", "destination_path"], ["moved"])
    stub = StubTransition2ExecClient([
        _grounded("move_file",
                  {"source_path": "/tmp/os2ie_sandbox/a.sh",
                   "destination_path": "/tmp/os2ie_sandbox/backup/a.sh"},
                  ["moved"])
    ])

    result = execute(
        task="Move the artifact to backup",
        state={
            "source_path": "/tmp/os2ie_sandbox/a.sh",
            "destination_path": "/tmp/os2ie_sandbox/backup/a.sh",
        },
        abstract_dstt=abstract,
        t2e=stub,
        available_tools=[],
    )

    assert result.status == "completed"
    assert "moved" in result.state       # declared key aliased into state
    assert result.state["moved"] is True # value preserved from actual output


# ---------------------------------------------------------------------------
# Test 3 — tool returns partial outputs → latch fires on missing key
# ---------------------------------------------------------------------------

def test_finally_latch_fires_on_partial_outputs(monkeypatch):
    """
    Abstract transition declares outputs ["copied", "checksum"].
    Tool returns only {"copied": True} — checksum never lands in state.
    Latch fires, reports the missing key.

    EscapeToShell analogy: shell returns {stdout, return_code} but output_binding
    only maps return_code → copied. checksum was declared but never produced.
    """
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "copy_file", lambda state: {"copied": True})  # checksum missing

    abstract = _abstract_dstt(
        "backup_config",
        ["source_path", "destination_path"],
        ["copied", "checksum"],   # checksum is not in initial context — tool must produce it
    )
    stub = StubTransition2ExecClient([
        _grounded("copy_file",
                  {"source_path": "/tmp/os2ie_sandbox/config.yaml",
                   "destination_path": "/tmp/os2ie_sandbox/backup/config.yaml"},
                  ["copied", "checksum"])
    ])

    result = execute(
        task="Back up config file",
        state={
            "source_path": "/tmp/os2ie_sandbox/config.yaml",
            "destination_path": "/tmp/os2ie_sandbox/backup/config.yaml",
        },
        abstract_dstt=abstract,
        t2e=stub,
        available_tools=[],
    )

    assert result.status == "failed"
    assert "finally" in result.execution_log[-1].error
    assert "checksum" in result.execution_log[-1].error


# ---------------------------------------------------------------------------
# Test 4 — EscapeToShell: output_binding maps shell key → abstract key → latch passes
# ---------------------------------------------------------------------------

def test_finally_latch_passes_via_output_binding(monkeypatch):
    """
    Shell command returns {return_code: 0}. Abstract transition declares ["moved"].
    output_binding: {"return_code": "moved"} maps shell key to abstract key.
    Latch sees "moved" in state (written by binding) and passes.
    """
    monkeypatch.setitem(__import__("src.tools", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY,
                        "run_shell_command",
                        lambda state: {"stdout": "", "stderr": "", "return_code": 0})

    abstract = _abstract_dstt("move_file_via_shell",
                               ["source_path", "destination_path"], ["moved"])
    stub = StubTransition2ExecClient([
        ok([{
            "id": "t1",
            "tool": "run_shell_command",
            "inputs": {"command": "mv /tmp/os2ie_sandbox/a.sh /tmp/os2ie_sandbox/backup/a.sh"},
            "outputs": {},
            "output_binding": {"return_code": "moved"},   # shell → abstract
        }])
    ])

    result = execute(
        task="Move file via shell",
        state={
            "source_path": "/tmp/os2ie_sandbox/a.sh",
            "destination_path": "/tmp/os2ie_sandbox/backup/a.sh",
        },
        abstract_dstt=abstract,
        t2e=stub,
        available_tools=[],
    )

    assert result.status == "completed"
    assert "moved" in result.state          # abstract key written by binding
    assert "moved" in result.milestone_reached
