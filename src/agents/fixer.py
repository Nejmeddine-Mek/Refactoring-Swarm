# src/agents/fixer.py
"""
Fixer Agent for the Refactoring Swarm system.
Takes a refactoring plan from the Auditor and applies code fixes.
"""

from pathlib import Path
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from src.utils.logger import log_experiment, ActionType
from src.tools.file_tools import read_file, write_file

load_dotenv()

class FixerAgent:
    """
    Fixer Agent
    -----------
    Applies refactoring plans to fix and improve Python code.
    Reads plans from Auditor and modifies code accordingly.
    """

    def __init__(self, prompt_path: str):
        """
        Initialize the Fixer Agent.
        
        Args:
            prompt_path: Path to the fixer prompt file
        """
        self.prompt_path = Path(prompt_path)
        self.system_prompt = self._load_prompt()

        # ---- Gemini configuration ----
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("❌ GOOGLE_API_KEY not found in .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    # --------------------------
    # Prompt loader
    # --------------------------
    def _load_prompt(self) -> str:
        """Load the fixer prompt from file."""
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Fixer prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    # --------------------------
    # Call Gemini for fixing
    # --------------------------
    def _ask_llm(self, plan: dict, current_code: str) -> str:
        """
        Send plan and code to LLM for fixing.
        
        Args:
            plan: Refactoring plan from Auditor (dict)
            current_code: Current content of the file
            
        Returns:
            str: Fixed code content
        """
        # Format plan as JSON string for the prompt
        plan_str = json.dumps(plan, indent=2)
        
        # Prepare full prompt with placeholders
        full_prompt = self.system_prompt.replace("{PLAN}", plan_str).replace("{CODE}", current_code)
        
        try:
            response = self.model.generate_content(full_prompt)
            fixed_code = response.text.strip()
            
            # Clean up response (remove any markdown, keep only code)
            if fixed_code.startswith("```python"):
                fixed_code = "\n".join(fixed_code.split("\n")[1:-1])
            elif fixed_code.startswith("```"):
                fixed_code = "\n".join(fixed_code.split("\n")[1:-1])
            
            return fixed_code
        except Exception as e:
            error_msg = f"LLM fixing failed: {str(e)}"
            raise RuntimeError(error_msg)

    # --------------------------
    # Apply fixes to a single file
    # --------------------------
    def fix_file(self, file_path: str, refactoring_plan: dict) -> dict:
        """
        Apply refactoring plan to a specific file.
        
        Args:
            file_path: Path to the file to fix
            refactoring_plan: Refactoring plan from Auditor
            
        Returns:
            dict: Report of the fixing operation
        """
        # Read current file content
        try:
            current_code = read_file(file_path)
        except Exception as e:
            return {
                "agent": "FixerAgent",
                "file": file_path,
                "status": "FAIL",
                "error": f"Failed to read file: {str(e)}",
                "changes_applied": False
            }
        
        # Get fixed code from LLM
        try:
            fixed_code = self._ask_llm(refactoring_plan, current_code)
            
            # Write fixed code back to file
            write_file(file_path, fixed_code)
            
            # Prepare report
            report = {
                "agent": "FixerAgent",
                "file": file_path,
                "status": "SUCCESS",
                "original_size": len(current_code),
                "fixed_size": len(fixed_code),
                "changes_applied": True,
                "plan_summary": refactoring_plan.get("summary", "No summary"),
                "issues_addressed": refactoring_plan.get("issues", [])
            }
            
            # Log the fixing action
            log_experiment(
                agent_name="FixerAgent",
                model_used="gemini-2.5-flash",
                action=ActionType.FIX,
                details={
                    "file_fixed": file_path,
                    "input_prompt": self.system_prompt.replace("{PLAN}", json.dumps(refactoring_plan, indent=2)).replace("{CODE}", current_code[:500] + "..." if len(current_code) > 500 else current_code),
                    "output_response": fixed_code[:500] + "..." if len(fixed_code) > 500 else fixed_code,
                    "plan_summary": refactoring_plan.get("summary", "No summary"),
                    "original_length": len(current_code),
                    "fixed_length": len(fixed_code)
                },
                status="SUCCESS"
            )
            
            return report
            
        except Exception as e:
            error_report = {
                "agent": "FixerAgent",
                "file": file_path,
                "status": "FAIL",
                "error": str(e),
                "changes_applied": False
            }
            
            # Log the failure
            log_experiment(
                agent_name="FixerAgent",
                model_used="gemini-2.5-flash",
                action=ActionType.FIX,
                details={
                    "file_fixed": file_path,
                    "input_prompt": self.system_prompt.replace("{PLAN}", json.dumps(refactoring_plan, indent=2)).replace("{CODE}", current_code[:500] + "..." if len(current_code) > 500 else current_code),
                    "output_response": f"Error: {str(e)}",
                    "plan_summary": refactoring_plan.get("summary", "No summary")
                },
                status="FAILURE"
            )
            
            return error_report

    # --------------------------
    # Apply fixes to multiple files
    # --------------------------
    def apply_refactoring_plan(self, plan_data: dict) -> dict:
        """
        Apply a complete refactoring plan across multiple files.
        
        Args:
            plan_data: Complete refactoring plan from Auditor
            
        Returns:
            dict: Summary of all fixes applied
        """
        files_to_fix = plan_data.get("files_to_fix", [])
        global_plan = plan_data.get("global_plan", {})
        
        results = []
        successful = 0
        failed = 0
        
        for file_info in files_to_fix:
            file_path = file_info.get("path")
            if not file_path:
                continue
                
            # Create file-specific plan
            file_plan = {
                **global_plan,
                "file_specific": file_info.get("issues", []),
                "suggestions": file_info.get("suggestions", []),
                "summary": f"Fix {file_path} based on audit findings"
            }
            
            # Fix the file
            result = self.fix_file(file_path, file_plan)
            results.append(result)
            
            if result.get("status") == "SUCCESS":
                successful += 1
            else:
                failed += 1
        
        # Summary report
        summary = {
            "agent": "FixerAgent",
            "operation": "batch_refactoring",
            "total_files": len(files_to_fix),
            "successful": successful,
            "failed": failed,
            "file_results": results,
            "overall_status": "COMPLETE" if failed == 0 else "PARTIAL"
        }
        
        return summary