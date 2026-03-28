# Transition2Shell — Issues Report

**Service:** `http://localhost:8002/transition2Shell`
**Model:** `qwen2.5:7b`
**Tested:** 2026-03-28
**Baseline:** 20/20 passing
**Negative suite:** 9/15 passing — 6 failures

---

## Summary

All 6 failures are **false positives** — the service returns `status: ok` with a
`script_description` when it should return `status: not_capable`. No false
negatives observed (the service never refused a task it could do).

Three distinct failure modes identified below.

---

## Issue 1 — Hallucinated commands

**Seeds:** n06, n10
**Severity:** High

The service invents commands that do not exist on any Unix system. The
`script_description` looks plausible but would fail immediately at runtime.

### n06 — `process_data`
**Request:**
```json
{
  "task": "Process the data file at /tmp/os2ie_sandbox/input.dat",
  "intent": "process_data",
  "inputs": ["file_path"],
  "outputs": ["result"],
  "context": { "file_path": "/tmp/os2ie_sandbox/input.dat" }
}
```
**Expected:** `status: not_capable` — intent is too vague to map to a shell command
**Actual:** `status: ok`
**script_description:** `"Use process_data /tmp/os2ie_sandbox/input.dat to process the data file at the specified path."`
**Problem:** `process_data` is not a Unix command. The service echoed the intent name as a command.

### n10 — empty intent
**Request:**
```json
{
  "task": "Do the thing with the file",
  "intent": "",
  "inputs": ["file_path"],
  "outputs": ["result"],
  "context": { "file_path": "/tmp/os2ie_sandbox/file.txt" }
}
```
**Expected:** `status: not_capable` — no intent signal, cannot determine what to do
**Actual:** `status: ok`
**script_description:** `"Use cp file_path destination to copy the file from the given path to the specified destination."`
**Problem:** With no intent, the service invented a `cp` operation from context alone. Wrong task.

**Ask:** When intent is empty or when the intent name does not correspond to any known Unix command, return `not_capable`. The service must not hallucinate commands.

---

## Issue 2 — Intent drift (falls back to wrong command)

**Seeds:** n07, n09
**Severity:** Medium

The service recognises that it cannot do exactly what was asked, but instead of
returning `not_capable` it falls back to a different, unrelated shell command.
The script_description is syntactically valid but does not implement the task.

### n07 — `transform_file`
**Request:**
```json
{
  "task": "Transform /tmp/os2ie_sandbox/data.csv",
  "intent": "transform_file",
  "inputs": ["file_path"],
  "outputs": ["output_path"],
  "context": { "file_path": "/tmp/os2ie_sandbox/data.csv" }
}
```
**Expected:** `status: not_capable` — "transform" is unspecified; no shell command can be chosen
**Actual:** `status: ok`
**script_description:** `"Use cp /tmp/os2ie_sandbox/data.csv output_path to copy the file."`
**Problem:** Copying is not transforming. The service drifted to a safe-sounding fallback.

### n09 — `analyze_logs`
**Request:**
```json
{
  "task": "Analyze the log file and report any anomalies",
  "intent": "analyze_logs",
  "inputs": ["file_path"],
  "outputs": ["anomalies"],
  "context": { "file_path": "/tmp/os2ie_sandbox/app.log" }
}
```
**Expected:** `status: not_capable` — "anomalies" requires semantic reasoning, not pattern matching
**Actual:** `status: ok`
**script_description:** `"Use grep -E 'anomaly_pattern' file_path to search for anomalies."`
**Problem:** `anomaly_pattern` is a placeholder — the service cannot know what pattern to use. The script would not work without that information.

**Ask:** When the task or intent is too vague to produce a concrete, complete shell command — no placeholders, no invented patterns — return `not_capable`. A script description with placeholder values is not a valid script.

---

## Issue 3 — Capability blind spots

**Seeds:** n13, n15
**Severity:** Medium

The service knows the correct shell command but fails to reason about constraints
that make the command unavailable or unsafe in the execution context.

### n13 — `chown root` requires sudo
**Request:**
```json
{
  "task": "Change the owner of /tmp/os2ie_sandbox/deploy.sh to root",
  "intent": "change_file_owner",
  "inputs": ["file_path", "owner"],
  "outputs": ["return_code"],
  "context": {
    "file_path": "/tmp/os2ie_sandbox/deploy.sh",
    "owner": "root"
  }
}
```
**Expected:** `status: not_capable` — changing ownership to root requires elevated permissions
**Actual:** `status: ok`
**script_description:** `"Use chown root /tmp/os2ie_sandbox/deploy.sh to change the owner."`
**Problem:** `chown` to root requires `sudo`. The generic shell profile does not guarantee elevated permissions. This script would fail with a permission error.

### n15 — atomic increment is not possible with awk
**Request:**
```json
{
  "task": "Atomically increment the counter in /tmp/os2ie_sandbox/count.txt by 1",
  "intent": "increment_counter",
  "inputs": ["file_path"],
  "outputs": ["new_value"],
  "context": { "file_path": "/tmp/os2ie_sandbox/count.txt" }
}
```
**Expected:** `status: not_capable` — shell read-modify-write is not atomic; concurrent access would corrupt the counter
**Actual:** `status: ok`
**script_description:** `"Use awk to atomically increment the counter in /tmp/os2ie_sandbox/count.txt by 1."`
**Problem:** `awk` does not provide atomicity. The word "atomically" in the task is a hard constraint the service ignored.

**Ask:** Extend the shell capability profile to include constraint-aware reasoning:
- Operations requiring elevated permissions (`root`, `sudo`) → `not_capable`
- Operations requiring atomicity or transactional guarantees → `not_capable`

---

## Test suite

Negative seeds: `training/transition2shell_negative_seed.json` (15 seeds)
Baseline seeds: `training/transition2shell_seed.json` (20 seeds)
Prompt: `prompts/shell_skill_check.md`

Run against live service to reproduce all issues above.

---

## Pass criteria reminder

| Case | Expected |
|------|----------|
| Task is shell-implementable with a concrete, complete command | `status: ok` + valid `script_description` |
| Intent is vague, empty, or maps to no Unix command | `status: not_capable` |
| Task requires network, DB, GUI, ML, elevated permissions, or atomicity | `status: not_capable` |
| script_description contains placeholders or invented commands | reject — return `not_capable` |
