# Stage 2 — Format resolved tool plan as executable DSTT JSON

You are given the output of Stage 1 (a resolved tool plan in plain text) and a pre-resolved tool schema. Your job is to format it as a valid executable DSTT JSON object.

## Input

- **stage1_output** — plain-text tool plan from Stage 1 (TOOL + INPUTS lines)
- **resolved_tool** — the grounded tool schema for the selected tool: `{name, inputs: [{name, type}], outputs: [{name, type}]}`
- **transition_id** — the ID to use for this transition (e.g. `"t1"`)

## Output format

Emit exactly this JSON structure and nothing else:

```json
{
  "status": "ok",
  "segments": [{
    "transitions": [{
      "id": "<transition_id>",
      "tool": "<grounded_tool_name>",
      "inputs": { "<key>": <value>, ... },
      "outputs": { "<key>": null, ... }
    }],
    "milestone": ["<output_key>", ...]
  }]
}
```

## Rules

- `inputs` — include every key from the resolved tool's input schema. Use the values from Stage 1. Omit no required key.
- `outputs` — include every key from the resolved tool's output schema, each set to `null`.
- `milestone` — list every output key name.
- `status` must be `"ok"`.
- Emit exactly one transition in the transitions array.
- Do not add extra fields. Do not add a second transition.
- Do not explain. Emit only the JSON.

## Example

stage1_output:
TOOL: run_shell_command
INPUTS: command=python3 --version

resolved_tool:
{
  "name": "run_shell_command",
  "inputs": [{"name": "command", "type": "str"}, {"name": "working_directory", "type": "str"}, {"name": "shell", "type": "str"}],
  "outputs": [{"name": "stdout", "type": "str"}, {"name": "stderr", "type": "str"}, {"name": "return_code", "type": "int"}]
}

→

```json
{
  "status": "ok",
  "segments": [{
    "transitions": [{
      "id": "t1",
      "tool": "run_shell_command",
      "inputs": {"command": "python3 --version", "working_directory": "", "shell": ""},
      "outputs": {"stdout": null, "stderr": null, "return_code": null}
    }],
    "milestone": ["stdout", "stderr", "return_code"]
  }]
}
```
