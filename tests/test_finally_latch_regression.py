"""
Finally latch — output satisfaction regression tests.

Tests every catalog tool against the latch: does the tool's natural output
satisfy the abstract transition's declared outputs? Also covers the binding
path (run_shell_command with output_binding → abstract key).

Matrix:
  Row = catalog tool
  Col = declared output key (what abstract DSTT planner might name it)
  Pass = latch passes (key lands in state)
  FAIL = latch fires (key missing — gap to fix in output_binding or planner)

This suite is the regression guard for the finally latch. If a new tool is
added to the catalog, add a row here. If a planner or output_binding change
affects key names, this suite will catch it.
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

def _dstt(abstract_tool: str, declared_outputs: list[str],
          grounded_tool: str, grounded_inputs: dict,
          output_binding: dict | None = None) -> tuple[AbstractDSTT, ExecutableDSTT]:
    abstract = AbstractDSTT(segments=[AbstractSegment(
        transitions=[AbstractTransition(
            id="t1", tool=abstract_tool,
            inputs=list(grounded_inputs.keys()),
            outputs=declared_outputs,
        )],
        milestone=declared_outputs,
    )])
    grounded = ok([{
        "id": "t1",
        "tool": grounded_tool,
        "inputs": grounded_inputs,
        "outputs": {},
        "output_binding": output_binding or {},
    }])
    return abstract, grounded


def run(abstract, grounded_resp, initial_state, tool_stub, monkeypatch):
    import src.tools as tools_mod
    for tool_name, fn in tool_stub.items():
        monkeypatch.setitem(tools_mod.TOOL_REGISTRY, tool_name, fn)
    stub = StubTransition2ExecClient([grounded_resp])
    return execute("test task", initial_state, abstract, stub, available_tools=[])


# ---------------------------------------------------------------------------
# exists — natural output: is_present
# ---------------------------------------------------------------------------

def test_exists_natural_output_passes(monkeypatch):
    """exists → is_present: natural key, latch passes."""
    abstract, grounded = _dstt(
        "check_file_exists", ["is_present"],
        "exists", {"file_path": "/tmp/os2ie_sandbox/f.txt"},
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/f.txt"},
                 {"exists": lambda s: {"is_present": True}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["is_present"] is True


def test_exists_1to1_auto_alias(monkeypatch):
    """Planner declares 'file_exists' but tool returns 'is_present' — 1:1 auto-alias, latch passes."""
    abstract, grounded = _dstt(
        "check_file_exists", ["file_exists"],   # declared key differs from natural
        "exists", {"file_path": "/tmp/os2ie_sandbox/f.txt"},
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/f.txt"},
                 {"exists": lambda s: {"is_present": True}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["file_exists"] is True   # aliased from is_present


# ---------------------------------------------------------------------------
# list_directory — natural output: entries
# ---------------------------------------------------------------------------

def test_list_directory_natural_output_passes(monkeypatch):
    """list_directory → entries: natural key, latch passes."""
    abstract, grounded = _dstt(
        "list_project_files", ["entries"],
        "list_directory", {"directory_path": "/tmp/os2ie_sandbox", "recursive": False},
    )
    result = run(abstract, grounded,
                 {"directory_path": "/tmp/os2ie_sandbox"},
                 {"list_directory": lambda s: {"entries": ["a.py", "b.py"]}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["entries"] == ["a.py", "b.py"]


def test_list_directory_1to1_auto_alias(monkeypatch):
    """Planner declares 'file_list' but tool returns 'entries' — 1:1 auto-alias, latch passes."""
    abstract, grounded = _dstt(
        "list_project_files", ["file_list"],   # declared key differs from natural
        "list_directory", {"directory_path": "/tmp/os2ie_sandbox", "recursive": False},
    )
    result = run(abstract, grounded,
                 {"directory_path": "/tmp/os2ie_sandbox"},
                 {"list_directory": lambda s: {"entries": ["a.py"]}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["file_list"] == ["a.py"]   # aliased from entries


# ---------------------------------------------------------------------------
# read_file — natural output: text
# ---------------------------------------------------------------------------

def test_read_file_natural_output_passes(monkeypatch):
    """read_file → text: natural key, latch passes."""
    abstract, grounded = _dstt(
        "read_source_file", ["text"],
        "read_file", {"file_path": "/tmp/os2ie_sandbox/a.txt"},
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/a.txt"},
                 {"read_file": lambda s: {"text": "hello"}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["text"] == "hello"


def test_read_file_abstract_key_via_binding_passes(monkeypatch):
    """Planner declares 'content'. output_binding maps text → content. Latch passes."""
    abstract, grounded = _dstt(
        "read_source_file", ["content"],
        "read_file", {"file_path": "/tmp/os2ie_sandbox/a.txt"},
        output_binding={"text": "content"},
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/a.txt"},
                 {"read_file": lambda s: {"text": "hello"}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["content"] == "hello"   # bound key
    assert result.state["text"] == "hello"      # grounded key also in state


def test_read_file_abstract_key_no_binding_auto_aliases(monkeypatch):
    """Planner declares 'content', no output_binding — 1:1 auto-alias resolves text→content."""
    abstract, grounded = _dstt(
        "read_source_file", ["content"],   # abstract key
        "read_file", {"file_path": "/tmp/os2ie_sandbox/a.txt"},
        output_binding={},                 # no binding — auto-alias kicks in
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/a.txt"},
                 {"read_file": lambda s: {"text": "hello"}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["content"] == "hello"   # aliased from text


# ---------------------------------------------------------------------------
# create_file — natural output: success
# ---------------------------------------------------------------------------

def test_create_file_natural_output_passes(monkeypatch):
    """create_file → success: natural key, latch passes."""
    abstract, grounded = _dstt(
        "write_output_file", ["success"],
        "create_file", {"file_path": "/tmp/os2ie_sandbox/out.txt", "content": "hi"},
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/out.txt", "content": "hi"},
                 {"create_file": lambda s: {"success": True}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["success"] is True


def test_create_file_1to1_auto_alias(monkeypatch):
    """Planner declares 'created' but tool returns 'success' — 1:1 auto-alias, latch passes."""
    abstract, grounded = _dstt(
        "write_output_file", ["created"],   # declared key differs from natural
        "create_file", {"file_path": "/tmp/os2ie_sandbox/out.txt", "content": "hi"},
    )
    result = run(abstract, grounded,
                 {"file_path": "/tmp/os2ie_sandbox/out.txt", "content": "hi"},
                 {"create_file": lambda s: {"success": True}}, monkeypatch)
    assert result.status == "completed"
    assert result.state["created"] is True   # aliased from success


# ---------------------------------------------------------------------------
# run_shell_command — outputs: stdout, stderr, return_code
# Binding required when abstract key differs from shell key
# ---------------------------------------------------------------------------

def test_shell_natural_outputs_pass(monkeypatch):
    """Shell transition declares [stdout, return_code] — natural keys, latch passes."""
    abstract, grounded = _dstt(
        "run_date_command", ["stdout", "return_code"],
        "run_shell_command", {"command": "date +%Y-%m-%d"},
    )
    result = run(abstract, grounded, {},
                 {"run_shell_command": lambda s: {
                     "stdout": "2026-03-28", "stderr": "", "return_code": 0}},
                 monkeypatch)
    assert result.status == "completed"
    assert result.state["return_code"] == 0


def test_shell_abstract_output_via_binding_passes(monkeypatch):
    """Shell declares ['python_version']. output_binding stdout→python_version. Latch passes."""
    abstract, grounded = _dstt(
        "check_python_version", ["python_version"],
        "run_shell_command", {"command": "python3 --version"},
        output_binding={"stdout": "python_version"},
    )
    result = run(abstract, grounded, {},
                 {"run_shell_command": lambda s: {
                     "stdout": "Python 3.14.0", "stderr": "", "return_code": 0}},
                 monkeypatch)
    assert result.status == "completed"
    assert result.state["python_version"] == "Python 3.14.0"


def test_shell_abstract_output_no_binding_fires_latch(monkeypatch):
    """Shell declares ['python_version'] with no binding — latch fires. stdout ≠ python_version."""
    abstract, grounded = _dstt(
        "check_python_version", ["python_version"],
        "run_shell_command", {"command": "python3 --version"},
        output_binding={},   # missing binding
    )
    result = run(abstract, grounded, {},
                 {"run_shell_command": lambda s: {
                     "stdout": "Python 3.14.0", "stderr": "", "return_code": 0}},
                 monkeypatch)
    assert result.status == "failed"
    assert "finally" in result.execution_log[-1].error
    assert "python_version" in result.execution_log[-1].error


# ---------------------------------------------------------------------------
# delete_file, copy_file, move_file, make_directory, remove_directory
# Natural keys — quick pass checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool,declared,stub_output", [
    ("delete_file",       ["deleted"],  {"deleted": True}),
    ("copy_file",         ["copied"],   {"copied": True}),
    ("move_file",         ["moved"],    {"moved": True}),
    ("make_directory",    ["created"],  {"created": True}),
    ("remove_directory",  ["removed"],  {"removed": True}),
    ("append_to_file",    ["success"],  {"success": True}),
])
def test_natural_output_keys_pass(tool, declared, stub_output, monkeypatch):
    """Each catalog tool's natural output key satisfies the latch."""
    inputs = {"file_path": "/tmp/os2ie_sandbox/f.txt"}
    if tool in ("copy_file", "move_file"):
        inputs = {"source_path": "/tmp/os2ie_sandbox/a.txt",
                  "destination_path": "/tmp/os2ie_sandbox/b.txt"}
    elif tool in ("make_directory", "remove_directory"):
        inputs = {"directory_path": "/tmp/os2ie_sandbox/d"}
    elif tool == "append_to_file":
        inputs = {"file_path": "/tmp/os2ie_sandbox/f.txt", "content": "x"}

    abstract, grounded = _dstt(f"abstract_{tool}", declared, tool, inputs)
    result = run(abstract, grounded, inputs,
                 {tool: lambda s, o=stub_output: o}, monkeypatch)
    assert result.status == "completed", \
        f"{tool}: latch fired unexpectedly — {result.execution_log[-1].error}"
