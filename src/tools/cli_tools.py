from pathlib import Path
import argparse
from src.tools.file_tools import list_python_files, read_file, ensure_in_sandbox

# -----------------------
# CLI Parser
# -----------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Refactoring Swarm CLI")
    parser.add_argument("--target_dir", type=str, required=True, help="Folder with buggy code")
    parser.add_argument("--max_iterations", type=int, default=5, help="Max retry attempts per file")
    parser.add_argument("--max_file_size", type=int, default=100_000, help="Max file size in bytes")
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
