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

2. **Produce the executable transition** — if viable, generate an
   `ExecutableDSTT` using `run_shell_command` with a concrete, correct command.

3. **Signal not_capable** — if the task cannot be done with a shell script,
   return `status: not_capable`. The caller escalates immediately.

---

## Contract

### Request

```json
{
  "task": "user-level task description",
  "abstract_transition": {
    "id": "t1",
    "tool": "abstract_tool_name",
    "inputs": ["input_key_1", "input_key_2"],
    "outputs": ["output_key_1"],
    "output_type": {"output_key_1": "str"}
  },
  "context": {}
}
```

### Response — capable

```json
{
  "status": "ok",
  "executable_transition": {
    "id": "t1",
    "tool": "run_shell_command",
    "inputs": {
      "command": "<concrete shell command>"
    },
    "outputs": {},
    "output_binding": {
      "stdout": "<abstract output key>",
      "return_code": "<abstract return key>"
    }
  }
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

```python
result = t2s.compile(task, abstract_transition, context)

if result.status == "not_capable":
    return Escalation(reason=result.reason, ...)

return EscapeToShell(executable_transition=result.executable_transition, ...)
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
| Input | `task` + `abstract_transition` + `context` |
| Output (ok) | `ExecutableTransition` with `run_shell_command` |
| Output (not_capable) | `status: not_capable` + `reason` |
| Tool produced | always `run_shell_command` |
| Prompt | `prompts/shell_skill_check.md` |
| Client | `src/clients.py` → `Transition2ShellClient` |
