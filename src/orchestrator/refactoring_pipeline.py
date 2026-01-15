import json
import os
from pathlib import Path
from typing import Dict, Any, List

from langchain.memory import ConversationBufferMemory

from src.agents.auditor import AuditorAgent
from src.agents.fixer import FixerAgent
from src.agents.judge import JudgeAgent

from src.tools.analysis_tools import run_pytest, run_pylint
from src.tools.file_tools import read_file
from src.utils.logger import log_experiment, ActionType

from src.depgraph.depgraph import create_dependency_graph
from src.depgraph.formatter import format_dependency_graph


class RefactoringPipeline:

    def __init__(
        self,
        target_dir: str | Path,
        auditor_prompt_path: str | Path,
        fixer_prompt_path: str | Path,
        judge_prompt_path: str | Path,
        files: List[Path],
        max_iterations: int = 8,
        require_logging_check: bool = True,
    ):
        self.files = files
        self.max_iterations = max_iterations
        self.require_logging = require_logging_check

        # Agents
        self.auditor = AuditorAgent(str(auditor_prompt_path))
        self.fixer = FixerAgent(str(fixer_prompt_path))
        self.judge = JudgeAgent(str(judge_prompt_path))

        # Global memory for storing audit results, plans, etc.
        self.memory = ConversationBufferMemory(
            memory_key="refactor_memory",
            return_messages=True
        )

    # ─────────────────────────────────────────────────────────────
    # Step 1: Dependency graph → initial strategy
    # ─────────────────────────────────────────────────────────────
    def generate_initial_plan_from_graph(self) -> Dict[str, Any]:
        
        depgraph = create_dependency_graph(self.files)
        formatted = format_dependency_graph(depgraph)

        self.memory.save_context(
            {"input": "Dependency graph"},
            {"output": formatted}
        )

        # Leaf-first order: files with no dependencies first
        ordered_files = sorted(depgraph.keys(), key=lambda f: len(depgraph[f]))

        plan = {
            "strategy": "Fix leaf dependencies first",
            "file_order": [str(f) for f in ordered_files],
            "dependency_graph": formatted,
        }

        self.memory.save_context(
            {"input": "Initial dependency-based plan"},
            {"output": json.dumps(plan, indent=2)}
        )

        return plan

    # ─────────────────────────────────────────────────────────────
    # Step 2: Audit all files
    # ─────────────────────────────────────────────────────────────
    def audit_files(self) -> List[Dict[str, Any]]:
        reports = []

        for file_path in self.files:
            code = read_file(file_path)
            report = self.auditor.audit(
                file_path=str(file_path),
                code=code,
                require_logging=self.require_logging
            )
            reports.append(report)

            self.memory.save_context(
                {"input": f"Audit report for {file_path.name}"},
                {"output": json.dumps(report, indent=2)}
            )

        return reports

    # ─────────────────────────────────────────────────────────────
    # Step 3: Build consolidated plan from memory
    # ─────────────────────────────────────────────────────────────
    def build_global_plan_from_memory(self) -> Dict[str, Any]:
        memory_text = self.memory.load_memory_variables({})["refactor_memory"]

        planner_prompt = f"""
    You are a senior software refactoring planner.

    Using the COMPLETE MEMORY below:
    - Dependency graph
    - Initial strategy
    - All audit reports

    Create ONE consolidated refactoring plan.

    Rules:
    - Fix files in correct dependency order
    - Group related issues
    - Avoid unnecessary rewrites
    - Output JSON with:
      - files_to_fix (list of dicts)
      - per-file issues
      - suggested changes
      - dependency rationale

    MEMORY:
    {memory_text}
    """

        response = self.fixer._ask_llm(plan={"dummy": True}, current_code=planner_prompt)

        try:
            raw_plan = json.loads(response)
        except Exception:
            raw_plan = {"note": "LLM output not valid JSON", "file_order": []}

        # --- Convert to Fixer-compatible structure ---
        files_to_fix = []
        
        # Add all user files first (skip test files)
        for file_path in self.files:
            if not file_path.name.startswith("test_"):
                files_to_fix.append({
                    "path": str(file_path),
                    "issues": [],
                    "suggestions": [],
                    "latest_pytest_output": "",
                    "latest_pylint_output": "",
                    "llm_feedback": ""
                })
        
        # Now optionally append test files (so they get linted/audited later)
        for file_path in self.files:
            if file_path.name.startswith("test_"):
                files_to_fix.append({
                    "path": str(file_path),
                    "issues": [],
                    "suggestions": [],
                    "latest_pytest_output": "",
                    "latest_pylint_output": "",
                    "llm_feedback": ""
                })


        plan = {
            "files_to_fix": files_to_fix,
            "global_plan": {
                "summary": raw_plan.get("strategy", "No summary")
            }
        }

        self.memory.save_context(
            {"input": "Final global refactoring plan"},
            {"output": json.dumps(plan, indent=2)}
        )

        return plan

    # ─────────────────────────────────────────────────────────────
    # Main iterative loop
    # ─────────────────────────────────────────────────────────────
    def run(self, target_dir: str) -> Dict[str, Any]:
        iteration = 0
        success = False
        history = []
        final_status = "MAX_ITERATIONS_REACHED"

        print("🔍 Generating initial dependency-based plan...")
        self.generate_initial_plan_from_graph()

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n===== ITERATION {iteration}/{self.max_iterations} =====")

            print("📋 Auditing files...")
            self.audit_files()

            print("🧠 Building consolidated refactoring plan...")
            global_plan = self.build_global_plan_from_memory()

            print("🛠 Applying fixes...")
            fix_result = self.fixer.apply_refactoring_plan(global_plan)

            # Run tests & lint
            print("⚖️ Running tests & lint...")
            pytest_output = run_pytest(target_dir)
            pylint_output = run_pylint(target_dir)

            judgement = self.judge.evaluate(pytest_output, pylint_output)

            # Save to history
            history.append({
                "iteration": iteration,
                "fix_status": fix_result.get("overall_status", "UNKNOWN"),
                "judge_decision": judgement["decision"],
                "judge_reason": judgement["reason"]
            })

            # Immediate per-iteration output
            print(f"\n✅ Iteration {iteration} Summary:")
            print(f"Fix status     : {fix_result.get('overall_status', 'UNKNOWN')}")
            print(f"Judge decision : {judgement['decision']}")
            print(f"Judge reason   : {judgement['reason']}")

            # Log iteration
            log_experiment(
                agent_name="Pipeline-Orchestrator",
                model_used=os.getenv("HF_MODEL", "unknown"),
                action=ActionType.ANALYSIS,
                details={
                    "iteration": iteration,
                    "decision": judgement["decision"],
                    "judge_reason": judgement.get("reason", ""),
                    "input_prompt": "Pipeline orchestrating audit/fix/judge cycle",
                    "output_response": f"Fix summary: {fix_result.get('overall_status', 'UNKNOWN')}"
                },
                status=judgement["decision"]
            )

            if judgement["decision"] == "SUCCESS":
                success = True
                final_status = "SUCCESS"
                print("\n🎉 Pipeline succeeded, stopping iterations.")
                break

        return {
            "status": final_status,
            "success": success,
            "iterations": iteration,
            "history": history,
        }


# ─────────────────────────────────────────────────────────────
# Helper for main.py
# ─────────────────────────────────────────────────────────────
def run_refactoring_pipeline(
    target_dir: str,
    auditor_prompt: str,
    fixer_prompt: str,
    judge_prompt: str,
    files: List[Path],
    max_iterations: int = 8,
) -> Dict[str, Any]:
    pipeline = RefactoringPipeline(
        target_dir=target_dir,
        auditor_prompt_path=auditor_prompt,
        fixer_prompt_path=fixer_prompt,
        judge_prompt_path=judge_prompt,
        files=files,
        max_iterations=max_iterations,
    )
    return pipeline.run(target_dir)
