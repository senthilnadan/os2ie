# AskStructured Tool — Specification

**Status:** Draft  
**Scope:** `demo/lib/prompting/`  
**Purpose:** Define the contract, design decisions, and implementation plan for the
`AskStructuredTool` — a prompt tool that produces validated structured output (dict)
from an LLM call.

---

## Problem

`AskTool` and `AskTemplateTool` both return a raw `str`. For workflows that need
to route on model output, feed structured fields into downstream transitions, or
enforce a data contract at a milestone, a string is not enough.

`AskStructuredTool` closes this gap: it sends a prompt to the model and returns a
`dict` whose shape is declared upfront.

---

## Interface

```python
class AskStructuredTool:
    def __init__(
        self,
        provider: Callable[[str], str],
        schema: Union[str, dict[str, str]],   # str → plain instruction; dict → field map
        validate: bool = True,                 # only applies when schema is dict
        max_retries: int = 1,                  # one retry, for connection errors only
    ) -> None: ...

    def execute(self, prompt: str) -> Union[str, dict]:
        """
        Send prompt to model.
        - schema is str  → appends it as an output instruction, returns raw str
        - schema is dict → appends JSON instruction, parses response, returns dict
        """
        ...
```

### Behaviour by schema type

| `schema` type | `validate` | `execute` returns | What happens |
|---------------|------------|-------------------|--------------|
| `str`         | ignored    | `str`             | Appended as a plain instruction to the prompt. Response returned as-is. |
| `dict`        | `True`     | `dict`            | JSON instruction appended. Response parsed, all schema keys checked present, extras dropped. |
| `dict`        | `False`    | `dict`            | JSON instruction appended. Response parsed. No key check — caller takes what the model returns. |

No type coercion. If the model returns `"3"` for a numeric field, it stays `"3"`.
The caller decides what to do with values.

### Why schema at `__init__`, not `execute`

The schema is a structural contract, not a runtime value. It belongs alongside the
provider — both define what the tool *is*, not what it is *asked*. Keeping it at
init means:

- DSTT transition inputs stay simple: `["prompt"]` from state
- The schema is inspectable on the tool instance without calling it
- Tests can construct the tool once and run many prompts through it

If the schema were at `execute` time, every transition would need to carry a
`schema` key in state — a leaky structural concern in a data store.

---

## Schema Format

### dict form — structured output

Each key is the expected output field name; each value is a plain-English
description that becomes the model's instruction for that field.

```python
schema = {
    "verdict":    "true or false — whether the statement is correct",
    "confidence": "high, medium, or low",
    "reason":     "one sentence explaining the verdict",
}
```

### str form — guided string output

A plain instruction appended after the prompt. The model returns a string and
the tool returns it unchanged — no parsing, no validation.

```python
schema = "Respond with a single sentence. No lists, no headers."
```

This makes `AskStructuredTool` a superset of `AskTool`: if you want raw output
with an instruction, use `schema: str`. If you want a parsed dict, use `schema: dict`.

---

## How the LLM Is Instructed

The tool appends a structured output instruction block to the prompt before sending:

```
{original prompt}

---
Respond with a JSON object and nothing else. Use exactly these keys:
  "verdict":    true or false — whether the statement is correct
  "confidence": high, medium, or low
  "reason":     one sentence explaining the verdict

Output only the JSON object. No explanation, no markdown fences.
```

This is **prompt-level instruction** — it works with any string-in / string-out
provider, including Ollama generate, OpenAI chat completions, and stubs.

**Provider-native structured output (optional enhancement):**  
Ollama supports `format: "json"` in the generate request body. `OllamaProvider`
can pass this flag when the caller opts in. The tool does not require it — prompt
instruction is the baseline. Provider-native mode is an optimisation.

---

## Return Value and Validation

`execute` returns a `dict` containing exactly the keys declared in `schema`.

**Validation steps:**
1. Strip the response string (remove whitespace and accidental markdown fences)
2. Parse as JSON — raise `ValueError` on parse failure
3. Check all schema keys are present — raise `ValueError` listing missing keys
4. Return the validated dict (extra keys from the model are dropped)

**Retry policy:**  
One retry, for connection errors only (`requests.RequestException` or equivalent).
The original prompt is re-sent unchanged — no error injection, no amended prompt.

Validation failures (bad JSON, missing keys) are **not retried** — they are raised
immediately. The DSTT kernel catches the exception, logs the failure, and halts —
consistent with the hard-fail contract.

---

## DSTT Transition Pattern

```python
# Tool provider entry
tool_provider = {
    "ask":            AskTool(provider),
    "asktemplate":    AskTemplateTool(provider),
    "askstructured":  AskStructuredTool(provider, schema={
        "verdict":    "true or false — whether the statement is correct",
        "confidence": "high, medium, or low",
        "reason":     "one sentence explaining the verdict",
    }),
}
```

```python
# DSTT transition
{
    "tool":    "askstructured",
    "inputs":  ["verify_prompt"],        # single prompt string from state
    "outputs": ["verification_result"],  # dict stored under this key in state
}
```

Downstream transitions read `verification_result` from state as a dict. If a
downstream transition needs a single field, a lightweight `ExtractTool` (not in
this spec) can project `verification_result["verdict"]` → `verdict`.

---

## Output Mapping in the Kernel

The kernel's `_call_tool` stores the return value of `execute()` under the single
output key:

```python
state["verification_result"] = {"verdict": True, "confidence": "high", "reason": "..."}
```

The dict is stored as-is. The kernel does not unpack it — that is the caller's
responsibility.

---

## Extension: Multi-Schema Tool Provider

When a workflow needs multiple structured tools with different schemas, each gets
its own named entry in `tool_provider`:

```python
tool_provider = {
    "classify_intent":   AskStructuredTool(provider, schema={...}),
    "extract_entities":  AskStructuredTool(provider, schema={...}),
    "score_quality":     AskStructuredTool(provider, schema={...}),
}
```

No tool name collision. No schema merging. Each tool is independently testable.

---

## What Needs to Be Built

1. **`AskStructuredTool`** in `demo/lib/prompting/tools.py`  
   — `__init__(provider, schema, max_retries=2)`  
   — `execute(prompt) -> dict`  
   — `_build_prompt(prompt) -> str` (appends schema instruction)  
   — `_parse_and_validate(response) -> dict` (strip → parse → check keys → drop extras)

2. **`build_tool_provider`** in `demo/lib/prompting/tools.py`  
   — extend to accept optional `structured_schemas: dict[str, dict]`  
   — for each entry, add `AskStructuredTool(provider, schema)` to the returned dict

3. **`OllamaProvider` optional `format` flag** in `demo/lib/prompting/providers.py`  
   — add `structured: bool = False` param to `__init__`  
   — if True, pass `"format": "json"` in the request body  
   — this is an optimisation, not a requirement for the tool to function

---

## Resolved Decisions

| Decision | Resolution |
|----------|------------|
| Retry strategy | One retry, connection errors only. Re-send original prompt unchanged. Validation errors raise immediately — no retry. |
| `validate=False` and missing keys | Return dict as-is. Caller takes whatever the model returned. `KeyError` or `ValueError` thrown downstream by the consumer — not swallowed here. |
