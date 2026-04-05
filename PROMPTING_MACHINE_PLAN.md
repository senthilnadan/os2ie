# Prompting Machine — Build Plan

## Honest Assessment

The real kernel (`src/kernel.py`) already exists and is production-ready.
State threading, milestone gating, execution logging — all working.
The stub kernel is test-only and irrelevant here.

What is missing is narrow and well-defined.

---

## What Already Exists

| Component | Status |
|-----------|--------|
| Kernel (execute loop) | ✓ done |
| Server (POST /execute) | ✓ done |
| Tool registry | ✓ done |
| Catalog | ✓ done |
| Transition2ExecClient | ✓ done |
| Task2PlanClient | ✓ done |
| State threading across transitions | ✓ done |
| Milestone gating between segments | ✓ done |
| Execution log (e1, e2...) | ✓ done |

---

### Architects Question 
I had not seen the kernal loop, yet.  all I know is we have a stub for testing purpose.. 
our kernal only helps build dstt.  it doesnt execute DSTT. 

The dependency is a DSTT, your assumption is wrong here. 

## What Needs to Be Built

### 1. Model client — `src/model_client.py`

A thin wrapper around Ollama (or any backend) that takes a prompt and returns a response.

```
call_model(prompt: str, model: str) → str
```

This is the only genuinely new infrastructure. Everything else plugs into existing slots.

**Dependency:** Ollama must be running locally with a model pulled.

---

### 2. Two tools — additions to `src/tools.py`

```
_ask(state)           — prompt from state["prompt"] → response
_asktemplate(state)   — template from state["template"], resolves {{keys}}
                         from state → prompt → response
```

Model name injected via `state["_model"]` (set at execution start, invisible to DSTT).

---

### 3. Catalog entries — additions to `src/catalog.py`

Two new entries: `ask` and `asktemplate`.
Both take string inputs, produce `response` (str).

---

### 4. Model config in server — small addition to `src/server.py`

```
POST /execute
{
  "task": "...",
  "context": { ... },
  "model": "qwen2.5:7b",    ← new optional field
  "strategy": "input_first",
  "available_tools": [ ... ]
}
```

On request, inject `_model` into state before kernel executes.

---

## What Is NOT Being Built

- No new kernel
- No new server
- No new execution loop
- No DSTT format changes
- No task2plan changes (caller provides DSTT directly for now)

---

## Build Sequence

```
Step 1 — src/model_client.py       (Ollama wrapper, ~20 lines)
Step 2 — src/tools.py              (add _ask, _asktemplate)
Step 3 — src/catalog.py            (add ask, asktemplate entries)
Step 4 — src/server.py             (accept model field, inject _model into state)
Step 5 — manual test               (hand-craft a 2-transition DSTT, POST to /execute)
```

---

## Feasibility

Fully feasible with the real kernel. Steps 1–4 are small, contained additions.
No architectural changes. The kernel runs prompt chains the same way it runs
file operations — it does not know or care what the tools do.

**Risk:** transition2exec must ground `ask`/`asktemplate` correctly from
abstract transition names. Mitigation: caller can pass `available_tools`
with only `ask` and `asktemplate` — no catalog ambiguity.

---

## First Test DSTT (manual, no task2plan needed)

```json
{
  "task": "Explain gravity simply then give an analogy",
  "context": { "topic": "gravity" },
  "model": "qwen2.5:7b",
  "available_tools": [ ask, asktemplate ],
  "dstt": {
    "segments": [{
      "transitions": [
        { "id": "t1", "tool": "ask_simple_explanation",
          "inputs": ["topic"], "outputs": ["explanation"] },
        { "id": "t2", "tool": "ask_analogy",
          "inputs": ["explanation"], "outputs": ["analogy"] }
      ],
      "milestone": ["explanation", "analogy"]
    }]
  }
}
```

Expected: kernel calls transition2exec for t1 → grounds to `asktemplate`,
executes, puts `explanation` in state. Then t2 → `asktemplate` with
`explanation` injected → `analogy` in state. Done.
