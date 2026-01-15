
from collections import defaultdict

def formatGraph(depgraph) -> str:
    """
    Format a dependency graph into a readable string.
    Each line shows a key file and the list of files it depends on.
    """
    lines = []
    for key, values in depgraph.items():
        # If the values list is empty, show 'None' or empty
        if values:
            values_str = ", ".join(str(v) for v in values)
        else:
            values_str = "None"
        lines.append(f"{key} -> {values_str}")
    
    # Join all lines into a single string
    return "\n".join(lines) 