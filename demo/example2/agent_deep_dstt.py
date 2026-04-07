"""
agent_deep_dstt.py — ReAct loop where ThinkTool, SeedAndRunTool, CheckTool
are Named DSTTs, not Python classes.

New primitives used:
  ask_structured_multi  — ask_structured that returns an ordered list, enabling
                          multi-output transitions in a single call
  execute_plan          — runs a dynamically generated DSTT plan from state keys,
                          using an inner tool_provider (work tools only)

LoopOrReturnTool stays Python — recursion guard cannot be expressed as DSTT
without a conditional branch kernel extension.

Named DSTTs:
  THINK_DSTT       — asktemplate → ask_think (ask_structured_multi)
  SEED_AND_RUN_DSTT — execute_plan
  CHECK_DSTT       — asktemplate → ask_check (ask_structured_multi)

react_step DSTT inlines all three as segments, followed by loop_or_return.
"""
from __future__ import annotations
import json
from typing import Callable

from demo.engine import DsttKernel
from demo.lib.prompting.tools import AskTemplateTool, AskTool, AskStructuredMultiTool
from demo.example2.agent import TOOL_CATALOG, CalculateTool, LookupTool


# ── Schemas ───────────────────────────────────────────────────────────────────

THINK_SCHEMA = {
    "thought":        "your reasoning about what to do next",
    "initial_values": "JSON object of key:value pairs to seed into state before transitions",
    "transitions":    "JSON array of {tool, inputs, outputs} — inputs are state keys, not literal values",
}

CHECK_SCHEMA = {
    "is_final": "true if the observation fully answers the task, false otherwise",
    "answer":   "the final answer if is_final is true, otherwise empty string",
}


# ── Templates (bake catalog in at module load) ────────────────────────────────

_CATALOG_TEXT = json.dumps(TOOL_CATALOG, indent=2)

THINK_TEMPLATE = (
    "You are an agent solving a task step by step using DSTT transitions.\n\n"
    "IMPORTANT — HOW INPUTS WORK:\n"
    "Transition inputs are STATE KEYS, not literal values.\n"
    "To use a literal value, seed it in initial_values first.\n\n"
    "EXAMPLE — count vowels in HELLO, then in the NEXT iteration divide 10 by that count:\n\n"
    "Iteration 1:\n"
    '{{"thought":"ask for the count",'
    '"initial_values":{{"q":"How many vowels in HELLO? Reply with just the number."}},'
    '"transitions":[{{"tool":"ask","inputs":["q"],"outputs":["vowel_count"]}}]}}\n'
    "→ observation: vowel_count = \"2\"\n\n"
    "Iteration 2:\n"
    '{{"thought":"vowel_count is 2, now calculate 10/2",'
    '"initial_values":{{"expr":"10 / 2"}},'
    '"transitions":[{{"tool":"calculate","inputs":["expr"],"outputs":["result"]}}]}}\n\n'
    "KEY RULE: expressions must use CONCRETE numbers, not state key names.\n\n"
    "TASK: {{0}}\n\n"
    f"TOOL CATALOG:\n{_CATALOG_TEXT}\n\n"
    "HISTORY SO FAR:\n{{1}}\n\n"
    "Output your thought, initial_values, and transitions."
)

CHECK_TEMPLATE = (
    "TASK: {{0}}\n\n"
    "CURRENT STATE (all computed values so far):\n{{1}}\n\n"
    "HISTORY:\n{{2}}\n\n"
    "Does the current state contain a value that directly and completely answers the task?\n"
    "- The answer must be the final computed result, not an intermediate step.\n"
    "- If the task asks to compute X divided by Y, both X and Y being known is NOT "
    "sufficient — the division result must exist.\n"
    "- Set is_final to true only if the exact answer to the task is present."
)


# ── ExecutePlanTool ────────────────────────────────────────────────────────────

class ExecutePlanTool:
    """Run a dynamically generated DSTT plan from state keys.

    inner_tool_provider contains only work tools (ask, calculate, lookup).
    Think/orchestration tools are never available here — the plan-as-gate
    assumption holds: the TOOL_CATALOG shown to the LLM only lists work tools.
    """

    def __init__(self, inner_tool_provider: dict) -> None:
        self._provider = inner_tool_provider

    def execute(self, initial_values_json: str, transitions_json: str) -> str:
        try:
            initial_values = json.loads(initial_values_json) if initial_values_json else {}
        except json.JSONDecodeError:
            initial_values = {}
        try:
            transitions = json.loads(transitions_json) if transitions_json else []
        except json.JSONDecodeError:
            return "EXECUTION ERROR: could not parse transitions JSON"

        if not transitions:
            return "No transitions produced."

        milestone = [k for t in transitions for k in t.get("outputs", [])]
        plan = {"segments": [{"transitions": transitions, "milestone": milestone}]}
        result = DsttKernel().execute(plan, self._provider, dict(initial_values))

        partial = {k: v for k, v in result.state.items() if not k.startswith("_")}
        if result.status == "failed":
            last = result.execution_log[-1]
            obs = f"EXECUTION ERROR at {last.tool}: {last.error}"
            if partial:
                obs += f"\nPartial results: {json.dumps(partial)}"
            return obs
        return json.dumps(partial)


# ── LoopOrReturnTool (stays Python) ───────────────────────────────────────────

class LoopOrReturnTool:
    """Recursion guard — stays Python. Checks is_final; if not, updates history
    and re-invokes react_step DSTT via DsttKernel.
    """

    def __init__(self, dstt: dict, tool_provider: dict, max_depth: int = 8) -> None:
        self._dstt = dstt
        self._tool_provider = tool_provider
        self._depth = 0
        self._max_depth = max_depth
        self._iteration = 0

    def execute(
        self,
        is_final: str,
        answer: str,
        thought: str,
        transitions_json: str,
        observation: str,
        task: str,
        history: str,
    ) -> str:
        self._iteration += 1
        print(f"\n── Iteration {self._iteration} {'─' * 55}")
        print(f"Thought:     {thought}")
        print(f"Observation: {observation[:300]}")

        if str(is_final).lower() == "true" and answer:
            print(f"\nFINAL ANSWER: {answer}")
            return answer

        if self._depth >= self._max_depth:
            return f"[exhausted after {self._max_depth} iterations]"

        updated_history = (history or "") + (
            f"\n[{self._iteration}] Thought: {thought}"
            f"\n[{self._iteration}] Transitions: {transitions_json}"
            f"\n[{self._iteration}] Observation: {observation}"
        )

        self._depth += 1
        try:
            result = DsttKernel().execute(
                self._dstt,
                self._tool_provider,
                {
                    "task":    task,
                    "history": updated_history,
                    "_think_template": THINK_TEMPLATE,
                    "_check_template": CHECK_TEMPLATE,
                },
            )
            if result.status == "failed":
                last = result.execution_log[-1]
                return f"[failed: {last.error}]"
            return result.state.get("final_answer", "[no answer]")
        finally:
            self._depth -= 1


# ── Named DSTTs ───────────────────────────────────────────────────────────────

THINK_DSTT = {
    "segments": [{
        "transitions": [
            {
                "tool":    "asktemplate",
                "inputs":  ["_think_template", "task", "history"],
                "outputs": ["think_prompt"],
            },
            {
                "tool":    "ask_think",
                "inputs":  ["think_prompt"],
                "outputs": ["thought", "initial_values_json", "transitions_json"],
            },
        ],
        "milestone": ["thought", "initial_values_json", "transitions_json"],
    }]
}

SEED_AND_RUN_DSTT = {
    "segments": [{
        "transitions": [
            {
                "tool":    "execute_plan",
                "inputs":  ["initial_values_json", "transitions_json"],
                "outputs": ["observation"],
            },
        ],
        "milestone": ["observation"],
    }]
}

CHECK_DSTT = {
    "segments": [{
        "transitions": [
            {
                "tool":    "asktemplate",
                "inputs":  ["_check_template", "task", "observation", "history"],
                "outputs": ["check_prompt"],
            },
            {
                "tool":    "ask_check",
                "inputs":  ["check_prompt"],
                "outputs": ["is_final", "answer"],
            },
        ],
        "milestone": ["is_final", "answer"],
    }]
}

_KEEP = ["task", "history", "_think_template", "_check_template"]

REACT_STEP_DSTT = {
    "segments": [
        # Segment 1 — think (from THINK_DSTT, inlined)
        {
            "transitions": THINK_DSTT["segments"][0]["transitions"],
            "milestone":   _KEEP + ["thought", "initial_values_json", "transitions_json"],
        },
        # Segment 2 — execute (from SEED_AND_RUN_DSTT, inlined)
        {
            "transitions": SEED_AND_RUN_DSTT["segments"][0]["transitions"],
            "milestone":   _KEEP + ["observation", "thought", "transitions_json"],
        },
        # Segment 3 — check (from CHECK_DSTT, inlined)
        {
            "transitions": CHECK_DSTT["segments"][0]["transitions"],
            "milestone":   _KEEP + ["observation", "thought", "transitions_json", "is_final", "answer"],
        },
        # Segment 4 — loop_or_return (Python)
        {
            "transitions": [
                {
                    "tool":    "loop_or_return",
                    "inputs":  ["is_final", "answer", "thought", "transitions_json",
                                "observation", "task", "history"],
                    "outputs": ["final_answer"],
                },
            ],
            "milestone": ["final_answer"],
        },
    ]
}


# ── Entry point ───────────────────────────────────────────────────────────────

def run(task: str, provider: Callable[[str], str], max_depth: int = 8) -> dict:
    # Inner tool_provider — work tools only, used by execute_plan
    inner_state: dict = {}
    inner_tool_provider = {
        "ask":       AskTool(provider),
        "calculate": CalculateTool(),
        "lookup":    LookupTool(inner_state),
    }

    # React tool_provider — orchestration tools + primitives
    # Bootstrap: build provider dict first, then wire LoopOrReturnTool into it
    react_tool_provider: dict = {}
    loop_tool = LoopOrReturnTool(REACT_STEP_DSTT, react_tool_provider, max_depth)

    react_tool_provider.update({
        "asktemplate":   AskTemplateTool(provider),
        "ask_think":     AskStructuredMultiTool(provider, THINK_SCHEMA),
        "ask_check":     AskStructuredMultiTool(provider, CHECK_SCHEMA),
        "execute_plan":  ExecutePlanTool(inner_tool_provider),
        "loop_or_return": loop_tool,
    })

    print(f"\nTASK  : {task}")
    print(f"MODE  : deep DSTT (Named DSTTs — no Python tool wrappers)")

    result = DsttKernel().execute(
        REACT_STEP_DSTT,
        react_tool_provider,
        {
            "task":              task,
            "history":           "",
            "_think_template":   THINK_TEMPLATE,
            "_check_template":   CHECK_TEMPLATE,
        },
    )

    answer = result.state.get("final_answer", "")
    status = "completed" if answer and not answer.startswith("[") else "exhausted"

    return {
        "status":     status,
        "answer":     answer,
        "iterations": loop_tool._iteration,
        "state":      result.state,
    }
