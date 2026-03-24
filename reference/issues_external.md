# External Issues Report

Filed against: **as_task2plan** and **transition2exec** services.
Generated from integration test run: 2026-03-23
Test suite: `tests/test_seeds.py`
Setup: `as_task2plan` on qwen2.5:3b (port 8001), `transition2exec` on qwen2.5:7b (port 8002)
Result: **10 passed, 6 failed, 1 skipped** (16 seed tests)

---

## Filed Against: as_task2plan

---

### ISS-AT-001 — Wrong tool selected for read task

**Test:** `test_13_read_nonexistent_file`

**Use case:**
Read the contents of a file that does not exist. The executor should attempt
`read_file`, fail because the file is absent, and return `status=failed`.

**Task sent:**
```
Read the contents of /tmp/.../ghost.txt
```

**Context provided:**
```json
{ "file_path": "/tmp/.../ghost.txt" }
```

**What went wrong:**
`as_task2plan` selected `exists` instead of `read_file`. The `exists` tool
checks for file presence and returns `{ is_present: False }` — it does not
fail. Execution completes with `status=completed` and `is_present: False` in
state. The test expects `status=failed` because reading a nonexistent file is
an error, not a presence check.

**Expected DSTT:**
```json
{ "tool": "read_file", "inputs": ["file_path"], "outputs": ["text"] }
```

**Actual DSTT produced:**
```json
{ "tool": "exists", "inputs": ["file_path"], "outputs": ["is_present"] }
```

**Impact:** Read tasks on nonexistent files silently succeed instead of failing.
Callers cannot distinguish "file not found" from "file read successfully."

---

### ISS-AT-002 — Wrong sequence for create-then-append task

**Test:** `test_10_create_and_append_twice`

**Use case:**
Create a file, then append "line1", then append "line2". Final file should
contain both lines.

**Task sent:**
```
Create /tmp/.../log.txt, append "line1", then append "line2"
```

**Context provided:**
```json
{ "file_path": "/tmp/.../log.txt" }
```

**What went wrong:**
The plan skipped `create_file` or sequenced it incorrectly. `append_to_file`
ran multiple times producing `line2line2line2line2` — the append step was
repeated rather than sequenced create → append(line1) → append(line2).
`line1` never appeared in the final file.

**Expected sequence:**
```
t1: create_file   → success
t2: append_to_file (content=line1) → success
t3: append_to_file (content=line2) → success
```

**Impact:** Multi-step create-then-append tasks produce corrupted output.

---

### ISS-AT-003 — Multi-step task incomplete: shell output not written to file

**Test:** `test_12_shell_stdout_to_file`

**Use case:**
Run a shell command and write its stdout to a file. Two steps: (1) run the
command, (2) write stdout to file.

**Task sent:**
```
Run the command 'echo hello_from_shell' and write its stdout to /tmp/.../out.txt
```

**Context provided:**
```json
{ "file_path": "/tmp/.../out.txt" }
```

**What went wrong:**
The plan either collapsed to a single step (shell command only, no write step)
or the write step was dropped. `status=failed` — the file was never created.

**Expected sequence:**
```
t1: run_shell_command (command='echo hello_from_shell') → stdout
t2: create_file (file_path=..., content=stdout) → success
```

**Impact:** Tasks that chain shell output into file writes fail silently.

---

### ISS-AT-004 — Multi-step task incomplete: make_directory then create_file

**Test:** `test_11_make_dir_then_create_file`

**Use case:**
Create a directory, then create a file inside it. Two dependent steps.

**Task sent:**
```
Create the directory /tmp/.../newdir then create the file /tmp/.../newdir/file.txt with content 'hi'
```

**Context provided:**
```json
{
  "directory_path": "/tmp/.../newdir",
  "file_path": "/tmp/.../newdir/file.txt",
  "content": "hi"
}
```

**What went wrong:**
`status=failed` — either the plan collapsed to one step (directory only,
file creation dropped) or the file creation step failed because the directory
step did not produce the expected output key for the next step.

**Expected sequence:**
```
t1: make_directory (directory_path=...) → created
t2: create_file (file_path=..., content='hi') → success
```

**Impact:** Any task requiring directory creation before file creation fails.

---

### ISS-AT-005 — count python files: return_code absent, wrong tool selected

**Test:** `test_07_count_python_files`

**Use case:**
Count all Python files in a directory using a shell command. Result should
land `return_code=0` and `stdout` in state.

**Task sent:**
```
Count all Python files in /tmp/.../test_dir
```

**Context provided:**
```json
{ "working_directory": "/tmp/.../test_dir" }
```

**What went wrong:**
The plan did not select `run_shell_command`. Instead it selected a non-shell
tool (e.g. `list_directory` or similar). `return_code` never landed in state.
`status=completed` but assertion on `return_code == 0` fails because the key
is absent.

**Impact:** Tasks that require shell-based counting or filtering don't produce
shell output keys.

---

## Filed Against: transition2exec

---

### ISS-T2E-001 — return_code absent from state after run_shell_command

**Tests:** `test_07_count_python_files`, `test_08_find_files_containing_string`

**Use case:**
Tasks that require running a shell command and inspecting its return code and
stdout. The executor dispatches `run_shell_command`, which returns
`{ stdout, stderr, return_code }`. These keys must land in state.

**What went wrong:**
`run_shell_command` executes and `status=ok` is returned by the tool. However
`return_code` is absent from state after the transition. `stdout` may also be
absent. The output binding is not mapping the tool's grounded output keys back
into state under the expected abstract key names.

**Observed state after transition (test_08):**
```json
{
  "directory_path": "/tmp/...",
  "working_directory": "/tmp/..."
}
```

**Expected state after transition:**
```json
{
  "directory_path": "/tmp/...",
  "working_directory": "/tmp/...",
  "return_code": 0,
  "stdout": "main.py\n",
  "stderr": ""
}
```

**Root cause hypothesis:**
The `output_binding` on the `ExecutableTransition` is missing or maps to
wrong key names. The executor applies the binding after dispatch — if the
grounded output keys don't match what binding declares, the keys are silently
dropped.

**Contract reference:**
`ExecutableTransition.output_binding` must emit `{ grounded_key: abstract_key }`
for every output. If grounded key equals abstract key, binding may be omitted
(identity). See executor contract.

**Impact:** Any task that depends on `return_code`, `stdout`, or `stderr`
from a shell command will fail assertion even when the command ran correctly.

---

## Test Run Summary

| Test | Task | Service | Status | Verdict |
|------|------|---------|--------|---------|
| 01 | Check file exists | — | PASS | — |
| 01b | Check file not exists | — | PASS | — |
| 02 | List directory | — | PASS | — |
| 03 | Read file | — | PASS | — |
| 04 | Delete file | — | PASS | — |
| 05 | Create file | — | PASS | — |
| 06 | Check python version | — | PASS | — |
| 07 | Count python files | transition2exec | FAIL | ISS-T2E-001 |
| 08 | Find files containing string | transition2exec | FAIL | ISS-T2E-001 |
| 09 | Create then read | — | PASS | — |
| 10 | Create and append twice | as_task2plan | FAIL | ISS-AT-002 |
| 11 | Make dir then create file | as_task2plan | FAIL | ISS-AT-004 |
| 12 | Shell stdout to file | as_task2plan | FAIL | ISS-AT-003 |
| 13 | Read nonexistent file | as_task2plan | FAIL | ISS-AT-001 |
| 14 | Delete nonexistent file | — | PASS | — |
| 15 | Nonzero return code | — | PASS | — |
| 16 | Subtask | — | SKIP | deferred |
