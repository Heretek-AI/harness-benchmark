"""Tests for the model-as-a-judge wrapper."""

from __future__ import annotations

from unittest.mock import patch

from evaluation.judge import ModelJudge


def test_heuristic_fallback_empty() -> None:
    judge = ModelJudge(api_url="")
    result = judge.grade("do something", "", "must be good")
    assert result.passed is False
    assert result.model == "heuristic-fallback"
    assert result.score < 0.5


def test_heuristic_fallback_with_code() -> None:
    judge = ModelJudge(api_url="")
    code = (
        "import os\n"
        "def sort_list(items):\n"
        "    return sorted(items)\n"
        "\n"
        "result = sort_list([3, 1, 2])\n"
        "print(result)\n"
    )
    result = judge.grade("write a sort function", code, "must sort correctly")
    assert result.passed is True
    assert result.score >= 0.5
    assert "heuristic" in result.model


def test_heuristic_fallback_error_penalty() -> None:
    judge = ModelJudge(api_url="")
    bad_output = "Traceback (most recent call last):\n  Error: something broke"
    result = judge.grade("do something", bad_output, "must work")
    assert result.passed is False


def test_parse_judge_response_valid() -> None:
    judge = ModelJudge(api_url="")
    response = '{"score": 0.85, "passed": true, "rationale": "Good solution", "criteria_met": ["correct"], "criteria_failed": []}'
    result = judge._parse_judge_response(response, pass_threshold=0.5)
    assert result.score == 0.85
    assert result.passed is True
    assert result.rationale == "Good solution"


def test_parse_judge_response_in_code_block() -> None:
    judge = ModelJudge(api_url="")
    response = '```json\n{"score": 0.7, "passed": true, "rationale": "OK"}\n```'
    result = judge._parse_judge_response(response, pass_threshold=0.5)
    assert result.score == 0.7
    assert result.passed is True


def test_parse_judge_response_low_score() -> None:
    judge = ModelJudge(api_url="")
    response = '{"score": 0.2, "passed": false, "rationale": "Poor quality"}'
    result = judge._parse_judge_response(response, pass_threshold=0.5)
    assert result.score == 0.2
    assert result.passed is False


def test_parse_judge_response_clamps_score() -> None:
    judge = ModelJudge(api_url="")
    response = '{"score": 1.5, "passed": true, "rationale": "Over"}'
    result = judge._parse_judge_response(response, pass_threshold=0.5)
    assert result.score == 1.0  # clamped

    response2 = '{"score": -0.3, "passed": false, "rationale": "Under"}'
    result2 = judge._parse_judge_response(response2, pass_threshold=0.5)
    assert result2.score == 0.0  # clamped


def test_grade_falls_back_on_llm_error() -> None:
    judge = ModelJudge(api_url="http://invalid-host:99999")
    result = judge.grade("task", "def f(): pass", "rubric")
    assert result.model == "heuristic-fallback"
    assert isinstance(result.score, float)


def test_grade_uses_mocked_llm() -> None:
    mock_response = '{"score": 0.9, "passed": true, "rationale": "Excellent", "criteria_met": ["all"], "criteria_failed": []}'

    judge = ModelJudge(api_url="http://fake-api/v1", model="test-judge")

    with patch.object(judge, "_call_llm", return_value=mock_response):
        result = judge.grade("task", "code here", "rubric")

    assert result.score == 0.9
    assert result.passed is True
    assert result.model == "test-judge"
