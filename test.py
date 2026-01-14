# main.py
import sys
import argparse
from pathlib import Path
import json
from src.orchestrator.refactoring_pipeline import run_refactoring_pipeline


def parse_arguments():
    parser = argparse.ArgumentParser(description="Refactoring Swarm")
    parser.add_argument("--target_dir", type=str, required=True,
                        help="Directory containing the code to refactor")
    parser.add_argument("--max_iterations", type=int, default=8,
                        help="Maximum number of refactoring iterations")
    return parser.parse_args()


def main():
    args = parse_arguments()

    target_dir = Path(args.target_dir).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: Directory not found → {target_dir}")
        sys.exit(1)

    print(f"Starting Refactoring Swarm on: {target_dir}")

    result = run_refactoring_pipeline(
        target_dir=str(target_dir),
        auditor_prompt="src/prompts/auditor_prompt.txt",
        fixer_prompt="src/prompts/fixer_prompt.txt",
        judge_prompt="src/prompts/judge_prompt.txt",
        max_iterations=args.max_iterations
    )

    print("\nFinal result:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()