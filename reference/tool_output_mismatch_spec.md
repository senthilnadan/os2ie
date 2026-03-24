# tool_output_mismatch — Detection Spec

**Context:** transition2exec ISS-015 asks the executor to detect, before dispatching a tool, whether the grounded tool is categorically incapable of producing the outputs required by the abstract transition.

---

## What we have at check time

After transition2exec compiles a grounded transition, the executor holds:

```
abstract_transition.outputs   → ["file_contents"]          # what the planner expects this step to produce
grounded.tool                 → "create_file"               # what transition2exec selected
grounded.outputs              → {"success": null}           # what the grounded tool actually produces (from catalog)
```

The catalog has type info for every output:

| Tool                    | Outputs                                        | Output class   |
|-------------------------|------------------------------------------------|----------------|
| exists                  | is_present: bool                               | operational    |
| read_file               | text: str                                      | data           |
| create_file             | success: bool                                  | operational    |
| append_to_file          | success: bool                                  | operational    |
| delete_file             | deleted: bool                                  | operational    |
| copy_file               | copied: bool                                   | operational    |
| move_file               | moved: bool                                    | operational    |
| make_directory          | created: bool                                  | operational    |
| remove_directory        | removed: bool                                  | operational    |
| list_directory          | entries: list[str]                             | data           |
| list_directory_recursive| entries: list[str]                             | data           |
| run_shell_command       | stdout: str, stderr: str, return_code: int     | data + status  |

---

## Two distinct failure modes

### Mode 1 — Genuine wrong tool (ISS-015)
The grounded tool is categorically incapable of producing the data the abstract transition needs.

```
abstract outputs:  ["file_contents"]       ← needs text data
grounded tool:     create_file             ← produces only {success: bool}
```

`create_file` can succeed and return `{success: True}` — but `file_contents` will never be in state. The next transition fails silently or on a missing key. This is a genuine mismatch and should be caught pre-dispatch.


## Architects Comments. 
    the success or failure is not determined by the output match or mismatch.  but but the subsequent segmentt hat needs it.
    in this case the tool creates a file in the system. ithe file is avaialble in the resources.  as a side effect rool returns a success or failure.  It would be good for a reason to determine if it good to proceed to the next step. keeping detailed dscription of this one teel in mind and the output status expected.  It is the subsequent transitions that determine what happens.

### Mode 2 — Valid alternative grounding (ISS-017)
The grounded tool is semantically valid but uses different output key names.

```
abstract outputs:  ["python_file_count"]   ← needs a count value
grounded tool:     list_directory_recursive← produces {entries: list[str]}
```

`entries` is not `python_file_count` but the data is there — the next step can count `len(entries)`. This is a grounding variant, not a failure. The executor merges `entries` into state and the runtime can decide what to do with it.

**The check must distinguish these two modes.** A simple key-name overlap check fails mode 2 (flags it as a mismatch when it is not).


## Architects Comments. 
    the success or failure is not determined by the output match or mismatch.  but but the subsequent segmentt hat needs it.
   we have a list but we dont know the count.  we need to derive the count from the content.  the question is is it a reason task .  it would be.  but it might result one having a tool that takes the list and count the files.  if such tools is availble.. it would mean we discover and use it. Ideally such reason call should have some patching tools avaialble. so it gets executed to resolve

---



## Detection approaches

### Option A — Output type class check (algorithmic)

Classify each tool's outputs as either **operational** (bool only) or **data** (str, int, list).

If the grounded tool produces only operational outputs but the abstract transition declares outputs with names that imply data (non-operational purpose), flag as `tool_output_mismatch`.

```
grounded outputs all bool  +  abstract output name not a pure status check  →  mismatch
```

Examples:
- `create_file` → `{success: bool}` only. Abstract needs `file_contents`. → mismatch ✓
- `list_directory_recursive` → `{entries: list[str]}`. Abstract needs `python_file_count`. → no mismatch ✓

**Tradeoffs:**
- Fully deterministic, no LLM call, no latency
- Fragile: depends on type annotations in catalog (ISS-005 still open on transition2exec side)
- Does not catch: wrong data-producing tool selected (e.g., `read_file` selected for a write step — both produce data but different kinds)
- Simple to implement; aligns with catalog already having type info

---

### Option B — Required output key name pattern match (algorithmic)

Check if the grounded tool's output key names share any token with the abstract transition's output names.

```
abstract outputs:  ["file_contents"]
grounded outputs:  ["success"]
→ "file" not in "success", "contents" not in "success" → mismatch
```

```
abstract outputs:  ["python_file_count"]
grounded outputs:  ["entries"]
→ "entries" is neutral → no match, but also no type conflict → allow
```

**Tradeoffs:**
- Fragile on naming conventions — relies on abstract names being descriptive
- Token matching is heuristic, not reliable
- ISS-015 would be caught (success ≠ file_contents)
- ISS-017 unclear — depends on whether "entries" and "python_file_count" share tokens (they don't, but the check should allow it)

---

### Option C — LLM binary check

A small LLM call: *"Can tool X (which produces outputs Y) satisfy the requirement for abstract output Z?"*

```
Can create_file (outputs: {success: bool}) satisfy the requirement for file_contents? → no
Can list_directory_recursive (outputs: {entries: list[str]}) satisfy the requirement for python_file_count? → yes (data is there, count is derivable)
```

**Tradeoffs:**
- Most accurate — handles semantic variants naturally
- Adds latency (one extra LLM call per transition with a mismatch risk)
- Adds LLM dependency to a step that is currently deterministic
- The executor is designed to be mechanical — an LLM call here breaks that principle
- Only needed when there is genuine ambiguity — most transitions have no mismatch

---

### Option D — Post-dispatch detection (fail on missing output)

Do not check pre-dispatch. Run the tool. After merging outputs into state, check whether the milestone keys declared in the abstract transition are now reachable.

If the grounded tool's outputs add nothing relevant to what the next segment's milestone needs → fail with `missing_output_for_milestone`.

**Tradeoffs:**
- Simplest kernel change — milestone check is already there
- ISS-015: `create_file` runs, writes an empty file, returns `{success: True}`. State has `success: True` but not `file_contents`. Milestone fails. Error is traceable.
- The tool runs even when it shouldn't — side effects happen (file is created when the intent was to read)
- Side-effect problem makes this worse than pre-dispatch for write operations

---

### Architects Comment. 

 - Post distpatch check happens during failure deduction.  but lets assume this executes in sandbox and we are user is immune to actual harm. 

## Recommendation — decision needed

The two realistic options:

| | Option A (type class, pre-dispatch) | Option D (post-dispatch, milestone) |
|---|---|---|
| Side effects prevented | Yes | No |
| Handles ISS-015 | Yes | Yes (after the fact) |
| Handles ISS-017 (no false positive) | Yes (data types pass) | Yes |
| LLM required | No | No |
| Catalog type dependency | Yes (ISS-005 risk) | No |
| Kernel complexity | Low (one if-block) | Already exists, just stricter |

**Open question:** Is preventing side effects (pre-dispatch) worth the catalog type dependency?

If ISS-005 (type info) is considered reliable enough now (our catalog already has type fields), Option A is the right call — it's fast, deterministic, and prevents bad writes.

If catalog types are considered unreliable, Option D is the safe fallback — it catches the error without depending on type annotations, at the cost of running the wrong tool once.

---

## Placement in the execution loop

Pre-dispatch check would sit here in `kernel.py`:

```python
# 2. For each grounded transition: PATCH → DISPATCH → MERGE
for grounded in exec_dstt.segments[0].transitions:
    state.update(grounded.inputs)

    tool_fn = TOOL_REGISTRY.get(grounded.tool)
    if tool_fn is None:
        return _fail(..., f"tool not found: {grounded.tool}")

    # ← tool_output_mismatch check here, before tool_fn(state)

    try:
        outputs = tool_fn(state)
    ...
```

The check has access to:
- `abstract_transition.outputs` — what the planner declared this step produces
- `grounded.outputs` — output keys and (via catalog lookup) their types
- No state, no LLM — purely structural


### Architects commends 

Abstract tools ouput can be infered as a collective goal of the transiton not just one transiton. 
Transition2Exec just provideds a DSST if it misses a step that doesnt meet the abstract output that must be flagged as a problem. 
but the sequence of transitions must lead to abstract outcome , else the abstract plan is wrong.  it hast to be healed. but a debugger outsdie. 