import json
from pathlib import Path
from typing import List, Dict, Any
import os 
import dotenv
from src.agents.auditor import AuditorAgent
from src.agents.fixer import FixerAgent
from src.agents.judge import JudgeAgent

from src.tools.analysis_tools import run_pytest, run_pylint
from src.tools.file_tools import list_python_files, read_file
from src.utils.logger import log_experiment, ActionType

dotenv.load_dotenv()
class RefactoringPipeline:
    def __init__(
        self,
        auditor_prompt_path: str | Path,
        fixer_prompt_path: str | Path,
        judge_prompt_path: str | Path,
        max_iterations: int = 8,
        require_logging_check: bool = True,
    ):
        self.max_iterations = max_iterations
        self.require_logging = require_logging_check

        # Initialize agents
        self.auditor = AuditorAgent(str(auditor_prompt_path))
        self.fixer = FixerAgent(str(fixer_prompt_path))
        self.judge = JudgeAgent(str(judge_prompt_path))

    def run(self, target_dir: str) -> Dict[str, Any]:
        target_path = Path(target_dir).resolve()
        if not target_path.exists() or not target_path.is_dir():
            raise ValueError(f"Target directory not found: {target_dir}")

        iteration = 0
        history = []
        success = False
        final_status = "MAX_ITERATIONS_REACHED"

        python_files = list_python_files(str(target_path))

        print(f"Starting refactoring pipeline on {len(python_files)} files...")
        print(f"Max iterations allowed: {self.max_iterations}\n")

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n===== ITERATION {iteration}/{self.max_iterations} =====")

            # ── 1. Audit Phase ───────────────────────────────────────
            audit_reports = []
            plan_files = []

            last_judge_feedback = judgement.get("suggested_fix", "") if iteration > 1 else ""

            for file_path in python_files:
                code = read_file(file_path)
                report = self.auditor.audit(file_path, code, self.require_logging)
                
                # If Auditor finds issues OR if Judge previously complained about this file
                if report["status"] != "PASS" or last_judge_feedback:
                    plan_files.append({
                        "path": file_path,
                        "issues": report["issues"] + ([f"Judge reported: {judgement.get('reason')}"] if last_judge_feedback else []),
                        "suggestions": report["suggestions"] + ([last_judge_feedback] if last_judge_feedback else []),
                        "latest_pylint_output": pylint_output if iteration > 1 else "", # Pass the actual error to the Fixer
                        "llm_feedback": report.get("llm_feedback", "")
                    })
            # Build complete plan for this iteration
            current_plan = {
                "iteration": iteration,
                "files_to_fix": plan_files,
                "global_summary": f"Iteration {iteration} - {len(plan_files)} files need attention"
            }

            history.append({
                "phase": f"Iter {iteration}: audit",
                "status": [r["status"] for r in audit_reports]
            })

            if not plan_files:
                 print("→ No issues found! All files passed audit.")
                 
                 # Still must run judge once
                 pytest_output = run_pytest(target_dir)
                 pylint_output = run_pylint(target_dir)
                
                 judgement = self.judge.evaluate(pytest_output, pylint_output)
                
                 if judgement["decision"] == "SUCCESS":
                     success = True
                     final_status = "SUCCESS"
                     break
                 if judgement["decision"] == "RETRY":
                    for f in plan_files:
                        f["issues"].append(judgement["reason"])
                        f["suggestions"].append(judgement.get("suggested_fix", ""))



            # ── 2. Fix Phase ─────────────────────────────────────────
            print(f"Fixing {len(plan_files)} files...")
            fix_result = self.fixer.apply_refactoring_plan(current_plan)

            history.append({
                "phase": f"Iter {iteration}: fix",
                "status": fix_result.get('overall_status')
            })

            print(f"Fix status: {fix_result.get('overall_status', 'UNKNOWN')}")

            # ── 3. Judge Phase ───────────────────────────────────────
            print("Evaluating quality...")
            pytest_output = run_pytest(target_dir)
            pylint_output = run_pylint(target_dir)

            judgement = self.judge.evaluate(pytest_output, pylint_output)

            history.append({
                "phase": f"Iter {iteration}: judge",
                "status": judgement["decision"]
            })

            print(f"\nJudge decision: {judgement['decision']}")
            print(f"→ {judgement.get('reason', 'No reason provided')}")

            # ── Logging the whole iteration ──────────────────────────
            log_experiment(
                agent_name="Pipeline-Orchestrator",
                model_used=os.getenv("HF_MODEL", "unknown"),
                action=ActionType.ANALYSIS,
                details={
                    "iteration": iteration,
                    "input_prompt": "Orchestrating refactoring cycle",
                    "output_response": json.dumps({
                        "decision": judgement["decision"],
                        "files_processed": len(python_files),
                        "files_fixed": fix_result.get("successful", 0),
                        "judge_reason": judgement.get("reason", "")
                    }, indent=2),
                    "pytest_output_sample": pytest_output[:600],
                    "pylint_output_sample": pylint_output[:600]
                },
                status=judgement["decision"]
            )

            if judgement["decision"] == "SUCCESS":
                success = True
                final_status = "SUCCESS"
                print("\n🎉 REFACTORING SUCCESSFULLY COMPLETED!")
                break

            print("→ Judge requires another iteration...\n")

        # Final summary
        summary = {
            "status": final_status,
            "iterations_performed": iteration,
            "success": success,
            "files_processed": len(python_files),
            "last_decision": judgement if 'judgement' in locals() else None,
            "history_summary": [
                f"Iter {i+1}: {h['phase']} → {h.get('decision', h.get('fix_summary', {}).get('overall_status', '—'))}"
                for i, h in enumerate(history)
            ]
        }

        return summary


# ── Helper for main.py ───────────────────────────────────────────────────────
def run_refactoring_pipeline(
    target_dir: str,
    auditor_prompt: str,
    fixer_prompt: str,
    judge_prompt: str,
    max_iterations: int = 8
) -> Dict:
    """Convenience function to be called from main.py"""
    pipeline = RefactoringPipeline(
        auditor_prompt_path=auditor_prompt,
        fixer_prompt_path=fixer_prompt,
        judge_prompt_path=judge_prompt,
        max_iterations=max_iterations
    )
    return pipeline.run(target_dir)