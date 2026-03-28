"""
Two-transition DSTT — live service tests.

Each test covers one seed from training/two_transition_dstt/seed.json.

Protocol per test:
  1. Compile T1 against live transition2exec service
  2. Verify T1 compiled to expected grounded tool
  3. Seed state with T1 outputs (deterministic — no real tool dispatch)
  4. Compile T2 against enriched state
  5. Verify T2 compiled to expected tool and resolved inputs from state

The pass criterion is state threading: transition2exec must resolve T2's
inputs from the enriched state that includes T1's outputs. Particularly
the text→content thread (tt01, tt06) and destination_path reuse (tt03, tt07).

Requires transition2exec running at http://127.0.0.1:8000.
"""
from __future__ import annotations
import pytest
from src.clients import Transition2ExecClient
from src.catalog import build_catalog
from src.models import AbstractTransition

T2E = Transition2ExecClient("http://127.0.0.1:8000")
CATALOG = build_catalog()

TASK = "two-transition integration test"


def compile_transition(abstract_transition: AbstractTransition, state: dict) -> object:
    exec_dstt, _ = T2E.compile(TASK, state, abstract_transition, available_tools=CATALOG)
    return exec_dstt


def grounded(exec_dstt) -> object:
    """Return first grounded transition from compiled ExecutableDSTT."""
    return exec_dstt.segments[0].transitions[0]


# ---------------------------------------------------------------------------
# tt01 — read_source_file → write_output_file  (text → content thread)
# ---------------------------------------------------------------------------

def test_tt01_read_then_write():
    """T1: read_file. T2: create_file. T2 content input resolved from state.text (T1 output)."""
    t1_abstract = AbstractTransition(
        id="t1", tool="read_source_file",
        inputs=["source_path"], outputs=["text"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="write_output_file",
        inputs=["destination_path", "content"], outputs=["success"],
    )
    initial_state = {
        "source_path": "/tmp/os2ie_sandbox/input.txt",
        "destination_path": "/tmp/os2ie_sandbox/output.txt",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok", f"T1 compile failed: {exec1}"
    g1 = grounded(exec1)
    assert g1.tool == "read_file", f"T1 expected read_file, got {g1.tool}"

    # Seed T1 output into state
    state_after_t1 = {**initial_state, "text": "hello from input.txt"}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok", f"T2 compile failed: {exec2}"
    g2 = grounded(exec2)
    assert g2.tool == "create_file", f"T2 expected create_file, got {g2.tool}"
    assert "file_path" in g2.inputs, "T2 missing file_path"
    assert "content" in g2.inputs, "T2 missing content — text→content thread broken"
    assert g2.inputs["content"] == "hello from input.txt", \
        f"T2 content not threaded from state.text: {g2.inputs['content']!r}"


# ---------------------------------------------------------------------------
# tt02 — create_output_directory → write_report_file
# ---------------------------------------------------------------------------

def test_tt02_make_dir_then_create_file():
    """T1: make_directory. T2: create_file. created in state, T2 resolves file_path and content."""
    t1_abstract = AbstractTransition(
        id="t1", tool="create_output_directory",
        inputs=["directory_path"], outputs=["created"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="write_report_file",
        inputs=["file_path", "content"], outputs=["success"],
    )
    initial_state = {
        "directory_path": "/tmp/os2ie_sandbox/reports",
        "file_path": "/tmp/os2ie_sandbox/reports/summary.txt",
        "content": "Build complete.",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "make_directory", f"T1 expected make_directory, got {g1.tool}"

    state_after_t1 = {**initial_state, "created": True}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "create_file", f"T2 expected create_file, got {g2.tool}"
    assert g2.inputs.get("file_path") == "/tmp/os2ie_sandbox/reports/summary.txt"
    assert g2.inputs.get("content") == "Build complete."


# ---------------------------------------------------------------------------
# tt03 — backup_config_file → verify_backup_exists
# ---------------------------------------------------------------------------

def test_tt03_copy_then_verify():
    """T1: copy_file. T2: exists. file_path from context flows to T2."""
    t1_abstract = AbstractTransition(
        id="t1", tool="backup_config_file",
        inputs=["source_path", "destination_path"], outputs=["copied"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="verify_backup_exists",
        inputs=["file_path"], outputs=["is_present"],
    )
    initial_state = {
        "source_path": "/tmp/os2ie_sandbox/config.yaml",
        "destination_path": "/tmp/os2ie_sandbox/backup/config.yaml",
        "file_path": "/tmp/os2ie_sandbox/backup/config.yaml",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "copy_file", f"T1 expected copy_file, got {g1.tool}"

    state_after_t1 = {**initial_state, "copied": True}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "exists", f"T2 expected exists, got {g2.tool}"
    assert g2.inputs.get("file_path") == "/tmp/os2ie_sandbox/backup/config.yaml"


# ---------------------------------------------------------------------------
# tt04 — check_old_artifact_exists → remove_old_artifact
# ---------------------------------------------------------------------------

def test_tt04_exists_then_delete():
    """T1: exists. T2: delete_file. file_path threads through both from initial context."""
    t1_abstract = AbstractTransition(
        id="t1", tool="check_old_artifact_exists",
        inputs=["file_path"], outputs=["is_present"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="remove_old_artifact",
        inputs=["file_path"], outputs=["deleted"],
    )
    initial_state = {"file_path": "/tmp/os2ie_sandbox/old_build.tar.gz"}

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "exists", f"T1 expected exists, got {g1.tool}"

    state_after_t1 = {**initial_state, "is_present": True}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "delete_file", f"T2 expected delete_file, got {g2.tool}"
    assert g2.inputs.get("file_path") == "/tmp/os2ie_sandbox/old_build.tar.gz"


# ---------------------------------------------------------------------------
# tt05 — list_project_files → read_readme
# ---------------------------------------------------------------------------

def test_tt05_list_then_read():
    """T1: list_directory. T2: read_file. file_path from context, entries in state."""
    t1_abstract = AbstractTransition(
        id="t1", tool="list_project_files",
        inputs=["directory_path"], outputs=["entries"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="read_readme",
        inputs=["file_path"], outputs=["text"],
    )
    initial_state = {
        "directory_path": "/tmp/os2ie_sandbox/project",
        "file_path": "/tmp/os2ie_sandbox/project/README.md",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "list_directory", f"T1 expected list_directory, got {g1.tool}"

    state_after_t1 = {**initial_state, "entries": ["README.md", "src", "tests"]}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "read_file", f"T2 expected read_file, got {g2.tool}"
    assert g2.inputs.get("file_path") == "/tmp/os2ie_sandbox/project/README.md"


# ---------------------------------------------------------------------------
# tt06 — read_log_entry → append_to_archive  (text → content thread)
# ---------------------------------------------------------------------------

def test_tt06_read_then_append():
    """T1: read_file. T2: append_to_file. T2 content resolved from state.text (T1 output)."""
    t1_abstract = AbstractTransition(
        id="t1", tool="read_log_entry",
        inputs=["source_path"], outputs=["text"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="append_to_archive",
        inputs=["file_path", "content"], outputs=["success"],
    )
    initial_state = {
        "source_path": "/tmp/os2ie_sandbox/today.log",
        "file_path": "/tmp/os2ie_sandbox/archive.log",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "read_file", f"T1 expected read_file, got {g1.tool}"

    state_after_t1 = {**initial_state, "text": "2026-03-28 build succeeded"}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "append_to_file", f"T2 expected append_to_file, got {g2.tool}"
    assert "file_path" in g2.inputs
    assert "content" in g2.inputs, "T2 missing content — text→content thread broken"
    assert g2.inputs["content"] == "2026-03-28 build succeeded", \
        f"T2 content not threaded from state.text: {g2.inputs['content']!r}"


# ---------------------------------------------------------------------------
# tt07 — create_backup_directory → move_artifact_to_backup
# ---------------------------------------------------------------------------

def test_tt07_make_dir_then_move():
    """T1: make_directory. T2: move_file. source/destination from context, created in state."""
    t1_abstract = AbstractTransition(
        id="t1", tool="create_backup_directory",
        inputs=["directory_path"], outputs=["created"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="move_artifact_to_backup",
        inputs=["source_path", "destination_path"], outputs=["moved"],
    )
    initial_state = {
        "directory_path": "/tmp/os2ie_sandbox/backup",
        "source_path": "/tmp/os2ie_sandbox/deploy.sh",
        "destination_path": "/tmp/os2ie_sandbox/backup/deploy.sh",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "make_directory", f"T1 expected make_directory, got {g1.tool}"

    state_after_t1 = {**initial_state, "created": True}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "move_file", f"T2 expected move_file, got {g2.tool}"
    assert g2.inputs.get("source_path") == "/tmp/os2ie_sandbox/deploy.sh"
    assert g2.inputs.get("destination_path") == "/tmp/os2ie_sandbox/backup/deploy.sh"


# ---------------------------------------------------------------------------
# tt08 — remove_stale_output → write_fresh_output
# ---------------------------------------------------------------------------

def test_tt08_delete_then_create():
    """T1: delete_file. T2: create_file. deleted in state, file_path and content from context."""
    t1_abstract = AbstractTransition(
        id="t1", tool="remove_stale_output",
        inputs=["file_path"], outputs=["deleted"],
    )
    t2_abstract = AbstractTransition(
        id="t2", tool="write_fresh_output",
        inputs=["file_path", "content"], outputs=["success"],
    )
    initial_state = {
        "file_path": "/tmp/os2ie_sandbox/result.txt",
        "content": "v2 build output",
    }

    exec1 = compile_transition(t1_abstract, initial_state)
    assert exec1.status == "ok"
    g1 = grounded(exec1)
    assert g1.tool == "delete_file", f"T1 expected delete_file, got {g1.tool}"

    state_after_t1 = {**initial_state, "deleted": True}

    exec2 = compile_transition(t2_abstract, state_after_t1)
    assert exec2.status == "ok"
    g2 = grounded(exec2)
    assert g2.tool == "create_file", f"T2 expected create_file, got {g2.tool}"
    assert g2.inputs.get("file_path") == "/tmp/os2ie_sandbox/result.txt"
    assert g2.inputs.get("content") == "v2 build output"
