from pathlib import Path
from typing import Dict, List


def format_dependency_graph(depgraph: Dict[Path, List[Path]]) -> str:
    """
    Format a dependency graph into a readable string.
    Each line shows a key file and the list of files it depends on.

    Args:
        depgraph: Dictionary mapping Path → List[Path]

    Returns:
        Multi-line string representation
    """
    lines = []

    # Sort keys for deterministic output
    for key in sorted(depgraph.keys(), key=lambda p: p.name):
        values = depgraph[key]

        if values:
            # Sort dependencies and show only the filename
            values_str = ", ".join(sorted(v.name for v in values))
        else:
            values_str = "None"

        lines.append(f"{key.name} -> {values_str}")

    return "\n".join(lines)
