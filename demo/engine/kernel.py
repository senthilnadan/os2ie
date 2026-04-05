"""
Demo DSTT Kernel — executes a DSTT using ask/asktemplate only.

No transition2exec. No task2plan. No catalog lookup.
Dispatch logic: if state has 'template' key for this transition → asktemplate,
otherwise → ask. Output is stored under the transition's declared output key.

Input DSTT format (same AbstractDSTT shape as src/models.py):
{
  "segments": [{
    "transitions": [
      { "id": "t1", "tool": "...", "inputs": [...], "outputs": [...] }
    ],
    "milestone": [...]
  }]
}
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .tools import ask, asktemplate
from .config import EngineConfig


@dataclass
class LogEntry:
    transition_id: str
    tool: str
    prompt: str
    response: str
    status: str
    error: str | None = None


@dataclass
class EngineResult:
    status: str                        # completed | failed
    state: dict[str, Any]
    execution_log: list[LogEntry]
    segments_completed: int
    milestone_reached: list[str]


def execute(
    task: str,
    dstt: dict[str, Any],
    context: dict[str, Any],
    config: EngineConfig | None = None,
) -> EngineResult:
    cfg = config or EngineConfig()
    state = dict(context)
    state["_task"] = task
    log: list[LogEntry] = []
    segments_completed = 0
    milestone_reached: list[str] = []
    exec_seq = 0

    for segment in dstt.get("segments", []):
        for t in segment.get("transitions", []):
            exec_seq += 1
            eid = f"e{exec_seq}"
            output_keys = t.get("outputs", [])
            output_key = output_keys[0] if output_keys else "response"

            # Dispatch: asktemplate if template in state, else ask
            try:
                if "template" in state:
                    result = asktemplate(state, cfg)
                    tool_used = "asktemplate"
                elif "prompt" in state:
                    result = ask(state, cfg)
                    tool_used = "ask"
                else:
                    # Build default prompt from task + transition intent + inputs
                    input_vals = {k: state[k] for k in t.get("inputs", []) if k in state}
                    prompt = _build_prompt(task, t["tool"], input_vals)
                    state["prompt"] = prompt
                    result = ask(state, cfg)
                    tool_used = "ask"
                    del state["prompt"]

                response = result.get("response", "")
                state[output_key] = response

                log.append(LogEntry(
                    transition_id=eid,
                    tool=tool_used,
                    prompt=state.get("template") or state.get("prompt", ""),
                    response=response,
                    status="ok",
                ))

            except Exception as e:
                log.append(LogEntry(
                    transition_id=eid,
                    tool=t.get("tool", "unknown"),
                    prompt="",
                    response="",
                    status="failed",
                    error=str(e),
                ))
                return EngineResult(
                    status="failed",
                    state=state,
                    execution_log=log,
                    segments_completed=segments_completed,
                    milestone_reached=milestone_reached,
                )

        reached = [k for k in segment.get("milestone", []) if k in state]
        milestone_reached.extend(reached)
        segments_completed += 1

    return EngineResult(
        status="completed",
        state=state,
        execution_log=log,
        segments_completed=segments_completed,
        milestone_reached=milestone_reached,
    )


def _build_prompt(task: str, intent: str, inputs: dict[str, Any]) -> str:
    parts = [f"Task: {task}", f"Step: {intent}"]
    for k, v in inputs.items():
        parts.append(f"{k}: {v}")
    return "\n".join(parts)
