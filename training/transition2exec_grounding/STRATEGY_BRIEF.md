# transition2exec — Strategy Brief

## Context

The OS2I taskexecutor is being benchmarked against a DSTT reasoning challenge
(15 tasks, L1–L6 complexity). To pass this benchmark on small models (3B–7B),
transition2exec needs to support multiple grounding strategies that can be
selected per model or per task type.

---

## Current State

transition2exec uses a single implicit strategy: match available inputs first,
then check outputs. This works well for simple tasks but breaks down when:

- Multiple tools share the same input signature (`file_path` → read_file,
  exists, delete_file, append_to_file all match)
- State has accumulated residue keys from prior transitions
- Abstract output name differs from tool output name

---

## Requested Changes

### 1. Add `output_first` grounding strategy

Implement a second named strategy alongside the existing one:

| Strategy | Selection logic |
|----------|----------------|
| `input_first` | match inputs → filter by outputs (current, keep as default) |
| `output_first` | match required abstract outputs → confirm inputs are satisfiable |

**Why:** abstract output `text` uniquely identifies `read_file`. Abstract output
`is_present` uniquely identifies `exists`. Output-first eliminates ambiguity
that input-first cannot resolve on small models.

**API change:** add optional `strategy` field to the request:

```json
{
  "task": "...",
  "context": { ... },
  "abstract_transition": { ... },
  "available_tools": [ ... ],
  "strategy": "output_first"
}
```

Default to `input_first` if omitted — fully backwards compatible.

---

### 2. Make `output_binding` mandatory in every response

Currently `output_binding` is omitted when tool output key matches abstract
output key by name. This causes silent failures when the kernel cannot
distinguish a correct match from a forgotten binding.

**Change:** always emit `output_binding` in every grounded transition, even
when keys match:

```json
"output_binding": {
  "text": "text"
}
```

This forces the model to reason about every output explicitly and removes
the majority of silent latch failures downstream.

---

### 3. Input resolution anchor rule

When state has multiple candidate keys, resolve inputs by anchoring on the
declared abstract input name — not by free-ranging over all state keys.
Residue keys from prior transitions must be ignored.

Full specification and examples:
`training/transition2exec_grounding/INPUT_RESOLUTION_RULE.md`

---

## Evaluation Plan

Once `output_first` is available, we will run the DSTT challenge task suite
under both strategies and compare:

- Correct tool selection rate
- Latch failure rate
- End-to-end task completion rate per challenge level (L1–L6)

This gives a direct, quantified comparison. The task suite is already
instrumented and ready to run.

---

## Priority

| Change | Impact | Effort | Priority |
|--------|--------|--------|----------|
| `output_first` strategy | eliminates wrong tool substitution | medium | P1 |
| mandatory `output_binding` | removes silent latch failures | low | P2 |
| input resolution anchor | fixes state pollution / name mismatch | low | P3 |
