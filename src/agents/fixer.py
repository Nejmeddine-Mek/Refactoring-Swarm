from pathlib import Path
import os
import json
import ast
from typing import Dict

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from src.utils.logger import log_experiment, ActionType
from src.tools.file_tools import read_file, write_file

load_dotenv()


class FixerAgent:
    """
    FixerAgent applies targeted refactoring based on a structured plan.
    It fixes all functional and style issues, including broken Python code.
    """

    def __init__(self, prompt_path: str):
        self.prompt_path = Path(prompt_path)
        self.system_prompt = self._load_prompt()

        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            raise EnvironmentError("❌ HF_TOKEN not found in .env")
        self.model_name = os.getenv("HF_MODEL")
        if not self.model_name:
            raise EnvironmentError("❌ HF_MODEL not set in .env")

        self.client = InferenceClient(model=self.model_name, token=hf_token)

    def _load_prompt(self) -> str:
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Fixer prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    def _ask_llm(self, plan: Dict, current_code: str) -> str:
        """
        Ask LLM to apply the refactoring plan.
        The prompt is loaded from file and placeholders {PLAN} and {CODE} are replaced.
        Returns only the fixed code as string.
        """
        plan_json = json.dumps(plan, indent=2, ensure_ascii=False)
        prompt_to_use = self.system_prompt.replace("{PLAN}", plan_json).replace("{CODE}", current_code)

        # Safety truncation
        if len(prompt_to_use) > 180_000:
            prompt_to_use = prompt_to_use[:175_000] + "\n\n[PROMPT TRUNCATED]"
            
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt_to_use}
            ],
            max_tokens=1000,
            temperature=0.1
        )
        text = response.choices[0].message.content.strip()
        # Remove code fences if LLM added them
        if text.startswith("```") and text.endswith("```"):
            text = text.strip("```").strip()
        return text

       
    def _validate_code(self, code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def fix_file(self, file_path: str, refactoring_plan: Dict) -> Dict:
        """
        Fix a single file according to the refactoring plan.
        Always writes the fixed file to disk.
        """
        try:
            current_code = read_file(file_path)
        except Exception:
            current_code = ""  # fallback if file cannot be read

        # Prefer judge suggestion if valid and reasonably long
        judge_fix = refactoring_plan.get("judge_suggested_fix")
        if isinstance(judge_fix, str) and len(judge_fix.strip()) > 20 and self._validate_code(judge_fix):
            fixed_code = judge_fix
        else:
            fixed_code = self._ask_llm(refactoring_plan, current_code)

    
        # Always write to file
        write_file(file_path, fixed_code)
        changes_applied = fixed_code != current_code

        return {
            "agent": "FixerAgent",
            "file": file_path,
            "status": "SUCCESS",
            "changes_applied": changes_applied,
            "original_size": len(current_code),
            "fixed_size": len(fixed_code)
        }

    def apply_refactoring_plan(self, plan_data: Dict) -> Dict:
        """
        Apply refactoring plan to all files.
        Returns a summary dict with results per file.
        """
        files_to_fix = plan_data.get("files_to_fix", [])
        global_plan = plan_data.get("global_plan", {})

        results = []
        successful = 0
        failed = 0

        for file_info in files_to_fix:
            if isinstance(file_info, str):
                file_info = {"path": file_info}

            path = file_info.get("path")
            if not path or not Path(path).is_file():
                continue

            file_plan = {**global_plan, **file_info, "file_path": path}
            result = self.fix_file(path, file_plan)
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
            "overall_status": (
                "COMPLETE"
                if failed == 0
                else "PARTIAL_SUCCESS"
                if successful > 0
                else "FAILURE"
            ),
            "file_results": results
        }

        return summary
