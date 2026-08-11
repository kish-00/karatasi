from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLD_PATH = ROOT / "data" / "synthetic" / "gold_qa.json"
MANIFEST_PATH = ROOT / "data" / "synthetic" / "manifest.json"
DOCS_DIR = ROOT / "data" / "synthetic" / "documents"
REAL_DB = ROOT / "data" / "smebrief.db"


@pytest.fixture(scope="session")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def gold() -> list[dict]:
    return json.loads(GOLD_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def manifest_files(manifest) -> set[str]:
    m = manifest
    return {
        inv["file"] for inv in m["invoices"]
    } | {r["file"] for r in m["receipts"]} | {
        c["file"] for c in m["contracts"]
    } | {s["file"] for s in m["statements"]}
