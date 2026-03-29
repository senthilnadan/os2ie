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
              "Check whether a single file or directory exists at the given path. "
              "Returns is_present=true if the path exists, false otherwise. "
              "Does NOT read content, count lines, validate syntax, or perform any operation on the file.",
              [("file_path", "str")],
              [("is_present", "bool")]),

        _tool("list_directory",
              "List the immediate children of a directory (files and subdirectories). "
              "Set recursive=true to include all nested entries. "
              "Returns names only — does NOT read file content, count files, search for patterns, "
              "filter by extension, or compute any metrics.",
              [("directory_path", "str"), ("recursive", "bool")],
              [("entries", "list[str]")]),

        _tool("read_file",
              "Read the full raw text content of a file and return it as a string. "
              "Use this when you need the content of a file to pass to a subsequent step. "
              "Does NOT count lines, search for patterns, parse structure, compute checksums, "
              "validate syntax, or process the content in any way.",
              [("file_path", "str")],
              [("text", "str")]),

        _tool("create_file",
              "Write content to a file, creating it if it does not exist and overwriting it if it does. "
              "Parent directories are created automatically. "
              "Does NOT append — use append_to_file for that. "
              "Does NOT execute the file or validate its content.",
              [("file_path", "str"), ("content", "str")],
              [("success", "bool")]),

        _tool("append_to_file",
              "Append a string to the end of an existing file without overwriting it. "
              "Does NOT create the file if it does not exist — use create_file for that.",
              [("file_path", "str"), ("content", "str")],
              [("success", "bool")]),

        _tool("delete_file",
              "Delete a single file at the given path. "
              "Returns deleted=false (not an error) if the file does not exist. "
              "Does NOT delete directories — use remove_directory for that.",
              [("file_path", "str")],
              [("deleted", "bool")]),

        _tool("copy_file",
              "Copy a single file from source_path to destination_path, preserving content and metadata. "
              "Does NOT copy directories. Does NOT move or rename — use move_file for that.",
              [("source_path", "str"), ("destination_path", "str")],
              [("copied", "bool")]),

        _tool("move_file",
              "Move or rename a single file from source_path to destination_path. "
              "Does NOT copy directories. Does NOT copy — use copy_file to keep the original.",
              [("source_path", "str"), ("destination_path", "str")],
              [("moved", "bool")]),

        _tool("make_directory",
              "Create a directory at the given path, including any missing parent directories. "
              "Does NOT create files inside the directory. "
              "Does NOT run scripts, initialise projects, copy files, or execute any commands. "
              "Does NOT remove directories — use remove_directory for that.",
              [("directory_path", "str")],
              [("created", "bool")]),

        _tool("remove_directory",
              "Remove a directory at the given path. "
              "Set recursive=true to remove non-empty directories including all contents. "
              "Does NOT remove individual files — use delete_file for that.",
              [("directory_path", "str"), ("recursive", "bool")],
              [("removed", "bool")]),

        _tool("evaluate_expression",
              "Evaluate a single inline Python expression and return the result. "
              "The expression must be self-contained — substitute all known values directly, "
              "no variable assignments, no imports, no file references. "
              "Examples: '((3 * 4) + 5) ** 2', "
              "'[n*2 if n%3==0 else n+5 for n in range(1,7)]', "
              "'int(bin(7)[2:][::-1], 2) * 3 - 5', "
              "'sum(n for n in range(1,11) if n%2==0)'. "
              "Does NOT read files, write files, or run shell commands.",
              [("expression", "str")],
              [("result", "any")]),

        _tool("run_shell_command",
              "Execute an arbitrary shell command and capture stdout, stderr, and return_code. "
              "Use this ONLY when no other catalog tool can fulfil the task — for example: "
              "counting lines (wc), searching content (grep), compressing files (tar/zip), "
              "checking system state (df, ps, git), running scripts or compilers, or any "
              "operation that requires a shell. "
              "Do NOT use this when exists, read_file, list_directory, create_file, "
              "copy_file, move_file, delete_file, make_directory, or remove_directory fits.",
              [("command", "str")],
              [("stdout", "str"), ("stderr", "str"), ("return_code", "int")]),
    ]
