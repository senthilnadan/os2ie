# transition2exec — Go Report
**Date:** 2026-03-28
**Branch:** v1.1-single-tool-tuning
**Commit:** e1c5e9c

---

## Decision: GO

transition2exec is cleared for release. Tool selection and input resolution are correct across all tested task patterns and catalog tools. The three-outcome contract is stable.

---

## Regression Suite

| Suite | Seeds | Result |
|-------|-------|--------|
| Baseline | 17 | 17/17 ✓ |
| Stress | 20 | 20/20 ✓ |
| **Total** | **37** | **37/37 ✓** |

Baseline covers the full catalog (copy, move, delete, read, write, list, exists, make_directory, remove_directory) with standard inputs. Stress covers harder abstract-name disambiguation, input resolution edge cases (content from task text, noisy context, multi-step prior outputs, non-recursive flags), and not_mappable boundary enforcement.

Run baseline only:
```
pytest tests/test_transition2exec_regression.py -v -m "not stress"
```
Run stress only:
```
pytest tests/test_transition2exec_regression.py -v -m stress
```
Run all:
```
pytest tests/test_transition2exec_regression.py -v
```

---

## Contract

Three outcomes, no others:

| Status | Meaning | Caller action |
|--------|---------|---------------|
| `ok` | Grounded tool + resolved inputs. | Execute directly. |
| `not_mappable` + `tool_plan` in context | Stage 1 found a match but Stage 2 could not format it. | Heal programmatically from `tool_plan`. |
| `not_mappable` + no `tool_plan` | No catalog tool covers this transition. | DSTT handler: shell fallback → escalate. |

**`run_shell_command` is not in `available_tools`.** It is the DSTT handler's shell fallback, not a planning-level tool. transition2exec must never see it.

---

## Issue Closed

**Issue 3 — Stage 2 false not_mappable** (`training/transition2exec_issues.json`)

Stage 2 was re-validating tool selection (Stage 1's job) and rejecting semantically distant abstract names (e.g. `duplicate_config` → `copy_file`). Fix: Stage 2 treats Stage 1's `tool_plan` as authoritative when it contains a valid grounded tool name. All 6 reproduction cases confirmed passing post-fix.

---

## Caveats

- **Content extraction from task text:** Tested with simple strings only. Content containing commas, quotes, or escape sequences is not covered by the current seed set.
- **Single-run confidence:** Each seed is run once. The pipeline is non-deterministic; repeated runs at scale may surface edge failures not seen here.
- **Catalog-scoped:** The not_mappable boundary is defined by the current catalog. Adding new tools changes which tasks are mappable — re-run stress seeds after any catalog change.

---

## Artifacts

| File | Purpose |
|------|---------|
| `tests/test_transition2exec_regression.py` | Regression suite — 17 baseline + 20 stress |
| `training/transition2exec_seed.json` | Baseline seed definitions |
| `training/transition2exec_stress_seed.json` | Stress seed definitions |
| `training/transition2exec_issues.json` | Issue log — Issue 3 filed and closed |
| `pytest.ini` | Stress marker registration |
