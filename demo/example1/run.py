"""
example1 — Sequential Prompt Workflow Choreography

Runs one of three reasoning workflows through the DSTT kernel, printing
milestone outputs at each segment boundary.

Usage:
    python -m demo.example1.run --workflow adversarial --input "AI should be regulated"
    python -m demo.example1.run --workflow research   --input "Why do projects fail?"
    python -m demo.example1.run --workflow code       --input "$(cat myfile.py)"

    # Run a named seed instead of a custom input:
    python -m demo.example1.run --workflow adversarial --seed as_01
    python -m demo.example1.run --workflow adversarial --seed as_01 --model llama3.2:3b
"""
import argparse
import json
from pathlib import Path

from demo.engine import DsttKernel
from demo.lib.prompting import build_tool_provider

WORKFLOWS = {
    "adversarial": "demo.example1.workflows.adversarial_synthesis",
    "research":    "demo.example1.workflows.deep_research",
    "code":        "demo.example1.workflows.code_review",
}

SEED_FILES = {
    "adversarial": Path(__file__).parent / "seeds" / "adversarial_seeds.json",
    "research":    Path(__file__).parent / "seeds" / "research_seeds.json",
    "code":        Path(__file__).parent / "seeds" / "code_review_seeds.json",
}

SEGMENT_LABELS = {
    "adversarial": ["build_case", "stress_test", "verdict"],
    "research":    ["decompose", "investigate", "report"],
    "code":        ["understand", "diagnose", "prescribe"],
}


def load_workflow(name: str):
    import importlib
    return importlib.import_module(WORKFLOWS[name])


def run(workflow_name: str, input_value: str, model: str):
    wf = load_workflow(workflow_name)
    tool_provider = build_tool_provider(model)
    initial_state = {wf.INPUT_KEY: input_value, **wf.TEMPLATES}
    labels = SEGMENT_LABELS[workflow_name]

    print(f"\n{'=' * 70}")
    print(f"WORKFLOW : {workflow_name.upper()}")
    print(f"MODEL    : {model}")
    print(f"INPUT    : {input_value[:120]}")
    print(f"{'=' * 70}\n")

    result = DsttKernel().execute(wf.DSTT, tool_provider, initial_state)

    for i, entry in enumerate(result.execution_log):
        if entry.error:
            print(f"[ERROR] {entry.transition_id} / {entry.tool}: {entry.error}")

    if result.status == "failed":
        print(f"\nSTATUS: FAILED after segment {result.segments_completed}")
        return

    print(f"STATUS: {result.status.upper()} — {result.segments_completed} segment(s)\n")

    for i, label in enumerate(labels[:result.segments_completed]):
        print(f"── Milestone {i + 1}: {label} {'─' * (50 - len(label))}")
        for k, v in result.state.items():
            if not k.startswith("_"):
                print(f"\n  [{k}]\n{_indent(str(v))}")
        print()


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="example1 sequential workflow runner")
    parser.add_argument("--workflow", required=True, choices=list(WORKFLOWS),
                        help="adversarial | research | code")
    parser.add_argument("--model", default="qwen2.5:7b")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", dest="input_value",
                       help="raw input string for the workflow")
    group.add_argument("--seed", dest="seed_id",
                       help="seed id from the seeds file (e.g. as_01)")
    args = parser.parse_args()

    if args.seed_id:
        seeds = json.loads(SEED_FILES[args.workflow].read_text())
        match = next((s for s in seeds if s["id"] == args.seed_id), None)
        if match is None:
            parser.error(f"Seed {args.seed_id!r} not found in {args.workflow} seeds")
        wf = load_workflow(args.workflow)
        input_value = match[wf.INPUT_KEY]
        print(f"\nSEED     : {args.seed_id}")
        print(f"OBSERVE  : {match['observe']}")
    else:
        input_value = args.input_value

    run(args.workflow, input_value, args.model)
