from pathlib import Path
import argparse
from src.tools.file_tools import list_python_files, read_file, ensure_in_sandbox

# -----------------------
# CLI Parser
# -----------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Refactoring Swarm CLI")
    parser.add_argument("--file", type=str, help="configure the path to the file you want to fix")
    parser.add_argument("--dir", type=str, help="Configure the path to the directory that contains the files you want to fix")
    parser.add_argument("--max_iterations", type=int, help="configure the maximum number of iterations to do if the first fix fails")
    parser.add_argument("--max_size", type=int, help="Max file size in bytes")
    parser.add_argument("--ignore", nargs="*", default=[], help="Specify files or folders you want to ignore when extracting contents fo files, in case of --file, this argument is ignored")
    return parser.parse_args()


# -----------------------
# File formatter
# -----------------------
def format_code_for_llm(file_path: str, max_file_size: int = 100_000) -> dict:
    """
    Reads the file, ensures sandbox safety, checks size, and returns payload for LLM.
    """
    ensure_in_sandbox(file_path)

    path_obj = Path(file_path)
    size = path_obj.stat().st_size
    if size > max_file_size:
        raise ValueError(f"File too large: {file_path} ({size} bytes)")

    content = read_file(file_path)

    return {
        "file_name": str(path_obj),
        "file_size": size,
        "content": content
    }


# -----------------------
# Helper: prepare all files in a dir
# -----------------------
def prepare_payloads(target_dir: str, max_file_size: int = 100_000) -> list[dict]:
    """
    Scan target_dir for Python files, format each for LLM.
    """
    files = list_python_files(target_dir)
    payloads = []

    for f in files:
        try:
            payload = format_code_for_llm(f, max_file_size=max_file_size)
            payloads.append(payload)
        except ValueError as e:
            print(f"Skipping file: {e}")

    return payloads
