"""
v1.1 — list_directory focused tests

All tests use StubTransition2ExecClient (no live LLM, no network).
Safe to run repeatedly — list_directory is read-only and idempotent.

Scenarios:
  01  basic listing — correct entries returned
  02  empty directory — entries=[], not a failure
  03  non-recursive — subdirectory contents do not appear
  04  directory_path sourced from state — key resolution is correct
  05  missing directory — tool raises, executor returns failed
  06  entries key present in final state after execution
  07  multiple entries — all immediate children accounted for
  08  directory with mixed files and subdirs — entries include both
"""
from __future__ import annotations
import pytest
from src.kernel import execute
from src.models import AbstractDSTT, AbstractSegment, AbstractTransition
from tests.stub_t2e import StubTransition2ExecClient, ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _abstract_dstt(transition_id: str = "t1") -> AbstractDSTT:
    """Single-transition abstract DSTT for list_directory."""
    return AbstractDSTT(
        segments=[
            AbstractSegment(
                transitions=[
                    AbstractTransition(
                        id=transition_id,
                        tool="list_directory",
                        inputs=["directory_path"],
                        outputs=["entries"],
                    )
                ],
                milestone=["entries"],
            )
        ]
    )


def _stub(transition_id: str, directory_path: str) -> StubTransition2ExecClient:
    """Stub that returns a single list_directory grounded transition."""
    return StubTransition2ExecClient(
        [ok([{
            "id": transition_id,
            "tool": "list_directory",
            "inputs": {"directory_path": directory_path},
            "outputs": {"entries": "list[str]"},
        }])]
    )


def run(directory_path: str, state: dict | None = None) -> object:
    initial_state = {"directory_path": directory_path}
    if state:
        initial_state.update(state)
    t2e = _stub("t1", directory_path)
    return execute("List files", initial_state, _abstract_dstt(), t2e, available_tools=[])


# ---------------------------------------------------------------------------
# 01 — basic listing
# ---------------------------------------------------------------------------

def test_01_basic_listing(tmp_path):
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.txt").write_text("b")

    result = run(str(tmp_path))

    assert result.status == "completed"
    entries = result.state.get("entries", [])
    names = {e.split("/")[-1] for e in entries}
    assert "alpha.txt" in names
    assert "beta.txt" in names


# ---------------------------------------------------------------------------
# 02 — empty directory
# ---------------------------------------------------------------------------

def test_02_empty_directory(tmp_path):
    empty = tmp_path / "empty_dir"
    empty.mkdir()

    result = run(str(empty))

    assert result.status == "completed"
    assert result.state.get("entries") == []


# ---------------------------------------------------------------------------
# 03 — non-recursive (subdirectory contents must not appear)
# ---------------------------------------------------------------------------

def test_03_non_recursive(tmp_path):
    (tmp_path / "top.txt").write_text("top")
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested")

    result = run(str(tmp_path))

    assert result.status == "completed"
    entries = result.state.get("entries", [])
    names = {e.split("/")[-1] for e in entries}
    assert "top.txt" in names
    assert "sub" in names          # subdir itself appears
    assert "nested.txt" not in names  # but not its contents


# ---------------------------------------------------------------------------
# 04 — directory_path is read from state (key resolution)
# ---------------------------------------------------------------------------

def test_04_directory_path_from_state(tmp_path):
    (tmp_path / "c.py").write_text("")

    # directory_path is already in state — stub passes it through unchanged
    result = run(str(tmp_path))

    assert result.status == "completed"
    assert result.state["directory_path"] == str(tmp_path)


# ---------------------------------------------------------------------------
# 05 — non-existent directory → tool raises → executor returns failed
# ---------------------------------------------------------------------------

def test_05_missing_directory(tmp_path):
    ghost = str(tmp_path / "does_not_exist")

    result = run(ghost)

    assert result.status == "failed"
    assert result.execution_log[-1].error is not None
    assert result.execution_log[-1].tool == "list_directory"


# ---------------------------------------------------------------------------
# 06 — entries key is present in final state
# ---------------------------------------------------------------------------

def test_06_entries_in_final_state(tmp_path):
    (tmp_path / "x.txt").write_text("")

    result = run(str(tmp_path))

    assert result.status == "completed"
    assert "entries" in result.state
    assert isinstance(result.state["entries"], list)


# ---------------------------------------------------------------------------
# 07 — all immediate children accounted for (exact count)
# ---------------------------------------------------------------------------

def test_07_exact_child_count(tmp_path):
    for name in ["one.txt", "two.txt", "three.txt"]:
        (tmp_path / name).write_text("")

    result = run(str(tmp_path))

    assert result.status == "completed"
    assert len(result.state.get("entries", [])) == 3


# ---------------------------------------------------------------------------
# 08 — mixed files and subdirectories both appear
# ---------------------------------------------------------------------------

def test_08_mixed_files_and_subdirs(tmp_path):
    (tmp_path / "file.txt").write_text("")
    (tmp_path / "pkg").mkdir()

    result = run(str(tmp_path))

    assert result.status == "completed"
    names = {e.split("/")[-1] for e in result.state.get("entries", [])}
    assert "file.txt" in names
    assert "pkg" in names
