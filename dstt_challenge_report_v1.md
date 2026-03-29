# DSTT Challenge — Run Report v1

**Date:** 2026-03-30
**Model:** task2plan: deepseek-r1:7b + qwen2.5:7b | transition2exec: qwen2.5:7b
**New in this run:** `evaluate_expression` tool added to catalog. Strategy field wired end-to-end.

---

## Results by Strategy

| Task | Expected | input_first | output_first | scored |
|------|----------|-------------|--------------|--------|
| 1. Create → filter → sum → write | file written | ✓ | ✓ | ✗ truncation |
| 2. x=3, ×4, +5, square | 289 | ✓ 289 | ✓ 289 | ✓ 289 |
| 3. Conditional transform 1–6 | [2,4,4,8,4,6] | ✗ truncation | ✗ escalated | ✗ truncation |
| 4. Schedule A/B/C with constraint | A→B→C, 6h | ✗ escalated | ✗ escalated | ✗ escalated |
| 5. 5-box logic puzzle | box 4 | ~ (empty state) | ~ (empty state) | ~ (empty state) |
| 6. Binary reverse ×3 −5 | 19 | ✗ escalated | ✗ truncation | ✗ truncation |

**Score:** input_first: 2/6 | output_first: 2/6 | scored: 1/6

---

## Progress Since Last Run

| | Previous | This run |
|--|---------|----------|
| Task 1 | ✓ | ✓ |
| Task 2 | ✗ escalated | ✓ **fixed** — evaluate_expression |
| Task 3 | ✗ escalated | ✗ truncation (closer) |
| Task 4 | ✗ timeout | ✗ escalated (no longer hangs) |
| Task 5 | ~ empty | ~ empty |
| Task 6 | ✗ escalated | ✗ truncation (closer) |

---

## Issue Analysis

### Issue A — Expression truncation (tasks 3, 6) — transition2exec

transition2exec truncates the `expression` value mid-string in its JSON response:

```
"expression": "'[n*2 if n%3==0 else n+5 for n in range(1"   ← cut off
"expression": "'int(bin(7)[2:][::-1]"                        ← cut off
```

The model generates the correct expression but the output field is truncated before the closing bracket/parenthesis. This is a transition2exec output length limit issue.

**Fix needed (transition2exec team):** increase the output token budget for string-type input fields, particularly `expression`. The full expressions are:
- Task 3: `[n*2 if n%3==0 else n+5 for n in range(1,7)]`
- Task 6: `int(bin(7)[2:][::-1], 2) * 3 - 5`

---

### Issue B — Task 4 escalated by transition2shell (scheduling)

transition2shell still refuses scheduling tasks. This is likely a genuine L4 (constraint satisfaction) boundary for a 7B model — even with shell, generating a correct schedule requires reasoning, not just execution.

**Likely fix:** task2plan needs to break the scheduling into atomic steps (compute A end time, compute B start, compute total) rather than one monolithic `schedule_tasks` transition.

---

### Issue C — Task 5 empty state (logic puzzle)

The kernel completes with no tools executed and empty state. task2plan produces a plan with no grounded output — the answer never lands in state.

**Fix needed (task2plan team):** final transition must write the answer to a declared state key (e.g. `answer`).

---

## Strategy Comparison

| Metric | input_first | output_first | scored |
|--------|-------------|--------------|--------|
| Correct completions | 2 | 2 | 1 |
| Tool selection quality | good (uses shell for filter/sum) | mixed (uses read_file for computation) | mixed |
| Truncation errors | 1 | 1 | 2 |

`input_first` and `output_first` tie at 2/6. `scored` performs worse due to more truncation errors on complex expressions. No strategy winner yet — the blocking issue is transition2exec truncation, not strategy selection.

---

## Next Steps

| Priority | Action | Owner |
|----------|--------|-------|
| P1 | Fix expression truncation in transition2exec output | transition2exec team |
| P2 | Fix task 5 empty state — declare answer output key | task2plan team |
| P3 | Break task 4 into atomic scheduling steps | task2plan team |
| P4 | Re-run benchmark after P1 fix | kernel |
