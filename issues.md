# Issues

Track open problems, gaps, and deferred decisions.
Updated after each test run.

---

## Open — executor (this repo)

| # | Priority | Area     | Issue                                                                                                                          |
|---|----------|----------|--------------------------------------------------------------------------------------------------------------------------------|
| 1 | HIGH     | models   | `ExecutionResult` is a working contract defined in the absence of the DSTT runtime. Must be realigned when runtime publishes its official interface. |
| 2 | LOW      | subtask  | Subtask tool not implemented. test_16 skipped. Deferred.                                                                      |
| 3 | LOW      | asserter | `src/asserter.py` and training seeds exist as repair service artifacts. Not wired into executor — by design.                  |
| 4 | HIGH     | latency  | End-to-end latency is high — two LLM calls per transition (as_task2plan + transition2exec), each hitting a 7B model. Noticeable under test load. Needs profiling per stage to identify dominant cost. Possible mitigations: single-model pipeline, response caching for repeated abstract transitions, batching. |
| 5 | DEFERRED | latency  | Parallel abstract DSTT generation — independent sub-tasks with no data dependency can call as_task2plan concurrently. Only viable where independence is detectable by rule (disjoint milestone keys, no shared inputs). Defer until latency is measured and confirmed unacceptable in practice. |
| 6 | DEFERRED | latency  | Evaluate 3B model (e.g. qwen2.5:3b) as drop-in replacement for 7B. Two-stage pipeline with pre-resolved schema mitigates controllability risk at smaller size. Measure accuracy delta against 7B baseline on seed suite. Accuracy gaps addressable through prompt tuning and training within small-LLM constraints. Adopt if latency gain justifies accuracy tradeoff. |

---

## Open — transition2exec (log there)

| # | Priority | Status | Issue                                                                                                                      |
|---|----------|--------|-----------------------------------------------------------------------------------------------------------------------------|
| 1 | HIGH     | ACTIVE | `return_code` not landing in state after `run_shell_command` — tests 07, 08 complete with `status=ok` but `return_code` key absent from state. Output binding not mapping grounded key to state correctly. |
| 2 | HIGH     | NOT DEPLOYED | Stage 2 malformed JSON for `run_shell_command` — `outputs` missing, spurious second transition. Pydantic validation rejects, returns `not_mappable`. Their ISS-008/009 report fixes applied internally but not yet visible in running service. |
| 3 | HIGH     | NOT DEPLOYED | ISS-003: Inputs absent from context — synthesize from task text. Prompt fix defined and seeded. Not yet reflected in running service. |
| 4 | HIGH     | CONTRACT CHANGE | Must emit `output_binding: {grounded_key: abstract_key}` on every `ExecutableTransition`. Binding maps grounded tool output keys → abstract transition output keys. Executor applies binding after dispatch so abstract output keys land in state and milestones resolve. If grounded key equals abstract key, binding may be omitted (identity). See `src/models.py ExecutableTransition.output_binding`. |ract output keys land in state and milestones resolve. If grounded key equals abstract key, binding may be omitted (identity). See `src/models.py ExecutableTransition.output_binding`. |

---

## Open — as_task2plan (log there)

| # | Priority | Tests     | Issue                                                                                                                      |
|---|----------|-----------|----------------------------------------------------------------------------------------------------------------------------|
| 1 | HIGH     | 13        | Wrong tool selected — used `exists` instead of `read_file` for a read task. `exists` on a nonexistent file returns `{is_present: False}` with `status=completed`. Test expects `status=failed`. |
| 2 | HIGH     | 14        | Wrong tool selected — used `exists` instead of `delete_file` for a delete task. `deleted` key never lands in state. `status=completed` but assertion fails. |
| 3 | HIGH     | 10        | Wrong sequence — append ran multiple times (`line2line2line2line2`), create step skipped or sequenced incorrectly. `line1` never written. |
| 4 | HIGH     | 12        | Multi-step incomplete — shell command ran, write to file never planned. `status=failed`. |
| 5 | HIGH     | 05        | `create_file` task returning `status=failed`. Tool or plan not resolving correctly. Root cause needs tracing. |
| 6 | HIGH     | 06        | Malformed shell command generated — `echo -n "terminal_opened` (unclosed quote). Bash syntax error, `return_code=2`. Model generating broken command strings. |

---

## Open — patch service (in training — log for sharing)

| # | Priority | Seed | Verdict   | Issue                                                                                                                                                 |
|---|----------|------|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | HIGH     | P04  | not_mappable | `get_first` not selected for `derive_first_py_file_from_entries`. Model does not recognise "first" as a retrieval signal from a list. Training gap — add `get_first` labelled seed. |
| 2 | HIGH     | P09  | MISMATCH  | Multi-step step 1: asked for `filter_suffix` (to produce `py_files`) but model selected `count_list` instead. Model sees the output key name `py_files` and jumps to the counting tool. Stage 1 is using output key name rather than abstract tool name as primary signal. Fix: prompt clarification + labelled seed for filter→count chain. |
| 3 | HIGH     | P10  | not_mappable | `split_lines` not selected for `derive_entry_lines_from_stdout`. Model does not match "lines" in the output key to the split-lines tool. Training gap — add `split_lines` labelled seed. |

**Passing (9/12):** P01 `count_list`, P02 `cast_int`, P03 `cast_float`, P05 `split_lines` (direct), P06 `join_list`, P07 `cast_str`, P08 `filter_suffix`, P14 `run_shell_command` (size fallback), P15 `run_shell_command` (grep fallback).
**Skipped (3/12):** P11, P12, P13 — `not_resolvable` by design, no grounding to verify.

---

## Closed — executor

| # | Area    | Issue                                                                                  | Fixed in         |
|---|---------|----------------------------------------------------------------------------------------|------------------|
| 1 | tools   | `delete_file` raised on missing file instead of returning `deleted=false`              | `src/tools.py`   |
| 2 | tools   | `run_shell_command` crashed if `WORKING_DIRECTORY` in `.env` did not exist             | `src/tools.py`   |
| 3 | catalog | transition2exec rejected catalog entries — `signature` field missing or wrong type     | `src/catalog.py` |
| 4 | cli     | CLI aborted on `low_confidence` from task2plan — should only abort on `ambiguous`      | `src/cli.py`     |

---

## Test run history

| Date       | Passed | Failed | Skipped | Notes                                                                                        |
|------------|--------|--------|---------|----------------------------------------------------------------------------------------------|
| 2026-03-22 | 8      | 8      | 1       | First real integration run. 13 min. All failures traced to task2plan/transition2exec.        |
| 2026-03-22 | 8      | 8      | 1       | Second run (6 min 24 sec). No change in score. transition2exec fixes not yet deployed. Failure breakdown below. |
| 2026-03-22 | —      | —      | —       | Patch contract test: 9/12 pass (3 skip by design). P04 `get_first`, P09 multi-step order, P10 `split_lines` are training gaps. Logged for patch service team. |

### Second run failure breakdown

| Test | Root cause | Service   | Detail                                                                 |
|------|------------|-----------|------------------------------------------------------------------------|
| 04   | task2plan  | task2plan | Delete ran twice — two segments generated. State ends with `deleted=False`. |
| 06   | t2e deploy | transition2exec | `run_shell_command` not_mappable — ISS-008/009 fix not in running service. |
| 07   | t2e deploy | transition2exec | Same as 06.                                                           |
| 09   | task2plan  | task2plan | Multi-step collapsed — two `create_file` calls, no `read_file`. One segment. |
| 11   | task2plan  | task2plan | Second transition dropped — `make_directory` ran, `create_file` missing. |
| 12   | task2plan  | task2plan | Multi-step incomplete — shell command ran, write to file never planned. |
| 13   | task2plan  | task2plan | Wrong tool — `exists` used instead of `read_file`. Nonexistent file returns `completed` not `failed`. |
| 15   | t2e deploy | transition2exec | `exit 1` → not_mappable. Same root cause as 06/07.                   |
