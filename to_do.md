# OS2I — To Do

## Active: feature/not-mappable-handler

### DSTTHandler.CreateTransitionHandler — Path A: not_mappable pivot

**Spec confirmed. Ready for implementation.**

---

#### Architect's Note (incorporated)

`dstt_handler` was too generic — it hid intent. We are specifically handling
a failure to **create an executable transition**. The name must express that.

Revised structure:

```
DSTTHandler                        ← namespace / top-level class
  └── CreateTransitionHandler      ← handles compile-time failures
        └── handle_not_mappable()  ← Path A recovery
```

Call site reads as intent:
```python
dstt_handler.CreateTransitionHandler.handle_not_mappable(...)
```

Recovery outcomes are named by what happened, not just success/fail:

```python
if isinstance(result, Escalation):      # nothing worked — surface to caller
if isinstance(result, EscapeToShell):   # shell fallback produced an executable transition
```

---

#### Role

`CreateTransitionHandler` is the recovery layer for compile-time failures.
The kernel executes mechanically and stops the moment `transition2exec`
returns `not_mappable`. `CreateTransitionHandler` owns what happens next.

The kernel does not retry, reason, or escalate — that is not its job.

---

#### Scope (Path A only)

Triggered when `t2e.compile()` returns `status == "not_mappable"`.
Compile-time failure — no tool dispatched, no state changed, nothing to roll back.

Two recovery steps, in order:

**Step 1 — Shell fallback → `EscapeToShell`**
- Retry `t2e.compile()` with `run_shell_command` added to `available_tools`
- If `status == "ok"` → return `EscapeToShell(executable_dstt=...)`
- Kernel receives it, unwraps the `ExecutableDSTT`, continues execution

**Step 2 — Escalate → `Escalation`**
- Shell fallback also returned `not_mappable`
- Return `Escalation(...)` to the kernel
- Kernel returns `ExecutionResult(status="escalated", ...)` to the caller
- Partial state preserved; caller decides: provide context, delegate, or abort

---

#### Interface (revised)

```python
# src/dstt_handler.py

class DSTTHandler:
    class CreateTransitionHandler:
        @staticmethod
        def handle_not_mappable(
            task: str,
            state: dict[str, Any],
            abstract_transition: AbstractTransition,
            t2e: Transition2ExecClient,
            available_tools: list[dict],   # injected by provider/agent upstream
        ) -> EscapeToShell | Escalation:
            ...
```

**Outcome types** (lightweight dataclasses — never cross a service boundary):

```python
@dataclass
class EscapeToShell:
    executable_dstt: ExecutableDSTT   # shell-fallback compile result
    transition_id: str
    abstract_tool: str

@dataclass
class Escalation:
    reason: str               # "not_mappable_after_shell_fallback"
    transition_id: str        # where in the DSTT execution it failed
    segment_index: int        # escalation locator — which segment
    abstract_tool: str        # abstract tool that could not be mapped
    context: dict             # state snapshot at point of escalation
```

---

#### Kernel change (minimal)

Replace `kernel.py:31-34`:
```python
# before
if exec_dstt.status != "ok":
    return _fail(...)

# after
if exec_dstt.status != "ok":
    result = DSTTHandler.CreateTransitionHandler.handle_not_mappable(
        task, state, abstract_transition, t2e, available_tools
    )
    if isinstance(result, Escalation):
        return _escalate(result, execution_log, state, segments_completed, milestone_reached)
    exec_dstt = result.executable_dstt   # EscapeToShell — recovered, continue loop
```

---

#### What it does NOT own

- Tool dispatch — kernel only
- State mutation — kernel only
- Reasoning repair on tool errors — Path B, separate branch
- Multi-step recovery — Plan C, comes after A and B

---

#### Decisions locked

1. **`available_tools` injection** — provided to `kernel.execute()` by a
   provider/agent upstream. The client does not own the catalog. Handler
   receives it as a parameter and appends `run_shell_command` for the
   shell fallback retry.

2. **`Escalation` payload** — carries `context` (state snapshot) and an
   escalation locator (`transition_id` + `segment_index`). No `tool_plan`
   field — the context signal and locator are sufficient for the caller.

---

## Next: Kernel Modes — compile_dstt vs explore

**Two independent modes. Designed and built separately.**

### Output contracts (locked)

| Mode | Output |
|------|--------|
| `compile_dstt` | `ExecutableDSTT` + `available_tools` |
| `explore` | `ExecutableDSTT` + `available_tools` + `exploration_tree` |

`available_tools` is the injected catalog (minus `run_shell_command`) — same
in both modes. `exploration_tree` is the additional set produced by explore
mode: tools tried, alternatives considered, paths taken during execution.

### compile_dstt  ← we are here
`user_task → ExecutableDSTT + available_tools`

Compile only — no dispatch, no state mutation from tools.

- Calls `transition2exec` for every abstract transition
- Accumulates grounded transitions into a fully compiled executable DSTT
- Output: `ExecutableDSTT` + `available_tools`
- not_mappable → Path A (CreateTransitionHandler: shell fallback → escalation)
- No tool errors possible — nothing is dispatched

**Portability property (1-to-M):**
The compiled output is not bound to the agent that produced it. Any agent
capable of executing the tools in `available_tools` can pick up the
`ExecutableDSTT` and execute it — now or in the future — as long as the
user task is equivalent. One compiled DSTT, M capable agents, each free
to choose their own execution path.

### explore
Execute AND produce an executable DSTT + exploration set.

- Compiles each transition and dispatches it immediately
- State grows as tools execute; each compile sees live state
- Output: `ExecutableDSTT` + `available_tools` + `exploration_tree`
- `exploration_tree` captures the decision trail — tools tried, branches
  taken, outcomes at each node
- not_mappable → Path A applies at compile step
- Tool error → Path B applies at dispatch step (reasoning repair →
  shell fallback → escalate)
- Full exploration set feeds Generation 2 adaptive execution (conditional
  segment routing, milestone validation, partial replanning)

---

## Next: not_mappable handler — shell scripter skill check

**Problem:** current shell fallback is a blind retry. The abstract DSTT tool
name is opaque — we cannot predict shell viability from it.

**Solution: shell scripter prompt — separate LLM call, separate role**

Not the transition2exec prompt. A distinct prompt where the LLM acts as a
**shell scripter**, not a tool mapper. Generic shell profile is static —
baked into the prompt, no runtime dependency.

### Flow

```
not_mappable received
  │
  ├─ Shell scripter LLM call  (prompts/shell_skill_check.md)
  │    role:   shell scripter
  │    given:  abstract transition (task intent, inputs, outputs)
  │            + generic shell capability profile (static, in prompt)
  │    asked:  can this task be implemented as a shell script?
  │            if yes — describe the script
  │    output: capable=bool + script_description=str
  │
  ├─ capable=true
  │    → shell fallback compile with script_description injected as context
  │    → EscapeToShell
  │
  └─ capable=false
       → Escalation immediately — no retry wasted
```

### Prompt design (prompts/shell_skill_check.md)

Role: shell scripter
Static shell profile section: what a Unix shell can do (file ops, process
execution, stdio, pipes, env vars) and what it cannot (HTTP without curl,
GUI, pure computation without system commands)
Task section: filled at runtime from abstract_transition
Output format: `{"capable": true/false, "script_description": "..."}`

### What gets built

1. `prompts/shell_skill_check.md` — shell scripter prompt with static profile
2. `src/shell_skill_check.py` — LLM call wrapper, returns `ShellSkillResult`
3. `src/dstt_handler.py` — `CreateTransitionHandler` updated:
   - Call shell scripter before retry
   - `capable=false` → escalate immediately
   - `capable=true` → retry compile with script_description in context
4. Tests — stub skill check, both routes

---

## Backlog

- **Path B** — tool error handler inside explore mode: reasoning repair →
  shell fallback → escalate *(explore mode, after compile_dstt is sealed)*
- **Plan C** — multi-step / wider recovery *(explore mode, after Path B)*
