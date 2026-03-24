"""
Seed integration tests — training/basic_seed.md

Each test calls the real task2plan and transition2exec services and asserts
on observable outcomes (filesystem state, shell output). No hardcoded DSTTs.

Requires both services to be running:
  task2plan      http://127.0.0.1:8000
  transition2exec http://127.0.0.1:8001
"""
from __future__ import annotations
import pytest
from src.clients import Task2PlanClient, Transition2ExecClient
from src.kernel import execute

T2P = Task2PlanClient("http://127.0.0.1:8000")
T2E = Transition2ExecClient("http://127.0.0.1:8002")


def run(task: str, state: dict) -> object:
    abstract_dstt, meta = T2P.plan(task)
    return execute(task, state, abstract_dstt, T2E)


# ---------------------------------------------------------------------------
# Single transition
# ---------------------------------------------------------------------------

def test_01_check_file_exists(tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("print('hello')")
    result = run(f"Check whether hello.py exists in {tmp_path}", {"file_path": str(f)})
    assert result.status == "completed"
    assert result.state.get("is_present") is True


def test_01b_check_file_not_exists(tmp_path):
    f = tmp_path / "hello.py"
    result = run(f"Check whether hello.py exists in {tmp_path}", {"file_path": str(f)})
    assert result.status == "completed"
    assert result.state.get("is_present") is False


def test_02_list_directory(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    result = run(f"List all files in {tmp_path}", {"directory_path": str(tmp_path)})
    assert result.status == "completed"
    assert len(result.state.get("entries", [])) >= 2


def test_03_read_file(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("# hello")
    result = run(f"Read the contents of {f}", {"file_path": str(f)})
    assert result.status == "completed"
    assert "hello" in result.state.get("text", "")


def test_04_delete_file(tmp_path):
    f = tmp_path / "temp.txt"
    f.write_text("bye")
    result = run(f"Delete the file {f}", {"file_path": str(f)})
    assert result.status == "completed"
    assert result.state.get("deleted") is True
    assert not f.exists()


def test_05_create_file(tmp_path):
    f = tmp_path / "notes.txt"
    result = run(
        f'Create the file {f} with content "first note"',
        {"file_path": str(f), "content": "first note"},
    )
    assert result.status == "completed"
    assert f.exists()
    assert f.read_text() == "first note"


def test_06_check_python_version():
    result = run("Check the Python version installed on this system", {})
    assert result.status == "completed"
    assert result.state.get("return_code") == 0
    output = result.state.get("stdout", "") + result.state.get("stderr", "")
    assert "Python" in output


def test_07_count_python_files(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    result = run(
        f"Count all Python files in {tmp_path}",
        {"working_directory": str(tmp_path)},
    )
    assert result.status == "completed"
    assert result.state.get("return_code") == 0


def test_08_find_files_containing_string(tmp_path):
    f = tmp_path / "main.py"
    f.write_text("import fastapi\napp = FastAPI()")
    result = run(
        f'Find all files containing "import fastapi" in {tmp_path}',
        {"working_directory": str(tmp_path)},
    )
    assert result.status == "completed"
    assert result.state.get("return_code") == 0
    assert "main.py" in result.state.get("stdout", "")


# ---------------------------------------------------------------------------
# Multi-step
# ---------------------------------------------------------------------------

def test_09_create_then_read(tmp_path):
    f = tmp_path / "temp.txt"
    result = run(
        f'Create {f} with content "hello" then read it back',
        {"file_path": str(f), "content": "hello"},
    )
    assert result.status == "completed"
    assert "hello" in result.state.get("text", "")


def test_10_create_and_append_twice(tmp_path):
    f = tmp_path / "log.txt"
    result = run(
        f'Create {f}, append "line1", then append "line2"',
        {"file_path": str(f)},
    )
    assert result.status == "completed"
    assert f.exists()
    content = f.read_text()
    assert "line1" in content
    assert "line2" in content


def test_11_make_dir_then_create_file(tmp_path):
    d = tmp_path / "newdir"
    f = d / "file.txt"
    result = run(
        f"Create the directory {d} then create the file {f} with content 'hi'",
        {"directory_path": str(d), "file_path": str(f), "content": "hi"},
    )
    assert result.status == "completed"
    assert d.exists()
    assert f.exists()


def test_12_shell_stdout_to_file(tmp_path):
    out = tmp_path / "out.txt"
    result = run(
        f"Run the command 'echo hello_from_shell' and write its stdout to {out}",
        {"file_path": str(out)},
    )
    assert result.status == "completed"
    assert out.exists()
    assert "hello_from_shell" in out.read_text()


# ---------------------------------------------------------------------------
# Failure cases
# ---------------------------------------------------------------------------

def test_13_read_nonexistent_file(tmp_path):
    f = tmp_path / "ghost.txt"
    result = run(f"Read the contents of {f}", {"file_path": str(f)})
    assert result.status == "failed"
    assert result.execution_log[-1].error is not None


def test_14_delete_nonexistent_file(tmp_path):
    f = tmp_path / "ghost.txt"
    result = run(f"Delete the file {f}", {"file_path": str(f)})
    # Not an error — executor continues, deleted=False
    assert result.status == "completed"
    assert result.state.get("deleted") is False


def test_15_nonzero_return_code():
    result = run("Run the shell command 'exit 1'", {})
    # Executor treats non-zero as ok — caller inspects return_code
    assert result.status == "completed"
    assert result.state.get("return_code") == 1


# ---------------------------------------------------------------------------
# Subtask — deferred
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="subtask tool not yet wired")
def test_16_subtask_setup_project():
    pass
