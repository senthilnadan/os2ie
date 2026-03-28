# not_mappable handler — Go Report
**Date:** 2026-03-28
**Branch:** feature/not-mappable-handler
**Commit:** 15344f9

---

## Decision: GO

Path A (EscapeToShell) is cleared. The not_mappable recovery layer is
operational. 14 of 20 tested not_mappable scenarios recover via shell fallback
without escalating. The remaining 6 escalate with a structured reason. No silent
failures.

---

## What was built

### DSTTHandler.CreateTransitionHandler
Recovery layer for compile-time `not_mappable` failures. The kernel stops on
`not_mappable`; the handler owns what happens next.

Two outcomes:

| Outcome | Condition | Kernel action |
|---------|-----------|---------------|
| `EscapeToShell` | Transition2Shell returns `ok` | Wrap into `ExecutableTransition`, continue loop |
| `Escalation` | Transition2Shell returns `not_capable` or call fails | Log as `escalated`, return partial state |

### Transition2Shell (external service)
Standalone service at `http://localhost:8002/transition2Shell`. Acts as a shell
scripter — assesses whether the task can be implemented as a Unix command and
returns a `script_description` if so. Does not assemble transitions; that is the
handler's job.

**Contract:**

| Field | Description |
|-------|-------------|
| Input | `task`, `intent`, `inputs`, `outputs`, `context` |
| Output (ok) | `{status: ok, script_description: "..."}` |
| Output (not capable) | `{status: not_capable, reason: "..."}` |

**Shell capability profile** is static — baked into the prompt
(`prompts/shell_skill_check.md`). No runtime dependency.

**Output binding** — `run_shell_command` outputs mapped to abstract output keys:
`stdout → outputs[0]`, `return_code → outputs[1]`, `stderr → outputs[2]`.

---

## Test Results

### Unit tests — handler + kernel integration

| Test | Result |
|------|--------|
| capable → EscapeToShell | ✓ |
| not_capable → Escalation | ✓ |
| call failure → Escalation | ✓ |
| kernel integration (EscapeToShell path) | ✓ |
| kernel integration (Escalation path) | ✓ |
| partial state preserved on escalation | ✓ |

```
pytest tests/test_not_mappable_handler.py -v
```

### Transition2Shell service — seed suite

| Suite | Seeds | Result |
|-------|-------|--------|
| Baseline | 20 | 20/20 ✓ |
| Negative v1 | 15 | 14/15 — n07 deferred |
| Negative v2 | 11 | 8/11 — Issues 4-5 deferred |
| **Total** | **46** | **42/46** |

**n07 deferred** — `transform_file` vague intent: model falls back to `cp` instead
of returning `not_capable`. Requires two-pass chain-of-thought reasoning. Deferred
to Transition2Shell v2.

**Issues 4-5 deferred** — context value injection and intent bias failures. Both
are structural limitations of single-pass reasoning. Deferred to two-pass
architecture.

---

## Fallback Recovery Rate

Of 20 tested not_mappable scenarios, 14 recover via EscapeToShell (70%).
The 6 that escalate are genuinely out of reach for a Unix shell:
HTTP, database, GUI, ML inference, email.

```
not_mappable scenarios → EscapeToShell: 14  (date, pwd, wc, find, grep,
                                              export/echo, tar, stat, sed,
                                              sha256sum, base64, ps, du, ln)
not_mappable scenarios → Escalation:     6  (http_get, json_extract, db_query,
                                              gui_click, ml_inference, send_email)
```

---

## Issues

| Issue | Seeds | Status |
|-------|-------|--------|
| 1 — Hallucinated commands | n06, n10 | Resolved by service team |
| 2 — Intent drift | n07, n09 | n09 resolved; n07 deferred (CoT) |
| 3 — Capability blind spots | n13, n15 | Resolved by service team |
| 4 — Intent bias (false negative) | v2-c02 | Deferred — two-pass architecture |
| 5 — Context value injection | v2-i02, v2-i03 | Deferred — two-pass architecture |

Full reproduction cases: `reference/transition2shell_issues.md`

---

## Scope Freeze

Path A (EscapeToShell) is sealed at this commit. Two future paths are
documented in `to_do.md` but frozen:

| Path | Capability | Dependency |
|------|------------|------------|
| Path B | EscapeToCode — Transition2Code service | Separate branch |
| Path C | HumanInteraction — callback + resume | StreamedTaskExecutor + session/task tracking |

---

## Caveats

- **Single-run confidence:** Seeds run once. Non-deterministic pipeline — edge
  failures may surface at scale.
- **34/35 on Transition2Shell:** n07 is a known deferred case, not a regression.
  The service team resolved 5 of 6 v1 failures.
- **`run_shell_command` excluded from `available_tools`:** Injected only via the
  handler. The kernel never sees it directly.
- **Output binding is positional:** stdout→outputs[0], return_code→outputs[1].
  Multi-output binding for complex shell pipelines is Gen 2 scope.

---

## Artifacts

| File | Purpose |
|------|---------|
| `src/dstt_handler.py` | CreateTransitionHandler — Path A recovery |
| `src/kernel.py` | Kernel — not_mappable hook + EscapeToShell/Escalation dispatch |
| `src/clients.py` | Transition2ShellClient |
| `src/models.py` | Transition2ShellResult, EscapeToShell, Escalation |
| `prompts/shell_skill_check.md` | Shell scripter prompt — static Unix capability profile |
| `tests/test_not_mappable_handler.py` | Unit + integration tests |
| `training/transition2shell_seed.json` | 20 baseline seeds |
| `training/transition2shell_negative_seed.json` | 15 negative seeds (v1) |
| `training/transition2shell_negative_seed_v2.json` | 11 negative seeds (v2) |
| `reference/transition2shell_spec.md` | Full service requirement spec |
| `reference/transition2shell_issues.md` | Issues log — 5 issues, 3 resolved, 2 deferred |
| `to_do.md` | Roadmap — Path B, Path C, StreamedTaskExecutor, structured Escalation |
