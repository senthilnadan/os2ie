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

## Backlog

- **Path B** — tool error handler: reasoning repair → shell fallback → escalate
  *(blocked on Path A)*
- **Plan C** — multi-step / wider recovery
  *(blocked on Path A + B)*
