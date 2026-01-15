import os
from pathlib import Path

from src.orchestrator.refactoring_pipeline import run_refactoring_pipeline

# ---- Sandbox files ----
sandbox_dir = Path("sandbox")
sandbox_files = list(sandbox_dir.glob("*.py"))

# ---- Prompts (already exist) ----
auditor_prompt = "src/prompts/auditor_prompt.txt"
fixer_prompt = "src/prompts/fixer_prompt.txt"
judge_prompt = "src/prompts/judge_prompt.txt"

# ---- Run pipeline ----
result = run_refactoring_pipeline(
    target_dir=str(sandbox_dir),
    auditor_prompt=auditor_prompt,
    fixer_prompt=fixer_prompt,
    judge_prompt=judge_prompt,
    files=sandbox_files,
    max_iterations=2
)

print("\n===== PIPELINE RESULT =====")
print(result)

# ---- Optional: Show fixed files ----
print("\n===== FIXED FILES =====")
for f in sandbox_files:
    print(f"\n--- {f.name} ---")
    print(f.read_text())
