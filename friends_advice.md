Fix (must do)

Change selection priority:

PRIMARY: required outputs
SECONDARY: available inputs

👉 This alone will fix:

wrong tool substitution
write vs read confusion
exists vs read_file issue
3️⃣ Output Namespace Mismatch (Your Gap #2)

You already identified it correctly.

Your best fix (keep it simple)

Make this mandatory:

"output_binding": {
  "tool_output": "abstract_output"
}

And enforce:

final state MUST contain abstract outputs

👉 This removes 80% of silent failures