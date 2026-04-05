"""
Minimal demo — runs a 2-transition prompting DSTT through the engine.

Usage:
    python -m demo.run_demo
"""
import json
from demo.engine import execute, EngineConfig

# Engine config — model to use
config = EngineConfig(model="qwen2.5:7b")

# Hand-crafted DSTT — no task2plan needed
dstt = {
    "segments": [{
        "transitions": [
            {
                "id": "t1",
                "tool": "explain_topic",
                "inputs": ["topic"],
                "outputs": ["explanation"],
            },
            {
                "id": "t2",
                "tool": "give_analogy",
                "inputs": ["explanation"],
                "outputs": ["analogy"],
            },
        ],
        "milestone": ["explanation", "analogy"],
    }]
}

# Context — initial state
context = {
    "topic": "gravity",
    "template": "Explain {{topic}} in two sentences.",
}

task = "Explain gravity and give an analogy"

print(f"Running: {task}\n")
result = execute(task, dstt, context, config)

print(f"Status: {result.status}")
print(f"Segments completed: {result.segments_completed}")
print(f"Milestones reached: {result.milestone_reached}")
print()
for entry in result.execution_log:
    print(f"[{entry.transition_id}] {entry.tool} — {entry.status}")
    if entry.response:
        print(f"  → {entry.response[:200]}")
    if entry.error:
        print(f"  ! {entry.error}")
print()
print("Final state keys:", [k for k in result.state if not k.startswith("_")])
