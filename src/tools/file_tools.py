from pathlib import Path
import shutil
from src.tools.security import ensure_in_sandbox


def list_python_files(target_dir: str) -> list[str]:
    """
    Recursively list all Python files in a directory.
    Ignores __pycache__ folders.
    """
    base = Path(target_dir)

    if not base.exists():
        raise FileNotFoundError(f"Target directory not found: {target_dir}")

    files = []
    for path in base.rglob("*.py"):
        if "__pycache__" not in path.parts:
            files.append(str(path.resolve()))
    return files


def read_file(file_path):
    encodings = ["utf-8", "utf-8-sig", "latin1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    raise ValueError(f"Cannot read file {file_path} with supported encodings")


def backup_file(path: str) -> None:
    """
    Create a backup of a file with .bak suffix.
    """
    file_path = Path(path)

    if file_path.exists():
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy(file_path, backup_path)


def write_file(path: str, content: str) -> None:
    """
    Safely write content to a file inside sandbox.
    Creates parent directories if missing.
    Automatically creates a .bak backup before writing.
    """
    ensure_in_sandbox(path)

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    backup_file(path)
    file_path.write_text(content, encoding="utf-8")
