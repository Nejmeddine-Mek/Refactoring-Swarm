import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from src.utils.logger import log_experiment, ActionType

# Toolsmith helpers
from src.tools.cli_tools import parse_args, prepare_payloads
from src.tools.analysis_tools import run_pylint, run_pytest
from src.tools.file_tools import write_file, backup_file, compile_auditor_prompt
from src.orchestrator.refactoring_pipeline import run_refactoring_pipeline

# we should remove ipynb later
extensions_set = {".py", ".ipynb"}

load_dotenv()


# --------------------------
# Main
# --------------------------
def main():
    global MAX_SIZE, MAX_ITERATIONS
    MAX_SIZE = 50 * 1024  # default maximum size of a file
    MAX_ITERATIONS = 10    # default maximum number of iterations
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
        # this should work recursively, when you get a directory, you get the subfiles too
        
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d not in ignore_files]
            # check if the files is not in the whitelist, is of appropriate type.
            for name in files:
                f = Path(root) / name
                # we keep this as security measure
                if not f.is_file():
                    continue
                if f.name in ignore_files:
                    continue
                if f.suffix.lower() not in extensions_set:
                    continue
                # print(f, f.name)
                if f.stat().st_size > MAX_SIZE:
                    print(f"{f} is too big")
                    sys.exit(2)
                # add the file name (using f itself gives us directly the path, not only the name)
                file_names_list.append(f)
        
        #print(f"{f} is a python file")
        #print(file_names_list)
        # now, all the files should be grouped in the file_names_list. we can proceed
    # create a dependency graph grouping files that depend on each other in an adjacency list for the next steps
    #dependency_graph = createDepGraph(file_names_list)
    #print(formatGraph(dependency_graph))
    #compile_auditor_prompt(dependency_graph)
    # now the main work starts
    print("\n" + "=" * 70)
    print("   Starting real Refactoring Pipeline   ".center(70))
    print("=" * 70 + "\n")
    
    result = run_refactoring_pipeline(
        target_dir=args.dir if args.dir else str(Path(args.file).parent),
        auditor_prompt="src/prompts/auditor_prompt.txt",
        fixer_prompt="src/prompts/fixer_prompt.txt",
        judge_prompt="src/prompts/judge_prompt.txt",
        files=[str(f) for f in file_names_list],     # list of files to treat, at least 1
        max_iterations = MAX_ITERATIONS
    )

"""
    # ── Real pipeline call ───────────────────────────────────────────────
    result = run_refactoring_pipeline(
        target_dir=args.dir if args.dir else str(Path(args.file).parent),
        auditor_prompt="src/prompts/auditor_prompt.txt",
        fixer_prompt="src/prompts/fixer_prompt.txt",
        judge_prompt="src/prompts/judge_prompt.txt",
        files=[str(f) for f in file_names_list],     # list of files to treat, at least 1
        dep_graph=dependency_graph,                             # here goes the dependency graph
        max_iterations=MAX_ITERATIONS
    )
        #print(f"🚀 DEMARRAGE SUR : {args.dir}")
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


    print("\n" + "=" * 70)
    print("   Starting real Refactoring Pipeline   ".center(70))
    print("=" * 70 + "\n")

    # ── Real pipeline call ───────────────────────────────────────────────
    result = run_refactoring_pipeline(
        target_dir=args.dir if args.dir else str(Path(args.file).parent),
        auditor_prompt="src/prompts/auditor_prompt.txt",
        fixer_prompt="src/prompts/fixer_prompt.txt",
        judge_prompt="src/prompts/judge_prompt.txt",
        max_iterations=MAX_ITERATIONS
        # files=[str(f) for f in file_names_list],     # ← add this line if your pipeline accepts a list of files
        # dep_graph=graph,                             # ← optional
    )

    print("\nFinal result:")
    print(json.dumps(result, indent=2))

    print("\n" + "═" * 70)
    print("   MISSION COMPLETE   ".center(70, "═"))
    print("═" * 70)

    """
if __name__ == "__main__":
    main()
    
    
    
#this is the running command :  python test.py --target_dir sandbox/test_project --max_iterations 3
