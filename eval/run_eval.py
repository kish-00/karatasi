"""Gold-QA eval harness — scores the QueryRouter against data/synthetic/gold_qa.json.

Usage:  venv/bin/python eval/run_eval.py [--json] [--fail-fast]
Exit 0 when all 50 questions match gold values+files, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOLD = ROOT / "data" / "synthetic" / "gold_qa.json"
DB = ROOT / "data" / "smebrief.db"


def normalize(values: list[dict]) -> list[tuple[str, float]]:
    return sorted(
        (v.get("currency", "count"), round(float(v.get("value", 0.0)), 3)) for v in (values or [])
    )


def run(gold_path: Path = GOLD, db_path: Path = DB) -> tuple[list[dict], int]:
    from src.retrieval.router import QueryRouter
    from src.storage.store import FinanceStore

    gold = json.loads(gold_path.read_text())
    store = FinanceStore(db_path)
    router = QueryRouter(store)
    results: list[dict] = []
    passed = 0
    try:
        for item in gold:
            ans = router.answer(item["question"])
            values_ok = normalize(ans.values) == normalize(item.get("gold_values") or [])
            files_ok = set(ans.files) == set(item.get("gold_files") or [])
            ok = values_ok and files_ok
            passed += int(ok)
            results.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "route": ans.route,
                    "ok": ok,
                    "got_values": ans.values,
                    "got_files": ans.files,
                    "gold_values": item.get("gold_values") or [],
                    "gold_files": item.get("gold_files") or [],
                }
            )
    finally:
        store.close()
    return results, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the query router against gold QA.")
    parser.add_argument("--json", action="store_true", help="emit results as JSON")
    parser.add_argument("--fail-fast", action="store_true", help="stop at first mismatch")
    args = parser.parse_args()

    results, passed = run()
    total = len(results)
    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({"passed": passed, "total": total, "failures": failed}, indent=2))
    else:
        for r in failed:
            print(f"FAIL {r['id']} [{r['route']}] {r['question']}")
            print(f"  got  v={r['got_values']} f={r['got_files']}")
            print(f"  gold v={r['gold_values']} f={r['gold_files']}")
            if args.fail_fast:
                break
        print(f"PASS {passed}/{total} FAIL_IDS=[{','.join(r['id'] for r in failed)}]")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
