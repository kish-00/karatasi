from __future__ import annotations

import json

from tests.conftest import DOCS_DIR, GOLD_PATH, MANIFEST_PATH


def _all_manifest_files(manifest: dict) -> list[str]:
    m = manifest
    return (
        [inv["file"] for inv in m["invoices"]]
        + [r["file"] for r in m["receipts"]]
        + [c["file"] for c in m["contracts"]]
        + [s["file"] for s in m["statements"]]
    )


def test_manifest_meta_counts_match_arrays(manifest) -> None:
    meta = manifest["meta"]["counts"]
    assert meta["invoices"] == len(manifest["invoices"])
    assert meta["receipts"] == len(manifest["receipts"])
    assert meta["contracts"] == len(manifest["contracts"])
    assert meta["statements"] == len(manifest["statements"])
    assert meta["total"] == (
        len(manifest["invoices"]) + len(manifest["receipts"])
        + len(manifest["contracts"]) + len(manifest["statements"])
    )
    assert meta["total"] == 60


def test_manifest_files_are_unique(manifest) -> None:
    files = _all_manifest_files(manifest)
    assert len(files) == len(set(files)), "manifest contains duplicate filenames"


def test_every_manifest_file_exists_on_disk(manifest) -> None:
    missing = [f for f in _all_manifest_files(manifest) if not (DOCS_DIR / f).exists()]
    assert missing == [], f"documents missing on disk: {missing}"


def test_invoice_math_is_internally_consistent(manifest) -> None:
    for inv in manifest["invoices"]:
        amount = round(sum(q * p for _, q, p in inv["items"]), 2)
        vat = round(amount * inv["vat_rate"] / 100, 2)
        assert inv["amount"] == amount
        assert inv["vat"] == vat
        assert inv["total"] == round(amount + vat, 2)


def test_invoice_filenames_match_lang_and_scanned(manifest) -> None:
    for inv in manifest["invoices"]:
        prefix = "facture" if inv["lang"] == "fr" else "invoice"
        suffix = "png" if inv["scanned"] else "pdf"
        expected = f"{prefix}_{inv['code']}.{suffix}"
        assert inv["file"] == expected, inv["file"]


def test_statement_closing_equals_entries_sum(manifest) -> None:
    for s in manifest["statements"]:
        closing = sum(
            e["amount"] if e["kind"] == "invoice" else -e["amount"]
            for e in s["entries"]
        )
        assert abs(closing - s["closing"]) < 1e-6, s["file"]


def test_gold_qa_shape(gold) -> None:
    assert len(gold) == 50
    categories = {g["category"] for g in gold}
    assert categories == {
        "numeric_extraction", "temporal", "aggregation", "contract", "multilingual"
    }
    ids = [g["id"] for g in gold]
    assert len(ids) == len(set(ids)), "duplicate gold question ids"


def test_gold_sql_path_distribution(gold) -> None:
    from collections import Counter

    counts = Counter(g["sql_path"] for g in gold)
    assert counts == {"sql": 46, "semantic": 4}


def test_gold_files_reference_real_manifest_files(gold, manifest) -> None:
    known = set(_all_manifest_files(manifest))
    for g in gold:
        unknown = [f for f in g["gold_files"] if f not in known]
        assert unknown == [], f"{g['id']} references unknown files: {unknown}"


def test_gold_answers_have_source_in_manifest(gold, manifest) -> None:
    known = set(_all_manifest_files(manifest))
    for g in gold:
        assert g["gold_source"] in known, f"{g['id']} bad gold_source {g['gold_source']}"


def test_generator_regenerates_identical_artifacts() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("generator", MANIFEST_PATH.parent / "generator.py")
    gen = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(gen)

    m_regen = gen.build_manifest()
    g_regen = gen.build_gold_qa(m_regen)

    m_disk = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    g_disk = json.loads(GOLD_PATH.read_text(encoding="utf-8"))

    assert m_regen == m_disk, "regenerated manifest differs from committed file"
    assert g_regen == g_disk, "regenerated gold_qa differs from committed file"
