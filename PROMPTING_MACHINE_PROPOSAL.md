# Prompting Machine — DSTT Proposal

## The Idea

A DSTT executor where every transition is a prompt call. Two tools only.
State carries every response forward. The model is configured once at the system level.

The same kernel that executes file operations executes prompt chains — no new infrastructure.

---

## The Two Tools

### `ask`
Send a raw prompt to the configured model and return the response.

```
inputs:  prompt (str)
outputs: response (str)
```

### `asktemplate`
Resolve a template against current state, send to model, return response.

```
inputs:  template (str)   — uses {{key}} placeholders resolved from state
outputs: response (str)
```

`asktemplate` is the power tool. Every prior response is in state and can be
injected into the next prompt automatically. The model builds on its own prior
outputs without the caller managing context manually.

---

## What the DSTT Enables

A DSTT is a plan of prompt transitions with declared inputs, outputs, and milestones.
The kernel threads state across all transitions. This gives you:

### Chain of Thought
```
t1: ask("Break this problem into steps: {{problem}}")        → plan
t2: asktemplate("Execute step 1 of: {{plan}}")               → step1_result
t3: asktemplate("Execute step 2 of: {{plan}} using {{step1_result}}") → step2_result
t4: asktemplate("Summarise the final answer from {{step2_result}}")   → final_output
```

### Verify-and-Correct
```
t1: asktemplate("Solve: {{problem}}")                        → answer
t2: asktemplate("Verify this answer: {{answer}}")            → verdict
t3: asktemplate("If verdict is wrong, fix: {{answer}} because {{verdict}}") → final_output
```

### Decompose-then-Execute
```
t1: ask("Decompose this task into subtasks: {{task}}")       → subtask_list
t2: asktemplate("Execute subtask 1 from: {{subtask_list}}")  → result_1
t3: asktemplate("Execute subtask 2 from: {{subtask_list}} given {{result_1}}") → result_2
t4: asktemplate("Combine {{result_1}} and {{result_2}}")     → final_output
```

### Critic-Refine Loop (with milestone gate)
```
Segment 1:
  t1: asktemplate("Draft answer for: {{problem}}")           → draft
  t2: asktemplate("Critique this draft: {{draft}}")          → critique
  milestone: [critique]

Segment 2:
  t3: asktemplate("Refine {{draft}} using {{critique}}")     → final_output
  milestone: [final_output]
```

---

## System Design

```
POST /prompt-execute
{
  "task":    "...",
  "context": { "problem": "...", ... },
  "dstt":    { ... },          ← caller provides the DSTT directly
  "model":   "qwen2.5:7b"     ← optional override
}
→ ExecutionResult (state contains all intermediate + final responses)
```

Two modes:
- **Direct DSTT** — caller provides the abstract DSTT (full control)
- **Auto-plan** — task2plan generates the DSTT from the task description

The model config is the only system-level dependency. Swap the model, run the
same DSTT — instant A/B comparison across models with identical prompting chains.

---

## Implementation

Two new tools in `src/tools.py`:

```python
def _ask(state):
    prompt = state["prompt"]
    response = call_model(prompt, model=state.get("_model"))
    return {"response": response}

def _asktemplate(state):
    template = state["template"]
    prompt = template.replace("{{", "{").replace("}}", "}")
    prompt = prompt.format(**{k: v for k, v in state.items()
                              if not k.startswith("_")})
    response = call_model(prompt, model=state.get("_model"))
    return {"response": response}
```

`call_model` calls Ollama (or any backend). `_model` is injected into state
at execution start from the request config — invisible to the DSTT.

---

## Why This Is a Beast

- **Any reasoning pattern** expressible as a prompt chain runs on this
- **State is the memory** — no manual context window management
- **Milestones gate progress** — segment 2 only runs if segment 1 produced
  the required keys — built-in quality control
- **Model is a variable** — same DSTT, different model, instant benchmark
- **Composable with file tools** — a transition can read a file, pass text
  to `asktemplate`, write the response back — LLM + filesystem in one chain
- **Auditable** — every prompt, every response, every transition logged
  in the execution log with e1, e2, e3 IDs

The two-tool constraint is the strength, not the limitation.
Everything complex is expressed as a DSTT — the tools stay simple.
