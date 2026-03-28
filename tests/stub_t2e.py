"""
Stub Transition2ExecClient for testing.
Provide a list of ExecutableDSTT responses — returned in order as compile() is called.
Each grounded tool name is validated against the catalog so tests stay honest.
"""
from __future__ import annotations
from typing import Any
from src.models import AbstractTransition, ExecutableDSTT, ExecutableSegment, ExecutableTransition
from src.catalog import build_catalog

_CATALOG_NAMES: set[str] = {t["name"] for t in build_catalog()}


class StubTransition2ExecClient:
    def __init__(self, responses: list[ExecutableDSTT]):
        self._queue = list(responses)
        for resp in responses:
            for seg in resp.segments:
                for t in seg.transitions:
                    if t.tool not in _CATALOG_NAMES:
                        raise ValueError(
                            f"StubTransition2ExecClient: tool {t.tool!r} is not in the catalog. "
                            f"Known tools: {sorted(_CATALOG_NAMES)}"
                        )

    def compile(
        self,
        task: str,
        state: dict[str, Any],
        abstract_transition: AbstractTransition,
        available_tools: list[dict[str, Any]] | None = None,
    ) -> tuple[ExecutableDSTT, dict[str, Any]]:
        if not self._queue:
            raise RuntimeError("StubTransition2ExecClient: no more responses queued")
        return self._queue.pop(0), {}


def ok(transitions: list[dict]) -> ExecutableDSTT:
    """Shorthand to build a single-segment ExecutableDSTT with status=ok."""
    return ExecutableDSTT(
        status="ok",
        segments=[
            ExecutableSegment(
                transitions=[ExecutableTransition(**t) for t in transitions],
                milestone=[t["id"] for t in transitions],
            )
        ],
    )


def not_mappable() -> ExecutableDSTT:
    """Shorthand for a not_mappable response with no segments."""
    return ExecutableDSTT(status="not_mappable", segments=[])
