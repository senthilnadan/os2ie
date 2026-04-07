"""
example2 — DSTT-only ReAct loop (lightweight experiment)

Replaces DSPy task2plan + transition2exec with ask_structured calls.
The think step produces executable DSTT transitions directly.
The kernel runs them. A Python while loop drives the cycle.

This is an experiment: does DSTT alone produce valid transitions
that the kernel can execute without errors?
"""
from __future__ import annotations
import json
import math
from demo.engine import DsttKernel
from demo.lib.prompting.tools import AskStructuredTool


class CalculateTool:
    """Evaluate a safe arithmetic expression. Supports n! notation."""
    _SAFE = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    _SAFE["factorial"] = math.factorial

    def execute(self, expression: str) -> str:
        import re
        expression = re.sub(r'(\d+)!', r'factorial(\1)', expression)
        try:
            result = eval(expression, {"__builtins__": {}}, self._SAFE)  # noqa: S307
            return str(result)
        except Exception as exc:
            raise ValueError(f"calculate failed for {expression!r}: {exc}") from exc


class LookupTool:
    """Return a value from state by key. Useful for passing values between transitions."""
    def __init__(self, state_ref: dict) -> None:
        self._state = state_ref

    def execute(self, key: str) -> str:
        if key not in self._state:
            raise ValueError(f"lookup: key {key!r} not in state")
        return str(self._state[key])

TOOL_CATALOG = [
    {
        "name": "ask",
        "description": "Send a plain text question to the model and get a text answer. Use this for factual lookups, counting, classification, or any question where the answer is a string.",
        "inputs": [
            {"key": "prompt", "type": "str", "note": "a state key whose value is the question string — seed it in initial_values first"}
        ],
        "outputs": [
            {"key": "<your chosen key>", "type": "str", "note": "the model's answer stored under the key you name in outputs"}
        ],
        "example": "seed {\"q\": \"How many vowels in HELLO?\"} then transition: {tool: ask, inputs: [q], outputs: [vowel_count]}"
    },
    {
        "name": "calculate",
        "description": "Evaluate a Python arithmetic expression and return the result as a string. Supports standard math operators, factorial(n), sqrt(n), and all math module functions. The expression must be a CONCRETE value — no state key references. Seed the expression string in initial_values using the ACTUAL numbers you know.",
        "inputs": [
            {"key": "expression", "type": "str", "note": "a state key whose value is a concrete arithmetic expression string, e.g. 'factorial(12) / 4'"}
        ],
        "outputs": [
            {"key": "<your chosen key>", "type": "str", "note": "the numeric result as a string"}
        ],
        "example": "seed {\"expr\": \"factorial(12) / 4\"} then transition: {tool: calculate, inputs: [expr], outputs: [result]}"
    },
]

THINK_SCHEMA = {
    "thought":        "your reasoning about what to do next",
    "initial_values": "JSON object of key:value pairs to seed into state before running transitions (use this for literal values like expressions or questions)",
    "transitions":    "JSON array of {tool, inputs, outputs} steps — inputs are state keys, not literal values",
}

CHECK_SCHEMA = {
    "is_final": "true if the observation fully answers the task, false otherwise",
    "answer":   "the final answer if is_final is true, otherwise empty string",
}

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


def run(task: str, provider, tool_provider: dict, max_iterations: int = 5) -> dict:
    think = AskStructuredTool(provider, THINK_SCHEMA)
    check = AskStructuredTool(provider, CHECK_SCHEMA)
    catalog_text = json.dumps(TOOL_CATALOG, indent=2)

    state: dict = {"task": task}
    history = ""
    iterations = 0
    lookup = LookupTool(state)

    while iterations < max_iterations:
        iterations += 1
        print(f"\n── Iteration {iterations} {'─' * 55}")

        # Think
        thought_raw = think.execute(
            THINK_PROMPT.format(task=task, catalog=catalog_text, history=history or "(none)")
        )
        thought = thought_raw.get("thought", "")
        transitions_raw = thought_raw.get("transitions", [])
        if isinstance(transitions_raw, str):
            try:
                transitions_raw = json.loads(transitions_raw)
            except json.JSONDecodeError:
                transitions_raw = []

        # Seed initial values the model wants in state
        initial_values = thought_raw.get("initial_values", {})
        if isinstance(initial_values, dict):
            state.update(initial_values)

        print(f"Thought: {thought}")
        if initial_values:
            print(f"Seeded:  {json.dumps(initial_values)}")
        print(f"Transitions: {json.dumps(transitions_raw, indent=2)}")

        if not transitions_raw:
            print("No transitions produced — stopping.")
            break

        # Milestone = all output keys so compression preserves them
        milestone = [k for t in transitions_raw for k in t.get("outputs", [])]

        # Execute — extend tool_provider with calculate and lookup for this iteration
        active_tools = {
            **tool_provider,
            "calculate": CalculateTool(),
            "lookup": lookup,
        }
        plan = {"segments": [{"transitions": transitions_raw, "milestone": milestone}]}
        result = DsttKernel().execute(plan, active_tools, state)

        partial = {k: v for k, v in result.state.items()
                   if not k.startswith("_") and k not in ("task",) + tuple(state.keys())}
        if result.status == "failed":
            last = result.execution_log[-1]
            error_msg = f"EXECUTION ERROR at {last.tool}: {last.error}"
            observation = error_msg
            if partial:
                state.update(partial)
                observation += f"\nPartial results computed before error: {partial}"
            print(f"Kernel error: {error_msg}")
        else:
            state.update(result.state)
            observation = json.dumps({k: v for k, v in result.state.items()
                                      if not k.startswith("_") and k != "task"})
        print(f"Observation: {observation[:400]}")

        # Check
        try:
            check_raw = check.execute(
                CHECK_PROMPT.format(task=task, observation=observation, history=history or "(none)")
            )
            is_final = str(check_raw.get("is_final", "false")).lower() == "true"
            answer = check_raw.get("answer", "")
        except ValueError:
            is_final = False
            answer = ""

        history += (
            f"\n[{iterations}] Thought: {thought}"
            f"\n[{iterations}] Transitions: {json.dumps(transitions_raw)}"
            f"\n[{iterations}] Observation: {observation}"
        )

        if is_final:
            print(f"\nFINAL ANSWER: {answer}")
            return {"status": "completed", "answer": answer, "iterations": iterations, "state": state}

    return {"status": "exhausted", "iterations": iterations, "state": state}
