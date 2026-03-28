"""
Two-transition DSTT — kernel execution + milestone verification tests.

Tests full kernel execution (compile → dispatch → merge → finally latch →
milestone check) using StubTransition2ExecClient and monkeypatched tool stubs.
No live service required.

Coverage:
  1.  Happy path — both transitions complete, all milestone keys in milestone_reached
  2.  Multi-key milestone — segment declares two milestone keys, both verified
  3.  Text→content thread — T1 output value flows as T2 input, milestone confirms
  4.  T1 latch fires — T2 never runs, milestone empty, segments_completed = 0
  5.  T2 tool fails — milestone partial (T1 output present, T2 not), segments_completed = 0
  6.  T2 latch fires — T2 tool ran but output missing, milestone partial
  7.  Two segments — segment 1 milestone then segment 2 milestone, both accumulated
  8.  Segment 1 fails — segment 2 never runs, segments_completed = 0
  9.  output_binding on T1 — abstract key from binding lands in state, milestone resolves
  10. Partial milestone — milestone declares key T2 never produces, milestone incomplete
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

def _two_transition_abstract(
    t1_tool: str, t1_inputs: list[str], t1_outputs: list[str],
    t2_tool: str, t2_inputs: list[str], t2_outputs: list[str],
    milestone: list[str],
) -> AbstractDSTT:
    return AbstractDSTT(segments=[AbstractSegment(
        transitions=[
            AbstractTransition(id="t1", tool=t1_tool, inputs=t1_inputs, outputs=t1_outputs),
            AbstractTransition(id="t2", tool=t2_tool, inputs=t2_inputs, outputs=t2_outputs),
        ],
        milestone=milestone,
    )])


def _grounded(tid: str, tool: str, inputs: dict, output_binding: dict | None = None) -> dict:
    return {"id": tid, "tool": tool, "inputs": inputs, "outputs": {}, "output_binding": output_binding or {}}


def _run(abstract, stub_responses, initial_state, tool_stubs, monkeypatch):
    import src.tools as tools_mod
    for name, fn in tool_stubs.items():
        monkeypatch.setitem(tools_mod.TOOL_REGISTRY, name, fn)
    stub = StubTransition2ExecClient(stub_responses)
    return execute("test task", initial_state, abstract, stub, available_tools=[])


# ---------------------------------------------------------------------------
# Test 1 — happy path: both transitions complete, milestone fully reached
# ---------------------------------------------------------------------------

def test_both_transitions_complete_milestone_full(monkeypatch):
    """T1 and T2 both succeed. milestone=['deleted', 'success'] — both in milestone_reached."""
    abstract = _two_transition_abstract(
        "remove_stale", ["file_path"], ["deleted"],
        "write_fresh", ["file_path", "content"], ["success"],
        milestone=["deleted", "success"],
    )
    stubs = [
        ok([_grounded("t1", "delete_file", {"file_path": "/tmp/os2ie_sandbox/old.txt"})]),
        ok([_grounded("t2", "create_file", {"file_path": "/tmp/os2ie_sandbox/old.txt", "content": "fresh"})]),
    ]
    result = _run(abstract, stubs,
                  {"file_path": "/tmp/os2ie_sandbox/old.txt", "content": "fresh"},
                  {"delete_file": lambda s: {"deleted": True},
                   "create_file": lambda s: {"success": True}},
                  monkeypatch)

    assert result.status == "completed"
    assert result.segments_completed == 1
    assert "deleted" in result.milestone_reached
    assert "success" in result.milestone_reached
    assert len(result.milestone_reached) == 2


# ---------------------------------------------------------------------------
# Test 2 — multi-key milestone: both keys must land in state
# ---------------------------------------------------------------------------

def test_multi_key_milestone_both_present(monkeypatch):
    """milestone=['copied', 'is_present'] — T1 produces copied, T2 produces is_present."""
    abstract = _two_transition_abstract(
        "backup_config", ["source_path", "destination_path"], ["copied"],
        "verify_backup", ["file_path"], ["is_present"],
        milestone=["copied", "is_present"],
    )
    stubs = [
        ok([_grounded("t1", "copy_file", {
            "source_path": "/tmp/os2ie_sandbox/cfg.yaml",
            "destination_path": "/tmp/os2ie_sandbox/bak/cfg.yaml",
        })]),
        ok([_grounded("t2", "exists", {"file_path": "/tmp/os2ie_sandbox/bak/cfg.yaml"})]),
    ]
    result = _run(abstract, stubs,
                  {"source_path": "/tmp/os2ie_sandbox/cfg.yaml",
                   "destination_path": "/tmp/os2ie_sandbox/bak/cfg.yaml",
                   "file_path": "/tmp/os2ie_sandbox/bak/cfg.yaml"},
                  {"copy_file": lambda s: {"copied": True},
                   "exists": lambda s: {"is_present": True}},
                  monkeypatch)

    assert result.status == "completed"
    assert "copied" in result.milestone_reached
    assert "is_present" in result.milestone_reached


# ---------------------------------------------------------------------------
# Test 3 — text→content thread: T1 output value flows as T2 input value
# ---------------------------------------------------------------------------

def test_text_to_content_thread_milestone(monkeypatch):
    """T1 produces text='hello'. T2 grounded with content='hello' from state. Milestone=['success']."""
    abstract = _two_transition_abstract(
        "read_source", ["source_path"], ["text"],
        "write_output", ["destination_path", "content"], ["success"],
        milestone=["success"],
    )
    # T2 inputs include content resolved from state.text by transition2exec
    stubs = [
        ok([_grounded("t1", "read_file", {"file_path": "/tmp/os2ie_sandbox/in.txt"})]),
        ok([_grounded("t2", "create_file", {
            "file_path": "/tmp/os2ie_sandbox/out.txt",
            "content": "hello",   # threaded from state.text
        })]),
    ]

    captured_content = {}

    def read_fn(s):
        return {"text": "hello"}

    def create_fn(s):
        captured_content["content"] = s.get("content")
        return {"success": True}

    result = _run(abstract, stubs,
                  {"source_path": "/tmp/os2ie_sandbox/in.txt",
                   "destination_path": "/tmp/os2ie_sandbox/out.txt"},
                  {"read_file": read_fn, "create_file": create_fn},
                  monkeypatch)

    assert result.status == "completed"
    assert result.state["text"] == "hello"
    assert result.state["success"] is True
    assert "success" in result.milestone_reached
    assert captured_content["content"] == "hello"


# ---------------------------------------------------------------------------
# Test 4 — T1 finally latch fires: T2 never runs, milestone empty
# ---------------------------------------------------------------------------

def test_t1_latch_fires_t2_never_runs(monkeypatch):
    """T1 tool returns two keys neither matching declared 'text' — ambiguous N:M, escape hatch fires. T2 never runs."""
    abstract = _two_transition_abstract(
        "read_source", ["source_path"], ["text"],
        "write_output", ["destination_path", "content"], ["success"],
        milestone=["success"],
    )
    # Tool returns {"raw_bytes": ..., "encoding": ...} — declared "text" absent,
    # 2 unbound actuals vs 1 declared → ambiguous N:M → escape hatch (not auto-alias).
    stubs = [
        ok([_grounded("t1", "read_file", {"file_path": "/tmp/os2ie_sandbox/in.txt"})]),
        ok([_grounded("t2", "create_file", {"file_path": "/tmp/os2ie_sandbox/out.txt", "content": "x"})]),
    ]

    t2_called = {"called": False}

    def create_fn(s):
        t2_called["called"] = True
        return {"success": True}

    result = _run(abstract, stubs,
                  {"source_path": "/tmp/os2ie_sandbox/in.txt",
                   "destination_path": "/tmp/os2ie_sandbox/out.txt"},
                  {"read_file": lambda s: {"raw_bytes": b"hello", "encoding": "utf-8"},
                   "create_file": create_fn},
                  monkeypatch)

    assert result.status == "failed"
    assert "finally" in result.execution_log[-1].error
    assert result.milestone_reached == []
    assert result.segments_completed == 0
    assert not t2_called["called"], "T2 should never have run after T1 latch fired"


# ---------------------------------------------------------------------------
# Test 5 — T2 tool fails: milestone partial, segments_completed = 0
# ---------------------------------------------------------------------------

def test_t2_tool_fails_milestone_partial(monkeypatch):
    """T1 succeeds (deleted in state). T2 tool raises — execution stops. Milestone empty."""
    abstract = _two_transition_abstract(
        "remove_stale", ["file_path"], ["deleted"],
        "write_fresh", ["file_path", "content"], ["success"],
        milestone=["deleted", "success"],
    )
    stubs = [
        ok([_grounded("t1", "delete_file", {"file_path": "/tmp/os2ie_sandbox/old.txt"})]),
        ok([_grounded("t2", "create_file", {"file_path": "/tmp/os2ie_sandbox/old.txt", "content": "x"})]),
    ]
    result = _run(abstract, stubs,
                  {"file_path": "/tmp/os2ie_sandbox/old.txt", "content": "x"},
                  {"delete_file": lambda s: {"deleted": True},
                   "create_file": lambda s: (_ for _ in ()).throw(RuntimeError("disk full"))},
                  monkeypatch)

    assert result.status == "failed"
    assert result.segments_completed == 0
    assert "deleted" in result.state          # T1 output is in state
    assert "success" not in result.state      # T2 never completed
    assert result.milestone_reached == []     # milestone check never ran


# ---------------------------------------------------------------------------
# Test 6 — T2 latch fires: T2 tool ran but declared output missing
# ---------------------------------------------------------------------------

def test_t2_latch_fires_milestone_partial(monkeypatch):
    """T1 ok. T2 tool returns wrong key — ambiguous mismatch. Milestone has only T1's keys."""
    abstract = _two_transition_abstract(
        "make_dir", ["directory_path"], ["created"],
        "write_report", ["file_path", "content"], ["success"],
        milestone=["created", "success"],
    )
    stubs = [
        ok([_grounded("t1", "make_directory", {"directory_path": "/tmp/os2ie_sandbox/d"})]),
        ok([_grounded("t2", "create_file", {"file_path": "/tmp/os2ie_sandbox/d/r.txt", "content": "x"})]),
    ]
    result = _run(abstract, stubs,
                  {"directory_path": "/tmp/os2ie_sandbox/d",
                   "file_path": "/tmp/os2ie_sandbox/d/r.txt", "content": "x"},
                  {"make_directory": lambda s: {"created": True},
                   # create_file returns two unbound keys vs one declared — ambiguous
                   "create_file": lambda s: {"ok": True, "written": True}},
                  monkeypatch)

    assert result.status == "failed"
    assert "finally" in result.execution_log[-1].error
    assert "success" in result.execution_log[-1].error
    assert result.segments_completed == 0
    assert result.milestone_reached == []     # milestone check never ran (failed mid-segment)


# ---------------------------------------------------------------------------
# Test 7 — two segments: milestone accumulated across both
# ---------------------------------------------------------------------------

def test_two_segments_milestone_accumulated(monkeypatch):
    """Segment 1: exists → deleted. Segment 2: create_file → success. Both milestones accumulated."""
    abstract = AbstractDSTT(segments=[
        AbstractSegment(
            transitions=[
                AbstractTransition(id="t1", tool="check_exists", inputs=["file_path"], outputs=["is_present"]),
                AbstractTransition(id="t2", tool="remove_file", inputs=["file_path"], outputs=["deleted"]),
            ],
            milestone=["deleted"],
        ),
        AbstractSegment(
            transitions=[
                AbstractTransition(id="t3", tool="write_fresh", inputs=["file_path", "content"], outputs=["success"]),
            ],
            milestone=["success"],
        ),
    ])
    stubs = [
        ok([_grounded("t1", "exists", {"file_path": "/tmp/os2ie_sandbox/f.txt"})]),
        ok([_grounded("t2", "delete_file", {"file_path": "/tmp/os2ie_sandbox/f.txt"})]),
        ok([_grounded("t3", "create_file", {"file_path": "/tmp/os2ie_sandbox/f.txt", "content": "new"})]),
    ]
    result = _run(abstract, stubs,
                  {"file_path": "/tmp/os2ie_sandbox/f.txt", "content": "new"},
                  {"exists": lambda s: {"is_present": True},
                   "delete_file": lambda s: {"deleted": True},
                   "create_file": lambda s: {"success": True}},
                  monkeypatch)

    assert result.status == "completed"
    assert result.segments_completed == 2
    assert "deleted" in result.milestone_reached
    assert "success" in result.milestone_reached


# ---------------------------------------------------------------------------
# Test 8 — segment 1 fails: segment 2 never runs, segments_completed = 0
# ---------------------------------------------------------------------------

def test_segment1_fails_segment2_never_runs(monkeypatch):
    """T2 in segment 1 fails. Segment 2 never starts. segments_completed = 0."""
    abstract = AbstractDSTT(segments=[
        AbstractSegment(
            transitions=[
                AbstractTransition(id="t1", tool="make_dir", inputs=["directory_path"], outputs=["created"]),
                AbstractTransition(id="t2", tool="copy_artifact", inputs=["source_path", "destination_path"], outputs=["copied"]),
            ],
            milestone=["created", "copied"],
        ),
        AbstractSegment(
            transitions=[
                AbstractTransition(id="t3", tool="verify_copy", inputs=["file_path"], outputs=["is_present"]),
            ],
            milestone=["is_present"],
        ),
    ])

    t3_called = {"called": False}

    def verify_fn(s):
        t3_called["called"] = True
        return {"is_present": True}

    stubs = [
        ok([_grounded("t1", "make_directory", {"directory_path": "/tmp/os2ie_sandbox/d"})]),
        ok([_grounded("t2", "copy_file", {
            "source_path": "/tmp/os2ie_sandbox/a.sh",
            "destination_path": "/tmp/os2ie_sandbox/d/a.sh",
        })]),
        ok([_grounded("t3", "exists", {"file_path": "/tmp/os2ie_sandbox/d/a.sh"})]),
    ]
    result = _run(abstract, stubs,
                  {"directory_path": "/tmp/os2ie_sandbox/d",
                   "source_path": "/tmp/os2ie_sandbox/a.sh",
                   "destination_path": "/tmp/os2ie_sandbox/d/a.sh",
                   "file_path": "/tmp/os2ie_sandbox/d/a.sh"},
                  {"make_directory": lambda s: {"created": True},
                   "copy_file": lambda s: (_ for _ in ()).throw(RuntimeError("permission denied")),
                   "exists": verify_fn},
                  monkeypatch)

    assert result.status == "failed"
    assert result.segments_completed == 0
    assert not t3_called["called"], "Segment 2 should never have run"
    assert result.milestone_reached == []


# ---------------------------------------------------------------------------
# Test 9 — output_binding on T1: abstract key lands in state, milestone resolves
# ---------------------------------------------------------------------------

def test_output_binding_t1_milestone_resolves(monkeypatch):
    """T1 shell returns return_code. output_binding: return_code→moved. milestone=['moved']."""
    abstract = _two_transition_abstract(
        "move_via_shell", ["source_path", "destination_path"], ["moved"],
        "verify_moved", ["file_path"], ["is_present"],
        milestone=["moved", "is_present"],
    )
    stubs = [
        ok([_grounded("t1", "run_shell_command",
                      {"command": "mv /tmp/os2ie_sandbox/a.sh /tmp/os2ie_sandbox/bak/a.sh"},
                      output_binding={"return_code": "moved"})]),
        ok([_grounded("t2", "exists", {"file_path": "/tmp/os2ie_sandbox/bak/a.sh"})]),
    ]
    result = _run(abstract, stubs,
                  {"source_path": "/tmp/os2ie_sandbox/a.sh",
                   "destination_path": "/tmp/os2ie_sandbox/bak/a.sh",
                   "file_path": "/tmp/os2ie_sandbox/bak/a.sh"},
                  {"run_shell_command": lambda s: {"stdout": "", "stderr": "", "return_code": 0},
                   "exists": lambda s: {"is_present": True}},
                  monkeypatch)

    assert result.status == "completed"
    assert result.state["moved"] == 0           # bound from return_code
    assert "moved" in result.milestone_reached
    assert "is_present" in result.milestone_reached


# ---------------------------------------------------------------------------
# Test 10 — partial milestone: one milestone key never produced
# ---------------------------------------------------------------------------

def test_partial_milestone_key_missing(monkeypatch):
    """Segment milestone declares ['deleted', 'checksum']. T1 produces deleted, no tool produces checksum.
    Kernel completes (milestone check is non-blocking), but milestone_reached is partial."""
    abstract = _two_transition_abstract(
        "remove_stale", ["file_path"], ["deleted"],
        "write_fresh", ["file_path", "content"], ["success"],
        milestone=["deleted", "checksum"],   # checksum never produced by any tool
    )
    stubs = [
        ok([_grounded("t1", "delete_file", {"file_path": "/tmp/os2ie_sandbox/f.txt"})]),
        ok([_grounded("t2", "create_file", {"file_path": "/tmp/os2ie_sandbox/f.txt", "content": "x"})]),
    ]
    result = _run(abstract, stubs,
                  {"file_path": "/tmp/os2ie_sandbox/f.txt", "content": "x"},
                  {"delete_file": lambda s: {"deleted": True},
                   "create_file": lambda s: {"success": True}},
                  monkeypatch)

    assert result.status == "completed"          # kernel does not fail on partial milestone
    assert result.segments_completed == 1
    assert "deleted" in result.milestone_reached
    assert "checksum" not in result.milestone_reached   # never produced
    assert "success" not in result.milestone_reached    # not declared in milestone
