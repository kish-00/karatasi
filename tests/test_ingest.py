from __future__ import annotations

import json
from pathlib import Path

from src.ingest.ingest import (
    MAX_CHUNK_CHARS,
    chunk_document,
    chunk_page,
    ingest_manifest,
)
from src.storage.store import FinanceStore


def _tiny_manifest(tmp: Path) -> tuple[Path, Path]:
    docs = tmp / "docs"
    docs.mkdir()
    manifest = tmp / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "invoices": [
                    {
                        "code": "AT-2024-0007",
                        "date": "2024-01-15",
                        "supplier": "AfricaTextiles Ltd",
                        "buyer": "Aya Traoré (Import/Export)",
                        "currency": "USD",
                        "amount": 7000.0,
                        "vat": 1120.0,
                        "vat_rate": 16.0,
                        "total": 8120.0,
                        "paid": True,
                        "paid_date": "2024-01-20",
                        "terms": "Net 30 days",
                        "lang": "en",
                        "scanned": False,
                        "file": "invoice_AT-2024-0007.pdf",
                    }
                ],
                "receipts": [],
                "contracts": [],
                "statements": [],
            }
        ),
        encoding="utf-8",
    )
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "INVOICE AT-2024-0007 total 8120.00 USD paid")
    pdf.save(str(docs / "invoice_AT-2024-0007.pdf"))
    pdf.close()
    return manifest, docs


def test_ingest_populates_db(tmp_path) -> None:
    manifest, docs = _tiny_manifest(tmp_path)
    db = tmp_path / "t.db"
    counts = ingest_manifest(manifest, docs, db, force=True)
    assert counts["documents"] == 1
    assert counts["invoices"] == 1
    assert counts["chunks"] >= 1


def test_ingest_without_force_is_noop_on_populated_db(tmp_path) -> None:
    manifest, docs = _tiny_manifest(tmp_path)
    db = tmp_path / "t.db"
    first = ingest_manifest(manifest, docs, db, force=True)
    second = ingest_manifest(manifest, docs, db, force=False)
    assert second == first, "re-ingest without --force must not change the DB"

    store = FinanceStore(db)
    n_chunks = store.run_sql("SELECT COUNT(*) AS n FROM chunks")[0]["n"]
    n_docs = store.count_documents()
    store.close()
    assert n_chunks == first["chunks"]
    assert n_docs == first["documents"]


def test_ingest_force_rebuilds_cleanly(tmp_path) -> None:
    manifest, docs = _tiny_manifest(tmp_path)
    db = tmp_path / "t.db"
    first = ingest_manifest(manifest, docs, db, force=True)
    rebuilt = ingest_manifest(manifest, docs, db, force=True)
    assert rebuilt == first, "force rebuild must produce identical counts"


def test_chunk_page_respects_max_chars() -> None:
    chunks = chunk_page("a" * (MAX_CHUNK_CHARS - 5) + "\n" + "b" * 10, 1, "en")
    assert all(len(c["text"]) <= MAX_CHUNK_CHARS for c in chunks)


def test_chunk_page_preserves_lines() -> None:
    chunks = chunk_page("line one\nline two\nline three", 1, "en")
    assert len(chunks) == 1
    assert chunks[0]["text"].splitlines() == ["line one", "line two", "line three"]


def test_chunk_document_global_idx_across_pages() -> None:
    chunks = chunk_document(["hello world", "second page"], "en")
    idxs = [c["chunk_idx"] for c in chunks]
    assert idxs == list(range(len(chunks)))
    assert [c["page"] for c in chunks] == [1, 2]
