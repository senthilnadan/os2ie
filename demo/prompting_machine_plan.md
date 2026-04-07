# Prompting Machine — Execution Plan
## demo/example1: Sequential Prompt Workflow Choreography

---

## Goal

Demonstrate that DSTT is a simpler, more testable alternative to LangChain/LangGraph
for sequential prompt orchestration. No graph DSL. No framework coupling. Just a flat
state dict, explicit milestones, and composable prompt tools.

The claim: what LangGraph expresses as a node graph with edge conditions and shared
state objects, DSTT expresses as segments → transitions → milestones with a plain dict.

---

## Primitives

Three prompt primitives power all workflows:

| Tool | Inputs | Output | Purpose |
|------|--------|--------|---------|
| `ask` | `prompt` | `response` | Raw prompt → string |
| `asktemplate` | `template`, `*values` | `response` | Fill `{{0}}`, `{{1}}` … then prompt |
| `askstructured` | `prompt`, `schema` | `structured` | Prompt → validated JSON dict |

`askstructured` is the only missing primitive — it wraps the provider with a schema
instruction and parses the JSON response. Everything else is already built.

---

## Workflows

### W1 — Adversarial Synthesis
**Capability tested:** can the model hold two opposing views simultaneously and
synthesise without collapsing to one side?

```
Segment 1: build_case
  transitions:
    - asktemplate(argue_for_template, topic)   → case_for
    - asktemplate(argue_against_template, topic) → case_against
  milestone: [case_for, case_against]

Segment 2: stress_test
  transitions:
    - asktemplate(weaknesses_template, case_for, case_against) → weaknesses
    - asktemplate(steelman_template, case_against, weaknesses) → steelmanned
  milestone: [weaknesses, steelmanned]

Segment 3: verdict
  transitions:
    - asktemplate(synthesise_template, case_for, steelmanned) → synthesis
    - asktemplate(verdict_template, synthesis, weaknesses)    → verdict
  milestone: [synthesis, verdict]
```

---

### W2 — Deep Research Report
**Capability tested:** can the model decompose a hard question, answer sub-parts
independently, detect its own contradictions, and produce a coherent report?

```
Segment 1: decompose
  transitions:
    - asktemplate(decompose_template, question) → sub_questions
  milestone: [sub_questions]

Segment 2: investigate
  transitions:
    - asktemplate(answer_each_template, sub_questions)           → answers
    - asktemplate(cross_check_template, sub_questions, answers)  → contradictions
  milestone: [answers, contradictions]

Segment 3: report
  transitions:
    - asktemplate(resolve_template, answers, contradictions) → resolved
    - asktemplate(summarise_template, resolved)              → summary
    - asktemplate(format_template, summary)                  → report
  milestone: [report]
```

---

### W3 — Iterative Code Review
**Capability tested:** can the model separate intent analysis from code analysis,
merge them into prioritised issues, and produce verifiable fix suggestions?

```
Segment 1: understand
  transitions:
    - asktemplate(intent_template, code)      → intent
    - asktemplate(code_analysis_template, code) → code_analysis
  milestone: [intent, code_analysis]

Segment 2: diagnose
  transitions:
    - asktemplate(find_issues_template, intent, code_analysis) → issues
    - asktemplate(prioritise_template, issues)                 → prioritised_issues
  milestone: [issues, prioritised_issues]

Segment 3: prescribe
  transitions:
    - asktemplate(suggest_fixes_template, prioritised_issues, code) → fix_suggestions
    - asktemplate(verify_logic_template, fix_suggestions, intent)   → reviewed_code
  milestone: [reviewed_code]
```

---

## File Layout

```
demo/
  example1/
    __init__.py
    workflows/
      __init__.py
      adversarial_synthesis.py   # W1 DSTT + templates + tool_provider
      deep_research.py           # W2 DSTT + templates + tool_provider
      code_review.py             # W3 DSTT + templates + tool_provider
    seeds/
      adversarial_seeds.json     # topic → known synthesis shape
      research_seeds.json        # question → known sub-questions + contradictions
      code_review_seeds.json     # code snippet → known issues + priorities
    run.py                       # CLI: --workflow --model --seed
```

Each workflow module exposes:
```python
DSTT: dict              # the plan
INITIAL_STATE: dict     # templates keyed exactly as DSTT expects
build_tool_provider(model) -> dict
```

`run.py` wires them together and prints milestone-by-milestone output.

---

## What Needs to Be Built

1. **`askstructured` tool** in `demo/lib/prompting/tools.py`
   — prompt + JSON schema instruction → parse + validate response

2. **W1, W2, W3 workflow modules** under `demo/example1/workflows/`
   — DSTT definition, templates, `build_tool_provider`

3. **Seeds** for each workflow under `demo/example1/seeds/`
   — 3–5 seeds per workflow, with `known_answer` and `observe`

4. **`run.py`** CLI entry point

---

## The Demonstration Point

For each workflow, the side-by-side comparison is:

| Concern | LangGraph | DSTT |
|---------|-----------|------|
| State | TypedDict schema + graph state | flat `dict` |
| Orchestration | node functions + edge conditions | segments + milestones |
| Prompt design | inside node functions, hard to isolate | templates in initial_state, inspectable |
| Testing | mock nodes, patch edges | swap tool_provider, run any seed |
| Mid-run inspection | graph snapshot (framework API) | `result.state` at any milestone |

The milestone boundary is the key differentiator — each segment's output is a named,
inspectable checkpoint before the next segment begins.
