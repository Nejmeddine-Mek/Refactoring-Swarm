import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from src.utils.logger import log_experiment, ActionType

# Toolsmith helpers
from src.tools.cli_tools import parse_args, prepare_payloads
from src.tools.analysis_tools import run_pylint, run_pytest
from src.tools.file_tools import write_file, backup_file

load_dotenv()


# --------------------------
# Dummy agent function for testing
# --------------------------
def dummy_agent(file_path: str, code: str) -> str:
    if code.startswith("# Fixed by dummy_agent"):
        return code  # already fixed
    return "# Fixed by dummy_agent\n" + code


# --------------------------
# Self-healing loop
# --------------------------
def attempt_fix(file_path: str, code: str, max_iterations: int) -> bool:
    for i in range(max_iterations):
        new_code = dummy_agent(file_path, code)
        backup_file(file_path)
        write_file(file_path, new_code)

        # Run pylint & pytest
        pylint_result = run_pylint(file_path)
        pytest_result = run_pytest(Path(file_path).parent)

        # Log each iteration
        log_experiment(
            "DummyAgent",            # agent_name
            "test",                  # model_used
            ActionType.ANALYSIS,     # action
            {
                "file": str(file_path),
                "iteration": i + 1,
                "input_prompt": "Simulated agent prompt",
                "output_response": new_code,
                "pylint_output": pylint_result[:200],
                "pytest_output": pytest_result[:200],
            },
            "SUCCESS" if "failed" not in pytest_result.lower() else "RETRY"
        )

        # Stop if pytest passes
        if "failed" not in pytest_result.lower():
            return True

    return False


# --------------------------
# Main
# --------------------------
def main():
    args = parse_args()

    if not os.path.exists(args.target_dir):
        print(f"❌ Dossier {args.target_dir} introuvable.")
        sys.exit(1)

    print(f"🚀 DEMARRAGE SUR : {args.target_dir}")

    # Log startup
    log_experiment(
        "System",
        "unknown",
        ActionType.ANALYSIS,
        {
            "input_prompt": "System startup",
            "output_response": f"Target directory: {args.target_dir}"
        },
        "INFO"
    )

    # Prepare payloads (sandbox-safe + size check)
    payloads = prepare_payloads(args.target_dir, max_file_size=args.max_file_size)
    print(f"📂 {len(payloads)} fichiers préparés pour l'agent.")

    # Process each file
    for payload in payloads:
        file_path = payload["file_name"]
        code = payload["content"]
        print(f"📝 Traitement du fichier: {file_path}")
        
        # DEBUG: show the code that was read
        print("📄 Code lu :")
        print(code)
        print("-" * 50)
    
        success = attempt_fix(file_path, code, args.max_iterations)
        if success:
            print(f"✅ {file_path} corrigé avec succès.")
        else:
            print(f"❌ {file_path} n'a pas pu être corrigé après {args.max_iterations} itérations.")


    print("🚀 MISSION_COMPLETE")

    # Log shutdown
    log_experiment(
        "System",
        "unknown",
        ActionType.ANALYSIS,
        {
            "input_prompt": "System shutdown",
            "output_response": f"Target directory: {args.target_dir}"
        },
        "INFO"
    )


if __name__ == "__main__":
    main()
