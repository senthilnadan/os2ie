# OS2I Architecture — Structured Agent on Small LLMs

## 1. Vision

Most agent frameworks assume a large model that can plan, reason, and act in a
single context window. OS2I takes the opposite approach — break the agent loop
into small, focused steps, each handled by a separate LLM call or a deterministic
executor. Any model that can solve one focused problem at a time can run this
system.

The result is a structured ReAct loop where:

- **Thought** is externalised as an Abstract DSTT (a plan)
- **Action** is compiled into a grounded tool call by a small LLM
- **Observation** is executed deterministically and merged into state
- **State** is the only memory — explicit, inspectable, passed between services

No single model sees the whole task. Each service sees exactly what it needs.


## 2. System Overview

```
User / Caller
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│  DSTT Runtime                                                │
│                                                              │
│  owns: dstt object, execution context, runtime state        │
│                                                              │
│  ┌─────────────┐   abstract_dstt   ┌──────────────────────┐ │
│  │  task2plan  │ ────────────────► │    taskexecutor      │ │
│  │             │                   │                      │ │
│  │  task →     │                   │  purely mechanical:  │ │
│  │  abstract   │                   │  compile → patch     │ │
│  │  DSTT       │                   │  → dispatch → merge  │ │
│  └─────────────┘                   │                      │ │
│         ▲                          │  calls transition2   │ │
│         │                          │  exec per transition │ │
│  ambiguity                         └──────────────────────┘ │
│  resolver                                    │               │
│         │                             ExecutionResult        │
│         │                          (state, log, segments,    │
│         │                           failed transition+error) │
│         │                                    │               │
│         └──── ambiguous ◄──────── status? ───┤               │
│                                              │               │
│              repair service ◄──── failed ───┘               │
│              (uses dstt ref +                                │
│               execution log                                  │
│               to patch & retry)                              │
└──────────────────────────────────────────────────────────────┘
```

### Services

| Service            | Port | Responsibility                                                       |
|--------------------|------|----------------------------------------------------------------------|
| action splitter    | TBD  | Task → ordered atomic actions (rough decomposition, no tool awareness)|
| task2plan          | 8000 | Atomic action → Abstract DSTT transition (LLM, no tool awareness)   |
| transition2exec    | 8001 | Abstract transition → Executable transition(s) — owns split/join     |
| taskexecutor       | 8002 | Execute DSTT mechanically — compile, dispatch, merge, report result  |
| ambiguity resolver | TBD  | Owned by DSTT runtime — resolves task2plan ambiguous status          |
| repair service     | TBD  | Owned by DSTT runtime — uses execution log + DSTT ref to patch/retry |

**taskexecutor scope:** execute one DSTT run, return `ExecutionResult`. No knowledge of retry, repair, or the DSTT runtime object.

**DSTT runtime scope:** owns the DSTT object and runtime context. Passes them to the executor. Handles the result — invokes repair on failure, ambiguity resolver on ambiguous, or returns to caller on completion.

**transition2exec owns split/join:** The action splitter and task2plan have no
tool awareness — they cannot know whether an abstract action maps to one tool,
requires splitting into multiple tool calls, or can be joined with an adjacent
action. transition2exec is the only component that sees the tool catalog. It
holds the responsibility for:
- **Split** — one abstract transition → multiple executable transitions, when
  a single abstract action requires more than one tool call to fulfil.
- **Join** — multiple abstract transitions → fewer executable transitions, when
  adjacent actions collapse to a single tool call.
- **not_mappable** — no tool in the catalog can fulfil the abstract transition.

This means the action splitter's decomposition size does not need to be correct
— only roughly bounded. transition2exec corrects it. The splitter's only
requirement is to avoid merging clearly independent actions.

### Data flow

```
task + context
    → task2plan
    → abstract_dstt

abstract_dstt + state
    → taskexecutor
    → for each abstract_transition:
          abstract_transition + state → transition2exec → executable_transition
          executable_transition.inputs → state (patch)
          tool(state) → outputs → state (merge)
    → completed state + execution log
```


## 3. Core Concepts

### Abstract DSTT
A plan expressed as abstract tool names and key names — no concrete values,
no grounded tool calls. Produced by task2plan. Describes *what* to do.

```json
{
  "segments": [{
    "transitions": [{
      "id": "t1",
      "tool": "check_python_file_existence",
      "inputs": ["project_folder_path"],
      "outputs": ["python_file_exists"]
    }],
    "milestone": ["python_file_exists"]
  }]
}
```

### Executable DSTT
A grounded plan with concrete tool names, concrete input values, and null
output slots. Produced by transition2exec. Describes *how* to do it.

```json
{
  "status": "ok",
  "segments": [{
    "transitions": [{
      "id": "t1",
      "tool": "exists",
      "inputs": {"file_path": "/path/to/hello.py"},
      "outputs": {"is_present": null}
    }],
    "milestone": ["is_present"]
  }]
}
```

### State
A flat key-value dict — the single source of truth for all inputs and outputs.

- Initialised from the caller's context (runtime facts)
- transition2exec contributes resolved concrete values (inputs patch)
- Tools read from state and write back to state
- Grows cumulatively — nothing is removed during execution
- Passed as `context` to transition2exec on every call

### Segment / Transition / Milestone
- **Transition** — one unit of work: one abstract tool → one or more grounded tools
- **Segment** — a group of transitions that together achieve a milestone
- **Milestone** — the set of output keys that must be in state before the next
  segment begins. Acts as a checkpoint gate.

### TransitionRecord
The evidentiary unit of execution. One record is produced per transition,
capturing the complete epistemic state of the system at the moment of decision
and the full chain of what happened as a result.

A `TransitionRecord` is not a log entry. It is a self-contained artifact —
sufficient to reconstruct exactly what the system knew, what it was asked to do,
what it decided, and what changed, without reference to any other record.

```json
{
  "transition_id": "t1",
  "timestamp": "2026-03-22T10:04:00Z",

  "state_snapshot":        { "...full state before this transition..." },
  "abstract_transition":   { "tool": "check_python_file_existence", "..." },

  "prompt_sent":           "...exact prompt text sent to the model, verbatim...",
  "model_raw_output":      "...raw LLM response before any parsing...",
  "executable_transition": { "tool": "exists", "inputs": {"file_path": "..."}, "..." },

  "tool_name":    "exists",
  "tool_inputs":  { "file_path": "/path/to/hello.py" },
  "tool_outputs": { "is_present": true },
  "state_delta":  { "is_present": true },

  "status":         "completed",
  "failure_reason": null
}
```

`failure_reason` is populated when `status` is `failed`, naming the stage
(`compile`, `parse`, `dispatch`, `tool`) and the error.

The `ExecutionResult` contains the full list of `TransitionRecord`s as its
primary artifact. Final state is derivable from them — it is included for
convenience, not as the source of truth.

### Tool Registry
Tools are injected into the taskexecutor kernel at startup. The kernel dispatches
by name only — it has no knowledge of what any tool does. This is the primary
extension point for adding new capabilities.

### Tool Adapters

Every tool is wrapped by an adapter before registration. The adapter owns the
execution lifecycle — pre-flight, dispatch, verification, and healing. The kernel
always calls the adapter, never the tool directly.

**General adapter** — for idempotent tools (read, exists, list, copy, move):
- Pre-flight: validate inputs are present and correctly typed
- Dispatch: call tool
- On failure: safe to retry with corrected inputs, no side effects to undo

**Special adapter** — for non-idempotent write tools (`create_file`, `append_to_file`):
- Pre-flight: validate inputs (content non-empty, newline handling explicit, path writable)
- Snapshot: read current file state before executing (rollback point stored in state)
- Dispatch: call tool
- Post-write verification: read back and compare against expected content
- On mismatch: rollback from snapshot, surface as failure with corrected inputs
- Rollback:
  - `create_file` → restore previous content or delete if file was new
  - `append_to_file` → truncate back to pre-append size using snapshot

The special adapter makes write tools safe to reason about and retry — the healing
path provides corrected inputs, the adapter handles the side effect lifecycle.
The kernel has no knowledge of adapter type; dispatch is uniform by tool name.

### Subtask
A tool in the registry that spawns a new kernel instance for a sub-problem.
Takes `task`, `context`, and `parent_task` as inputs. Before executing, it checks
that the subtask is a genuine reduction of the parent (LLM binary check). If not,
it fails immediately. The parent kernel blocks until the subtask completes.


## 4. Service Contracts

### task2plan
```
POST /task2plan
{
  "task": "string"
}

→ {
  "abstract_dstt": { segments: [...] },
  "meta": { "status": "ok|ambiguous|low_confidence", ... }
}
```

### transition2exec
```
POST /transition2exec
{
  "task": "string",
  "context": { ...state... },
  "abstract_transition": { id, tool, inputs, outputs, ... },
  "available_tools": [ ...grounded tool catalog... ]  // optional
}

→ {
  "executable_dstt": { status, segments: [...] },
  "meta": { "status": "ok|error", "model": "...", ... }
}
```

### taskexecutor
```
POST /taskexec
{
  "task": "string",
  "parent_task": null,          // null for top-level, set for subtask calls
  "state": { ...context... },
  "abstract_dstt": { segments: [...] }
}

→ {
  "status": "completed|failed",
  "state": { ...final state... },
  "transition_records": [
    {
      "transition_id", "timestamp",
      "state_snapshot", "abstract_transition",
      "prompt_sent", "model_raw_output", "executable_transition",
      "tool_name", "tool_inputs", "tool_outputs", "state_delta",
      "status", "failure_reason"
    }
  ],
  "segments_completed": 1,
  "milestone_reached": ["key1", "key2"]
}
```


## 5. Execution Flow

End-to-end trace for: *"Check whether hello.py exists in the project folder."*

```
1. Caller → POST /task2plan
   { "task": "Check whether hello.py exists in the project folder." }

   ← abstract_dstt:
     segment[0] → t1: check_python_file_existence
                  inputs: [project_folder_path]
                  outputs: [python_file_exists]

2. Caller → POST /taskexec
   {
     "task": "Check whether hello.py exists...",
     "state": { "project_folder_path": "/path/project", "target_file": "hello.py" },
     "abstract_dstt": { ...from step 1... }
   }

3. taskexecutor kernel → POST /transition2exec
   {
     "task": "Check whether hello.py exists...",
     "context": { "project_folder_path": "/path/project", "target_file": "hello.py" },
     "abstract_transition": { "tool": "check_python_file_existence", ... }
   }

   ← executable_dstt:
     t1: exists  inputs: { "file_path": "/path/project/hello.py" }
                 outputs: { "is_present": null }

4. kernel patches state:
   state["file_path"] = "/path/project/hello.py"

5. kernel dispatches: exists(state)
   → reads state["file_path"]
   → Path("/path/project/hello.py").exists() → True
   → returns { "is_present": True }

6. kernel merges:
   state["is_present"] = True

7. milestone ["python_file_exists"] resolved via "is_present" in state → reached

8. ← taskexec response:
   {
     "status": "completed",
     "state": { ..., "is_present": true },
     "execution_log": [{ "tool": "exists", "outputs": {"is_present": true}, "status": "ok" }],
     "milestone_reached": ["is_present"]
   }
```


## 6. Design Principles

**One LLM call per step, small and focused**
Each LLM call solves one narrow problem: map one abstract tool to one grounded
tool. The model never sees the full task history, only the current transition
and the current state.

**Hard failures, no silent fallbacks**
If a transition cannot be mapped or a tool fails, execution stops immediately.
The caller sees the exact failure point and the state at that point. Nothing
is swallowed silently.

**State over context window**
State is the agent's memory. It is explicit, serialisable, and passed between
services as a plain dict. No model holds memory between calls.

**DSTT as working memory**
The abstract DSTT is the plan. The executable DSTT is the compiled plan. Both
are data — inspectable, loggable, replayable.

**Tools are the extension point**
The kernel has no built-in capabilities. Everything it can do comes from the
tool registry. Adding a new capability means adding a tool — no kernel changes.

**Subtask = recursive agent, not special case**
A subtask is just another tool. The kernel does not know it spawns a new agent.
The reduction check (is this task scoped inside the parent?) prevents infinite
loops without a depth counter.

**Tool awareness belongs to transition2exec, nowhere else**
The action splitter and task2plan are deliberately tool-unaware. They describe
what to do, not how. Split/join decisions require knowing what tools exist and
what they can do — that knowledge lives only in transition2exec. Pushing split/join
decisions upstream (into the splitter or planner) produces brittle, tool-coupled
planning. transition2exec corrects the decomposition using mechanics — tool catalog
lookup, compatibility checking — alongside LLM reasoning. This is an intentional
architectural boundary, not a convenience.

**Evidentiary record, not logging**
The `TransitionRecord` is a first-class output of execution — not an afterthought.
The prompt sent to the model, the raw model output, the state at decision time,
and the state delta are captured as named artifacts at the moment they occur.
The record must be sufficient to answer: *what did the system know, what was it
asked, what did it decide, and what changed* — without needing anything else.
This is what makes failure diagnosis and auditing possible without re-running.


## 7. What This Is Not

- **Not a full agent framework** — no memory management, no prompt chaining,
  no agent personas. One loop, one state bag.
- **Not multi-model orchestration** — all LLM calls use the same model config.
  Different models per service are possible but not the design goal.
- **Not parallel** — execution is strictly sequential within a segment.
  Segments are also sequential.
- **Not LangChain / AutoGen / CrewAI** — no agent abstractions, no prompt
  templates beyond the two in `prompts/`. Just FastAPI, Pydantic, DSPy, and
  stdlib.


## 8. Reference Implementation

The reference implementation lives in this repository under `src/`.

### Stack

| Concern         | Library              | Why                                      |
|-----------------|----------------------|------------------------------------------|
| HTTP service    | FastAPI              | Lightweight, Pydantic-native             |
| Data models     | Pydantic v2          | Validation, serialisation, no boilerplate|
| LLM calls       | DSPy + Ollama        | Local model support, simple LM interface |
| Execution       | pathlib, subprocess  | stdlib — no extra dependencies           |
| Config          | pydantic-settings    | Env var loading, `.env` support          |

### Layout

```
src/
  transition2exec/
    api/
      app.py          FastAPI app, /transition2exec endpoint
      models.py       Request/response models
    transition/
      dspy_module.py  Two-stage LLM pipeline (tool_sequence → dstt_format)
      providers.py    Backend wiring (qwen / stub)
      mapping.py      resolve_input, default_output_value
    tool_catalog.py   Grounded tool definitions (name, inputs, outputs)
    validation.py     Executable DSTT validation
    service.py        Orchestrates backend + validation
    config.py         Settings from env

prompts/
  tool_sequence.md    Stage 1 prompt — abstract tool → grounded tool plan
  dstt_format.md      Stage 2 prompt — plan → executable DSTT JSON
```

### Two-stage LLM pipeline (transition2exec)

```python
# Stage 1 — resolve abstract tool to grounded tool(s), plain text
stage1 = lm(tool_sequence_prompt(task, abstract_tool, context, tool_list))
# → "TOOL: exists\nINPUTS: file_path=/path/hello.py"

# Stage 2 — format as executable DSTT JSON
resolved = extract_resolved_tools(stage1, available_tools, state)
stage2 = lm(dstt_format_prompt(stage1, resolved))
# → {"status":"ok","segments":[{"transitions":[...],"milestone":[...]}]}
```

Stage 1 keeps the LLM output simple (plain text).
Stage 2 constrains it with a pre-resolved tool schema so the model cannot
hallucinate tool names or input keys.

### Tool dispatch (taskexecutor)

```python
TOOL_REGISTRY = {
    "exists":                   lambda state: {"is_present": Path(state["file_path"]).exists()},
    "read_file":                lambda state: {"text": Path(state["file_path"]).read_text()},
    "create_file":              lambda state: Path(state["file_path"]).write_text(state["content"]) or {"success": True},
    "run_shell_command":        lambda state: subprocess.run(state["command"], shell=True, ...),
    "subtask":                  lambda state: run_subtask(state["task"], state["context"], state["parent_task"]),
    # ...
}

def dispatch(tool_name, state):
    fn = TOOL_REGISTRY[tool_name]
    return fn(state)
```

### Subtask tool

```python
def run_subtask(task, context, parent_task):
    # 1. Check reduction
    if not is_subtask_of(task, parent_task):   # binary LLM call
        raise ValueError("subtask does not reduce parent task")

    # 2. Plan
    abstract_dstt = call_task2plan(task, context)

    # 3. Execute in new kernel instance
    return call_taskexec(task, context, abstract_dstt, parent_task=parent_task)
```


### DSTT Handler — Transition Failure Recovery

Transition failures are owned by the DSTT handler (runtime level), not the
executor and not the segment healer. The executor returns the failure signal;
the DSTT handler decides the recovery strategy.

**Two entry points, two cascades:**

**A. No executable transition found (`not_mappable`):**
```
not_mappable
  │
  ├─ 1. Shell fallback
  │       add run_shell_command to available_tools
  │       retry transition2exec with task + state
  │       if ok → hand back to executor, continue
  │       if fails → next
  │
  ├─ 2. Other healing options
  │       (domain-specific tools, alternate catalog, alternate model)
  │       if ok → hand back to executor, continue
  │       if fails → next
  │
  └─ 3. Escalate up the stack
            surface to caller with full context
            caller decides: provide missing context, delegate, or abort
            execution suspended until caller responds
```

**B. Transition found but tool failed (tool error):**
```
tool error
  │
  ├─ 1. Reasoning repair             (idempotent tools only)
  │       re-run transition2exec with error as additional context
  │       "previous attempt: tool=X inputs=Y error=Z"
  │       model corrects tool selection or inputs
  │       retry dispatch via executor
  │       if fails → next
  │
  ├─ 2. Shell fallback
  │       add run_shell_command to available_tools
  │       retry transition2exec with task + state + error context
  │       hand back to executor to dispatch
  │       if fails → next
  │
  └─ 3. Escalate up the stack
            surface to caller with full context
            caller decides: provide missing context, delegate, or abort
            execution suspended until caller responds
```

**Precondition for write tools:** strategies 1 and 2 in cascade B are only
available if the special adapter confirms rollback succeeded. If rollback
failed, skip directly to escalation.

**State machine extension:**
```
running → not_mappable  → dstt_handler → shell_fallback    → running
                                       → other_healing      → running
                                       → escalated          → resumed  → running
                                                            → aborted  → failed

running → tool_error    → dstt_handler → reasoning_repair  → running
                                       → shell_fallback     → running
                                       → escalated          → resumed  → running
                                                            → aborted  → failed

running → zero_segments → dstt_handler → escalated         → resumed  → running
                                                            → aborted  → failed
```

The DSTT handler owns all failure modes — transition `not_mappable`, tool
errors, and zero-segment scenarios. There is no separate segment healer.
All recovery paths flow through the DSTT handler. Escalation is the terminal
in every case — the caller decides to resume or abort.

---

## 9. V2 Scope — Generation 2 Capabilities

Each service has a defined V2 scope. V1 remains the current implementation.
V2 capabilities are additive — they extend V1 without replacing it.

### taskexecutor V2 — Control signal handling

V1 execution loop: `running → completed | failed`

V2 adds three control signals from transition2exec and task2plan that the
executor must recognise and act on:

| Signal | Source | Executor action |
|--------|--------|-----------------|
| `ambiguous` | task2plan / transition2exec | Suspend. Return `status=ambiguous` to DSTT runtime with question and state snapshot. Resume on context receipt. |
| `getOrAskContextAndConstraints` | task2plan (abstract transition) | Pause at transition. Surface question to caller. Patch state with answer. Resume from paused transition. |
| `task2Plan` | task2plan (abstract transition) | Spawn child kernel as subtask. Block until child completes. Merge child state. Continue. |

V2 execution state machine:
```
running → ambiguous → suspended → resumed → running
running → getOrAsk  → suspended → resumed → running
running → task2Plan → subtask   → merged  → running
running → completed
running → failed
```

These are control signals, not failures. The executor must not treat them as
`status=failed`. Each has a defined resolution path.

---

### transition2exec V2 — Split/Join mechanics

V1: one abstract transition → one executable transition (LLM only)

V2 adds a mechanics layer (Python, not LLM) that runs before and after V1:

- **Pre-analysis** — semantic signal extraction, candidate tool narrowing,
  adjacency check for join opportunities
- **Post-validation** — output overlap check, split detection, output binding
  enforcement, `tool_output_mismatch` detection

**Split:** one abstract transition → multiple executable transitions when no
single tool can fulfil the abstract action alone.

**Join:** multiple adjacent abstract transitions → fewer executable transitions
when they collapse to a single tool call.

**Contract change from V1:** V2 receives the full segment transition list,
not one transition at a time. Split/join decisions require adjacency context.
The kernel must pass the segment, not individual transitions.

---

### task2plan V2 — Structured signal emission

V1: produces abstract DSTT transitions with abstract tool names.

V2 formalises three signal types the executor depends on:

| Signal | When to emit | Executor response |
|--------|-------------|-------------------|
| `ambiguous` (meta status) | Task is underspecified — cannot plan without clarification | Executor suspends, surfaces to caller |
| `getOrAskContextAndConstraints` (abstract tool) | Specific input value needed, not in state or task | Executor pauses, requests value, resumes |
| `task2Plan` (abstract tool) | Sub-problem requires its own planning cycle | Executor spawns child kernel |

**Validation requirement:** These signals must only fire on genuinely
ambiguous or recursive tasks. False positives — triggering on clear,
well-specified tasks — are a correctness failure. The signal must be
warranted by the task, not used as a default fallback.

---

---

### transition2exec v1.1 — Programmatic Transition Construction

**Problem with v1.0:** The two-stage LLM pipeline (tool_sequence → dstt_format) asks the
model to resolve concrete values from state AND format them as JSON. Small models (3b/7b)
consistently corrupt values — substituting output key names, paraphrasing paths, or echoing
key names as values. Value copying is not an LLM task.

**New internal pipeline:**
```
Stage 1  (LLM)      — tool selection + key binding only
Stage 1.5 (program) — value resolution + transition construction
Stage 2  (LLM)      — eliminated
```

**Stage 1 output (plain text):**
```
TOOL: list_directory
BIND: directory_path ← folder
```

The LLM declares which state key maps to each tool input key. It never sees or copies
concrete values — only key names and semantics.

**Stage 1.5 resolution algorithm:**
```
tool = lookup(tool_name, available_tools)

# Input resolution — input signature only, output signature never in scope
for input_key in tool.input_signature:
    bind_key = BIND.get(input_key, input_key)

    if bind_key in state:
        inputs[input_key] = state[bind_key]       # exact copy, no paraphrase
    elif input_key in state:
        inputs[input_key] = state[input_key]      # direct match
    else:
        result = extract_from_task(input_key, task)
        if result is None or result == "" or result == input_key:
            mark ambiguous                         # key echo = not found
        else:
            inputs[input_key] = result

# Output binding — output signature only, input signature never in scope
for output_key in tool.output_signature:
    outputs[output_key] = null

# Construct transition — no LLM involved
transition = ExecutableTransition(id, tool, inputs, outputs)
segment    = ExecutableSegment([transition], milestone=tool.output_signature.keys)
```

**Key invariant:** input resolution and output binding operate on strictly separate
namespaces. Confusion between the two is structurally impossible.

**extract_from_task null contract:**
`extract_from_task` must return `None` when the LLM returns an empty string, null,
or a value identical to the input key name (key echo). The caller treats `None` as
"nothing found" and marks the transition ambiguous. The extract LLM call must never
guarantee a non-null response — a forced guess is worse than an explicit ambiguous.

**Ambiguous conditions:**
- Stage 1 returned `STATUS: ambiguous` or an unknown tool name
- A required input has no state match and `extract_from_task` returned None
- Multiple state keys match an input key with equal confidence

**Status values:**

| Status | Meaning |
|--------|---------|
| `ok` | All inputs resolved, transition constructed |
| `ambiguous` | One or more inputs unresolvable — DSTT runtime escalates |
| `not_mappable` | No tool in catalog can fulfil the abstract transition |

**Failure handling:** Bad literals that pass through (key echo, paraphrased path) surface
as `ValueError` at the tool call and are handled by the repair service. v1.1 eliminates
only the silent substitution class (`directory_path=entries`) where no error is raised and
the wrong value propagates undetected.

**What is eliminated:**

| v1.0 | v1.1 |
|------|------|
| Stage 1 outputs `TOOL + INPUTS` (values) | Stage 1 outputs `TOOL + BIND` (key mappings only) |
| Stage 2 LLM formats JSON | Stage 2 eliminated — program constructs directly |
| LLM copies values from state | Program copies values from state |
| Value corruption failures | Structurally impossible |

---

## 10. Open Decisions

- **Tool registry injection** — static registry at startup or dynamic registration
  via API? Current implementation is static.
- **Subtask reduction check** — binary LLM call format not yet specified.
  Should live in a `prompts/` file like the other LLM calls.
- **available_tools in transition2exec** — currently defaults to the built-in
  catalog. Runtime-provided tool lists would allow domain-specific grounding.
- **extract_from_task null contract** — the narrow LLM call for deriving input values
  not present in state must have a defined null response (empty, null, or key echo →
  return None). Currently `_extract_value` always returns something. Contract must be
  enforced before v1.1 resolver is implemented.
