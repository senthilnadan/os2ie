# Input Resolution Rule for transition2exec

## The Problem

After several transitions, state accumulates keys from every previous step. Without a clear rule, even a careful reader (human or model) may pick the wrong key — because multiple keys look plausible for the same input.

This is not a model gap. It is an inherent ambiguity that requires an explicit rule.

---

## The Rule

> **Use only the keys declared in `abstract_transition.inputs` to look up values in state.**
> All other state keys are residue from prior transitions and must be ignored.

If a declared input key is present in state → use its value directly.

If a declared input key is absent from state → find the state key whose name best matches the declared name (semantic proximity). Never guess from the full state freely.

---

## Example 1 — State Pollution

**Scenario:** T1 copied a file (added `source_path`, `destination_path`, `copied` to state). T2 must now read the copied file.

**State at T2 compile time:**
```json
{
  "source_path": "/tmp/workspace/main.py",
  "destination_path": "/tmp/copy/main.py",
  "copied": true
}
```

**Abstract transition T2:**
```json
{ "tool": "read_workspace_source", "inputs": ["destination_path"], "outputs": ["text"] }
```

**Wrong (free-range over state):** model sees `source_path` and `destination_path`, picks `source_path` because it appeared earlier or "looks like the source."

**Correct:** `destination_path` is the declared input → `file_path = "/tmp/copy/main.py"`.

---

## Example 2 — Name Mismatch

**Scenario:** State has two path-like keys. The abstract input name does not match either exactly.

**State at T3 compile time:**
```json
{
  "source_path": "/tmp/today.log",
  "archive_path": "/tmp/archive.log",
  "text": "<log content>",
  "success": true
}
```

**Abstract transition T3:**
```json
{ "tool": "verify_archive", "inputs": ["archive_path"], "outputs": ["is_present"] }
```

**Wrong:** model picks `source_path` because it appeared earlier in the task description.

**Correct:** `archive_path` is the declared input → `file_path = "/tmp/archive.log"`.

---

## Summary

| Situation | Rule |
|-----------|------|
| Declared input key is in state | Use it directly |
| Declared input key is absent, one semantically close key exists | Use the closest match |
| Multiple plausible keys exist | Declared name wins — do not guess |
| Key is residue from a prior transition | Ignore it unless declared |
