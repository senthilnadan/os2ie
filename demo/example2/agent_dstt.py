"""
example2 — DSTT-native ReAct loop

Same logic as agent.py but the Python while loop is replaced by DSTT transitions
and Named DSTT self-invocation. The execute step recurses into react_step via
LoopOrReturnTool — no Python loop, no external driver.

DSTT structure (react_step):

  Segment 1: think
    think(task, history) → (thought, initial_values_json, transitions_json)
    milestone: [thought, initial_values_json, transitions_json, task, history, catalog]

  Segment 2: execute
    seed_and_run(initial_values_json, transitions_json) → observation
    milestone: [observation, task, history, catalog, thought, transitions_json]

  Segment 3: check
    check(task, observation, history) → (is_final, answer)
    milestone: [is_final, answer, task, observation, history, catalog, thought, transitions_json]

  Segment 4: loop_or_return
    loop_or_return(is_final, answer, thought, transitions_json, observation)
      → final_answer  (if is_final)
      → invokes react_step again with updated history  (if not)
    milestone: [final_answer]
"""
from __future__ import annotations
import json
import math
import re
from typing import Callable

from demo.engine import DsttKernel
from demo.lib.prompting.tools import AskStructuredTool
from demo.example2.agent import TOOL_CATALOG, CalculateTool, LookupTool


# ── Prompts ──────────────────────────────────────────────────────────────────

THINK_PROMPT = """\
You are an agent solving a task step by step using DSTT transitions.

IMPORTANT — HOW INPUTS WORK:
Transition inputs are STATE KEYS, not literal values.
To use a literal value, first put it in initial_values, then reference its key.

EXAMPLE — count vowels in HELLO, then in the NEXT iteration divide 10 by that count:

Iteration 1 — get the value first:
{{
  "thought": "ask for the vowel count",
  "initial_values": {{"q_vowels": "How many vowels are in HELLO? Reply with just the number."}},
  "transitions": [{{"tool": "ask", "inputs": ["q_vowels"], "outputs": ["vowel_count"]}}]
}}
→ observation shows: vowel_count = "2"

Iteration 2 — now use the concrete value:
{{
  "thought": "vowel_count is 2 from the observation, now calculate 10 / 2",
  "initial_values": {{"expr_div": "10 / 2"}},
  "transitions": [{{"tool": "calculate", "inputs": ["expr_div"], "outputs": ["result"]}}]
}}

KEY RULE: expressions in initial_values must use CONCRETE numbers, not state key names.
Read the values from the observation/history, then write them directly into the expression.

TASK: {task}

TOOL CATALOG:
{catalog}

HISTORY SO FAR:
{history}

Output your thought, initial_values, and transitions. All inputs must be state keys.
"""

CHECK_PROMPT = """\
TASK: {task}

CURRENT STATE (all computed values so far):
{observation}

HISTORY:
{history}

Does the current state contain a value that directly and completely answers the task?
- The answer must be the final computed result, not an intermediate step.
- If the task asks to compute X divided by Y, both X and Y being known is NOT sufficient — the division result must exist.
- Set is_final to true only if the exact answer to the task is present in the state.
"""

THINK_SCHEMA = {
    "thought":        "your reasoning about what to do next",
    "initial_values": "JSON object of key:value pairs to seed into state before running transitions",
    "transitions":    "JSON array of {tool, inputs, outputs} steps — inputs are state keys, not literal values",
}

CHECK_SCHEMA = {
    "is_final": "true if the observation fully answers the task, false otherwise",
    "answer":   "the final answer if is_final is true, otherwise empty string",
}


# ── Tools ────────────────────────────────────────────────────────────────────

class ThinkTool:
    """Run ask_structured to produce thought + initial_values + transitions.
    Returns a 3-tuple so the kernel maps to 3 output keys.
    """

    def __init__(self, provider: Callable[[str], str], catalog_text: str) -> None:
        self._tool = AskStructuredTool(provider, THINK_SCHEMA)
        self._catalog = catalog_text

    def execute(self, task: str, history: str) -> tuple:
        raw = self._tool.execute(
            THINK_PROMPT.format(task=task, catalog=self._catalog, history=history or "(none)")
        )
        thought = raw.get("thought", "")
        iv = raw.get("initial_values", {})
        tr = raw.get("transitions", [])
        if isinstance(iv, dict):
            iv = json.dumps(iv)
        if isinstance(tr, list):
            tr = json.dumps(tr)
        return thought, iv, tr


class SeedAndRunTool:
    """Seed initial_values into state, then run LLM-generated transitions via DsttKernel.
    Returns an observation string.
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


class CheckTool:
    """Run ask_structured to determine if the task is complete.
    Returns a 2-tuple (is_final_str, answer).
    """

    def __init__(self, provider: Callable[[str], str]) -> None:
        self._tool = AskStructuredTool(provider, CHECK_SCHEMA)

    def execute(self, task: str, observation: str, history: str) -> tuple:
        try:
            raw = self._tool.execute(
                CHECK_PROMPT.format(task=task, observation=observation, history=history or "(none)")
            )
        except ValueError:
            return "false", ""
        return str(raw.get("is_final", "false")), raw.get("answer", "")


class LoopOrReturnTool:
    """If is_final: return the answer.
    If not: update history and re-invoke react_step via Named DSTT.
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
            next_state = {
                "task": task,
                "history": updated_history,
                "catalog": json.dumps(TOOL_CATALOG, indent=2),
            }
            result = DsttKernel().execute(self._dstt, self._tool_provider, next_state)
            if result.status == "failed":
                last = result.execution_log[-1]
                return f"[failed: {last.error}]"
            return result.state.get("final_answer", "[no answer]")
        finally:
            self._depth -= 1


# ── DSTT ─────────────────────────────────────────────────────────────────────

def make_react_step_dstt() -> dict:
    keep = ["task", "history", "catalog"]
    return {
        "segments": [
            {
                "transitions": [
                    {"tool": "think", "inputs": ["task", "history"],
                     "outputs": ["thought", "initial_values_json", "transitions_json"]},
                ],
                "milestone": keep + ["thought", "initial_values_json", "transitions_json"],
            },
            {
                "transitions": [
                    {"tool": "seed_and_run", "inputs": ["initial_values_json", "transitions_json"],
                     "outputs": ["observation"]},
                ],
                "milestone": keep + ["observation", "thought", "transitions_json"],
            },
            {
                "transitions": [
                    {"tool": "check", "inputs": ["task", "observation", "history"],
                     "outputs": ["is_final", "answer"]},
                ],
                "milestone": keep + ["observation", "thought", "transitions_json", "is_final", "answer"],
            },
            {
                "transitions": [
                    {"tool": "loop_or_return",
                     "inputs": ["is_final", "answer", "thought", "transitions_json",
                                "observation", "task", "history"],
                     "outputs": ["final_answer"]},
                ],
                "milestone": ["final_answer"],
            },
        ]
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def run(task: str, provider: Callable[[str], str], max_depth: int = 8) -> dict:
    catalog_text = json.dumps(TOOL_CATALOG, indent=2)

    # Inner tool provider — used by SeedAndRunTool for actual work transitions
    inner_state: dict = {}
    inner_tool_provider = {
        "ask":       __import__("demo.lib.prompting.tools", fromlist=["AskTool"]).AskTool(provider),
        "calculate": CalculateTool(),
        "lookup":    LookupTool(inner_state),
    }

    # Bootstrap: build react_step DSTT, then wire tools that reference it
    react_step_dstt = make_react_step_dstt()
    react_tool_provider: dict = {}

    loop_tool = LoopOrReturnTool(react_step_dstt, react_tool_provider, max_depth)

    react_tool_provider.update({
        "think":          ThinkTool(provider, catalog_text),
        "seed_and_run":   SeedAndRunTool(inner_tool_provider),
        "check":          CheckTool(provider),
        "loop_or_return": loop_tool,
    })

    print(f"\nTASK  : {task}")
    print(f"MODE  : DSTT-native ReAct loop")

    initial_state = {
        "task":    task,
        "history": "",
        "catalog": catalog_text,
    }

    result = DsttKernel().execute(react_step_dstt, react_tool_provider, initial_state)

    answer = result.state.get("final_answer", "")
    status = "completed" if answer and not answer.startswith("[") else "exhausted"

    return {
        "status":     status,
        "answer":     answer,
        "iterations": loop_tool._iteration,
        "state":      result.state,
    }
