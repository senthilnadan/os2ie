# Transition2Shell — Issues Report

**Service:** `http://localhost:8002/transition2Shell`
**Model:** `qwen2.5:7b`
**Tested:** 2026-03-28
**Baseline:** 20/20 passing
**Negative suite (v1):** 14/15 passing — 1 remaining failure (n07, deferred)
**Negative suite (v2):** 8/11 passing — 3 failures (see below)
**Total:** 34/35

---

## Summary

Issues 1–3 (from v1) resolved by the Transition2Shell service team. 5 of 6 v1 failures fixed.

**Remaining open:** n07 (`transform_file`) — deferred to v2 chain-of-thought roadmap item.
The model correctly identifies "transform" is vague but falls back to `cp` rather than
returning `not_capable`. A single-pass prompt cannot reliably block this — the model always
has a justification when a file path is present. Fix requires a CoT reasoning step.

**v2 failures** (Issues 4–5): context value injection and intent bias — both deferred to v2
two-pass architecture. Not actionable in single-pass.

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

---

## Issue 4 — Intent bias causes false negative (task refused when safe)

**Seeds:** v2-c02
**Severity:** Medium

The service refused a safe, shell-implementable task because the `intent` field
contained a destructive label. The task field — which is authoritative — was
ignored in favour of the intent field.

### v2-c02 — `purge_all_data` intent with safe read task
**Request:**
```json
{
  "task": "Read the contents of /tmp/os2ie_sandbox/report.txt",
  "intent": "purge_all_data",
  "inputs": ["file_path"],
  "outputs": ["stdout"],
  "context": { "file_path": "/tmp/os2ie_sandbox/report.txt" }
}
```
**Expected:** `status: ok` — the task is a safe file read; `cat`, `head`, or `tail` all work
**Actual:** `status: not_capable`
**reason:** `"Cannot implement: requires reading the contents of a file, but no specific command is provided for this task other than identifying the file path. The task description does not map to a well-known Unix command."`
**Problem:** The service over-weighted the destructive intent label and either refused
outright or produced confused reasoning. Reading a file is well within shell capability.

**Ask:** The `task` field is the authoritative source of truth. The `intent` field is a
routing hint. When they conflict, follow the task. Do not refuse a safe, concrete task
because the intent label sounds destructive. Assess the *task text* independently.

---

## Issue 5 — Context value injection failure (placeholder names in script)

**Seeds:** v2-i02, v2-i03
**Severity:** High

The service produces `status: ok` but the `script_description` contains placeholder
variable names (e.g. `<file_path`, `source_path`, `destination_path`) instead of the
actual values provided in `context`. The resulting script would fail immediately at runtime.

### v2-i02 — `wc` with placeholder path
**Request:**
```json
{
  "task": "Count the number of lines in the log file",
  "intent": "count_lines",
  "inputs": ["file_path"],
  "outputs": ["stdout"],
  "context": { "file_path": "/tmp/os2ie_sandbox/access.log" }
}
```
**Expected:** `status: ok`, script contains `/tmp/os2ie_sandbox/access.log`
**Actual:** `status: ok`
**script_description:** `"Use \`wc -l <file_path\` to count the number of lines in the log file."`
**Problem:** The context value `/tmp/os2ie_sandbox/access.log` was not injected. The
literal string `<file_path` appears instead — malformed and unexecutable.

### v2-i03 — `cp` with placeholder source and destination
**Request:**
```json
{
  "task": "Copy the config file to the backup location",
  "intent": "duplicate_config",
  "inputs": ["source_path", "destination_path"],
  "outputs": ["return_code"],
  "context": {
    "source_path": "/tmp/os2ie_sandbox/config.yaml",
    "destination_path": "/tmp/os2ie_sandbox/backup/config.yaml"
  }
}
```
**Expected:** `status: ok`, script contains both actual paths
**Actual:** `status: ok`
**script_description:** `"Use \`cp source_path destination_path\` to copy the config file from the source location to the backup location."`
**Problem:** Both paths from context were not injected. The placeholders `source_path` and
`destination_path` appear literally — the script cannot execute without substitution.

**Ask:** When `context` provides concrete values for input names, those values **must**
appear verbatim in the `script_description`. The description must be a ready-to-run
command, not a template. If the service cannot substitute context values, return
`not_capable` rather than emitting a placeholder script.

---

## Test suite

Negative seeds (v1): `training/transition2shell_negative_seed.json` (15 seeds)
Negative seeds (v2): `training/transition2shell_negative_seed_v2.json` (11 seeds)
Baseline seeds: `training/transition2shell_seed.json` (20 seeds)
Prompt: `prompts/shell_skill_check.md`

Run against live service to reproduce all issues above.

---

## Roadmap — Two-pass chain of thought

**Target:** Transition2Shell v2

All five issues documented here are structural limitations of the current single-pass
design. The model is asked to simultaneously assess capability, resolve task-vs-intent
conflicts, check constraints, and inject context values — all in one generation step.
Single-pass reasoning cannot reliably do all of these in conflicting situations.

**Planned fix:** A two-pass chain of thought within the same generation:

- **Pass 1 (reasoning):** Explicit scratchpad — capability check, constraint analysis,
  task-vs-intent priority resolution, context value extraction.
- **Pass 2 (output):** Structured JSON response derived from Pass 1 conclusions, not
  from free-association.

The output schema would add a `reasoning` field (stripped by the caller before returning
to the client): `{reasoning: "...", status: ..., script_description: ...}`.

**Scope:** Do not attempt to address Issues 4 or 5 in v1. The prompt cannot compensate
for the architectural gap. Schedule two-pass CoT for the v2 prompt and training cycle.

---

## Pass criteria reminder

| Case | Expected |
|------|----------|
| Task is shell-implementable with a concrete, complete command | `status: ok` + valid `script_description` |
| Intent is vague, empty, or maps to no Unix command | `status: not_capable` |
| Task requires network, DB, GUI, ML, elevated permissions, or atomicity | `status: not_capable` |
| script_description contains placeholders or invented commands | reject — return `not_capable` |
