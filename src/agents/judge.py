from pathlib import Path
import os
import json
import re
from typing import Dict

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from src.utils.logger import log_experiment, ActionType

load_dotenv()


class JudgeAgent:
    """
    JudgeAgent evaluates overall code quality using pytest & pylint output.
    It returns structured decisions usable by the pipeline and FixerAgent.
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

        self.client = InferenceClient(
            model=self.model_name,
            token=hf_token
        )

    # ─────────────────────────────────────────────────────────────
    # Prompt loader
    # ─────────────────────────────────────────────────────────────
    def _load_prompt(self) -> str:
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Judge prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    # ─────────────────────────────────────────────────────────────
    # Robust JSON parsing from LLM output
    # ─────────────────────────────────────────────────────────────
    def _parse_llm_json(self, llm_text: str) -> Dict:
        """
        Attempt to extract valid JSON from LLM output.
        Fallbacks are deterministic and pipeline-safe.
        """
        # 1. Direct parse
        try:
            return json.loads(llm_text)
        except Exception:
            pass

        # 2. Extract JSON object from text
        try:
            match = re.search(r"\{[\s\S]*\}", llm_text)
            if not match:
                raise ValueError("No JSON object found")

            cleaned = match.group(0)
            cleaned = cleaned.replace("“", '"').replace("”", '"')

            return json.loads(cleaned)
        except Exception:
            return {
                "decision": "RETRY",
                "reason": "Unable to parse LLM output as JSON",
                "suggested_fix": "",
                "failed_files": [],
            }

    # ─────────────────────────────────────────────────────────────
    # LLM call
    # ─────────────────────────────────────────────────────────────
    def _ask_llm(self, pytest_output: str, pylint_output: str) -> str:
        """
        Ask the LLM to evaluate pytest & pylint output.
        """
        user_prompt = (
            self.system_prompt
            .replace("{PYTEST}", pytest_output)
            .replace("{PYLINT}", pylint_output)
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=600,
                temperature=0.1,
            )

            text = response.choices[0].message.content.strip()

            # Remove code fences if present
            if text.startswith("```") and text.endswith("```"):
                text = "\n".join(text.split("\n")[1:-1]).strip()

            return text

        except Exception as e:
            return json.dumps({
                "decision": "RETRY",
                "reason": f"LLM call failed: {str(e)}",
                "suggested_fix": "",
                "failed_files": [],
            })

    # ─────────────────────────────────────────────────────────────
    # Main evaluation entry point
    # ─────────────────────────────────────────────────────────────
    def evaluate(self, pytest_output: str, pylint_output: str) -> dict:
        """
        Evaluate the code quality after an iteration.
        Ignores cosmetic/style issues (docstrings, import order, spacing),
        and focuses only on real errors, test failures, or forbidden code.
        Always returns a reason for the decision.
        """
        # --- Ask LLM for judgment ---
        llm_feedback = self._ask_llm(pytest_output, pylint_output)
    
        # --- Parse LLM JSON safely ---
        try:
            parsed = self._parse_llm_json(llm_feedback)
            decision = parsed.get("decision", "RETRY")
            reason = parsed.get("reason", "")
            suggested_fix = parsed.get("suggested_fix", "")
        except Exception:
            decision = "RETRY"
            reason = "Judge could not parse LLM output"
            suggested_fix = "Check pytest and pylint outputs"
    
        # --- Filter out cosmetic pylint warnings ---
        def _filter_pylint_output(output: str) -> str:
            ignore_codes = [
                "C0114",  # missing module docstring
                "C0115",  # missing class docstring
                "C0116",  # missing function docstring
                "C0301",  # line too long
                "C0411",  # wrong import order
                "C0330",  # bad spacing
            ]
            filtered_lines = [
                line for line in output.split("\n")
                if not any(code in line for code in ignore_codes)
            ]
            return "\n".join(filtered_lines)
    
        filtered_pylint = _filter_pylint_output(pylint_output)
    
        # --- Decide based on tests and critical errors only ---
        if decision != "SUCCESS":
            if "error" in filtered_pylint.lower() or "fail" in pytest_output.lower():
                decision = "RETRY"
                reason = (
                    f"Tests or critical issues remain.\n"
                    f"Pytest output:\n{pytest_output}\n"
                    f"Pylint critical issues:\n{filtered_pylint}"
                )
            else:
                decision = "SUCCESS"
                reason = "Tests pass and only cosmetic linting issues remain (ignored)."
    
        # Ensure reason is always set
        if not reason:
            reason = "No issues detected."
    
        # --- Build report ---
        report = {
            "agent": "JudgeAgent",
            "decision": decision,
            "reason": reason,
            "suggested_fix": suggested_fix,
            "llm_feedback": llm_feedback,
        }
    
        # --- Log ---
        log_experiment(
            agent_name="JudgeAgent",
            model_used=self.model_name,
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": self.system_prompt,
                "output_response": report,
            },
            status="SUCCESS" if decision == "SUCCESS" else "REVIEW",
        )
    
        return report
