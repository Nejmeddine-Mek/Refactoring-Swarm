from pathlib import Path
import os
import google.generativeai as genai
from dotenv import load_dotenv
from src.utils.logger import log_experiment, ActionType

load_dotenv()

class AuditorAgent:
    """
    Auditor Agent
    -------------
    Reviews code using:
    - rule-based security checks
    - LLM analysis (Gemini)
    """

    def __init__(self, prompt_path: str):
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
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Auditor prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    # --------------------------
    # Call Gemini
    # --------------------------
    def _ask_llm(self, code: str) -> str:
       full_prompt = f"""
   {self.system_prompt}
   
   --- CODE TO AUDIT ---
   {code}
   """
       try:
           response = self.model.generate_content(full_prompt)
           return response.text
       except Exception as e:
           return f"[LLM unavailable] {str(e)}"




    # --------------------------
    # Main audit function
    # --------------------------
    def audit(self, file_path: str, code: str, require_logging: bool = True) -> dict:
        issues = []
        suggestions = []
    
        # ---- Basic security checks ----
        forbidden_keywords = [
            "os.system",
            "subprocess",
            "eval(",
            "exec(",
            "pickle.loads",
            "__import__",
        ]
    
        for keyword in forbidden_keywords:
            if keyword in code:
                issues.append(f"Forbidden usage detected: {keyword}")
                suggestions.append(
                    f"Remove or replace `{keyword}` with a safe alternative."
                )
    
        # ---- Logging format check (optional) ----
        if require_logging and "log_experiment" not in code:
            issues.append("No logging detected with log_experiment.")
            suggestions.append(
                "Add log_experiment calls to track agent actions."
            )
    
        # ---- Encoding / file safety ----
        if "\x00" in code:
            issues.append("Null byte detected in file.")
            suggestions.append(
                "Clean file encoding and remove binary content."
            )
    
        # ---- LLM audit ----
        llm_feedback = self._ask_llm(code)
    
        # ---- Final status ----
        status = "PASS" if not issues else "FAIL"
    
        report = {
            "agent": "AuditorAgent",
            "file": file_path,
            "status": status,
            "issues": issues,
            "suggestions": suggestions,
            "llm_feedback": llm_feedback,
        }
    
        # ---- Log the audit (MANDATORY FORMAT) ----
        log_experiment(
            agent_name="AuditorAgent",
            model_used="gemini-2.5-flash",
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": self.system_prompt,
                "output_response": report,
            },
            status="SUCCESS" if status == "PASS" else "REVIEW",
        )
    
        return report
    