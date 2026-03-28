from __future__ import annotations
from typing import Any
from .models import AbstractDSTT, ExecutableDSTT, ExecutableSegment, ExecutionResult, LogEntry
from .tools import TOOL_REGISTRY
from .clients import Transition2ExecClient, Transition2ShellClient
from .dstt_handler import DSTTHandler, EscapeToShell, Escalation


def execute(
    task: str,
    state: dict[str, Any],
    abstract_dstt: AbstractDSTT,
    t2e: Transition2ExecClient,
    available_tools: list[dict[str, Any]],
    t2s: Transition2ShellClient | None = None,
    parent_task: str | None = None,
) -> ExecutionResult:
    # available_tools is injected by the caller — CLI, client, or agent upstream.
    # The kernel is blind: it does not know the catalog and never builds it.
    # t2s (Transition2ShellClient) is optional — if absent, not_mappable → fail.
    state = dict(state)
    execution_log: list[LogEntry] = []
    segments_completed = 0
    milestone_reached: list[str] = []

    for segment_index, segment in enumerate(abstract_dstt.segments):
        for abstract_transition in segment.transitions:

            # 1. COMPILE
            try:
                exec_dstt, meta = t2e.compile(
                    task, state, abstract_transition, available_tools=available_tools
                )
            except Exception as e:
                return _fail(execution_log, state, segments_completed, milestone_reached,
                             abstract_transition.id, abstract_transition.tool,
                             {}, f"compile error: {e}")

            # 1a. not_mappable — hand to CreateTransitionHandler
            if exec_dstt.status != "ok":
                if t2s is None:
                    return _fail(execution_log, state, segments_completed, milestone_reached,
                                 abstract_transition.id, abstract_transition.tool,
                                 {}, "not_mappable: no Transition2ShellClient provided")

                result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
                    task, state, abstract_transition, t2s,
                    segment_index=segment_index,
                )
                if isinstance(result, Escalation):
                    return _escalate(result, execution_log, state,
                                     segments_completed, milestone_reached)

                # EscapeToShell — wrap ExecutableTransition into dispatch loop
                exec_dstt = ExecutableDSTT(
                    status="ok",
                    segments=[ExecutableSegment(
                        transitions=[result.executable_transition],
                        milestone=[result.executable_transition.id],
                    )],
                )

            # 2. For each grounded transition: PATCH → DISPATCH → MERGE
            for grounded in exec_dstt.segments[0].transitions:
                state.update(grounded.inputs)

                tool_fn = TOOL_REGISTRY.get(grounded.tool)
                if tool_fn is None:
                    return _fail(execution_log, state, segments_completed, milestone_reached,
                                 grounded.id, grounded.tool,
                                 grounded.inputs, f"tool not found: {grounded.tool}")

                try:
                    outputs = tool_fn(state)
                except Exception as e:
                    return _fail(execution_log, state, segments_completed, milestone_reached,
                                 grounded.id, grounded.tool,
                                 grounded.inputs, str(e))

                state.update(outputs)

                # Apply output binding: grounded key → abstract key
                # Writes abstract key into state so milestones resolve correctly.
                for grounded_key, abstract_key in grounded.output_binding.items():
                    if grounded_key in state and grounded_key != abstract_key:
                        state[abstract_key] = state[grounded_key]

                execution_log.append(LogEntry(
                    transition_id=grounded.id,
                    tool=grounded.tool,
                    inputs=grounded.inputs,
                    outputs=outputs,
                    status="ok",
                ))

        reached = [k for k in segment.milestone if k in state]
        milestone_reached.extend(reached)
        segments_completed += 1

    return ExecutionResult(
        status="completed",
        state=state,
        execution_log=execution_log,
        segments_completed=segments_completed,
        milestone_reached=milestone_reached,
    )


def _fail(
    log: list[LogEntry],
    state: dict[str, Any],
    segments_completed: int,
    milestone_reached: list[str],
    transition_id: str,
    tool: str,
    inputs: dict[str, Any],
    error: str,
) -> ExecutionResult:
    log.append(LogEntry(
        transition_id=transition_id,
        tool=tool,
        inputs=inputs,
        outputs={},
        status="failed",
        error=error,
    ))
    return ExecutionResult(
        status="failed",
        state=state,
        execution_log=log,
        segments_completed=segments_completed,
        milestone_reached=milestone_reached,
    )


def _escalate(
    escalation: Escalation,
    log: list[LogEntry],
    state: dict[str, Any],
    segments_completed: int,
    milestone_reached: list[str],
) -> ExecutionResult:
    log.append(LogEntry(
        transition_id=escalation.transition_id,
        tool=escalation.abstract_tool,
        inputs={},
        outputs={},
        status="escalated",
        error=escalation.reason,
    ))
    return ExecutionResult(
        status="escalated",
        state=state,
        execution_log=log,
        segments_completed=segments_completed,
        milestone_reached=milestone_reached,
    )
