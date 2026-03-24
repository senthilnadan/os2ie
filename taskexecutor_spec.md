TaskExecutor Spec
=================

Overview
--------
TaskExecutor is a runtime kernel that materialises and executes an AbstractDSTT.
It owns the execution loop, holds the tool registry, and uses state as the single
channel between all transitions.

For each abstract transition it calls transition2exec to compile it to a grounded
executable transition, patches the resolved inputs into state, dispatches the tool,
and merges the outputs back into state before moving to the next transition.


Architecture
------------

    ┌─────────────────────────────────────────────────────┐
    │  TaskExecutor                                        │
    │                                                      │
    │  tool registry (injected at startup)                 │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ exists, read_file, create_file, ...          │   │
    │  │ run_shell_command                            │   │
    │  │ subtask  ← recursive kernel instance        │   │
    │  └──────────────────────────────────────────────┘   │
    │                                                      │
    │  DSTT Kernel                                         │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ for each segment:                            │   │
    │  │   for each abstract_transition:              │   │
    │  │     1. compile  → transition2exec            │   │
    │  │     2. patch    → state.update(inputs)       │   │
    │  │     3. dispatch → tool(state)                │   │
    │  │     4. merge    → state.update(outputs)      │   │
    │  │   milestone reached → next segment           │   │
    │  └──────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────┘


Endpoint
--------
POST /taskexec


Input
-----
{
  "task": "Check whether hello.py exists in the project folder.",
  "parent_task": null,
  "state": {
    "project_folder_path": "/path/to/project",
    "target_file": "hello.py"
  },
  "abstract_dstt": {
    "segments": [
      {
        "transitions": [
          {
            "id": "t1",
            "tool": "check_python_file_existence",
            "inputs": ["project_folder_path"],
            "outputs": ["python_file_exists"],
            "output_type": {"python_file_exists": "bool"},
            "complexityTime": "O(1)",
            "complexitySpace": "O(1)",
            "skill_required": ["programmer"],
            "resource_required": ["filesystem"]
          }
        ],
        "milestone": ["python_file_exists"]
      }
    ]
  }
}


Output
------
{
  "status": "completed",
  "state": {
    "project_folder_path": "/path/to/project",
    "target_file": "hello.py",
    "file_path": "/path/to/project/hello.py",
    "is_present": true
  },
  "transition_records": [
    {
      "transition_id": "t1",
      "timestamp": "2026-03-22T10:04:00Z",

      "state_snapshot": {
        "project_folder_path": "/path/to/project",
        "target_file": "hello.py"
      },
      "abstract_transition": {
        "id": "t1",
        "tool": "check_python_file_existence",
        "inputs": ["project_folder_path"],
        "outputs": ["python_file_exists"]
      },

      "prompt_sent": "...exact prompt text sent to the model, verbatim...",
      "model_raw_output": "TOOL: exists\nINPUTS: file_path=/path/to/project/hello.py",
      "executable_transition": {
        "tool": "exists",
        "inputs": {"file_path": "/path/to/project/hello.py"},
        "outputs": {"is_present": null}
      },

      "tool_name": "exists",
      "tool_inputs": {"file_path": "/path/to/project/hello.py"},
      "tool_outputs": {"is_present": true},
      "state_delta": {"is_present": true},

      "status": "completed",
      "failure_reason": null
    }
  ],
  "segments_completed": 1,
  "milestone_reached": ["is_present"]
}

On failure (compile stage):
{
  "status": "failed",
  "state": { "project_folder_path": "/path/to/project", "target_file": "hello.py" },
  "transition_records": [
    {
      "transition_id": "t1",
      "timestamp": "2026-03-22T10:04:00Z",

      "state_snapshot": { "project_folder_path": "/path/to/project", "target_file": "hello.py" },
      "abstract_transition": { "id": "t1", "tool": "check_python_file_existence", "..." },

      "prompt_sent": "...exact prompt text sent to the model, verbatim...",
      "model_raw_output": "...raw output that failed to parse...",
      "executable_transition": null,

      "tool_name": null,
      "tool_inputs": null,
      "tool_outputs": null,
      "state_delta": null,

      "status": "failed",
      "failure_reason": { "stage": "parse", "error": "..." }
    }
  ],
  "segments_completed": 0,
  "milestone_reached": []
}

TransitionRecord is the primary artifact. Every field is populated at the moment
it occurs — not reconstructed after the fact. `failure_reason.stage` names the
exact stage that failed: "compile", "parse", "dispatch", or "tool".


Execution Loop
--------------
for each segment in abstract_dstt.segments:

    for each abstract_transition in segment.transitions:

        BEGIN TransitionRecord
          record.transition_id       = abstract_transition.id
          record.timestamp           = now()
          record.state_snapshot      = copy of current state   ← captured before anything changes
          record.abstract_transition = abstract_transition

        1. COMPILE
           Build prompt from: task, context (current state), abstract_transition.
           record.prompt_sent = prompt                         ← captured verbatim
           POST /transition2exec with prompt payload.
           record.model_raw_output = raw response              ← captured before parsing
           Parse response → executable_dstt.
           If parse fails → record.failure_reason = {stage: "parse", error: ...}
                            record.status = "failed" → stop.
           If status != "ok" → record.failure_reason = {stage: "compile", error: ...}
                               record.status = "failed" → stop.
           record.executable_transition = parsed executable_transition

        2. for each grounded_transition in executable_dstt.segments[0].transitions:

           a. PATCH STATE
              Merge grounded_transition.inputs into state.
              record.tool_inputs = grounded_transition.inputs

           b. DISPATCH
              Look up tool name in registry.
              record.tool_name = tool_name
              If tool not found → record.failure_reason = {stage: "dispatch", error: ...}
                                  record.status = "failed" → stop.
              Call tool, passing state as context.
              If tool raises → record.failure_reason = {stage: "tool", error: ...}
                               record.status = "failed" → stop.
              record.tool_outputs = tool return value

           c. MERGE OUTPUTS
              Merge tool outputs into state.
              record.state_delta = tool outputs

        record.status = "completed"
        APPEND record to transition_records

    milestone_reached += segment.milestone keys that are now in state.

Return status, final state, transition_records, segments_completed, milestone_reached.


State
-----
State is the single channel between all transitions and all tools.

- Initialised from the request's `state` field (the runtime context).
- transition2exec contributes resolved concrete values (inputs patch).
- Tools read inputs from state and write outputs back to state.
- State grows cumulatively — nothing is removed during execution.
- Keys from earlier transitions remain available to later ones.


Tool Registry
-------------
Tools are injected into the kernel by TaskExecutor at startup.
The kernel is tool-agnostic — it dispatches by name only.

Built-in tools (filesystem / shell):

  exists(file_path)                        → is_present
  list_directory(directory_path)           → entries
  list_directory_recursive(directory_path) → entries
  read_file(file_path)                     → text
  create_file(file_path, content)          → success
  append_to_file(file_path, content)       → success
  delete_file(file_path)                   → deleted
  copy_file(source_path, destination_path) → copied
  move_file(source_path, destination_path) → moved
  make_directory(directory_path)           → created
  remove_directory(directory_path,
                   recursive)              → removed
  run_shell_command(command,
                    working_directory)     → stdout, stderr, return_code

Subtask tool:

  subtask(task, context, parent_task)      → milestone outputs of the subtask

  The subtask tool:
    1. Calls /task2plan with task + context to get an abstract_dstt.
    2. Spins up a new kernel instance with that abstract_dstt and context as state.
    3. Executes to completion (sequential, blocking).
    4. Returns the subtask's final milestone outputs to the parent state.

  The parent kernel blocks until the subtask completes before continuing to
  the next transition.

  Subtask carries a reference to its parent task. Before executing, the kernel
  asks: "Is this task a subtask of the parent task?" via an LLM check.

  - If yes → reduction confirmed, proceed with execution.
  - If no  → not a subtask of the parent, fail immediately with status "failed"
             and error "subtask does not reduce parent task".

  This is a single binary LLM call — lightweight, no depth counter needed.
  A genuine subtask (narrower scope, delegated step, concrete sub-problem)
  will pass. A repeated or unrelated task will fail.


Failure Handling
----------------
- Any failure (compile, dispatch, tool error) stops execution immediately.
- No silent fallbacks. No retries.
- Partial state (up to the failed transition) is returned in the response.
- The execution log records the error on the failed transition entry.
- status = "failed"


Seed Tasks
----------
┌────────────────────────────┬──────────────────────────┬─────────────────────────────────────────┐
│            Task            │       Grounded Tool      │          Key behaviour tested           │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Check file exists          │ exists                   │ single transition, boolean output       │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ List directory             │ list_directory_recursive │ list output into state                  │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Read file                  │ read_file                │ text output into state                  │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Delete file                │ delete_file              │ side effect, deleted flag               │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Create file                │ create_file              │ content input from state                │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Append to file             │ append_to_file           │ chained — file_path reused across steps │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Run shell command          │ run_shell_command        │ stdout/stderr/return_code into state    │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Multi-step (create + read) │ create_file → read_file  │ state threading between transitions     │
├────────────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
│ Subtask                    │ subtask                  │ recursive kernel, outputs into parent   │
└────────────────────────────┴──────────────────────────┴─────────────────────────────────────────┘


Open Questions
--------------
- Should /task2plan URL be configurable per kernel instance or global config?
- How are tool registry extensions provided at runtime (config file, injection API)?


V2 Scope
--------
V1 execution loop is a linear state machine: running → completed | failed.
V2 extends this to handle control signals emitted by transition2exec and
task2plan that require the executor to pause, delegate, or surface to the caller.

### Control signals the executor must handle in V2

**`ambiguous`** — emitted by transition2exec or task2plan when the task or
transition is underspecified and cannot proceed without more context.

  Executor action: suspend execution. Return `status=ambiguous` to the DSTT
  runtime with the question and the current state snapshot. Do not fail.
  Execution resumes when the runtime provides the missing context.

**`getOrAskContextAndConstraints`** — emitted as an abstract transition signal
when the planner determines it needs a specific input value not present in state
and not derivable from the task.

  Executor action: pause at this transition. Surface the question to the caller.
  On receipt of the answer, patch state with the provided value and resume
  execution from the paused transition. Do not advance to the next transition
  until the answer is received.

**`task2Plan`** — emitted as an abstract transition signal when the planner
determines a sub-problem requires its own planning cycle (recursive subtask).

  Executor action: treat as a subtask signal. Spawn a child kernel instance
  with the sub-problem as the task and current state as context. Block until
  the child completes. Merge child's final state into parent state. Continue
  parent execution from the next transition.

### V2 execution state machine

```
running
  → ambiguous      → suspended (waiting for caller context) → resumed → running
  → getOrAsk       → suspended (waiting for specific value) → resumed → running
  → task2Plan      → subtask   (child kernel)               → merged  → running
  → completed
  → failed
```

### V2 status values

| Status | Meaning |
|--------|---------|
| `completed` | All segments completed, milestones reached |
| `failed` | Hard failure — compile, dispatch, or tool error |
| `ambiguous` | Execution suspended — task underspecified, caller must clarify |
| `suspended` | Execution paused — waiting for specific context value |

### What V2 does not change

- The mechanical execution loop (compile → patch → dispatch → merge) is unchanged
- Hard failures still stop immediately
- The evidentiary TransitionRecord is captured for all states including suspended
- The executor has no knowledge of retry or repair — those remain DSTT runtime concerns
