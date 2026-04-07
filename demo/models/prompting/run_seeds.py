"""
Run complex reasoning seeds through the DSTT prompting engine.

Each seed is a compound multi-part probe. The DSTT runs two transitions:
  1. ask(probe)                          → response
  2. asktemplate(validator, probe, response) → assessment

The operator reads the assessment against known_answer and observe
to build a capability and strategy profile for the model.

Usage:
    python -m demo.models.prompting.run_seeds
    python -m demo.models.prompting.run_seeds --model llama3.2:3b
    python -m demo.models.prompting.run_seeds --seed cr_01 cr_03
"""
import json
import argparse
from pathlib import Path
from demo.engine import DsttKernel
from demo.lib.prompting import build_tool_provider

SEEDS_FILE = Path(__file__).parent / "seeds" / "complex_reasoning_seeds.json"

VALIDATOR_TEMPLATE = (
    "You are a response checker.\n\n"
    "ORIGINAL PROMPT:\n{{0}}\n\n"
    "MODEL RESPONSE:\n{{1}}\n\n"
    "Check the response against the prompt. For each requirement in the prompt:\n"
    "- Did the model satisfy it? Mark as [MET] or [MISSED].\n"
    "- Did the model follow the ordering constraint? Mark as [ORDERED] or [DISORDERED].\n"
    "- List only the items that are [MISSED] or [DISORDERED] or factually wrong.\n"
    "Be concise. Output only the failure list. If nothing failed, output: ALL MET."
)

DSTT = {
    "segments": [{
        "transitions": [
            {"tool": "ask", "inputs": ["probe"], "outputs": ["response"]},
            {"tool": "asktemplate", "inputs": ["_validator", "probe", "response"], "outputs": ["assessment"]},
        ],
        "milestone": ["response", "assessment"],
    }]
}


def run(model: str, seed_ids: list[str] | None = None):
    seeds = json.loads(SEEDS_FILE.read_text())
    if seed_ids:
        seeds = [s for s in seeds if s["id"] in seed_ids]

    tool_provider = build_tool_provider(model)

    for seed in seeds:
        print(f"\n{'=' * 70}")
        print(f"[{seed['id']}] {seed['capability'].upper()}")
        print(f"{'=' * 70}")
        print(f"PROBE:\n{seed['probe']}\n")

        initial_state = {
            "probe": seed["probe"],
            "_validator": VALIDATOR_TEMPLATE,
        }

        result = DsttKernel().execute(DSTT, tool_provider, initial_state)

        if result.status == "completed":
            print(f"RESPONSE:\n{result.state.get('response', '')}\n")
            print(f"ASSESSMENT:\n{result.state.get('assessment', '')}\n")
        else:
            for entry in result.execution_log:
                if entry.error:
                    print(f"ERROR [{entry.transition_id}]: {entry.error}")

        print(f"OBSERVE:  {seed['observe']}")
        print(f"EXPECTED: {json.dumps(seed['known_answer'], indent=2)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--seed", nargs="*", dest="seeds")
    args = parser.parse_args()
    run(args.model, args.seeds)
