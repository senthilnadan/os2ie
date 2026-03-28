"""
OS2I CLI executor.

Usage:
    python -m src.cli "Check whether hello.py exists" \
        --context '{"project_folder_path": "/path/to/project"}' \
        --task2plan-url http://localhost:8000 \
        --transition2exec-url http://localhost:8001
"""
from __future__ import annotations
import argparse
import json
import sys
from .catalog import build_catalog
from .clients import Task2PlanClient, Transition2ExecClient
from .config import config
from .kernel import execute


def main() -> None:
    parser = argparse.ArgumentParser(description="OS2I CLI executor")
    parser.add_argument("task", help="Task description")
    parser.add_argument(
        "--context",
        default="{}",
        metavar="JSON",
        help='Initial state as a JSON object, e.g. \'{"project_folder_path": "/path"}\'',
    )
    parser.add_argument("--task2plan-url", default=config.task2plan_url)
    parser.add_argument("--transition2exec-url", default=config.transition2exec_url)
    args = parser.parse_args()

    try:
        context = json.loads(args.context)
    except json.JSONDecodeError as e:
        print(f"error: --context is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    t2p = Task2PlanClient(args.task2plan_url)
    t2e = Transition2ExecClient(args.transition2exec_url)

    # Plan
    print(f"→ planning: {args.task}")
    try:
        abstract_dstt, meta = t2p.plan(args.task)
    except Exception as e:
        print(f"error: task2plan failed: {e}", file=sys.stderr)
        sys.exit(1)

    plan_status = meta.get("status", "ok")
    if plan_status == "ambiguous":
        print(f"error: task2plan returned status='ambiguous' — task needs more context, aborting", file=sys.stderr)
        sys.exit(1)
    if plan_status == "low_confidence":
        print(f"warning: task2plan low_confidence — proceeding, verify results carefully", file=sys.stderr)

    total_transitions = sum(len(s.transitions) for s in abstract_dstt.segments)
    print(f"→ plan ready: {len(abstract_dstt.segments)} segment(s), {total_transitions} transition(s)")

    # Execute — available_tools injected here (run_shell_command excluded; handler adds it on fallback)
    available_tools = [t for t in build_catalog() if t["name"] != "run_shell_command"]
    result = execute(args.task, context, abstract_dstt, t2e, available_tools=available_tools)

    print(json.dumps(result.model_dump(), indent=2))
    sys.exit(0 if result.status == "completed" else 1)


if __name__ == "__main__":
    main()
