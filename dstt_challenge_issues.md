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
- Issues 2 and 3 are transition2shell capability gaps, not model reasoning gaps.
- Issue 2 (task 4 timeout) suggests task2plan struggles with constraint reasoning at 7B — this may be a genuine model size boundary (L4 in the challenge levels).
- Issue 3 (task 5 empty state) is a task2plan output contract gap — solvable independently of model size.
