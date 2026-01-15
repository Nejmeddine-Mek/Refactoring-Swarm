from pathlib import Path
import os
import json
import ast
from typing import List, Dict

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

from src.utils.logger import log_experiment, ActionType

load_dotenv()


class AuditorAgent:
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
            raise FileNotFoundError(f"Auditor prompt not found: {self.prompt_path}")
        return self.prompt_path.read_text(encoding="utf-8")

    # ─────────────────────────────────────────────────────────────
    # AST-based forbidden call detection
    # ─────────────────────────────────────────────────────────────
    def _detect_forbidden_calls(self, code: str) -> List[str]:
        forbidden_calls = {"eval", "exec", "__import__", "pickle.loads"}
        issues = []

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = getattr(node.func, "id", None)
                    if func_name in forbidden_calls:
                        issues.append(
                            f"Forbidden call `{func_name}` at line {node.lineno}"
                        )
        except SyntaxError:
            issues.append("Syntax error: unable to parse file")

        return issues

    # ─────────────────────────────────────────────────────────────
    # LLM semantic audit
    # ─────────────────────────────────────────────────────────────
    def _ask_llm(self, code: str) -> Dict:

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": f"Audit the following Python code:\n\n{code}"
                    }
                ],
                max_tokens=800,
                temperature=0.1,
            )

            raw_text = response.choices[0].message.content

            try:
                return json.loads(raw_text)
            except json.JSONDecodeError:
                return {"raw_feedback": raw_text}

        except Exception as e:
            return {"error": f"LLM unavailable: {str(e)}"}

    # ─────────────────────────────────────────────────────────────
    # Main audit entry point
    # ─────────────────────────────────────────────────────────────
    def audit(self, file_path: str, code: str, require_logging: bool = True) -> Dict:
        issues: List[str] = []
        suggestions: List[str] = []
        severity: List[str] = []

        # ── 1. Security checks (HIGH)
        forbidden_issues = self._detect_forbidden_calls(code)
        for issue in forbidden_issues:
            issues.append(issue)
            suggestions.append("Remove or replace forbidden call with a safe alternative.")
            severity.append("HIGH")

        # ── 2. Logging policy check (MEDIUM)
        if require_logging and "log_experiment" not in code:
            issues.append("No logging detected with log_experiment")
            suggestions.append("Add log_experiment calls to track agent actions")
            severity.append("MEDIUM")

        # ── 3. Encoding / file safety (HIGH)
        if "\x00" in code:
            issues.append("Null byte detected in file")
            suggestions.append("Clean file encoding and remove binary content")
            severity.append("HIGH")

        # ── 4. Semantic / architectural LLM review
        llm_feedback = self._ask_llm(code)

        # ── 5. Status resolution (severity-aware)
        if "HIGH" in severity:
            status = "FAIL"
        elif issues:
            status = "WARN"
        else:
            status = "PASS"

        report = {
            "agent": "AuditorAgent",
            "file": file_path,
            "status": status,
            "issues": issues,
            "suggestions": suggestions,
            "severity": severity,
            "llm_feedback": llm_feedback,
        }

        # ── 6. Mandatory logging (AutoCorrect-compatible)
        log_experiment(
            agent_name="AuditorAgent",
            model_used=self.model_name,
            action=ActionType.ANALYSIS,
            details={
                "input_prompt": self.system_prompt,
                "output_response": {
                    "file": file_path,
                    "status": status,
                    "issues": issues,
                    "severity": severity,
                    "llm_summary": llm_feedback,
                },
            },
            status="SUCCESS" if status == "PASS" else "REVIEW",
        )

        # Invariants (defensive)
        assert isinstance(issues, list)
        assert isinstance(suggestions, list)
        assert isinstance(severity, list)

        return report
