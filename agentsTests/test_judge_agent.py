# test_judge_agent.py
from src.agents.judge import JudgeAgent

def main():
    # Example test outputs for varied situations
    examples = [
        {
            "pytest_output": "6 passed, 0 failed",
            "pylint_output": "No critical errors detected"
        },
        {
            "pytest_output": "3 passed, 0 failed",
            "pylint_output": "No critical errors detected"
        },
        {
            "pytest_output": "3 passed, 0 failed",
            "pylint_output": "one critical errors detected"
        },
        {
            "pytest_output": "1 passed, 1 failed",
            "pylint_output": "No critical errors detected"
        },
      
    ]

    agent = JudgeAgent("src/prompts/judge_prompt.txt")

    for i, example in enumerate(examples, start=1):
        report = agent.evaluate(example["pytest_output"], example["pylint_output"])
        print(f"\n=== TEST CASE {i} ===")
        print(f"Pytest output: {example['pytest_output']}")
        print(f"Pylint output: {example['pylint_output']}")
        print(f"Agent decision: {report['decision']}")
        print(f"Reason: {report['reason']}")
        print(f"Suggested fix: {report['suggested_fix']}")
        print("-" * 40)

if __name__ == "__main__":
    main()
