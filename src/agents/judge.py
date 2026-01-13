# judge_agent.py
from pathlib import Path
import os
import google.generativeai as genai
from dotenv import load_dotenv
from src.utils.logger import log_experiment, ActionType
import json
import re

load_dotenv()

class JudgeAgent:
    def __init__(self, prompt_path: str):
        self.prompt_path = Path(prompt_path)
        self.system_prompt = self._load_prompt()

        # ---- Gemini configuration ----
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("❌ GOOGLE_API_KEY not found in .env")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(os.getenv("GOOGLE_MODEL"))

    def _parse_llm_json(self, llm_text: str) -> dict:
        import json, re
    
        # Try direct JSON first
        try:
            return json.loads(llm_text)
        except Exception:
            pass
    
        # Try to extract JSON block
        try:
            match = re.search(r'\{[\s\S]*\}', llm_text)
            if not match:
                raise ValueError("No JSON found")
    
            cleaned = match.group(0)
    
            # Remove smart quotes if any
            cleaned = cleaned.replace("“", '"').replace("”", '"')
    
            return json.loads(cleaned)
        except Exception:
            return {
                "decision": "RETRY",
                "reason": "Could not parse LLM output",
                "suggested_fix": "Check pytest and pylint outputs"
            }
    
    # --------------------------
    # Prompt loader
    # --------------------------
    def _load_prompt(self) -> str:
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Judge prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    # --------------------------
    # Call Gemini
    # --------------------------
    def _ask_llm(self, pytest_output: str, pylint_output: str) -> str:
        full_prompt = self.system_prompt.replace("{PYTEST}", pytest_output).replace("{PYLINT}", pylint_output)
        response = self.model.generate_content(full_prompt)
        text = response.text.strip()
    
        # Remove code fences or extra newlines
        if text.startswith("```") and text.endswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
    
        # Remove any leading/trailing non-brace characters
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
    
        return text



    # --------------------------
    # Main evaluation function
    # --------------------------
    def evaluate(self, pytest_output: str, pylint_output: str) -> dict:
        llm_feedback = self._ask_llm(pytest_output, pylint_output)

        # Basic JSON parsing attempt (if LLM returned valid JSON)
        decision = "RETRY"
        reason = "Could not parse LLM output"
        suggested_fix = "Check pytest and pylint outputs"

        try:
            import json
            parsed = self._parse_llm_json(llm_feedback)
            decision = parsed.get("decision", "RETRY")
            reason = parsed.get("reason", "")
            suggested_fix = parsed.get("suggested_fix", "")

        except Exception:
            # Keep default RETRY if parsing fails
            pass

        report = {
            "agent": "JudgeAgent",
            "decision": decision,
            "reason": reason,
            "suggested_fix": suggested_fix,
            "llm_feedback": llm_feedback,
        }

        # ---- Log the evaluation ----
        log_experiment(
            agent_name="JudgeAgent",
            model_used="gemini-2.5-flash",
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": self.system_prompt,
                "output_response": report,
            },
            status="SUCCESS" if decision == "SUCCESS" else "REVIEW",
        )

        return report
