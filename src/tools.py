from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from typing import Any
from .config import config

_DEFAULT_CWD = str(config.working_directory)


def _exists(state: dict[str, Any]) -> dict[str, Any]:
    return {"is_present": Path(state["file_path"]).exists()}


def _list_directory(state: dict[str, Any]) -> dict[str, Any]:
    return {"entries": [str(e) for e in Path(state["directory_path"]).iterdir()]}


def _list_directory_recursive(state: dict[str, Any]) -> dict[str, Any]:
    return {"entries": [str(e) for e in Path(state["directory_path"]).rglob("*")]}


def _read_file(state: dict[str, Any]) -> dict[str, Any]:
    return {"text": Path(state["file_path"]).read_text()}


def _create_file(state: dict[str, Any]) -> dict[str, Any]:
    path = Path(state["file_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.get("content", ""))
    return {"success": True}


def _append_to_file(state: dict[str, Any]) -> dict[str, Any]:
    with Path(state["file_path"]).open("a") as f:
        f.write(state["content"])
    return {"success": True}


def _delete_file(state: dict[str, Any]) -> dict[str, Any]:
    p = Path(state["file_path"])
    if not p.exists():
        return {"deleted": False}
    p.unlink()
    return {"deleted": True}


def _copy_file(state: dict[str, Any]) -> dict[str, Any]:
    shutil.copy2(state["source_path"], state["destination_path"])
    return {"copied": True}


def _move_file(state: dict[str, Any]) -> dict[str, Any]:
    shutil.move(state["source_path"], state["destination_path"])
    return {"moved": True}


def _make_directory(state: dict[str, Any]) -> dict[str, Any]:
    Path(state["directory_path"]).mkdir(parents=True, exist_ok=True)
    return {"created": True}


def _remove_directory(state: dict[str, Any]) -> dict[str, Any]:
    p = Path(state["directory_path"])
    if state.get("recursive", False):
        shutil.rmtree(p)
    else:
        p.rmdir()
    return {"removed": True}


def _run_shell_command(state: dict[str, Any]) -> dict[str, Any]:
    shell_exe = state.get("shell")  # e.g. "bash", "zsh", "pwsh", "cmd"
    command = state["command"]

    _cwd = state.get("working_directory") or _DEFAULT_CWD
    cwd = _cwd if _cwd and Path(_cwd).exists() else None

    if shell_exe:
        args = [shell_exe, "/c", command] if shell_exe == "cmd" else [shell_exe, "-c", command]
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    else:
        result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "return_code": result.returncode,
    }


# subtask is wired in by the kernel (needs access to clients), so omitted here.
TOOL_REGISTRY: dict[str, Any] = {
    "exists":                    _exists,
    "list_directory":            _list_directory,
    "list_directory_recursive":  _list_directory_recursive,
    "read_file":                 _read_file,
    "create_file":               _create_file,
    "append_to_file":            _append_to_file,
    "delete_file":               _delete_file,
    "copy_file":                 _copy_file,
    "move_file":                 _move_file,
    "make_directory":            _make_directory,
    "remove_directory":          _remove_directory,
    "run_shell_command":         _run_shell_command,
}
