# DSTT Challenge Issues — Goalpost Run Results

Run date: 2026-03-29
Model: 7B (task2plan: deepseek-r1:7b + qwen2.5:7b, transition2exec: qwen2.5:7b)

---

## Summary

| Task | Status | Issue |
|------|--------|-------|
| 1. Create → filter → sum → write | ✓ completed | — |
| 2. x=3, ×4, +5, square | ✗ escalated | transition2shell refuses arithmetic |
| 3. Conditional transform on 1–6 | ✗ escalated | transition2shell refuses rule-based logic |
| 4. Schedule A/B/C with constraint | ✗ timed out | task2plan or execution hung |
| 5. 5-box logic puzzle | ~ completed (empty state) | answer not captured in state |
| 6. Binary reverse → decimal → ×3 −5 | ✗ escalated | transition2shell refuses binary ops |

---

## Issue 1 — transition2shell over-rejects arithmetic and algorithmic tasks

**Affects:** Tasks 2, 3, 6

transition2shell returns `Cannot implement` for tasks that are trivially expressible as shell one-liners:

- Task 2: `echo "scale=0; (3*4+5)^2" | bc` or `python3 -c "x=3; print(((x*4)+5)**2)"`
- Task 3: `python3 -c "print([n*2 if n%3==0 else n+5 for n in range(1,7)])"`
- Task 6: `python3 -c "print(int(bin(7)[2:][::-1],2)*3-5)"`

**Root cause:** transition2shell's capability boundary is too conservative. It refuses tasks involving arithmetic, conditionals, and bit operations — all of which are well within shell/python3 capability.

**Fix needed (transition2shell team):** expand the accepted capability set to include:
- Arithmetic expressions via `bc` or `python3 -c`
- List comprehensions and conditional transforms via `python3 -c`
- Binary/bitwise operations via `python3 -c`

---

## Issue 2 — Task 4 timed out

**Affects:** Task 4 (scheduling with constraints)

The request never returned within the 120s timeout. Likely cause: task2plan is spending too long reasoning about the scheduling constraint (`B must start after A`) and either looping or generating a very large plan.

**Fix needed (task2plan team):** scheduling/constraint tasks should produce a simple linear plan (run A → run B → run C, compute total) not open-ended reasoning.

---

## Issue 3 — Task 5 completed with empty state

**Affects:** Task 5 (5-box logic puzzle)

The kernel returned `status: completed` but `state: {}` — the answer (which box holds the key) was never written to state. task2plan likely produced a plan with no output transitions, or the output key was not declared.

**Fix needed (task2plan team):** the final transition must write the answer to a declared output key (e.g. `answer`) in state so the caller can read the result.

---

## Observations

- Task 1 passing end-to-end confirms the pipeline works for file + shell chains.
- Issues 1 and 3 are transition2shell capability gaps, not model reasoning gaps.
- Issue 2 (task 4 timeout) suggests task2plan struggles with constraint reasoning at 7B — this may be a genuine model size boundary (L4 in the challenge levels).
- Issue 3 (task 5 empty state) is a task2plan output contract gap — solvable independently of model size.

---

## transition2exec Readiness — Recommendations for DSTT Challenge

The following changes to transition2exec are needed before it can reliably handle the challenge tasks. These come from both observed failures and architectural review.

### R1 — Add `output_first` as a named grounding strategy

**Current behaviour:** transition2exec uses a single strategy — match available inputs first, then check outputs (`input_first`).

**Problem:** multiple tools share the same input signature. Example: `file_path` input matches `read_file`, `exists`, `delete_file`, `append_to_file` — wrong tool gets selected based on input proximity.

**Proposal:** add a second named strategy `output_first` alongside the existing one:

| Strategy | Selection order |
|----------|----------------|
| `input_first` | match inputs → filter by outputs (current default) |
| `output_first` | match required outputs → confirm inputs are satisfiable (new) |

Example with `output_first`: abstract output `text` → only `read_file` produces `text` → unambiguous, no input proximity confusion.

**Why a named strategy and not a replacement:** keeping both allows direct evaluation — run the same task set under each strategy and compare correctness. The DSTT challenge task suite is a ready-made benchmark for this comparison.

**Request to transition2exec team:** implement `output_first` as an opt-in strategy, expose it via a request field (e.g. `"strategy": "output_first"`), and we will run the goalpost tasks under both to measure the difference.

---

### R2 — Mandatory output_binding in every response

**Current behaviour:** `output_binding` is optional. When tool output key matches abstract output key by name, it is left empty.

**Problem:** silent failures when keys don't match. The kernel cannot distinguish "matched correctly" from "model forgot to declare the binding."

**Fix:** make `output_binding` mandatory in every grounded transition response. When names match, emit `{"text": "text"}` explicitly. This forces the model to reason about every output, not just the mismatched ones, and removes 80% of silent latch failures.

---

### R3 — Input resolution anchor rule (see INPUT_RESOLUTION_RULE.md)

When state has multiple candidate keys, transition2exec must use the declared abstract input name as the exclusive anchor — not free-range over all state keys. Residue keys from prior transitions must be ignored.

This is already documented in `training/transition2exec_grounding/INPUT_RESOLUTION_RULE.md`.

---

### Priority order for transition2exec team

| # | Change | Impact | Effort |
|---|--------|--------|--------|
| R1 | Output-first selection | fixes wrong tool substitution | medium |
| R2 | Mandatory output_binding | removes silent latch failures | low |
| R3 | Input resolution anchor | fixes state pollution / name mismatch | low (prompt rule) |
