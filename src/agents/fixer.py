from pathlib import Path
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

from src.utils.logger import log_experiment, ActionType
from src.tools.file_tools import read_file, write_file

load_dotenv()

class FixerAgent:
    def __init__(self, prompt_path: str):
        self.prompt_path = Path(prompt_path)
        self.system_prompt = self._load_prompt()

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("❌ GOOGLE_API_KEY not found in .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            os.getenv("GOOGLE_MODEL"),
            generation_config={"temperature": 0.15}  # more deterministic
        )

    def _load_prompt(self) -> str:
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Fixer prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    def _ask_llm(self, plan: dict, current_code: str) -> str:
        plan_json = json.dumps(plan, indent=2, ensure_ascii=False)

        full_prompt = (
            self.system_prompt
            .replace("{PLAN}", plan_json)
            .replace("{CODE}", current_code)
            .replace("{LATEST_PYTEST}", plan.get("latest_pytest_output", "[no output]"))
            .replace("{LATEST_PYLINT}", plan.get("latest_pylint_output", "[no output]"))
        )

        # Safety truncation
        if len(full_prompt) > 180_000:
            full_prompt = full_prompt[:175_000] + "\n\n[PROMPT WAS TRUNCATED DUE TO LENGTH LIMIT]"

        try:
            response = self.model.generate_content(full_prompt)
            text = response.text.strip()

            # Better code block extraction
            if "```python" in text:
                return text.split("```python", 1)[1].rsplit("```", 1)[0].strip()
            if "```" in text:
                parts = text.split("```", 2)
                if len(parts) >= 3:
                    return parts[1].strip()
            return text

        except Exception as e:
            raise RuntimeError(f"LLM fixing failed: {str(e)}")

    def fix_file(self, file_path: str, refactoring_plan: dict) -> dict:
        try:
            current_code = read_file(file_path)
        except Exception as e:
            return {
                "file": file_path,
                "status": "FAIL",
                "error": f"Failed to read file: {str(e)}",
                "changes_applied": False
            }

        # Prefer judge's concrete suggestion when available
        judge_suggestion = refactoring_plan.get("judge_suggested_fix", "")
        if judge_suggestion and len(judge_suggestion.strip()) > 30:
            print(f"  → Using judge's suggested fix for {file_path}")
            fixed_code = judge_suggestion
        else:
            try:
                fixed_code = self._ask_llm(refactoring_plan, current_code)
            except Exception as e:
                return {
                    "file": file_path,
                    "status": "FAIL",
                    "error": str(e),
                    "changes_applied": False
                }

        # Minimal sanity check
        if len(fixed_code.strip()) < 20:
            print(f"Warning: LLM returned almost empty code for {file_path} → keeping original")
            fixed_code = current_code

        try:
            write_file(file_path, fixed_code)
        except Exception as e:
            return {
                "file": file_path,
                "status": "FAIL",
                "error": f"Failed to write file: {str(e)}",
                "changes_applied": False
            }

        report = {
            "agent": "FixerAgent",
            "file": file_path,
            "status": "SUCCESS",
            "original_size": len(current_code),
            "fixed_size": len(fixed_code),
            "changes_applied": fixed_code != current_code,
            "plan_summary": refactoring_plan.get("global_plan", {}).get("summary", "No summary")
        }

        # ---- Log the audit (MANDATORY FORMAT) ----
        log_experiment(
            agent_name="FixerAgent",
            model_used=os.getenv("GOOGLE_MODEL"),
            action=ActionType.FIX,
            details={
                "file": file_path,
                "changes_made": report["changes_applied"],
                "original_length": len(current_code),
                "new_length": len(fixed_code),
                # --- ADD THESE TWO LINES ---
                "input_prompt": self.system_prompt, 
                "output_response": fixed_code 
            },
            status="SUCCESS"
        )

        return report

    def apply_refactoring_plan(self, plan_data: dict) -> dict:
        files_to_fix = plan_data.get("files_to_fix", [])
        global_plan = plan_data.get("global_plan", {})

        results = []
        successful = 0
        failed = 0

        for file_info in files_to_fix:
            path = file_info.get("path")
            if not path or not Path(path).is_file():
                continue

            file_specific_plan = {
                **global_plan,
                **file_info,  # merge judge info, issues, suggestions, etc.
                "file_path": path,
            }

            result = self.fix_file(path, file_specific_plan)
            results.append(result)

            if result["status"] == "SUCCESS":
                successful += 1
            else:
                failed += 1

        summary = {
            "agent": "FixerAgent",
            "total_files": len(files_to_fix),
            "successful": successful,
            "failed": failed,
            "overall_status": "COMPLETE" if failed == 0 else "PARTIAL_SUCCESS" if successful > 0 else "FAILURE",
            "file_results": [r["file"] for r in results]
        }

        return summary