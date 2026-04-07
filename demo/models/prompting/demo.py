"""
Prompting model demo — composes explain + analogy using ask/asktemplate primitives.

Usage:
    python -m demo.models.prompting.demo
"""
from demo.engine import DsttKernel
from demo.lib.prompting import build_tool_provider

tool_provider = build_tool_provider("qwen2.5:7b")

dstt = {
    "segments": [{
        "transitions": [
            {
                "tool": "asktemplate",
                "inputs": ["explain_template", "topic"],
                "outputs": ["explanation"],
            },
            {
                "tool": "asktemplate",
                "inputs": ["analogy_template", "explanation"],
                "outputs": ["analogy"],
            },
        ],
        "milestone": ["explanation", "analogy"],
    }]
}

initial_state = {
    "topic": "gravity",
    "explain_template": "Explain {{0}} in two sentences.",
    "analogy_template": "Give one simple analogy for this explanation: {{0}}",
}

print("Running: Explain gravity and give an analogy\n")
result = DsttKernel().execute(dstt, tool_provider, initial_state)

print(f"Status: {result.status}")
print(f"Milestones reached: {result.milestone_reached}")
print()
for entry in result.execution_log:
    print(f"[{entry.transition_id}] {entry.tool} — {entry.status}")
    if entry.error:
        print(f"  ! {entry.error}")
print()
for k, v in result.state.items():
    print(f"  {k}: {str(v)[:200]}")
