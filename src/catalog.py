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
from typing import Any


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
    return [
        _tool("exists",
              "Check whether a single file exists at the given path. "
              "Does NOT execute commands, check system state, or verify anything other than file presence.",
              [("file_path", "str")],
              [("is_present", "bool")]),

        _tool("list_directory",
              "List the contents of a directory. "
              "Set recursive=true to include all nested files and subdirectories. "
              "Set recursive=false to return immediate children only. "
              "Returns entry names only — does NOT count, filter, or search file contents.",
              [("directory_path", "str"), ("recursive", "bool")],
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
              "Execute a shell command and capture its output. "
              "Do NOT use this tool when a more specific tool (exists, read_file, list_directory, etc.) can fulfil the task.",
              [("command", "str")],
              [("stdout", "str"), ("stderr", "str"), ("return_code", "int")]),
    ]
