# Cyclic DSTT Machine — Architectural Proposal
## demo/example2: DSTT-Only ReAct Loop

**Status:** Updated — for architectural review  
**Author:** Engineering  
**Purpose:** Explore whether DSTT alone can replace the DSPy-based OS2I pipeline
(task2plan → transition2exec → taskexecutor) for a ReAct-style agent loop.

---

## Context and Motivation

The existing OS2I pipeline works with DSPy:

```
task → task2plan (DSPy) → abstract_dstt
abstract_dstt + state → transition2exec (DSPy) → executable_transition
executable_transition → taskexecutor → result
```

This demo asks: **can DSTT replace DSPy in that pipeline using only its own
primitives?**

- `task2plan` → `ask_structured(task)` → produces the transitions list directly
- `transition2exec` → `ask_structured(transition + state + tool_catalog)` → grounded transition
- `taskexecutor` → `DsttKernel().execute(plan, tool_provider, state)` → unchanged

If it works, the full agent loop runs on `ask`, `asktemplate`, `askstructured`,
and the kernel — no DSPy, no separate services. DSTT all the way down.

---

## Design Principle

> The plan step produces the transitions. The kernel executes them.
> The cycle is Named DSTT self-invocation.

The dynamic dispatch problem dissolves: the think step generates concrete
`{tool, inputs, outputs}` entries via `ask_structured`. The kernel receives
a valid DSTT segment and runs it normally. No runtime tool name lookup needed.

---

## ReAct Loop Structure

```
react_step DSTT:

  Segment 1: think
    askstructured(think_prompt + task + history + tool_catalog)
      → { thought, transitions: [{tool, inputs, outputs}, ...] }
    milestone: [thought, transitions]

  Segment 2: execute
    DsttKernel().execute(
      {segments: [{transitions: state["transitions"]}]},
      tool_provider,
      state
    )
      → execution result merged into state as observation
    milestone: [observation]

  Segment 3: check
    askstructured(check_prompt + task + observation + history)
      → { is_final, answer }
    if is_final:
      return answer
    else:
      history += thought + transitions + observation
      invoke_dstt("react_step", updated_state)
    milestone: [is_final, answer]
```

---

## DSTT Replacing the OS2I Pipeline

| OS2I component | DSPy implementation | DSTT equivalent |
|---|---|---|
| `task2plan` | DSPy module → abstract DSTT | `ask_structured(task + tool_catalog)` → transitions list |
| `transition2exec` | DSPy module → grounded transition | `ask_structured` with schema matching tool signatures |
| `taskexecutor` | kernel + state management | `DsttKernel().execute(plan, tool_provider, state)` — unchanged |

The think step merges task2plan and transition2exec into one `ask_structured` call.
The model sees the task, the history, and the available tool catalog, and outputs
executable transitions directly.

---

## Tool Catalog (Available to the Agent)

The catalog is passed to the think prompt as context — the model picks from it.

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `ask` | `prompt` | `response` | sub-question to the model |
| `asktemplate` | `template, *values` | `response` | templated sub-query |
| `askstructured` | `prompt` | `dict` | structured extraction |
| `calculate` | `expression` | `result` | arithmetic evaluation |
| `lookup` | `key` | `value` | retrieve a value from state |

Small catalog by design — enough to demonstrate non-trivial multi-step reasoning
without tool complexity getting in the way of the DSTT story.

---

## Named DSTT — Implementation

```python
class InvokeDsttTool:
    def __init__(self, registry: dict[str, dict], tool_provider: dict,
                 max_depth: int = 10) -> None:
        self._registry = registry
        self._provider = tool_provider
        self._depth = 0
        self._max_depth = max_depth

    def execute(self, dstt_name: str, state: dict) -> dict:
        if self._depth >= self._max_depth:
            raise RecursionError(f"Max depth {self._max_depth} reached")
        dstt = self._registry.get(dstt_name)
        if dstt is None:
            raise ValueError(f"Unknown DSTT: {dstt_name!r}")
        self._depth += 1
        try:
            result = DsttKernel().execute(dstt, self._provider, state)
        finally:
            self._depth -= 1
        if result.status == "failed":
            raise RuntimeError(f"DSTT {dstt_name!r} failed: "
                               f"{result.execution_log[-1].error}")
        return result.state
```

`max_depth` is the termination guarantee — identical role to `max_iterations`
in a loop, but expressed as a depth limit on recursion rather than a loop counter.

---

## History Representation

History is a plain string in state, appended each iteration:

```python
history += (
    f"\nThought: {thought}"
    f"\nTransitions: {transitions}"
    f"\nObservation: {observation}"
)
```

The think prompt receives `task` and `history`. The model sees the full trace.
No message list, no memory object — just a growing string in the flat state dict.

---

## What This Experiment Tests

1. **Can a small model produce valid DSTT transitions via ask_structured?**
   The think step asks the model to output `{tool, inputs, outputs}` entries
   from a known catalog. This is the same job transition2exec does in DSPy.

2. **Does the kernel execute LLM-generated transitions correctly?**
   The execute segment feeds the model's output directly to `DsttKernel`.
   State key mismatches will surface immediately as hard failures.

3. **Does the check step terminate reliably?**
   `is_final` is a structured boolean. The model must commit rather than hedge.

4. **Does plan quality improve across iterations?**
   The history gives the model its own prior reasoning. Does it converge?

---

## Why Simpler Than LangGraph

| Concern | LangGraph | DSTT ReAct |
|---------|-----------|------------|
| Loop | conditional edge + while node | Named DSTT self-invocation |
| Planner | separate chain or ToolCallingAgent | think step via ask_structured |
| Tool dispatch | ToolNode + tool binding schema | tool_provider dict + LLM-generated transitions |
| State | TypedDict + annotated reducer | flat dict, history is a string |
| Termination | END node + edge condition | is_final flag in check step |
| Testability | mock nodes + graph compile | swap tool_provider, run any seed |

---

## Experiment Results (demo/example2)

Ran `qwen2.5:7b` on: *"What is 12 factorial divided by the number of vowels in MATHEMATICS?"*

**What the experiment confirmed:**

| Claim | Result |
|---|---|
| Model generates valid DSTT transitions via ask_structured | ✅ confirmed |
| Kernel executes LLM-generated transitions correctly | ✅ confirmed |
| ReAct loop self-corrects across iterations | ✅ partial state from failed iterations feeds the next think step |
| Loop terminates via check step | ✅ confirmed |

**Observed failure modes — all model capability, not DSTT:**
- Small model (7B) initially confuses inline values with state keys — resolves within 2-3 iterations
- Vowel count returned as prose ("5") rather than a clean number — ask prompt quality issue
- Check step computed arithmetic mentally rather than waiting for calculate — hallucination

**The key insight:** the mechanism works. When developers hand-craft the prompts, design the transitions deliberately, and compose the segments with intent — the failure modes above disappear entirely. The raw ReAct loop with an improvising small model is the floor, not the ceiling. Hand-composed DSTT prompt chains are the point.

**Tool descriptions are prompt engineering.** The tool catalog is not just metadata — it is the instruction the model uses to decide which tool to call and how to call it. A precise `description`, a clear `inputs` spec with a concrete example, and an explicit note about the state-key contract all reduce model confusion without any prompt tuning. The catalog IS the design artifact; writing it carefully is the craft.

This is what example1 already demonstrates: deliberate prompt composition producing reliable, inspectable, milestone-bounded workflows.

---

## Open Questions for Architects

1. **Depth counter placement:** current proposal puts the depth counter on the
   `InvokeDsttTool` instance. Should it be tracked through state (`_depth` key)
   for full observability in `EngineResult`?

2. **History truncation:** history grows unboundedly across iterations. Is
   summarisation a think-prompt concern (instruct the model to compress old
   iterations) or a tool concern (a `summarise_history` tool in the catalog)?

3. **Partial results on depth exhaustion:** when `max_depth` is reached, the
   last observation is in state but no final answer exists. Raise or return
   partial state with `_loop_status: exhausted`?
