# Named DSTT Tools — Primitive Proposal
## Replacing ThinkTool, SeedAndRunTool, CheckTool with Named DSTTs

**Status:** Proposal — for review  
**Context:** `demo/example2/agent_dstt.py` implements ThinkTool, SeedAndRunTool, and
CheckTool as Python classes. This document asks: what is the minimum set of new
transition primitives that allows these three to be expressed as Named DSTTs instead?

---

## Current Python Tools and What They Do

| Tool | Core operation | Returns |
|------|---------------|---------|
| `ThinkTool` | `ask_structured(think_prompt, THINK_SCHEMA)` → extract 3 fields | 3-tuple |
| `SeedAndRunTool` | parse JSON transitions, seed state, run `DsttKernel` | observation str |
| `CheckTool` | `ask_structured(check_prompt, CHECK_SCHEMA)` → extract 2 fields | 2-tuple |

ThinkTool and CheckTool are structurally identical — both build a prompt, call
`ask_structured`, and distribute the output fields into separate state keys.
SeedAndRunTool is fundamentally different — it runs a dynamically generated DSTT.

---

## The Two Primitives Needed

### Primitive 1 — `ask_structured_multi`

**What it does:** sends a prompt to the model with a JSON schema instruction, parses
the response, and returns the field values as an **ordered list** matching schema key
order. The kernel maps each value to its corresponding output key.

```python
class AskStructuredMultiTool:
    """Like AskStructuredTool but returns values as a list, not a dict.

    Enables multi-output transitions — one ask_structured call writes directly
    into multiple state keys without an unpack step.

    schema key order = output key order in the DSTT transition.
    """
    def __init__(self, provider, schema: dict[str, str], validate: bool = True) -> None: ...
    def execute(self, prompt: str) -> list:
        # parse JSON response → return [schema_key_0_value, schema_key_1_value, ...]
```

**Kernel mapping** (already supported):
```python
# kernel._call_tool — existing logic handles this:
elif isinstance(raw, (list, tuple)) and len(output_keys) == len(raw):
    for key, val in zip(output_keys, raw):
        result[key] = val
```

No kernel change needed. The list return type is already handled.

**ThinkTool as Named DSTT using this primitive:**
```python
THINK_DSTT = {
    "segments": [{
        "transitions": [
            {
                "tool": "asktemplate",
                "inputs": ["_think_template", "task", "history"],
                "outputs": ["think_prompt"],
            },
            {
                "tool": "ask_structured_multi",   # schema = THINK_SCHEMA
                "inputs": ["think_prompt"],
                "outputs": ["thought", "initial_values_json", "transitions_json"],
            },
        ],
        "milestone": ["thought", "initial_values_json", "transitions_json"],
    }]
}
```

**CheckTool as Named DSTT using this primitive:**
```python
CHECK_DSTT = {
    "segments": [{
        "transitions": [
            {
                "tool": "asktemplate",
                "inputs": ["_check_template", "task", "observation", "history"],
                "outputs": ["check_prompt"],
            },
            {
                "tool": "ask_structured_multi",   # schema = CHECK_SCHEMA
                "inputs": ["check_prompt"],
                "outputs": ["is_final", "answer"],
            },
        ],
        "milestone": ["is_final", "answer"],
    }]
}
```

`asktemplate` already exists. The only new primitive is `ask_structured_multi`.

**Difficulty: LOW.** `AskStructuredMultiTool` is a two-line variant of
`AskStructuredTool` — same prompt building, same parsing, different return type.

---

### Primitive 2 — `execute_plan`

**What it does:** takes `initial_values_json` and `transitions_json` from state,
parses them, seeds an inner state, and runs `DsttKernel` with an inner tool provider.
Returns the observation string.

```python
class ExecutePlanTool:
    """Run a dynamically generated DSTT plan from state keys.

    Inputs:
      initial_values_json — JSON object string: keys and literal values to seed
      transitions_json    — JSON array string: [{tool, inputs, outputs}, ...]

    Output:
      observation — JSON string of computed state keys, or error message

    The inner tool_provider (ask, calculate, lookup, …) is injected at init.
    It is SEPARATE from the react-step tool_provider — clean boundary between
    orchestration tools and work tools.
    """
    def __init__(self, inner_tool_provider: dict) -> None: ...
    def execute(self, initial_values_json: str, transitions_json: str) -> str: ...
```

**SeedAndRunTool as Named DSTT using this primitive:**
```python
SEED_AND_RUN_DSTT = {
    "segments": [{
        "transitions": [
            {
                "tool": "execute_plan",
                "inputs": ["initial_values_json", "transitions_json"],
                "outputs": ["observation"],
            },
        ],
        "milestone": ["observation"],
    }]
}
```

This DSTT has one transition. Its value is not in the DSTT itself — it is in making
`execute_plan` a first-class, named, inspectable, swappable unit. You can replace
`execute_plan` with a stub in tests, or with a sandboxed variant in production.

**Difficulty: MODERATE.** The implementation is identical to `SeedAndRunTool.execute`.
The difficulty is the boundary contract:
- `execute_plan` receives its inner tool_provider at init, not from state
- The inner tool_provider must NOT include react-step tools (think, check, loop_or_return)
  — those belong to the outer orchestration layer
- This separation is the design invariant: **work tools ≠ orchestration tools**

---

## Why Not an `unpack` Primitive?

An `unpack` tool (takes a dict state key, writes each field as a separate state key)
would also enable ThinkTool and CheckTool as Named DSTTs. But it adds an extra
transition per use and requires a field-list input. `ask_structured_multi` is
strictly simpler: one transition, no intermediate dict in state, schema defines
the output contract directly.

---

## Full Named DSTT react_step (after both primitives)

```
react_step DSTT:

  Segment 1: think  (THINK_DSTT via invoke_dstt or inline)
    asktemplate → think_prompt
    ask_structured_multi → thought, initial_values_json, transitions_json
    milestone: [thought, initial_values_json, transitions_json, task, history, catalog]

  Segment 2: execute  (SEED_AND_RUN_DSTT via invoke_dstt or inline)
    execute_plan(initial_values_json, transitions_json) → observation
    milestone: [observation, task, history, catalog, thought, transitions_json]

  Segment 3: check  (CHECK_DSTT via invoke_dstt or inline)
    asktemplate → check_prompt
    ask_structured_multi → is_final, answer
    milestone: [is_final, answer, task, observation, history, catalog, ...]

  Segment 4: loop_or_return
    loop_or_return(...) → final_answer   ← still a Python tool (see below)
    milestone: [final_answer]
```

---

## What Cannot Become a Named DSTT

**`LoopOrReturnTool` must remain a Python tool.**

Its job is to decide whether to recurse. That decision and the recursive
`DsttKernel().execute(react_step_dstt, ...)` call require Python-level control flow.
Expressing conditional recursion as a DSTT segment would require either:
- A conditional branch primitive (new kernel feature, not in scope)
- Or self-invoking Named DSTT with an explicit termination guard

Both are kernel extensions. The clean boundary is: recursion guard = Python.
Everything inside each iteration = DSTT.

---

## Summary

| Tool | Named DSTT possible? | Primitive needed | Difficulty |
|------|---------------------|-----------------|------------|
| `ThinkTool` | Yes | `ask_structured_multi` | Low |
| `CheckTool` | Yes | `ask_structured_multi` | Low |
| `SeedAndRunTool` | Yes (one-transition wrapper) | `execute_plan` | Moderate |
| `LoopOrReturnTool` | No — recursion guard stays Python | — | — |

**Two primitives, one boundary:** `ask_structured_multi` + `execute_plan`.
Everything except the recursion guard becomes expressible in DSTT.


## Architects  Review 

1. ask_structured_multi  is approved for build
2. execute_plan tool is similar to dsttengine kernel execute. but without no thinking tools.  
Explore the plan for using DSTT Kernal instances with think tools and DSTT Kernal instance without thinktools. that would solve the problem.  We meed a white listing mechanism for tools that can be used from the provider.  it is more like switching mode , execute mode will not be able think,  while explore mode would have access to think.   
this might not be necessary , when we have a plan that is without the the think tools in it.  
the plan would just be plan.  Just explore that option and report me. your thought process

---

## Engineering Response to Architects Review

### The two options explored

**Option A — Two kernel instances with mode switching (whitelist)**

Two `DsttKernel` instances, each given a filtered tool_provider:

```
Think kernel  → tool_provider: {ask, asktemplate, ask_structured_multi, calculate, lookup}
Execute kernel → tool_provider: {calculate, lookup, domain_tools}   ← no think tools
```

A whitelist is enforced at construction: `execute_plan` is initialised with the
execute-mode provider only. Think tools are physically absent from it.

Advantage: hard guarantee — even a hand-crafted or adversarial plan cannot invoke
think tools inside execute_plan, because they are not in the provider at all.
Disadvantage: requires an explicit whitelist/filter step at setup time. Adds
infrastructure without adding new capability.

---

**Option B — Plan as gate (no whitelist needed)**

One pool of tools, one kernel. The gate is the TOOL_CATALOG shown to the LLM
during the think step. That catalog lists only work tools:

```json
[
  {"name": "ask",       "description": "..."},
  {"name": "calculate", "description": "..."}
]
```

The LLM generates transitions only from tools it was told about. Think tools
(`ask_structured_multi`, `loop_or_return`, etc.) are never in the catalog, so
they are never in the generated plan. The kernel never invokes what the plan
does not reference.

Advantage: no whitelist mechanism, no mode concept, no infrastructure.
The catalog IS the scope gate. This is already how the current implementation works.

---

### The existing design already solves this

Looking at `agent_dstt.py`:

```
react_tool_provider  = {think, seed_and_run, check, loop_or_return}  ← orchestration
inner_tool_provider  = {ask, calculate, lookup}                       ← work
```

These are already two separate dicts passed to two separate `DsttKernel` instances:
- Outer kernel runs react_step DSTT with `react_tool_provider`
- Inner kernel (inside `SeedAndRunTool` / future `execute_plan`) runs user-task plan with `inner_tool_provider`

The separation is structural, not enforced by a whitelist. The plan never
references think tools because the catalog never advertises them.

---

### Recommendation

**Option B is correct. The plan is the whitelist.**

The architect's second instinct is right — when the plan does not contain think
tools, the kernel never calls them, regardless of what is in the provider. No
whitelist mechanism is needed.

The two-kernel-instance pattern already exists in the design and is the correct
boundary:

| Kernel | Tool provider | Drives |
|--------|--------------|--------|
| Outer (react kernel) | orchestration tools | react_step DSTT |
| Inner (execute kernel) | work tools only | user-task plan |

The TOOL_CATALOG passed to the think prompt is the design-time scope declaration.
The inner tool_provider is the runtime enforcement. Both point at the same set.
No whitelist — no additional mechanism.

**`execute_plan` is approved to build with this model:** it is simply a tool that
holds an inner tool_provider (work tools only) and calls `DsttKernel().execute`
on whatever plan arrives from state. The boundary is clean, the kernel is unchanged.

## Architects Feedback 

tool_provider  can be the inner_tool_provider as well.   If we work under the assumption that execution of plan, doesnt dynamically create a transtion that involves think tools in it.  
However..There would some DSTT Execution models that can observe micro transtion execution and dynamically. fix them.  In that case we would need this mechanism.  When we hit that scenario we will know the nuances of building it.  innner_tool_provider would not be enough in that case we need policy.  Rethink

---

## Engineering Rethink — Policy Model

### Why `inner_tool_provider` is not enough

`inner_tool_provider` is a **static dict** — the tool set is fixed at construction
time and cannot adapt during execution. This works today because execute mode
never needs think tools.

The repair/observe scenario breaks this:

```
Normal:  transition → ok → next transition
Repair:  transition → fail → observer fires
         observer reasons (needs ThinkTool) → produces fix
         observer retries (needs WorkTool)  → continues
```

The observer needs ThinkTools to reason but must NOT get OrchestrationTools
(it cannot spawn a new react_step). A static dict cannot express this middle ground.

---

### The Policy Model

Replace the static `tool_provider` dict with a two-part structure:

**1. Tool Registry** — all tools tagged by class at registration:

| Class | Examples |
|-------|---------|
| `WorkTool` | ask, calculate, lookup, domain tools |
| `ThinkTool` | ask_structured_multi, asktemplate |
| `OrchestrationTool` | loop_or_return, invoke_dstt |

**2. Policy** — maps execution context to allowed tool classes:

| Context | Allowed |
|---------|---------|
| `execute_mode` | WorkTool |
| `repair_mode` | WorkTool + ThinkTool |
| `orchestrate_mode` | WorkTool + ThinkTool + OrchestrationTool |

**3. Resolved provider** — what the kernel sees at runtime:

```python
resolved = registry.filter(policy.allowed_classes(current_context))
```

The kernel still receives a plain dict. No kernel change.

---

### Context switching

The context is held by the runtime, not the kernel. A micro-observer switches it
on failure:

```
execute_mode → (transition fails) → repair_mode
repair_mode  → (repaired or exhausted) → execute_mode
```

The observer runs in `repair_mode` — it can reason and retry, but cannot orchestrate.

---

### What `execute_plan` becomes

```python
class ExecutePlanTool:
    def __init__(self, registry: ToolRegistry, default_context: str = "execute") -> None:
        self._registry = registry
        self._context = default_context

    def execute(self, initial_values_json: str, transitions_json: str) -> str:
        provider = self._registry.resolve(self._context)
        # DsttKernel().execute(plan, provider, state)
```

Today: `default_context = "execute"` — resolves to WorkTools only. Identical to
the current `inner_tool_provider` behaviour. No regression.
Future: attach an observer that temporarily switches context to `repair_mode` on
failure — ThinkTools become available without changing the kernel or the plan.

---

### What does NOT change

- Kernel unchanged — still receives a plain dict
- TOOL_CATALOG shown to the LLM is still the design-time scope gate
- Plan-as-gate assumption holds — LLM-generated plans only reference catalog tools
- Policy enforcement is at the runtime layer, not inside the kernel

---

### Defer until repair agent is designed

The current static `inner_tool_provider` remains correct for `execute_plan` today.
Build the policy model when the first repair/observe agent is scoped — the three
tool classes and the context-switching points will be concrete by then, not speculative.