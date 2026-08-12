"""Ingest the synthetic corpus into FinanceStore.

Reads data/synthetic/manifest.json (the single source of truth) and
loads every document into the SQLite + sqlite-vec store:

  1. `documents` row        — via upsert_document (type/lang/date/page_count)
  2. structured financial   — set_invoice / set_receipt / set_contract /
     row                      set_statement (deterministic SQL answers)
  3. text chunks + vectors  — PDF text via PyMuPDF, scanned PNGs via
                             Tesseract; chunks embedded with
                             multilingual-e5-small (384-dim)

Run:  venv/bin/python -m src.ingest [--db PATH] [--force]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from src.embeddings import embed_documents
from src.storage.store import FinanceStore

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parents[2]  # repo root
DEFAULT_MANIFEST = BASE / "data" / "synthetic" / "manifest.json"
DEFAULT_DOCS = BASE / "data" / "synthetic" / "documents"
DEFAULT_DB = BASE / "data" / "smebrief.db"
TESSERACT_CMD = BASE / "venv" / "bin" / "tesseract"

MAX_CHUNK_CHARS = 500  # hard cap per chunk (soft split at line boundaries)


# ── Text extraction ─────────────────────────────────────────────────

def extract_pdf_text(path: Path) -> list[str]:
    """Return per-page text of a PDF (PyMuPDF)."""
    import fitz

    pages: list[str] = []
    with fitz.open(str(path)) as doc:
        for page in doc:
            pages.append(page.get_text())
    return pages


def extract_image_text(path: Path) -> list[str]:
    """OCR a scanned photo (Tesseract).

    Prefers a venv-bundled tesseract at venv/bin/tesseract (with its libs
    and tessdata pinned via env vars), but transparently falls back to a
    system tesseract on PATH so ingest works after a venv rebuild without
    manual symlinks.
    """
    import os

    import pytesseract
    from PIL import Image

    if TESSERACT_CMD.exists():
        # venv-bundled binary: pin libs + tessdata to the venv so the
        # subprocess resolves libtesseract/liblept and eng.traineddata.
        lib_dirs = [str(BASE / "venv" / "lib"), str(BASE / "venv" / "lib" / "x86_64-linux-gnu")]
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = ":".join(d for d in [*lib_dirs, existing] if d)
        os.environ["TESSDATA_PREFIX"] = str(BASE / "venv" / "share" / "tessdata")
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)
    else:
        # System tesseract on PATH: clear any stale venv tessdata pin so it
        # falls back to its compiled-in data directory.
        stale = os.environ.get("TESSDATA_PREFIX", "")
        if stale and not Path(stale).exists():
            os.environ.pop("TESSDATA_PREFIX", None)
        pytesseract.pytesseract.tesseract_cmd = "tesseract"

    with Image.open(path) as img:
        text = pytesseract.image_to_string(img)
    return [text] if text.strip() else []


def extract_text(path: Path) -> list[str]:
    """Per-page text for a document file (PDF or scanned PNG)."""
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    return extract_image_text(path)


# ── Chunking ────────────────────────────────────────────────────────

def chunk_page(text: str, page: int, lang: str, chunk_idx_offset: int = 0) -> list[dict[str, Any]]:
    """Split one page's text into chunks at line boundaries (≤ MAX_CHUNK_CHARS).

    Preserves line structure for invoice/receipt/contract text; a chunk
    never cuts mid-line.
    """
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    chunks: list[dict[str, Any]] = []
    buf: list[str] = []
    size = 0
    for ln in lines:
        if buf and size + len(ln) + 1 > MAX_CHUNK_CHARS:
            chunks.append(
                dict(page=page, chunk_idx=chunk_idx_offset + len(chunks),
                     lang=lang, text="\n".join(buf))
            )
            buf, size = [], 0
        buf.append(ln)
        size += len(ln) + 1
    if buf:
        chunks.append(
            dict(page=page, chunk_idx=chunk_idx_offset + len(chunks),
                 lang=lang, text="\n".join(buf))
        )
    return chunks


def chunk_document(pages: list[str], lang: str) -> list[dict[str, Any]]:
    """Chunk all pages of one document; chunk_idx is global across pages."""
    chunks: list[dict[str, Any]] = []
    for i, page_text in enumerate(pages):
        chunks.extend(chunk_page(page_text, i + 1, lang, len(chunks)))
    return chunks


# ── Per-type loaders ────────────────────────────────────────────────

def _upsert_with_chunks(
    store: FinanceStore,
    *,
    file: str,
    doc_type: str,
    lang: str,
    date: str | None,
    docs_dir: Path,
) -> int:
    """Insert/replace a document row and (re)index its text chunks."""
    path = docs_dir / file
    pages = extract_text(path) if path.exists() else []
    doc_id = store.upsert_document(
        file, doc_type=doc_type, lang=lang, date=date, page_count=max(1, len(pages)),
    )
    if pages:
        chunks = chunk_document(pages, lang)
        embeddings = embed_documents([c["text"] for c in chunks])
        store.add_chunks(doc_id, chunks, embeddings)
    return doc_id


def load_invoices(store: FinanceStore, invs: list[dict], docs_dir: Path) -> None:
    for inv in invs:
        doc_id = _upsert_with_chunks(
            store, file=inv["file"], doc_type="invoice", lang=inv["lang"],
            date=inv["date"], docs_dir=docs_dir,
        )
        store.set_invoice(
            doc_id,
            number=inv["code"], date=inv["date"], supplier=inv["supplier"],
            buyer=inv["buyer"], currency=inv["currency"], amount=inv["amount"],
            vat=inv["vat"], vat_rate=inv["vat_rate"], total=inv["total"],
            paid=1 if inv["paid"] else 0, paid_date=inv["paid_date"],
            payment_terms=inv["terms"],
        )


def load_receipts(store: FinanceStore, recs: list[dict], docs_dir: Path) -> None:
    for r in recs:
        doc_id = _upsert_with_chunks(
            store, file=r["file"], doc_type="receipt", lang=r["lang"],
            date=r["date"], docs_dir=docs_dir,
        )
        store.set_receipt(
            doc_id, number=r["code"], date=r["date"], amount=r["amount"],
            currency=r["currency"], from_name=r["from_name"],
        )


def load_contracts(store: FinanceStore, contracts: list[dict], docs_dir: Path) -> None:
    for c in contracts:
        doc_id = _upsert_with_chunks(
            store, file=c["file"], doc_type="contract", lang=c["lang"],
            date=None, docs_dir=docs_dir,
        )
        store.set_contract(doc_id, c["type"], c["clauses"])


def load_statements(store: FinanceStore, statements: list[dict], docs_dir: Path) -> None:
    for s in statements:
        doc_id = _upsert_with_chunks(
            store, file=s["file"], doc_type="statement", lang=s["lang"],
            date=s["end"], docs_dir=docs_dir,
        )
        store.set_statement(doc_id, s["supplier"], s["period"], s["entries"])


# ── Entry point ─────────────────────────────────────────────────────

def ingest_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    docs_dir: Path = DEFAULT_DOCS,
    db_path: Path = DEFAULT_DB,
    force: bool = False,
) -> dict[str, int]:
    """Load the synthetic manifest into FinanceStore. Returns counts."""
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    store = FinanceStore(db_path)
    if not force and store.count_documents() > 0:
        logger.warning("DB already has %d docs (use --force to rebuild)", store.count_documents())
        counts = dict(
            documents=store.count_documents(),
            invoices=store.run_sql("SELECT COUNT(*) AS n FROM invoices")[0]["n"],
            receipts=store.run_sql("SELECT COUNT(*) AS n FROM receipts")[0]["n"],
            contracts=store.run_sql("SELECT COUNT(*) AS n FROM contracts")[0]["n"],
            statements=store.run_sql("SELECT COUNT(*) AS n FROM statements")[0]["n"],
            chunks=store.run_sql("SELECT COUNT(*) AS n FROM chunks")[0]["n"],
        )
        store.close()
        return counts
    if force:
        store.delete_all()

    load_invoices(store, m["invoices"], docs_dir)
    load_receipts(store, m["receipts"], docs_dir)
    load_contracts(store, m["contracts"], docs_dir)
    load_statements(store, m["statements"], docs_dir)

    counts = dict(
        documents=store.count_documents(),
        invoices=len(m["invoices"]),
        receipts=len(m["receipts"]),
        contracts=len(m["contracts"]),
        statements=len(m["statements"]),
        chunks=store.run_sql("SELECT COUNT(*) AS n FROM chunks")[0]["n"],
    )
    store.close()
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest synthetic corpus into FinanceStore")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--force", action="store_true", help="wipe the DB before loading")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    counts = ingest_manifest(args.manifest, args.docs, args.db, force=args.force)
    print("=== INGEST COMPLETE ===")
    for k, v in counts.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
