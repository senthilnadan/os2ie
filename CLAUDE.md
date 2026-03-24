# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

**OS2I** is a structured agent architecture designed to run on small LLMs. Instead of a single large model holding the full task context, it breaks execution into focused steps — each handled by a separate LLM call or a deterministic executor.

The two specification documents are the primary artifacts:
- `architecture.md` — full system design, concepts, service contracts, and reference implementation layout
- `taskexecutor_spec.md` — detailed spec for the TaskExecutor kernel (execution loop, API, failure semantics)

## System Architecture

Three services, each with a single responsibility:

| Service         | Port | Role                                                  |
|-----------------|------|-------------------------------------------------------|
| task2plan       | 8000 | Task → Abstract DSTT (LLM planning)                  |
| transition2exec | —    | Abstract transition → Executable transition (LLM)    |
| taskexecutor    | 8002 | Execute DSTT, manage state, dispatch tools            |

**Data flow:**
```
task + context → task2plan → abstract_dstt
abstract_dstt + state → taskexecutor →
  for each abstract_transition:
    (abstract_transition + state) → transition2exec → executable_transition
    executable_transition.inputs → state (patch)
    tool(state) → outputs → state (merge)
→ completed state + execution log
```

## Core Concepts

**Abstract DSTT** — a plan in abstract tool names and key names (no concrete values). Produced by `task2plan`. Describes *what* to do.

**Executable DSTT** — the same plan with concrete tool names and resolved input values. Produced by `transition2exec`. Describes *how* to do it.

**State** — a flat key-value dict, the single memory for the entire execution. Initialised from the caller's context, grows cumulatively (nothing removed), passed to `transition2exec` on every call.

**Segment / Transition / Milestone** — a transition is one unit of work; a segment groups transitions that together achieve a milestone; a milestone is the set of output keys that must exist in state before the next segment begins.

## Running the CLI

```bash
# Install dependencies
pip install pydantic requests

# Run from repo root
python -m src.cli "Check whether hello.py exists" \
    --context '{"project_folder_path": "/path/to/project"}' \
    --task2plan-url http://localhost:8000 \
    --transition2exec-url http://localhost:8001
```

Exits `0` on `completed`, `1` on `failed`.

## Implementation Plan

The first implementation is a **plain Python CLI** — no FastAPI, no HTTP server. This validates the core execution loop before committing to a deployment form.

**CLI flow:**
```
cli args (task + context)
  → task2plan(task)                          # HTTP call to task2plan service
  → validate abstract_dstt                   # stop on ambiguity or error
  → for each abstract_transition:
      → transition2exec(task, state, transition)   # called as Python function
      → validate executable_transition             # stop on error
      → dispatch tool(state)
      → state.update(outputs)
  → print final state + execution log
```

**Stack:** Python stdlib + Pydantic v2 (models/validation) + DSPy + Ollama (LLM calls). No FastAPI at this stage.

**Planned layout:**
```
src/
  transition2exec/
    transition/
      dspy_module.py    Two-stage LLM pipeline (tool_sequence → dstt_format)
      providers.py      Backend wiring (qwen / stub)
      mapping.py        resolve_input, default_output_value
    tool_catalog.py     Grounded tool definitions
    validation.py       Executable DSTT validation
    service.py          transition2exec as a callable Python function

  executor/
    tools.py            Tool registry (filesystem, shell, subtask)
    kernel.py           Execution loop (compile → patch → dispatch → merge)

  cli.py                Entry point — parses args, calls task2plan, runs kernel

prompts/
  tool_sequence.md      Stage 1 prompt — abstract tool → grounded tool plan
  dstt_format.md        Stage 2 prompt — plan → executable DSTT JSON
```

## Key Design Decisions

**transition2exec is the component being implemented.** It is not necessarily an HTTP API — it could also be a CLI agent. Where its runtime lives (client-side or server-side) is an open decision. The reference layout under `src/transition2exec/` uses FastAPI, but that is not the only deployment form.

**Two-stage LLM pipeline in transition2exec:** Stage 1 outputs plain text (simple for the model); Stage 2 formats it as executable DSTT JSON using a pre-resolved tool schema to prevent hallucinated tool names or input keys.

**Asserter belongs to repair logic, not the executor.** `src/asserter.py` and `training/asserter_seeds.json` are training artifacts for a future repair/retry service that handles executor failures. The executor itself has no asserter dependency.

**Tool registry is the extension point:** The kernel dispatches by name only and has no built-in capabilities. Adding a new capability = adding a tool, no kernel changes.

**Subtask tool = recursive kernel:** A subtask is just another tool. Before executing, a binary LLM call checks that the subtask genuinely reduces the parent task (narrower scope). This prevents infinite loops without a depth counter.

**The executor is purely mechanical.** Compile → patch → dispatch → merge. No LLM reasoning inside the loop. Scope ends at returning `ExecutionResult`.

**The DSTT runtime owns everything else.** It holds the DSTT object and runtime context, drives the executor, and handles the result — invoking repair on failure or ambiguity resolution on ambiguous. The executor has no knowledge of either. `src/asserter.py` and `training/asserter_seeds.*` are training artifacts for the repair service, which is a DSTT runtime concern.

**Hard failures, no retries:** Any compile, dispatch, or tool error stops execution immediately. Partial state up to the failure point is returned.

## Open Decisions

- Tool registry injection: static at startup vs. dynamic registration via API (currently static)
- Subtask reduction check: binary LLM call format not yet specified — should live in `prompts/`
- `available_tools` in transition2exec: currently defaults to the built-in catalog; runtime-provided lists would allow domain-specific grounding
- `/task2plan` URL: configurable per kernel instance or global config?
- transition2exec runtime: CLI (current plan) — wrapping in an HTTP service is deferred
