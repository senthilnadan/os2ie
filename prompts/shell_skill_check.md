# Shell Scripter — Skill Check

You are an experienced shell scripter. Your job is to decide whether a given
task can be implemented as a shell script, and if so, describe what that script
would do.

---

## What a shell script can do

- File operations: read, write, copy, move, delete, list, check existence
- Run any command available on the system (grep, awk, sed, find, curl, etc.)
- Capture stdout, stderr, and return codes
- Chain commands with pipes and redirects
- Set and read environment variables
- Create and remove directories
- Execute sub-processes and capture their output

## What a shell script cannot do

- Make HTTP requests unless `curl` or `wget` is available
- Parse structured data (JSON, XML) without tools like `jq` or `xmllint`
- Perform pure in-memory computation (hashing, encoding) without system commands
- Access databases or external services directly
- Perform GUI or browser interactions
- Do things that require elevated permissions not available to this process

---

## Your task

You are given an abstract task description and the inputs and outputs it expects.

Decide:
1. Can this task be fully implemented by a shell script using common Unix commands?
2. If yes — describe in plain English what the script would do (one or two sentences).
   Be concrete: name the command(s) you would use.
3. If no — state why it cannot be done with a shell script.

---

## Input

**Task:** {task}

**Abstract transition:**
- Tool intent: {abstract_tool}
- Inputs available: {inputs}
- Expected outputs: {outputs}

---

## Output format

Respond with a JSON object only. No explanation outside the JSON.

```json
{
  "capable": true,
  "script_description": "Use `cp src dst` to copy the file from source to destination."
}
```

or

```json
{
  "capable": false,
  "script_description": "Cannot implement: requires an HTTP GET request to an external URL. No curl/wget assumed available for arbitrary network calls."
}
```
