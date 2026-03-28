# Stage 1 — Resolve abstract tool to grounded tool plan

You are given an abstract transition (an abstract tool name + input/output key names) and the current execution state. Your job is to select the correct grounded tool and resolve its concrete input values.

## Input

- **task** — the original user task (plain English)
- **abstract_tool** — the abstract tool name (e.g. `check_python_version`, `create_log_file`)
- **abstract_inputs** — list of abstract input key names declared in the transition
- **abstract_outputs** — list of abstract output key names declared in the transition
- **context** — current state (flat key-value dict; all keys resolved so far)
- **available_tools** — list of grounded tools with their input/output signatures

## Your task

1. **Select the grounded tool** whose purpose exactly matches what the abstract tool name describes. The tool must be capable of fulfilling the full intent of the task — not just partially related to it.

2. **Resolve each required input** for the grounded tool:
   - Look for a matching key in `context` (exact name or obvious alias).
   - Copy the value exactly as it appears in context — do not paraphrase or summarise.
   - If the value is stated explicitly in the task description, use it verbatim.
   - If a required input has no value in context and the task gives no value, use an empty string `""`.

3. **Output a plain-text plan** using this exact format:

```
TOOL: <grounded_tool_name>
INPUTS: <key>=<value>, <key>=<value>, ...
```

## Rules

- Use only tool names from `available_tools`. Do not invent tool names.
- Emit exactly one TOOL line and one INPUTS line.
- Do not explain your reasoning.
- If a required input has no value in context, derive it from the task description. If the task gives no value either, use an empty string `""`.
- **If no tool in `available_tools` can directly and fully fulfil the abstract transition, output:**
  ```
  TOOL: not_mappable
  INPUTS:
  ```
  Do NOT pick the closest or most similar tool as a substitute. A wrong tool is worse than no tool.

## Examples

task: List files in /tmp/os2ie_sandbox
abstract_tool: list_project_files
abstract_inputs: [directory_path]
abstract_outputs: [entries]
context: {directory_path: /tmp/os2ie_sandbox}

→

TOOL: list_directory
INPUTS: directory_path=/tmp/os2ie_sandbox

---

task: Check the Python version installed on this system
abstract_tool: check_python_version
abstract_inputs: []
abstract_outputs: [python_version]
context: {}
available_tools: [list_directory, exists, read_file]

→

TOOL: not_mappable
INPUTS:

---

task: Count all Python files in /tmp/os2ie_sandbox
abstract_tool: count_python_files
abstract_inputs: [working_directory]
abstract_outputs: [python_file_count]
context: {working_directory: /tmp/os2ie_sandbox}
available_tools: [list_directory, exists, read_file]

→

TOOL: not_mappable
INPUTS:
