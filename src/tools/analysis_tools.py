import subprocess
from pathlib import Path
from src.tools.security import ensure_in_sandbox


def _run_command(command: list[str], cwd: str | None = None) -> str:
    """
    Run a shell command safely and return combined output (stdout + stderr).
    Never raises an exception.
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=20  # prevent infinite loops
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out."
    except Exception as e:
        return f"ERROR: {str(e)}"


def run_pylint(target_path: str) -> str:
    """
    Run pylint on a file or directory.
    Returns the pylint output as string.
    """
    path = Path(target_path)

    if not path.exists():
        return f"ERROR: Path does not exist: {target_path}"

    # If running on a file inside sandbox, enforce sandbox safety
    if path.is_file():
        ensure_in_sandbox(path)

    return _run_command(["pylint", str(path)])


def run_pytest(target_dir: str) -> str:
    """
    Run pytest on a directory.
    Returns pytest output as string.
    """
    path = Path(target_dir)

    if not path.exists():
        return f"ERROR: Directory does not exist: {target_dir}"

    # Enforce sandbox safety
    ensure_in_sandbox(path)

    return _run_command(["pytest", str(path)])
