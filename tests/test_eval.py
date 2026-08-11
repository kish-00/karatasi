from __future__ import annotations

import json

import pytest

from tests.conftest import GOLD_PATH, REAL_DB
from eval.run_eval import normalize, run


def test_normalize_sorts_and_rounds() -> None:
    values = [{"currency": "XOF", "value": 4605540.1234}, {"currency": "USD", "value": 12673.0}]
    assert normalize(values) == [("USD", 12673.0), ("XOF", 4605540.123)]


def test_normalize_count_currency_default() -> None:
    assert normalize([{"value": 4}]) == [("count", 4.0)]
    assert normalize([]) == []


def test_normalize_mixed_currencies_grouped() -> None:
    values = [
        {"currency": "XOF", "value": 2952950.0},
        {"currency": "USD", "value": 14012.8},
    ]
    assert normalize(values) == [("USD", 14012.8), ("XOF", 2952950.0)]


@pytest.mark.skipif(not REAL_DB.exists(), reason="data/smebrief.db not built")
def test_eval_scores_50_of_50_on_real_db() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    results, passed = run(GOLD_PATH, REAL_DB)
    assert passed == len(gold) == 50
    failed = [r for r in results if not r["ok"]]
    assert failed == [], f"eval failures: {[r['id'] for r in failed]}"


@pytest.mark.skipif(not REAL_DB.exists(), reason="data/smebrief.db not built")
def test_eval_answers_carry_source_files() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    results, _ = run(GOLD_PATH, REAL_DB)
    for item, result in zip(gold, results):
        assert set(result["got_files"]) == set(item.get("gold_files") or []), item["id"]
