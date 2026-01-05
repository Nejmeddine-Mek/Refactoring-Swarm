from pathlib import Path

def get_project_root() -> Path:
    """
    Returns the absolute path to the project root directory.
    Assumes this file lives in src/tools/security.py
    """
    return Path(__file__).resolve().parents[2]


def get_sandbox_root() -> Path:
    """
    Returns the absolute path to the sandbox directory.
    """
    return get_project_root() / "sandbox"


def ensure_in_sandbox(path: str | Path) -> None:
    """
    Ensures that a given path is inside the sandbox directory.
    Raises ValueError if not.

    Works with:
    - relative paths
    - absolute paths
    - symlinks
    """
    sandbox_root = get_sandbox_root().resolve()
    target_path = Path(path).resolve()

    try:
        # Will raise ValueError if target_path is outside sandbox
        target_path.relative_to(sandbox_root)
    except ValueError:
        raise ValueError(
            f"SECURITY VIOLATION: Attempt to access path outside sandbox:\n{target_path}"
        )


def test_ensure_in_sandbox():
    """
    Run a series of tests to make sure sandbox protection works.
    Prints results to console.
    """

    sandbox_root = get_sandbox_root()
    print("Sandbox root:", sandbox_root)

    # ✅ Valid paths inside sandbox
    valid_paths = [
        sandbox_root / "file.py",
        sandbox_root / "subdir" / "nested.py",
        "./sandbox/file2.py"
    ]

    # ❌ Invalid paths outside sandbox
    invalid_paths = [
        "../main.py",
        "/etc/passwd",
        get_project_root() / "logs" / "experiment_data.json"
    ]

    print("\nTesting valid paths:")
    for p in valid_paths:
        try:
            ensure_in_sandbox(p)
            print(f"PASS ✅ {p}")
        except ValueError as e:
            print(f"FAIL ❌ {p}: {e}")

    print("\nTesting invalid paths:")
    for p in invalid_paths:
        try:
            ensure_in_sandbox(p)
            print(f"FAIL ❌ {p} should not be allowed")
        except ValueError as e:
            print(f"PASS ✅ {p}: {e}")
