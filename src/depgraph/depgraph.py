from collections import defaultdict
from pathlib import Path
import ast
from typing import Dict, List

from src.tools.file_tools import read_file


def create_dependency_graph(files: List[Path]) -> Dict[Path, List[Path]]:
    """
    Build a dependency graph where:
        A → B  means  file A imports file B

    Only local project files are included.
    External/library imports are ignored.
    """

    # Map module name → Path
    module_map: Dict[str, Path] = {}
    graph: Dict[Path, List[Path]] = defaultdict(list)

    # Register all modules first
    for file_path in files:
        if file_path.suffix != ".py":
            continue

        module_map[file_path.stem] = file_path
        graph[file_path] = []

    # Parse imports using AST
    for file_path in files:
        if file_path.suffix != ".py":
            continue

        try:
            source = read_file(file_path)
            tree = ast.parse(source)
        except Exception:
            # Skip files that fail parsing
            continue

        for node in ast.walk(tree):
            # import x, import x.y
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split(".")[0]
                    if module_name in module_map:
                        graph[file_path].append(module_map[module_name])

            # from x import y
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split(".")[0]
                    if module_name in module_map:
                        graph[file_path].append(module_map[module_name])

    return graph
