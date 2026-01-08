from src.agents.auditor import AuditorAgent

# Load the content of the fake file to simulate auditing it
def read_test_code():
    with open("sandbox/fake_file.py", "r", encoding="utf-8") as f:
        return f.read()

def main():
    TEST_CODE = read_test_code()

    agent = AuditorAgent("src/prompts/auditor_prompt.txt")

    report = agent.audit(
        file_path="sandbox/fake_file.py",
        code=TEST_CODE,
        require_logging=False
    )


    print("\n=== AUDIT REPORT ===")
    for k, v in report.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
