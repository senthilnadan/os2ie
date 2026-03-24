# transition2exec V2 — Cases to Cross the Finish Line

Filed for: transition2exec team
Purpose: steerco funding report
Date: 2026-03-23

Current score: 10/16 passing.
Fixing the cases below brings the score to 16/16.

---

## Category A — Split Cases (tests 10, 11)

Abstract DSTT collapses multiple operations into one abstract tool.
No single tool in the catalog fulfils the abstract tool.
transition2exec must split into N executable transitions with state threading.

---

### CASE-S01 — test_10: Create file, append line1, append line2

**Task:**
```
Create /tmp/log.txt, append "line1", then append "line2"
```

**State provided:**
```json
{"file_path": "/tmp/log.txt"}
```

**Abstract DSTT from task2plan:**
```json
{"tool":"create_log_file_and_append_lines","inputs":["log_directory","line1","line2"],"outputs":["log_file_path"]}
```

**What transition2exec currently does:**
Attempts to ground `create_log_file_and_append_lines` to a single tool.
No such tool exists. Produces `not_mappable` or grounds incorrectly to
`append_to_file` which runs multiple times without a prior create.
Result: `line2line2line2line2` — append repeated, create never ran.

**What V2 must do:**
Detect that `create_log_file_and_append_lines` implies a sequence.
Split into 3 executable transitions with state threading:

```json
{"id":"t1","tool":"create_file","inputs":{"file_path":"/tmp/log.txt","content":""},"outputs":{"success":null}}
{"id":"t2","tool":"append_to_file","inputs":{"file_path":"/tmp/log.txt","content":"line1"},"outputs":{"success":null}}
{"id":"t3","tool":"append_to_file","inputs":{"file_path":"/tmp/log.txt","content":"line2"},"outputs":{"success":null}}
```

**Split signal:** abstract tool name contains compound verbs (create + append).
No single catalog tool covers create + multi-append.

---

### CASE-S02 — test_11: Create directory then create file inside it

**Task:**
```
Create the directory /tmp/newdir then create the file /tmp/newdir/file.txt with content 'hi'
```

**State provided:**
```json
{"directory_path": "/tmp/newdir", "file_path": "/tmp/newdir/file.txt", "content": "hi"}
```

**Abstract DSTT from task2plan:**
```json
{"tool":"create_directory_and_file","inputs":["directory_path","file_name","content"],"outputs":["directory_created","file_written"]}
```

**What transition2exec currently does:**
Attempts to ground `create_directory_and_file` to a single tool.
No such tool exists. Execution fails — directory may be created but file
creation is dropped.

**What V2 must do:**
Detect compound tool name (directory + file). Split into 2 executable
transitions with state threading:

```json
{"id":"t1","tool":"make_directory","inputs":{"directory_path":"/tmp/newdir"},"outputs":{"created":null}}
{"id":"t2","tool":"create_file","inputs":{"file_path":"/tmp/newdir/file.txt","content":"hi"},"outputs":{"success":null}}
```

**Split signal:** abstract tool name `create_directory_and_file` — two distinct
catalog operations. `make_directory` + `create_file`. No single tool covers both.

---

## Category B — Grounding + Binding Cases (tests 07, 08, 12, 13)

Abstract tool exists but either grounds to the wrong concrete tool,
or grounds correctly but output keys do not land in state.

---

### CASE-G01 — test_07: Count Python files

**Task:**
```
Count all Python files in /tmp/testdir
```

**State provided:**
```json
{"working_directory": "/tmp/testdir"}
```

**Abstract DSTT from task2plan:**
```json
{"tool":"count_python_files","inputs":["/tmp/testdir"],"outputs":["python_file_count"],"output_type":{"python_file_count":"int"}}
```

**What transition2exec currently does:**
Grounds `count_python_files` to `list_directory_recursive` (outputs: `entries`).
`python_file_count` never lands in state — `entries` is a list, not a count.
`return_code` absent. Test asserts `return_code == 0` — fails.

**What V2 must do:**
Ground to `run_shell_command`. Output binding maps `stdout` → `python_file_count`.

```json
{"tool":"run_shell_command","inputs":{"command":"find /tmp/testdir -name '*.py' | wc -l","working_directory":"/tmp/testdir"},"outputs":{"stdout":null,"return_code":null},"output_binding":{"stdout":"python_file_count","return_code":"return_code"}}
```

**Grounding signal:** `output_type.python_file_count = int` + `resource_required = filesystem`.
Count operations on files → `run_shell_command`, not `list_directory`.

---

### CASE-G02 — test_08: Find files containing string

**Task:**
```
Find all files containing "import fastapi" in /tmp/testdir
```

**State provided:**
```json
{"working_directory": "/tmp/testdir"}
```

**Abstract DSTT from task2plan:**
```json
{"tool":"search_files_for_string","inputs":["directory_path","search_string"],"outputs":["matching_files"],"output_type":{"matching_files":"list<file_path>"}}
```

**What transition2exec currently does:**
Grounds to `list_directory` or similar. `return_code` and `stdout` never land
in state. Test asserts `return_code == 0` and `"main.py" in stdout` — both fail.

**What V2 must do:**
Ground to `run_shell_command`. Output binding maps stdout → matching_files.

```json
{"tool":"run_shell_command","inputs":{"command":"grep -rl 'import fastapi' /tmp/testdir","working_directory":"/tmp/testdir"},"outputs":{"stdout":null,"return_code":null},"output_binding":{"stdout":"matching_files","return_code":"return_code"}}
```

**Grounding signal:** `search_files_for_string` + content search → `run_shell_command` (grep).
Not a directory listing — a content search requiring shell execution.

---

### CASE-G03 — test_12: Run shell command and write stdout to file

**Task:**
```
Run the command 'echo hello_from_shell' and write its stdout to /tmp/out.txt
```

**State provided:**
```json
{"file_path": "/tmp/out.txt"}
```

**Abstract DSTT from task2plan:**
```json
segment 1: {"tool":"run_shell_command","inputs":["command"],"outputs":["stdout"]}
segment 2: {"tool":"write_to_file","inputs":["stdout","/tmp/out.txt"],"outputs":["written_content"]}
```

**Note:** task2plan correctly split into 2 segments. This is a grounding problem only.

**What transition2exec currently does:**
Segment 1 grounds correctly to `run_shell_command`. Segment 2 — `write_to_file`
has no direct catalog match. Grounding fails or grounds incorrectly.
File never written. `status=failed`.

**What V2 must do:**
Ground `write_to_file` to `create_file`. Input `content` comes from `stdout`
in state (threaded from segment 1). Input `file_path` comes from state.

```json
segment 1: {"tool":"run_shell_command","inputs":{"command":"echo hello_from_shell"},"outputs":{"stdout":null,"return_code":null}}
segment 2: {"tool":"create_file","inputs":{"file_path":"/tmp/out.txt","content":"{{stdout}}"},"outputs":{"success":null}}
```

**Grounding signal:** `write_to_file` → nearest catalog match is `create_file`.
Input `stdout` is available in state from segment 1 — thread it as `content`.

---

### CASE-G04 — test_13: Read nonexistent file

**Task:**
```
Read the contents of /tmp/ghost.txt
```

**State provided:**
```json
{"file_path": "/tmp/ghost.txt"}
```

**Abstract DSTT from task2plan:**
```json
{"tool":"read_file_content","inputs":["file_path"],"outputs":["file_contents"],"output_type":{"file_contents":"string"}}
```

**What transition2exec currently does:**
Grounds `read_file_content` to `exists` instead of `read_file`.
`exists` returns `{is_present: False}` and never fails.
Test expects `status=failed` — gets `status=completed`.

**What V2 must do:**
Ground `read_file_content` to `read_file`. The abstract tool name and output
type `string` unambiguously signal read, not existence check.

```json
{"tool":"read_file","inputs":{"file_path":"/tmp/ghost.txt"},"outputs":{"text":null},"output_binding":{"text":"file_contents"}}
```

`read_file` on a nonexistent file fails. Executor returns `status=failed`.
Test passes.

**Grounding signal:** `read_file_content` + `output_type: string` → `read_file`.
Never `exists` — `exists` returns `boolean`, not `string`.

---

## Summary

| Case | Test | Category | Fix | Score impact |
|------|------|----------|-----|--------------|
| CASE-S01 | 10 | Split | `create_log_file_and_append_lines` → create + append + append | +1 |
| CASE-S02 | 11 | Split | `create_directory_and_file` → make_directory + create_file | +1 |
| CASE-G01 | 07 | Grounding + Binding | `count_python_files` → run_shell_command + output binding | +1 |
| CASE-G02 | 08 | Grounding + Binding | `search_files_for_string` → run_shell_command + output binding | +1 |
| CASE-G03 | 12 | Grounding | `write_to_file` → create_file, thread stdout from state | +1 |
| CASE-G04 | 13 | Grounding | `read_file_content` → read_file not exists | +1 |

**Fixing all 6 cases: 10/16 → 16/16**

All fixes are in transition2exec. No changes required in taskexecutor,
task2plan, or the executor kernel.
