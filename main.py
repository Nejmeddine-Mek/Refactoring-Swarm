import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from src.utils.logger import log_experiment, ActionType

# Toolsmith helpers
from src.tools.cli_tools import parse_args, prepare_payloads
from src.tools.analysis_tools import run_pylint, run_pytest
from src.tools.file_tools import write_file, backup_file
# we should remove ipynb later
extensions_set = {".py", ".ipynb"}

# load_dotenv()

## CODE HERE WILL CHANGE

# --------------------------
# Dummy agent function for testing
# --------------------------
def dummy_agent(file_path: str, code: str) -> str:
    # I will work on those as soon as the cool prompt engineer prepares the prompts we need.
    # this should not be plain text, instead, we shall return an object with code to replace in each file.
    #this should operate on many files not only one
    if code.startswith("# Fixed by dummy_agent"):
        return code  # already fixed
    return "# Fixed by dummy_agent\n" + code


# --------------------------
# Self-healing loop
# --------------------------
def attempt_fix(file_path: str, code: str, max_iterations: int) -> bool:
    # here, on each attempt, prompt changes based on whether we are fixing for the first time, or we are trying to fix the returned code
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
    global MAX_SIZE, MAX_ITERATIONS
    MAX_SIZE = 50 * 1024 # default maximum size of a file
    MAX_ITERATIONS = 5 # default maximum number of iterations
    file_names_list = []
    
    args = parse_args()
    ignore_files = args.ignore
    if bool(args.dir) == bool(args.file):
        print("You must exclusively specify a directory or a file")
        sys.exit(1)
    # here we have a path crossing, if we have a dir, we shall read all files after locating the dir
    # if we have a file, we read one single file, and then the processing remains the same
    if bool(args.max_iterations):
        MAX_ITERATIONS = args.max_iterations
    if bool(args.max_size):
        MAX_SIZE = args.max_size
    # now, we did set the maximum values, we must then start reading the files we need
    # the case where we only have one file
    # the way I think we shall do this is as follows:
        # 1 - locate the file(s)
        # 2 - verify extensions to be .py
        # 3 - store file names in a list of file names of length >= 1
        # 4 - do the rest of the work ordinarily
    # get files to ignore if they exist
    
    if bool(args.file):
        if not os.path.exists(args.file):
            print(f"❌ File {args.file} is not found.")
            sys.exit(1)
        # now the file is found
        file_names_list.append(args.file)

    # now we check the case of the directory
    elif bool(args.dir):
        if not os.path.exists(args.dir):
            print(f"❌ File {args.dir} is not found.")
            sys.exit(1)

        # the directory exists, we need to get all file names ending in .py
        dir_path = Path(args.dir)
        for f in dir_path.iterdir():

            # check if the files is not in the whitelist, is of appropriate type. 
            if not f.is_file():
                continue
            if f.suffix.lower() not in extensions_set:
                continue
            if f.name in ignore_files:
                continue

            if f.stat().st_size > MAX_SIZE:
                print(f"{f} is too big")
                sys.exit(2)

            print(f"{f} is a python file")
        # now, all the files should be grouped in the file_names_list. we can proceed    

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
    
"""
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
    )"""


if __name__ == "__main__":
    main()
