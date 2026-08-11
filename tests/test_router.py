from __future__ import annotations

import pytest

from tests.conftest import REAL_DB
from src.retrieval.router import QueryRouter
from src.storage.store import FinanceStore


@pytest.fixture(scope="module")
def router() -> QueryRouter:
    store = FinanceStore(REAL_DB)
    try:
        return QueryRouter(store)
    finally:
        pass


def _normalize(values: list[dict]) -> list[tuple[str, float]]:
    return sorted(
        (v.get("currency", "count"), round(float(v.get("value", 0.0)), 3))
        for v in (values or [])
    )


@pytest.fixture(scope="module")
def real_db_available() -> bool:
    return REAL_DB.exists()


def test_router_sql_questions_match_gold(gold, router, real_db_available) -> None:
    if not real_db_available:
        pytest.skip("data/smebrief.db not built")
    failures = []
    sql_items = [g for g in gold if g["sql_path"] == "sql"]
    assert len(sql_items) == 46
    for item in sql_items:
        ans = router.answer(item["question"])
        values_ok = _normalize(ans.values) == _normalize(item.get("gold_values") or [])
        files_ok = set(ans.files) == set(item.get("gold_files") or [])
        route_ok = ans.route == "sql"
        if not (values_ok and files_ok and route_ok):
            failures.append(
                (item["id"], item["question"], ans.values, ans.files, ans.route)
            )
    assert failures == [], f"SQL route failures: {failures}"


@pytest.mark.parametrize(
    "category",
    ["numeric_extraction", "temporal", "aggregation", "contract", "multilingual"],
)
def test_router_per_category_sql_accuracy(gold, router, real_db_available, category) -> None:
    if not real_db_available:
        pytest.skip("data/smebrief.db not built")
    items = [g for g in gold if g["category"] == category and g["sql_path"] == "sql"]
    assert items, f"no sql items for {category}"
    failures = []
    for item in items:
        ans = router.answer(item["question"])
        values_ok = _normalize(ans.values) == _normalize(item.get("gold_values") or [])
        files_ok = set(ans.files) == set(item.get("gold_files") or [])
        if not (values_ok and files_ok):
            failures.append((item["id"], item["question"]))
    assert failures == [], f"{category} failures: {failures}"


def test_extract_supplier_matches_canonical_names() -> None:
    from src.retrieval.router import extract_supplier

    assert extract_supplier("payments to africatextiles") == "AfricaTextiles Ltd"
    assert extract_supplier("groupe comptoir de dakar factures") == "Groupe Comptoir de Dakar"
    assert extract_supplier("SENEXPORT SA") == "SENEXPORT SA"
    assert extract_supplier("what is our balance?") is None


def test_extract_period_quarters_and_months() -> None:
    from src.retrieval.router import extract_period

    assert extract_period("in Q2 2024") == ("2024-04-01", "2024-06-30")
    assert extract_period("first quarter") == ("2024-01-01", "2024-03-31")
    assert extract_period("between January and March 2024") == ("2024-01-01", "2024-03-31")
    assert extract_period("in 2024") == ("2024-01-01", "2024-12-31")
    assert extract_period("no time reference") is None


def test_code_regex_matches_invoice_and_receipt_codes() -> None:
    from src.retrieval.router import CODE_RE

    m = CODE_RE.search("how much was invoice AT-2024-0007?")
    assert m is not None and m.group(1).upper() == "AT-2024-0007"
    m = CODE_RE.search("reçu RCP-2024-031")
    assert m is not None and m.group(1).upper() == "RCP-2024-031"
    assert CODE_RE.search("no code here") is None


def test_formatting_helpers() -> None:
    from src.retrieval.router import fmt_amount, fmt_usd, fmt_xof

    assert fmt_xof(1250000) == "1 250 000"
    assert fmt_usd(8120.0) == "8,120.00"
    assert fmt_amount(8120.0, "USD") == "8,120.00"
    assert fmt_amount(1250000, "XOF") == "1 250 000"
