# Asserter Seeds

Training examples for the `assert_milestone` LLM call.

Each example gives:
- `milestone` — the abstract goal keys from the DSTT segment
- `state`     — the full state after execution. Always contains `task` (and
                `parent_task` for subtask calls). All tool outputs are also here.
- `expected`  — `ok: true/false` and a brief reason

`task` and `parent_task` are in state — the asserter does not receive them
as separate inputs. Everything it needs is in state.

The asserter must reason semantically — milestone key names will rarely match
state key names exactly. The job is to determine whether the intent of the
milestone was achieved, not whether keys match literally.

---

## 1. File existence check

### 1a. File exists — pass
```json
{
  "task": "Check whether hello.py exists in /tmp/os2ie_sandbox",
  "milestone": ["file_exists"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/hello.py",
    "is_present": true
  },
  "expected": { "ok": true, "reason": "is_present=true confirms file existence was checked and the file exists" }
}
```

### 1b. File does not exist — pass (task completed, result is false)
```json
{
  "task": "Check whether hello.py exists in /tmp/os2ie_sandbox",
  "milestone": ["file_exists"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/hello.py",
    "is_present": false
  },
  "expected": { "ok": true, "reason": "is_present=false is a valid result — the check ran and the answer is 'no'" }
}
```

### 1c. No result in state — fail
```json
{
  "task": "Check whether hello.py exists in /tmp/os2ie_sandbox",
  "milestone": ["file_exists"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/hello.py"
  },
  "expected": { "ok": false, "reason": "no existence check result in state — tool did not run or output was not merged" }
}
```

---

## 2. Read file

### 2a. File read — pass
```json
{
  "task": "Read the contents of README.md",
  "milestone": ["file_contents"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/README.md",
    "text": "# Hello World\nThis is the readme."
  },
  "expected": { "ok": true, "reason": "text key contains file contents — milestone achieved" }
}
```

### 2b. File read returned empty string — pass
```json
{
  "task": "Read the contents of README.md",
  "milestone": ["file_contents"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/README.md",
    "text": ""
  },
  "expected": { "ok": true, "reason": "text key is present — empty file is a valid read result" }
}
```

### 2c. Read failed, error in state — fail
```json
{
  "task": "Read the contents of README.md",
  "milestone": ["file_contents"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/README.md"
  },
  "expected": { "ok": false, "reason": "no text or file_contents key in state — read did not complete" }
}
```

---

## 3. Create file

### 3a. File created — pass
```json
{
  "task": "Create notes.txt with content 'first note'",
  "milestone": ["file_created"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/notes.txt",
    "content": "first note",
    "success": true
  },
  "expected": { "ok": true, "reason": "success=true confirms file was created" }
}
```

### 3b. Creation returned success=false — fail
```json
{
  "task": "Create notes.txt with content 'first note'",
  "milestone": ["file_created"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/notes.txt",
    "content": "first note",
    "success": false
  },
  "expected": { "ok": false, "reason": "success=false means file creation did not complete" }
}
```

---

## 4. Delete file

### 4a. File deleted — pass
```json
{
  "task": "Delete temp.txt",
  "milestone": ["file_deleted"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/temp.txt",
    "deleted": true
  },
  "expected": { "ok": true, "reason": "deleted=true confirms the file was removed" }
}
```

### 4b. File did not exist — pass (graceful non-error)
```json
{
  "task": "Delete temp.txt",
  "milestone": ["file_deleted"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/temp.txt",
    "deleted": false
  },
  "expected": { "ok": true, "reason": "deleted=false means file was not present — delete intent is satisfied, file is gone either way" }
}
```

### 4c. No delete result in state — fail
```json
{
  "task": "Delete temp.txt",
  "milestone": ["file_deleted"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/temp.txt"
  },
  "expected": { "ok": false, "reason": "no deleted key in state — delete tool did not run" }
}
```

---

## 5. Shell command — python version

### 5a. Command succeeded — pass
```json
{
  "task": "Check the Python version installed on this system",
  "milestone": ["python_version"],
  "state": {
    "command": "python3 --version",
    "stdout": "",
    "stderr": "Python 3.11.4\n",
    "return_code": 0
  },
  "expected": { "ok": true, "reason": "return_code=0 and stderr contains Python version string — milestone achieved" }
}
```

### 5b. Version in stdout — pass
```json
{
  "task": "Check the Python version installed on this system",
  "milestone": ["python_version"],
  "state": {
    "command": "python3 --version",
    "stdout": "Python 3.14.3\n",
    "stderr": "",
    "return_code": 0
  },
  "expected": { "ok": true, "reason": "stdout contains Python version — milestone achieved" }
}
```

### 5c. Command not found — fail
```json
{
  "task": "Check the Python version installed on this system",
  "milestone": ["python_version"],
  "state": {
    "command": "python3 --version",
    "stdout": "",
    "stderr": "python3: command not found\n",
    "return_code": 127
  },
  "expected": { "ok": false, "reason": "return_code=127 and stderr shows command not found — python version could not be determined" }
}
```

---

## 6. Shell command — non-zero exit (caller decides)

### 6a. Non-zero is expected — pass
```json
{
  "task": "Run the shell command 'exit 1'",
  "milestone": ["command_ran"],
  "state": {
    "command": "exit 1",
    "stdout": "",
    "stderr": "",
    "return_code": 1
  },
  "expected": { "ok": true, "reason": "the task was to run the command — it ran and produced return_code=1 as expected" }
}
```

---

## 7. Multi-step — create then read

### 7a. Both steps completed — pass
```json
{
  "task": "Create temp.txt with content 'hello' then read it back",
  "milestone": ["file_read_back"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/temp.txt",
    "content": "hello",
    "success": true,
    "text": "hello"
  },
  "expected": { "ok": true, "reason": "text='hello' confirms the file was created and read back successfully" }
}
```

### 7b. Create succeeded but read did not run — fail
```json
{
  "task": "Create temp.txt with content 'hello' then read it back",
  "milestone": ["file_read_back"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/temp.txt",
    "content": "hello",
    "success": true
  },
  "expected": { "ok": false, "reason": "success=true shows create ran but there is no text key — read step did not execute" }
}
```

---

## 8. Multi-step — create dir then create file inside

### 8a. Both steps completed — pass
```json
{
  "task": "Create the directory /tmp/os2ie_sandbox/newdir then create a file inside it",
  "milestone": ["setup_complete"],
  "state": {
    "directory_path": "/tmp/os2ie_sandbox/newdir",
    "file_path": "/tmp/os2ie_sandbox/newdir/file.txt",
    "content": "hi",
    "created": true,
    "success": true
  },
  "expected": { "ok": true, "reason": "created=true and success=true confirm both directory and file were created" }
}
```

### 8b. Dir created, file not created — fail
```json
{
  "task": "Create the directory /tmp/os2ie_sandbox/newdir then create a file inside it",
  "milestone": ["setup_complete"],
  "state": {
    "directory_path": "/tmp/os2ie_sandbox/newdir",
    "created": true
  },
  "expected": { "ok": false, "reason": "directory was created (created=true) but no file creation result in state — second step did not run" }
}
```

---

## 9. Shell stdout to file

### 9a. Both steps completed — pass
```json
{
  "task": "Run 'echo hello_from_shell' and write its stdout to /tmp/os2ie_sandbox/out.txt",
  "milestone": ["output_saved"],
  "state": {
    "command": "echo hello_from_shell",
    "stdout": "hello_from_shell\n",
    "stderr": "",
    "return_code": 0,
    "file_path": "/tmp/os2ie_sandbox/out.txt",
    "content": "hello_from_shell\n",
    "success": true
  },
  "expected": { "ok": true, "reason": "stdout captured and success=true confirms content was written to file" }
}
```

### 9b. Command ran but file not written — fail
```json
{
  "task": "Run 'echo hello_from_shell' and write its stdout to /tmp/os2ie_sandbox/out.txt",
  "milestone": ["output_saved"],
  "state": {
    "command": "echo hello_from_shell",
    "stdout": "hello_from_shell\n",
    "stderr": "",
    "return_code": 0
  },
  "expected": { "ok": false, "reason": "stdout was captured but no file write result in state — second step did not run" }
}
```

---

## 10. Read nonexistent file (failure case)

### 10a. Tool raised, no text produced — fail
```json
{
  "task": "Read the contents of /tmp/os2ie_sandbox/ghost.txt",
  "milestone": ["file_contents"],
  "state": {
    "file_path": "/tmp/os2ie_sandbox/ghost.txt"
  },
  "expected": { "ok": false, "reason": "no text or file_contents key in state — file read did not succeed, file likely does not exist" }
}
```

---

## Key reasoning rules for the asserter

1. **Semantic match, not literal key match** — `file_exists`, `file_present`, `is_present` all refer to the same intent.
2. **False is a valid result for boolean outputs** — `is_present=false`, `deleted=false` mean the tool ran successfully.
3. **Missing key = tool did not run** — the absence of an expected output key is a failure.
4. **null/None value = inconclusive** — treat as failure unless the task explicitly expects null.
5. **return_code=0 = shell success; non-zero = inspect stderr** — non-zero alone is not a milestone failure unless the task required success.
6. **Partial multi-step = fail** — if only the first of two steps completed, the segment milestone is not achieved.
