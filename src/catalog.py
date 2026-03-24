"""
Tool catalog — sent to transition2exec as `available_tools`.
Built at runtime so shell availability reflects the current system.

Each entry format (required by transition2exec):
  name:        str
  description: str
  signature:   { inputs: [str], outputs: [str] }   <- key names only
  inputs:      [{ name, type }]
  outputs:     [{ name, type }]
"""
from __future__ import annotations
import shutil
import sys
from typing import Any


def _detect_shells() -> list[dict[str, str]]:
    candidates = [
        {"name": "bash",       "path": shutil.which("bash")},
        {"name": "zsh",        "path": shutil.which("zsh")},
        {"name": "sh",         "path": shutil.which("sh")},
        {"name": "pwsh",       "path": shutil.which("pwsh")},
        {"name": "powershell", "path": shutil.which("powershell")},
        {"name": "cmd",        "path": shutil.which("cmd")},
    ]
    return [c for c in candidates if c["path"]]


def _tool(
    name: str,
    description: str,
    inputs: list[tuple[str, str]],   # (key_name, type)
    outputs: list[tuple[str, str]],  # (key_name, type)
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "description": description,
        "signature": {
            "inputs":  [k for k, _ in inputs],
            "outputs": [k for k, _ in outputs],
        },
        "inputs":  [{"name": k, "type": t} for k, t in inputs],
        "outputs": [{"name": k, "type": t} for k, t in outputs],
    }
    if extra:
        entry.update(extra)
    return entry


def build_catalog() -> list[dict[str, Any]]:
    shells = _detect_shells()
    shell_names = [s["name"] for s in shells]
    default_shell = shell_names[0] if shell_names else None

    shell_cmd_desc = (
        "Execute a shell command and capture its output. "
        f"Available shells on this system: {', '.join(shell_names) if shell_names else 'none'}. "
        f"Default shell: {default_shell}. "
        "Specify the 'shell' input to override (e.g. bash, zsh, pwsh). "
        "Write command syntax appropriate for the chosen shell."
    )

    return [
        _tool("exists",
              "Check whether a file exists at the given path.",
              [("file_path", "str")],
              [("is_present", "bool")]),

        _tool("list_directory",
              "List the immediate children of a directory (non-recursive).",
              [("directory_path", "str")],
              [("entries", "list[str]")]),

        _tool("list_directory_recursive",
              "Recursively list all files and directories under a given directory.",
              [("directory_path", "str")],
              [("entries", "list[str]")]),

        _tool("read_file",
              "Read the full text content of a file.",
              [("file_path", "str")],
              [("text", "str")]),

        _tool("create_file",
              "Create a file with the given content. Parent directories are created automatically. Overwrites if exists.",
              [("file_path", "str"), ("content", "str")],
              [("success", "bool")]),

        _tool("append_to_file",
              "Append text to the end of an existing file.",
              [("file_path", "str"), ("content", "str")],
              [("success", "bool")]),

        _tool("delete_file",
              "Delete a single file. Returns deleted=false (not an error) if the file does not exist.",
              [("file_path", "str")],
              [("deleted", "bool")]),

        _tool("copy_file",
              "Copy a file from source to destination, preserving metadata.",
              [("source_path", "str"), ("destination_path", "str")],
              [("copied", "bool")]),

        _tool("move_file",
              "Move or rename a file.",
              [("source_path", "str"), ("destination_path", "str")],
              [("moved", "bool")]),

        _tool("make_directory",
              "Create a directory, including any missing parent directories.",
              [("directory_path", "str")],
              [("created", "bool")]),

        _tool("remove_directory",
              "Remove a directory. Set recursive=true to remove non-empty directories.",
              [("directory_path", "str"), ("recursive", "bool")],
              [("removed", "bool")]),

        _tool("run_shell_command",
              shell_cmd_desc,
              [("command", "str"), ("working_directory", "str"), ("shell", "str")],
              [("stdout", "str"), ("stderr", "str"), ("return_code", "int")],
              extra={
                  "platform": sys.platform,
                  "available_shells": shells,
                  "default_shell": default_shell,
              }),
    ]
