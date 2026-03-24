from __future__ import annotations
from typing import Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# DSTT input models
# Received from task2plan and transition2exec. Internal to the executor.
# ---------------------------------------------------------------------------

class AbstractTransition(BaseModel):
    id: str
    tool: str
    inputs: list[str]
    outputs: list[str]
    output_type: dict[str, str] = {}
    complexityTime: str = ""
    complexitySpace: str = ""
    skill_required: list[str] = []
    resource_required: list[str] = []


class AbstractSegment(BaseModel):
    transitions: list[AbstractTransition]
    milestone: list[str]


class AbstractDSTT(BaseModel):
    segments: list[AbstractSegment]


class ExecutableTransition(BaseModel):
    id: str
    tool: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    output_binding: dict[str, str] = {}
    # Binding from grounded tool output key → abstract transition output key.
    # Produced by transition2exec. Applied by the executor after dispatch.
    # Example: {"text": "file_contents", "entries": "python_files"}
    # If a grounded key equals its abstract key, it may be omitted (identity).
    # Executor writes both the grounded key and the abstract key into state.


class ExecutableSegment(BaseModel):
    transitions: list[ExecutableTransition]
    milestone: list[str]


class ExecutableDSTT(BaseModel):
    status: str
    segments: list[ExecutableSegment]


# ---------------------------------------------------------------------------
# ExecutionResult — working contract between taskexecutor and the DSTT runtime.
#
# NOTE: This is a pragmatic interface defined in the absence of the DSTT runtime.
# When the DSTT runtime provides its official interface, this model must align
# to that spec. Until then, this is the agreed output format.
#
# The DSTT runtime owns the abstract DSTT, user task, and all transition DSTTs.
# It does not look inside the executor. It only reads ExecutionResult.
#
# On completed:
#   status="completed", full final state, all log entries ok.
#
# On failure:
#   status="failed", partial state up to the failure point,
#   execution_log[-1] has status="failed" and the error.
#   segments_completed tells the runtime how far execution got.
#   The runtime uses this to decide: repair, retry, or escalate.
# ---------------------------------------------------------------------------

class LogEntry(BaseModel):
    transition_id: str
    tool: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    status: str            # "ok" | "failed"
    error: str | None = None


class ExecutionResult(BaseModel):
    status: str            # "completed" | "failed"
    state: dict[str, Any]  # full state at the point execution stopped
    execution_log: list[LogEntry]  # one entry per grounded transition attempted
    segments_completed: int        # how many segments fully completed
    milestone_reached: list[str]   # milestone keys confirmed in state
