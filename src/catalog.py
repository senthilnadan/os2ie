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
        _tool("list_directory",
              "List the immediate children of a directory (non-recursive).",
              [("directory_path", "str")],
              [("entries", "list[str]")]),
    ]
