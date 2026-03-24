# OS2I Issues

## Response to TaskExecutor Team — transition2exec Contract and Runtime Expectations

_Date: 2026-03-22 | Baseline: 12/17 field test seeds passing_

---

### What transition2exec HONOURS (guaranteed)

1. **Grounded tool only.**
   Every executable transition references a tool that exists in the `available_tools` catalog supplied by the caller. We never hallucinate tool names.

2. **Inputs resolved from state.**
   Input values are drawn from context (state). If a value is not in state, it is synthesised from the task description. If it cannot be derived from either, it is emitted as `""`.

3. **Outputs are null slots.**
   Output keys match the grounded tool's signature and are set to `null`. taskexecutor fills them by running the tool.

4. **Status semantics.**
   - `ok` — grounded executable transition produced; tool is from the catalog.
   - `not_mappable` — no catalog tool matched the abstract transition.
   - `ambiguous` — task is underspecified; caller should provide more context.

5. **One transition at a time.**
   transition2exec maps exactly one abstract transition per call. It has no knowledge of prior or future transitions beyond what is in the current state.

---

### What transition2exec CANNOT honour (known gaps — design taskexecutor accordingly)

6. **Not a single canonical tool.**
   When multiple catalog tools can solve the same problem, either may be selected. Example: `write_stdout_to_file` may resolve to `create_file` or `run_shell_command` depending on context. **taskexecutor must accept any catalog tool that can produce the required output type — do not hard-code expected tool names.**

7. **Not exact command strings for `run_shell_command`.**
   The synthesised command is best-effort. Functional variants are expected:
   - Absolute path vs relative `.` with `working_directory`
   - `python` vs `python3`
   - Equivalent flag ordering
   **taskexecutor must surface `return_code != 0` as a recoverable interface mismatch, not a fatal failure.**

8. **Not reliable tool selection for count/search abstract tools (ISS-017).**
   Abstract tools like `count_python_files` or `find_files_with_import` may resolve to `list_directory_recursive` instead of `run_shell_command`. Both are in the catalog. The list-based approach is functional but slower.
   **taskexecutor should treat this as a valid (if suboptimal) grounding. The output type (`entries` vs `stdout`) will differ — state merge must be tolerant of output key name mismatches.**

9. **Not guaranteed correct tool for t2+ transitions when context is ambiguous (ISS-015).**
   When prior step outputs remain in state (e.g. `content: "hello"` from a create step), stage 1 may pick the tool that consumes those inputs rather than the tool that produces the required outputs. Example: `read_temp_file` resolves to `create_file` instead of `read_file`.
   **This is a genuine wrong-tool failure. The selected tool cannot produce `file_contents`. taskexecutor SHOULD detect this pre-dispatch: if the grounded tool's output keys have zero overlap with the abstract transition's `outputs`, fail immediately with status `tool_output_mismatch` and do not run the tool.**

10. **Empty string inputs are not failures.**
    `""` on an input means the value was not resolvable at grounding time. It is not an error from transition2exec's perspective.
    **taskexecutor should fail the transition with a clear `missing_input` error if the tool cannot proceed with an empty value, so the gap is traceable back to the abstract plan.**

---

### Design checklist for taskexecutor

| Scenario | taskexecutor behaviour |
|----------|----------------------|
| `return_code != 0` from `run_shell_command` | Surface error, allow retry with corrected command |
| Tool output keys differ from abstract transition outputs | Map by grounded tool schema, not by key name equality |
| Grounded tool output keys have zero overlap with abstract outputs | Fail pre-dispatch with `tool_output_mismatch` |
| Input value is `""` | Fail with `missing_input`, log which key |
| `status: not_mappable` from transition2exec | Fail transition, do not attempt dispatch |
| `status: ambiguous` from transition2exec | Surface to caller for context clarification |

---

## Issue Log

### ISS-001 — `shell` missing from `run_shell_command` catalog
**Status:** Fixed
Field test seed defines 3 inputs for `run_shell_command`: `command`, `working_directory`, `shell`. Catalog only had 2. Added `shell` to `DEFAULT_TOOLS`.

---

### ISS-002 — Batch runner did not handle top-level `available_tools`
**Status:** Fixed
Field test seed defines tools once at the top level, not per-entry. Batch runner now parses both JSON-with-seeds-array and JSONL formats, inheriting shared tools. Also added `expected` field validation (PASS/MISMATCH/FAIL verdict per seed).

---

### ISS-003 — Synthesise inputs from task when absent from state
**Status:** Fixed
Contract defined and prompt updated: if a required input has no state value, derive from task description; if task gives no value, emit `""`. Covers seeds 06, 12a, 15, 10a, 10b.

---

### ISS-004 — `content: ""` for create_file with no content in context
**Status:** Closed — covered by ISS-003

---

### ISS-005 — Type info not captured in GroundedTool model
**Status:** Open (P3 — low priority)
Seed tool definitions include `"type": "str"` on inputs/outputs. Our model ignores these. No impact on current pipeline. Useful for future runtime validation.

---

### ISS-006 — No strict expected validation in batch runner
**Status:** Fixed
Batch runner now reports PASS / MISMATCH (WRONG_TOOL, WRONG_INPUT) / FAIL per seed with full verdict.

---

### ISS-007 — Stage 1 planned the whole task instead of one transition
**Status:** Fixed
Prompt restructured: tool selection driven by `abstract_tool` + `required_outputs` only. Task text demoted to "value hint only". Over-generation resolved for 09b, 11a, 11b, 12a.

---

### ISS-008 — Stage 2 produced malformed JSON for run_shell_command
**Status:** Fixed
Root cause: stage 2 was a formatting LLM that had to fill blanks — it split transitions when values were empty. Fixed by making stage 1 + Python pre-fill all input values before stage 2. Stage 2 now just copies pre-populated templates.

---

### ISS-009 — `not_mappable` for trivial run_shell_command
**Status:** Fixed
Root cause: `working_directory` was required by seed tool signature but not emitted by stage 1. Fixed by merging stage 1 synthesised values into the resolved_tools template in Python (`_extract_resolved_tools`). Empty string kept as key rather than dropped.

---

### ISS-010 — Absolute vs relative path in shell commands
**Status:** Closed — best effort, runtime resolves
Model uses absolute paths; expected uses `.` relative to `working_directory`. Functionally equivalent. taskexecutor surfaces `return_code != 0` as recoverable mismatch.

---

### ISS-011 — Wrong tool for t2+ transitions
**Status:** Partially fixed
Fixed by: (a) Python output-match selection in `_extract_resolved_tools` — picks grounded tool whose name tokens overlap with abstract outputs; (b) stage 1 prompt restructure reducing task-driven planning.
- 11b: Fixed ✓
- 09b: Open (ISS-015)
- 12b: Closed as valid alternative (ISS-016)

---

### ISS-012 — Shell metacharacters broke stage 2 JSON parsing
**Status:** Fixed
Root cause: stage 2 was an LLM formatter that reinterpreted command strings. Fixed by moving all value resolution into Python before stage 2. Stage 2 copies verbatim.

---

### ISS-013 — Semantically equivalent command/content variants
**Status:** Closed — best effort, runtime resolves
`python` vs `python3`, `"line1"` vs `"line1\n"` — interface variants. Pipeline produces valid transitions. Runtime detects if the specific form fails.

---

### ISS-014 — `list_directory` vs `list_directory_recursive`
**Status:** Fixed
Required_outputs-driven selection and tool description improvement resolved this.

---

### ISS-015 — Wrong tool for read transition (seed 09b) — taskexecutor must guard
**Status:** Open — genuine wrong-tool failure, training data target
`read_temp_file` → stage 1 picks `create_file` instead of `read_file`. `create_file` cannot produce `file_contents`. This will fail at runtime with a type mismatch.
**taskexecutor action required:** before dispatching any tool, check that the grounded tool's output keys have at least one overlap with the abstract transition's `outputs`. If zero overlap → fail with `tool_output_mismatch`, do not run the tool.
Training fix: add `read_temp_file → read_file` as a labelled seed example.

---

### ISS-016 — Alternative tool for write transition (seed 12b)
**Status:** Closed — valid alternative
`write_stdout_to_file` → `run_shell_command` (via shell redirection). Both tools can write content to a file. Pipeline did not hallucinate. taskexecutor must tolerate output key name differences between the grounded tool and the abstract transition.

---

### ISS-017 — Count/search abstract tools resolve to list_directory instead of run_shell_command (seeds 07, 08)
**Status:** Open — best effort, taskexecutor must handle output type mismatch
`count_python_files` → `list_directory_recursive` (outputs: `entries`). Expected: `run_shell_command` (outputs: `stdout`). The list-based approach is in the catalog and functional but produces a different output type.
**taskexecutor action required:** abstract transition output `python_file_count` (int) will not be directly in state — `entries` (list) will be. The kernel must be tolerant of grounded output key names differing from abstract output names. Map grounded outputs into state by grounded key name, then let the next transition consume whatever is available.
**Training fix:** add `count_python_files → run_shell_command` and `find_files_with_import → run_shell_command` as labelled seed examples. The `run_shell_command` preference for count/search should be in training data, not hard-coded in prompts.
