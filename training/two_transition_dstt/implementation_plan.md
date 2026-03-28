# Two-Transition DSTT — Implementation Plan

**Branch:** `feature/two-transition-dstt`
**Seeds:** `training/two_transition_dstt/seed.json` (8 scenarios)

---

## Underlying assumptions

**State threading is a kernel guarantee.** The kernel loop always passes updated state
to the next compile call. This is mechanical — not tested, taken as given.

**Declared outputs are the contract.** Each `AbstractTransition.outputs` is the list
of keys that transition promises to produce in state. This is the only signal the
kernel has to verify that a transition actually did what it said.

---

## Step 0 — Finally transition (kernel change, prerequisite)

Before T2 can compile, we must know that T1 actually delivered its declared outputs.
Without this check, T2 compiles against incomplete state and produces a silent wrong
result.

**The finally transition is a deterministic closure check run by the kernel after each
transition dispatches.** It is not an LLM call and not a tool call. It verifies:

```
for key in abstract_transition.outputs:
    assert key in state
```

If any declared output key is absent → the transition did not honour its contract →
fire the escape hatch immediately, before the next transition starts.

### Execution flow with finally transition

```
T1 compile → T1 dispatch → state.update(T1 outputs)
  → finally: T1.outputs ⊆ state?
      NO  → escape hatch (fail / escalate) — T2 never runs
      YES → T2 compile (state is clean and complete)
              → T2 dispatch → state.update(T2 outputs)
                → finally: T2.outputs ⊆ state?
                    NO  → escape hatch
                    YES → segment milestone check → complete
```

### Kernel change

After the MERGE step (`state.update(outputs)`) and output_binding, add:

```python
# Finally transition — verify declared outputs landed in state
missing = [k for k in abstract_transition.outputs if k not in state]
if missing:
    return _fail(
        execution_log, state, segments_completed, milestone_reached,
        abstract_transition.id, abstract_transition.tool,
        grounded.inputs,
        f"finally: declared outputs missing from state: {missing}"
    )
```

This is the escape hatch. It fires before the next transition compiles.

### Why this matters for two-transition seeds

Seeds tt01 and tt06 thread `text → content` — T2's `content` input is resolved from
`text` in state (T1's output). If the finally transition fires after T1 and finds
`text` missing, T2 never compiles. Without the check, T2 would compile with no `text`
in state and produce a wrong or hallucinated binding.

---

## Step 1 — Test the finally transition (unit tests)

Three focused tests — no LLM, no live service:

| Test | Scenario | Expected |
|------|----------|----------|
| `test_finally_pass` | T1 outputs all declared keys | T2 compiles and runs |
| `test_finally_fail_missing_output` | T1 tool returns output with wrong key name | kernel fails before T2, log has finally error |
| `test_finally_fail_partial_output` | T1 returns one of two declared outputs | kernel fails before T2 |

Uses `StubTransition2ExecClient` + deterministic tool stubs. No filesystem.

---

## Step 2 — Live service test runner

With the finally transition in place, test the full two-transition compile flow
against the live transition2exec service.

**Per seed:**
1. Call transition2exec with T1's abstract transition + initial_context → get compiled T1
2. Simulate T1 dispatch — inject seed's `expected.t1.state_after` values into state
   (no real tool call — state is seeded deterministically)
3. Finally check: verify T1's declared outputs are in state (must pass, state was seeded)
4. Call transition2exec with T2's abstract transition + enriched state → get compiled T2
5. Assert T2's resolved inputs match `expected.t2.resolved_inputs` from seed

**What this validates:** transition2exec correctly resolves T2's inputs from enriched
state — specifically the cases where T2's input key is satisfied by T1's output key
(e.g. `content` ← `text`, `file_path` ← `destination_path`).

---

## Step 3 — File layout

```
src/kernel.py                           MODIFIED — finally transition check after MERGE

tests/
  test_two_transition_finally.py        NEW — 3 unit tests for finally transition
  test_two_transition_live.py           NEW — 8 live service tests (one per seed)
```

---

## Execution order

1. Add finally transition check to `src/kernel.py`
2. Write `tests/test_two_transition_finally.py` — 3 unit tests, must pass
3. Write `tests/test_two_transition_live.py` — 8 live service tests
4. Run unit tests: `pytest tests/test_two_transition_finally.py -v`
5. Run live tests against transition2exec service
6. Commit + push

---

## Pass criteria

| Check | Pass condition |
|-------|----------------|
| Finally unit tests | 3/3 — missing output fires escape hatch before T2 |
| Live T1 compile | 8/8 — transition2exec maps T1 correctly |
| Live T2 compile | 8/8 — transition2exec resolves T2 inputs from enriched state |
| Key thread cases | tt01, tt06 `text → content` resolved correctly |
| Escape hatch | Finally fires before T2 when T1 output missing |
