"""
Demo DSTT Kernel — faithful adaptation of the reference DsttKernal.

Source: https://github.com/senthilnadan/dstt/blob/main/src/dstt_kernel/kernel.py

The kernel is general purpose. It knows nothing about tools.
Tools are provided by the caller via tool_provider (dict of name → callable).
The DSTT declares which tool to use. The kernel resolves inputs from state,
dispatches, maps outputs, and compresses state to milestones.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class LogEntry:
    transition_id: str
    tool: str
    status: str
    error: str | None = None


@dataclass
class EngineResult:
    status: str
    state: dict[str, Any]
    execution_log: list[LogEntry]
    segments_completed: int
    milestone_reached: list[str]


class DsttKernel:

    def execute(
        self,
        dstt: dict[str, Any],
        tool_provider: dict[str, Any],
        initial_state: dict[str, Any] | None = None,
    ) -> EngineResult:
        state = dict(initial_state) if initial_state else {}
        log: list[LogEntry] = []
        segments_completed = 0
        milestone_reached: list[str] = []
        exec_seq = 0

        for segment in dstt.get("segments", []):
            for transition in segment.get("transitions", []):
                exec_seq += 1
                eid = f"e{exec_seq}"
                tool_name = transition.get("tool", "")

                try:
                    inputs = self._resolve_inputs(transition, state)
                    result = self._call_tool(transition, inputs, tool_provider)
                    state.update(result)
                    log.append(LogEntry(transition_id=eid, tool=tool_name, status="ok"))

                except Exception as e:
                    log.append(LogEntry(transition_id=eid, tool=tool_name,
                                        status="failed", error=str(e)))
                    return EngineResult(
                        status="failed", state=state, execution_log=log,
                        segments_completed=segments_completed,
                        milestone_reached=milestone_reached,
                    )

            milestone = segment.get("milestone", [])
            reached = [k for k in milestone if k in state]
            milestone_reached.extend(reached)
            state = self._compress_to_milestone(state, milestone)
            segments_completed += 1

        return EngineResult(
            status="completed", state=state, execution_log=log,
            segments_completed=segments_completed,
            milestone_reached=milestone_reached,
        )

    def _resolve_inputs(self, transition: dict, state: dict) -> list:
        resolved = []
        for key in transition.get("inputs", []):
            if key not in state:
                raise ValueError(f"Missing input: {key!r}")
            resolved.append(state[key])
        return resolved

    def _call_tool(self, transition: dict, inputs: list, tool_provider: dict) -> dict:
        tool_name = transition.get("tool")
        output_keys = transition.get("outputs", [])

        tool = tool_provider.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool not found: {tool_name!r}")

        raw = tool.execute(*inputs)

        result = {}
        if len(output_keys) == 1:
            result[output_keys[0]] = raw
        elif isinstance(raw, (list, tuple)) and len(output_keys) == len(raw):
            for key, val in zip(output_keys, raw):
                result[key] = val
        return result

    def _compress_to_milestone(self, state: dict, milestone: list) -> dict:
        return {k: state[k] for k in milestone if k in state}


# Convenience function
def execute(
    dstt: dict[str, Any],
    tool_provider: dict[str, Any],
    initial_state: dict[str, Any] | None = None,
) -> EngineResult:
    return DsttKernel().execute(dstt, tool_provider, initial_state)
