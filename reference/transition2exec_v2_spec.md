# transition2exec V2 Spec

## Why V2

V1 maps one abstract transition to one executable transition using LLM reasoning.
It works for O(1) tasks on a tight domain. Its known limits:

- Cannot split one abstract transition into multiple tool calls when required
- Cannot join adjacent abstract transitions into a single tool call when appropriate
- Grounding errors when abstract tool semantics are ambiguous (read → exists)
- Output binding gaps — grounded output keys do not always land in state

V2 adds a **mechanics layer** alongside the existing LLM reasoning. Mechanics
are deterministic — tool catalog lookup, compatibility checking, state threading
validation. The LLM still reasons. The mechanics correct what the LLM gets wrong
structurally.

V2 does not replace V1. It wraps it with pre- and post-processing steps that
handle what reasoning alone cannot reliably do.

---

## Responsibility boundary

transition2exec is the only component with access to the tool catalog. It owns:

- **Grounding** — which concrete tool fulfils an abstract transition
- **Split** — one abstract transition → multiple executable transitions
- **Join** — multiple adjacent abstract transitions → fewer executable transitions
- **Output binding** — grounded output keys correctly mapped into state
- **not_mappable** — detection and reporting when no tool can fulfil the abstract

The action splitter and task2plan are tool-unaware. They are not expected to
produce correct decomposition sizes. transition2exec corrects them.

---

## V2 Pipeline

```
abstract_transition(s) + state + tool_catalog
    │
    ▼
1. PRE-ANALYSIS (mechanical)
   - Semantic signal extraction from abstract tool name, inputs, outputs, resource_required
   - Candidate tool set narrowed by signal
   - Adjacency check — can this transition join with the next?
    │
    ▼
2. LLM REASONING (existing V1 two-stage)
   - Stage 1: tool selection + input resolution (plain text)
   - Stage 2: format as executable DSTT JSON
    │
    ▼
3. POST-VALIDATION (mechanical)
   - Output overlap check — grounded tool outputs vs abstract transition outputs
   - If zero overlap → wrong tool detected → retry with narrowed candidate set
   - Split check — does abstract transition require more than one tool call?
   - Join check — can this and the next abstract transition collapse to one?
   - Output binding — ensure grounded output keys are explicitly mapped to state keys
    │
    ▼
executable_transition(s) with validated output binding
```

---

## Mechanics — Split

**Trigger:** Abstract transition implies a multi-step operation that no single
tool in the catalog can fulfil alone.

**Detection:**
- Abstract tool name contains sequential verbs (run + write, create + append)
- OR: abstract outputs require inputs from an intermediate tool not in state
- OR: `resource_required` contains multiple distinct resource types

**Action:**
Decompose into N executable transitions. State threads between them — output
keys of transition K become input keys of transition K+1.

**Example:**
```
abstract: run_shell_command_and_write_stdout_to_file
  → t1: run_shell_command(command=...) → stdout
  → t2: create_file(file_path=..., content=stdout) → success
```

**Contract:** The split produces a self-contained sequence. Each sub-transition
is independently executable. State threading is explicit, not implicit.

---

## Mechanics — Join

**Trigger:** Two adjacent abstract transitions collapse to a single tool call.

**Detection:**
- Adjacent transitions share no output→input dependency (truly independent)
- AND: a single tool in the catalog can produce the combined output set
- OR: the second abstract transition has no tool mapping without context from
  the first — they are semantically one operation

**Action:**
Produce one executable transition that fulfils both abstract transitions.
Both abstract output key sets must be present in the combined grounded outputs.

**Example:**
```
abstract t1: check_if_file_exists
abstract t2: read_file_if_present
  → single: read_file(file_path=...) → text
  (existence check is implicit in read_file failure semantics)
```

**Constraint:** Join is conservative. Only join when the single tool provably
covers the combined abstract output requirements. When in doubt, do not join.

---

## Mechanics — Semantic Grounding Signal

Abstract tool names carry semantic signal that must be respected:

| Signal | Correct grounded tool | Wrong grounded tool |
|--------|-----------------------|---------------------|
| read, contents, text | `read_file` | `exists` |
| delete, remove | `delete_file` | `exists` |
| count, search, filter | `run_shell_command` | `list_directory` |
| exists, present, check | `exists` | `read_file` |
| append | `append_to_file` | `create_file` |

`resource_required` from the abstract DSTT is a mandatory signal:
- `["filesystem"]` → file operation tools
- `["shell"]` → `run_shell_command`
- `["human_input"]` → ambiguity surface, do not ground to a tool

---

## Mechanics — Output Binding

Every executable transition must emit an explicit `output_binding`:

```json
{
  "output_binding": {
    "grounded_key": "abstract_key"
  }
}
```

Rules:
- If grounded key equals abstract key → binding may be omitted (identity)
- If grounded tool produces `stdout` but abstract transition expects `file_count`
  → binding must be explicit: `{ "stdout": "file_count" }`
- Zero-overlap between grounded outputs and abstract outputs → `tool_output_mismatch`,
  do not emit transition, do not dispatch

The executor applies binding after dispatch. Without explicit binding, grounded
output keys land in state under grounded names. Abstract output names — which
the milestone checks — never resolve. Milestones fail silently.

---

## V2 Failure Modes

| Failure | Stage | Status emitted |
|---------|-------|----------------|
| No tool matches abstract semantics | Pre-analysis | `not_mappable` |
| LLM selects tool with zero output overlap | Post-validation | `tool_output_mismatch` |
| Split required but no split path found | Post-validation | `not_mappable` |
| Output binding cannot be established | Post-validation | `binding_error` |
| Abstract transition is underspecified | Pre-analysis | `ambiguous` |

---

## Open Issues from V1 addressed by V2

| V1 Issue | V2 Mechanic |
|----------|-------------|
| ISS-015 — wrong tool for read (read→exists) | Semantic grounding signal table |
| ISS-017 — count/search → list_directory | Semantic grounding signal + resource_required |
| ISS-T2E-001 — return_code absent from state | Output binding mandatory |
| ISS-AT-002 — create+append sequence wrong | Split mechanic |
| ISS-AT-003 — shell stdout not written to file | Split mechanic |
| ISS-AT-004 — mkdir+create_file incomplete | Split mechanic + state threading |

---

## What V2 does not address

- Model reasoning quality — still bounded by small LLM capability
- Tasks outside the tool catalog — `not_mappable` is the correct response
- Ambiguous tasks — surface to caller, do not guess
- Retry/repair — owned by the DSTT runtime, not transition2exec

---

## Implementation notes

The mechanics layer is **not an LLM call**. It is Python code operating on
the tool catalog as a data structure. It runs before and after the existing
V1 LLM pipeline. The LLM call is unchanged.

The split/join logic requires the full sequence of abstract transitions for
the current segment — not just the current one. transition2exec V2 must
receive the segment's transition list, not a single transition in isolation.

This is a **contract change** from V1. The caller (taskexecutor kernel) must
pass the full segment transition list. transition2exec returns the full
executable transition list for the segment.

---

## Control signals — pass-through responsibility

transition2exec does not own `ambiguous`, `getOrAskContextAndConstraints`,
or `task2Plan`. These are signals produced by task2plan and passed through
transition2exec to the executor.

When transition2exec receives an abstract transition that carries one of these
signals, it must pass it back to the executor without attempting to ground it
as a tool call:

| Signal received | transition2exec action |
|-----------------|----------------------|
| `getOrAskContextAndConstraints` | Return as-is with `status=suspended`. Do not ground. |
| `task2Plan` | Return as-is with `status=subtask`. Do not ground. |
| `ambiguous` (meta status) | Return `status=ambiguous` with the embedded question. |

These are **executor control signals**. The executor interprets them and acts.
transition2exec is the messenger, not the handler.

**Validation requirement:** transition2exec must not emit these signals
autonomously. It only passes them through when task2plan explicitly produced
them. Generating them as a fallback for unmappable transitions is incorrect —
`not_mappable` is the right status for that case.
