# Transition2Shell — Requirement Spec

## Role

`Transition2Shell` is the shell recovery service for the not_mappable path.
When `transition2exec` cannot map an abstract transition to a catalog tool,
`Transition2Shell` decides whether the transition can be implemented as a
shell script AND, if so, produces the executable transition.

One service. One call. One decision.

---

## Responsibility

Given an abstract transition that could not be mapped by `transition2exec`,
`Transition2Shell` must:

1. **Assess viability** — acting as a shell scripter, determine whether the
   abstract task can be fully implemented using shell commands available on
   a generic Unix system.

2. **Produce a script description** — if viable, return a plain-English
   description of the shell script that would implement the task, including
   the concrete command(s) to use. Nothing more — no transition assembly.

3. **Signal not_capable** — if the task cannot be done with a shell script,
   return `status: not_capable`. The caller escalates immediately.

`CreateTransitionHandler` owns the assembly step — it takes the
`script_description` and constructs the `ExecutableTransition` with
`run_shell_command` as the tool.

---

## Contract

### Request

Decomposed hints from the abstract transition — not the full transition object.
The shell scripter reasons from intent signals, not structured agent metadata.

```json
{
  "task": "user-level task description",
  "intent": "abstract_tool_name",
  "inputs": ["input_key_1", "input_key_2"],
  "outputs": ["output_key_1"],
  "context": {
    "input_key_1": "value_from_state",
    "input_key_2": "value_from_state"
  }
}
```

### Response — capable

```json
{
  "status": "ok",
  "script_description": "Use `cp /src/path /dst/path` to copy the file from source to destination."
}
```

### Response — not capable

```json
{
  "status": "not_capable",
  "reason": "short explanation of why shell cannot fulfil this task"
}
```

---

## Prompt role

The LLM inside `Transition2Shell` acts as a **shell scripter**, not a tool
mapper. It is given:

- The abstract transition (tool intent, inputs, outputs)
- A static generic Unix shell capability profile (baked into the prompt)
- The user task for additional context

It reasons in two steps:
1. Can a shell script do this?
2. If yes — what is the exact command?

The prompt lives at `prompts/shell_skill_check.md`.

---

## Shell capability profile (static — baked into prompt)

**Can do:**
- File operations: read, write, copy, move, delete, list, check existence
- Execute any command available on a generic Unix system
- Capture stdout, stderr, return code
- Pipe and redirect stdio
- Environment variable access
- Directory operations

**Cannot do (without specific tools):**
- HTTP requests — requires `curl` or `wget`
- JSON/XML parsing — requires `jq` or `xmllint`
- Pure in-memory computation (hashing, encoding) — requires `openssl`, `base64`, etc.
- GUI or browser interactions
- Database access
- Operations requiring elevated permissions

---

## Output binding

`run_shell_command` produces `stdout`, `stderr`, `return_code`.
`Transition2Shell` maps these to the abstract transition's output keys via
`output_binding`. The executor writes both the grounded key and the abstract
key into state.

---

## Caller: CreateTransitionHandler

`Transition2Shell` returns only `script_description`.
`CreateTransitionHandler` owns the assembly of the `ExecutableTransition`.

```python
# Transition2ShellClient.compile() signature:
#   compile(task, intent, inputs, outputs, context) -> Transition2ShellResult

result = t2s.compile(
    task=task,
    intent=abstract_transition.tool,   # abstract tool name as intent signal
    inputs=abstract_transition.inputs,
    outputs=abstract_transition.outputs,
    context=state,
)

if result.status == "not_capable":
    return Escalation(reason=result.reason, ...)

# Assembly — CreateTransitionHandler's responsibility
executable_transition = ExecutableTransition(
    id=abstract_transition.id,
    tool="run_shell_command",
    inputs={"command": result.script_description},
    outputs={},
    output_binding=_bind_shell_outputs(abstract_transition.outputs),
)
return EscapeToShell(executable_transition=executable_transition, ...)
```

## Response model (src/models.py)

```python
class Transition2ShellResult(BaseModel):
    status: str                            # "ok" | "not_capable"
    script_description: str | None = None  # present when status="ok"
    reason: str | None = None              # present when status="not_capable"
```

---

## Independence

`Transition2Shell` is a standalone service. It:
- Has no dependency on `transition2exec`
- Can be trained independently on shell viability cases
- Can be replaced or upgraded without touching the handler
- Owns its own seed file, regression suite, and go/no-go process

---

## Service details

| Property | Value |
|----------|-------|
| Input | `task` + `intent` + `inputs` + `outputs` + `context` |
| Output (ok) | `script_description: str` |
| Output (not_capable) | `status: not_capable` + `reason` |
| Tool produced | always `run_shell_command` |
| Prompt | `prompts/shell_skill_check.md` |
| Client | `src/clients.py` → `Transition2ShellClient` |
