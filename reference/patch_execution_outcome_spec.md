# /patchTaskExecutionOutcomeToAbstractOutcome — Interface Spec

**Version:** 1.0 — for architect review
**Date:** 2026-03-22
**Owner:** DSTT Runtime — patch service coexists with transition2exec (port 8001)
**Called by:** taskexecutor kernel — only on gap detection
**Status:** Pending architect approval

---

## Summary

When transition2exec grounds an abstract transition to a tool that produces compatible but differently-shaped output, the abstract outputs may not land in state. This is not a failure of execution — the tool ran correctly — but a grounding gap. Rather than aborting, the executor calls `/patchTaskExecutionOutcomeToAbstractOutcome`. The patch service resolves the gap and returns ready-to-run transitions. The executor runs them and continues.

**The executor stays mechanical throughout.** It does not decide how to patch. It detects, delegates, executes, and continues — or aborts if the patch service cannot resolve.

---

## Boundary

| Concern                                | Owner          |
|----------------------------------------|----------------|
| Detect the gap                         | taskexecutor   |
| Call the patch service                 | taskexecutor   |
| Decide how to resolve                  | patch service  |
| Select patching tool or available tool | patch service  |
| Align output keys to abstract outputs  | patch service  |
| Run the returned transitions           | taskexecutor   |
| Abort and signal `abort_and_heal`      | taskexecutor   |
| Heal the abstract plan                 | DSTT Runtime   |

---

## When this is called

After all grounded transitions for one abstract transition complete, the executor checks:

```
abstract_transition.outputs: ["python_file_count"]
state after grounded tools:  {"entries": ["a.py", "b.py", "c.py"]}
→ "python_file_count" not in state → gap → call patch service
```

If no gap — abstract outputs are in state — no call is made. Normal execution continues.

---

## Request

```
POST /patchTaskExecutionOutcomeToAbstractOutcome
{
  "task": "string",

  "abstract_transition": {
    "id": "t1",
    "tool": "count_python_files",
    "inputs": ["directory_path"],
    "outputs": ["python_file_count"]
  },

  "execution_outcome": {
    "tool": "list_directory_recursive",
    "outputs": { "entries": ["a.py", "b.py", "c.py"] }
  },

  "state": { ...full state at gap point... },

  "available_tools": [ ...runtime execution catalog... ],
  "patching_tools":  [ ...patch-time transformation tool catalog... ]
}
```

**`available_tools`** — the runtime execution catalog (filesystem, shell tools). Same catalog used by transition2exec. Provided as grounding context for the patch service.

**`patching_tools`** — a separate catalog of pure, side-effect-free type-bridging tools. The executor holds this registry (`PATCH_TOOL_REGISTRY`) and passes it so the patch service knows what transformation tools are available to select from. These tools are never reachable during normal execution.

---

## Response

### Resolved

```json
{
  "status": "resolved",
  "patch_transitions": [
    {
      "id": "patch_t1",
      "tool": "count_list",
      "inputs": { "items": ["a.py", "b.py", "c.py"], "result_key": "python_file_count" },
      "outputs": { "python_file_count": null }
    }
  ]
}
```

The patch service returns one or more fully grounded `ExecutableTransition` objects. Output keys already match the abstract transition's declared outputs — no executor-side mapping or casting required. The executor runs each through the normal dispatch path and merges outputs into state.

**`result_key` convention:** patching tools accept an optional `result_key` input that names their output key. This is how the patch service aligns tool output to the abstract output name — the tool writes directly to the required key.

### Not resolved

```json
{
  "status": "not_resolvable",
  "reason": "no patching or available tool can bridge list[str] → int"
}
```

The executor fails with `abort_and_heal`. DSTT Runtime repair service heals the abstract plan.

---

## Status semantics

| Status            | Executor action                                     | DSTT Runtime action                |
|-------------------|-----------------------------------------------------|------------------------------------|
| `resolved`        | Run patch_transitions via normal dispatch, continue | None — execution proceeds          |
| `not_resolvable`  | Fail with `abort_and_heal`                          | Repair service heals abstract plan |

---

## Execution flow

```
kernel — abstract_transition t1
  → grounded transitions run
  → post-transition check: abstract outputs not in state → gap detected

  → call /patchTaskExecutionOutcomeToAbstractOutcome

    resolved →
      for each patch_transition:
        PATCH → DISPATCH → MERGE  (normal kernel path)
      abstract outputs now in state
      → continue to t2

    not_resolvable →
      ExecutionResult { status: "failed", error: "abort_and_heal" }
      → DSTT Runtime heals abstract plan
```

---

## Executor changes (minimal)

**1. Post-abstract-transition gap check** — one new block in `kernel.py` after the grounded transitions loop:

```python
satisfied = [k for k in abstract_transition.outputs if k in state]
if not satisfied:
    if patch_client:
        patch_result = patch_client.call(
            task, abstract_transition, last_grounded_outputs, state, catalog
        )
        if patch_result.status == "resolved":
            for pt in patch_result.patch_transitions:
                state.update(pt.inputs)
                tool_fn = TOOL_REGISTRY.get(pt.tool) or PATCH_TOOL_REGISTRY.get(pt.tool)
                outputs = tool_fn(state)
                state.update(outputs)
                execution_log.append(LogEntry(..., status="ok"))
        else:
            return _fail(..., error="abort_and_heal")
    else:
        return _fail(..., error="abort_and_heal", detail="no patch service configured")
```

**2. `PATCH_TOOL_REGISTRY`** — a second tool registry alongside `TOOL_REGISTRY`. Contains patching tools only. Never used during normal dispatch.

**3. `PatchClient`** — a new HTTP client alongside `Transition2ExecClient`. Uses the same `TRANSITION2EXEC_URL` — the patch endpoint is served by the same service. No separate URL configuration required.

---

## Patching Tools

Pure functions. No filesystem access. No side effects. Owned by the patch service; registered in `PATCH_TOOL_REGISTRY` in the executor.

| Tool            | Inputs                           | Outputs via `result_key` | Purpose                          |
|-----------------|----------------------------------|--------------------------|----------------------------------|
| `count_list`    | items: list, result_key: str     | result_key: int          | `["a","b","c"]` → `3`           |
| `get_first`     | items: list, result_key: str     | result_key: any          | `["a","b"]` → `"a"`             |
| `cast_int`      | value: str, result_key: str      | result_key: int          | `"42"` → `42`                   |
| `cast_float`    | value: str, result_key: str      | result_key: float        | `"3.14"` → `3.14`               |
| `cast_str`      | value: any, result_key: str      | result_key: str          | `42` → `"42"`                   |
| `split_lines`   | text: str, result_key: str       | result_key: list[str]    | `"a\nb"` → `["a","b"]`         |
| `join_list`     | items: list, sep: str, result_key: str | result_key: str    | `["a","b"]`, `","` → `"a,b"`   |
| `filter_suffix` | items: list, suffix: str, result_key: str | result_key: list| filter `.py` files from entries  |

The patch service selects the tool and sets `result_key` to the required abstract output name. The executor runs it without knowing why or what the key means.

---

## Decisions

| Decision             | Resolution                                                                                      |
|----------------------|-------------------------------------------------------------------------------------------------|
| Patch strategy       | Patch service owns entirely — patching tools preferred, available tools as fallback             |
| Output key alignment | Patch service sets `result_key` on patching tools; output keys match abstract outputs exactly   |
| Multi-step patch     | `patch_transitions` is a list — patch service may return multiple; executor runs in order       |
| Patch depth          | No recursion. If a patch transition produces another gap, executor aborts — no second call      |
| Patch service URL    | Same as `TRANSITION2EXEC_URL` — coexists with transition2exec on port 8001.                    |

---

## Resolved decisions

| Question                              | Decision                                                                                    |
|---------------------------------------|---------------------------------------------------------------------------------------------|
| Patch service location                | Coexists with transition2exec — same service, port 8001. No separate deployment.            |
| `available_tools` side effects        | Acceptable. The execution catalog already includes shell and file tools with side effects. No opt-in required. |
| Patch service URL                     | Uses `TRANSITION2EXEC_URL`. No separate `PATCH_URL` in `.env`.                             |
| Patching tool ownership               | Executor holds `PATCH_TOOL_REGISTRY` and runs them. Patch service selects them via the `patching_tools` catalog passed in the request. Same pattern as `TOOL_REGISTRY` / `available_tools`. |
