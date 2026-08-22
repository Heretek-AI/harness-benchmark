"""Model-as-a-Judge evaluation wrapper.

Calls a configurable LLM to grade free-form agent outputs against a
rubric.  Returns a structured score + rationale that can be consumed
by the runner for composite scoring.

The judge uses any OpenAI-compatible API (including Claude via LiteLLM)
by reading ``LLM_API``, ``LLM_KEY``, and ``LLM_MODEL`` from environment.

Usage::

    from evaluation.judge import ModelJudge

    judge = ModelJudge()  # reads env vars
    result = judge.grade(
        task_description="Write a Python function that sorts a list",
        agent_output="def sort_list(items): return sorted(items)",
        rubric="Function must be named sort_list, must not mutate input, must handle empty lists",
    )
    print(result.score, result.passed, result.rationale)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default judge prompt template
DEFAULT_JUDGE_PROMPT = """\
You are an expert evaluator grading an AI agent's solution to a coding task.

## Task Description
{task_description}

## Agent Output
```
{agent_output}
```

## Grading Rubric
{rubric}

## Instructions
Evaluate the agent's output against the rubric. You MUST respond with a JSON object:
{{
  "score": <float between 0.0 and 1.0>,
  "passed": <true if score >= 0.5, false otherwise>,
  "rationale": "<1-2 sentence explanation of the grade>",
  "criteria_met": ["<list of rubric criteria that were met>"],
  "criteria_failed": ["<list of rubric criteria that were not met>"]
}}

Respond ONLY with the JSON object. No other text.
"""


@dataclass(frozen=True)
class JudgeResult:
    """Structured result from a model-as-judge evaluation."""

    score: float  # 0.0 to 1.0
    passed: bool
    rationale: str
    criteria_met: list[str]
    criteria_failed: list[str]
    model: str  # which model was used as judge


class ModelJudge:
    """Grade agent outputs using a configurable LLM judge."""

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        judge_prompt: str | None = None,
    ) -> None:
        self.api_url = api_url or os.environ.get("LLM_API", "")
        self.api_key = api_key or os.environ.get("LLM_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o")
        self.judge_prompt = judge_prompt or DEFAULT_JUDGE_PROMPT

    def grade(
        self,
        task_description: str,
        agent_output: str,
        rubric: str,
        pass_threshold: float = 0.5,
    ) -> JudgeResult:
        """Grade an agent's output against a rubric using the judge LLM.

        Falls back to a simple heuristic if the LLM call fails.
        """
        prompt = self.judge_prompt.format(
            task_description=task_description,
            agent_output=agent_output[:4000],  # truncate long outputs
            rubric=rubric,
        )

        try:
            response_text = self._call_llm(prompt)
            return self._parse_judge_response(response_text, pass_threshold)
        except Exception as e:
            logger.warning("Judge LLM call failed: %s — using heuristic fallback", e)
            return self._heuristic_fallback(agent_output, pass_threshold)

    def _call_llm(self, prompt: str) -> str:
        """Call the judge LLM via OpenAI-compatible API."""
        import urllib.request

        if not self.api_url:
            raise ValueError("No LLM_API configured for judge")

        url = self.api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"

        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 500,
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return data["choices"][0]["message"]["content"]

    def _parse_judge_response(self, text: str, pass_threshold: float) -> JudgeResult:
        """Parse the JSON response from the judge LLM."""
        # Try to extract JSON from the response
        text = text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the text
            import re
            match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError(f"Could not parse judge response: {text[:200]}")

        score = float(data.get("score", 0.0))
        return JudgeResult(
            score=max(0.0, min(1.0, score)),
            passed=score >= pass_threshold,
            rationale=data.get("rationale", "No rationale provided"),
            criteria_met=data.get("criteria_met", []),
            criteria_failed=data.get("criteria_failed", []),
            model=self.model,
        )

    def _heuristic_fallback(self, agent_output: str, pass_threshold: float) -> JudgeResult:
        """Simple heuristic when the LLM judge is unavailable."""
        output = agent_output.strip()
        score = 0.0

        # Basic heuristics
        if len(output) > 50:
            score += 0.2
        if len(output) > 200:
            score += 0.1
        if "def " in output or "function" in output:
            score += 0.2
        if "return " in output:
            score += 0.1
        if "import " in output:
            score += 0.1
        if "class " in output:
            score += 0.1
        # Penalty for errors
        if "error" in output.lower() or "traceback" in output.lower():
            score -= 0.3

        score = max(0.0, min(1.0, score))
        return JudgeResult(
            score=score,
            passed=score >= pass_threshold,
            rationale=f"Heuristic fallback (LLM unavailable): score {score:.2f}",
            criteria_met=[],
            criteria_failed=[],
            model="heuristic-fallback",
        )
