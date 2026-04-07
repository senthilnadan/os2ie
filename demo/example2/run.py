"""
Usage:
    # Python-loop driver (agent.py)
    python -m demo.example2.run --task "What is 12 factorial divided by the number of vowels in MATHEMATICS?"

    # DSTT-native driver (agent_dstt.py)
    python -m demo.example2.run --task "..." --dstt

    python -m demo.example2.run --task "..." --model llama3.2:3b --max-iterations 6
"""
import argparse
from demo.lib.prompting import OllamaProvider, build_tool_provider

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--dstt", action="store_true",
                        help="use DSTT-native ReAct loop (agent_dstt.py)")
    parser.add_argument("--deep", action="store_true",
                        help="use deep DSTT — ThinkTool/CheckTool/SeedAndRunTool as Named DSTTs (agent_deep_dstt.py)")
    args = parser.parse_args()

    provider = OllamaProvider(args.model)
    print(f"MODEL : {args.model}")

    if args.deep:
        from demo.example2.agent_deep_dstt import run
        result = run(args.task, provider, args.max_iterations)
    elif args.dstt:
        from demo.example2.agent_dstt import run
        result = run(args.task, provider, args.max_iterations)
    else:
        from demo.example2.agent import run
        tool_provider = build_tool_provider(provider)
        print(f"\nTASK  : {args.task}")
        result = run(args.task, provider, tool_provider, args.max_iterations)

    print(f"\n{'=' * 70}")
    print(f"STATUS     : {result['status']}")
    print(f"ITERATIONS : {result['iterations']}")
    if result.get("answer"):
        print(f"ANSWER     : {result['answer']}")
