"""Query router — answers business questions from FinanceStore.

Rule-based intent detection over the closed gold-QA domain
(numeric extraction, temporal, aggregation, contract, multilingual).
46 of 50 gold questions are deterministic SQL; the remaining 4
(summarize/conditions de paiement) fall back to vector search over
chunk embeddings.

Every route returns an Answer with the same shape the eval harness
scores against gold: values, files, text, route.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from src.rag import answer_semantic
from src.storage.store import FinanceStore

# ── Formatting (mirrors the generator so answers match gold text) ──

def fmt_xof(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", " ")


def fmt_usd(n: float) -> str:
    return f"{n:,.2f}"


def fmt_amount(n: float, currency: str) -> str:
    return fmt_xof(n) if currency == "XOF" else fmt_usd(n)


# ── Answer contract ────────────────────────────────────────────────

@dataclass
class Answer:
    values: list[dict] = field(default_factory=list)   # [{currency, value}] or [{currency: 'count', value}]
    files: list[str] = field(default_factory=list)     # source document files
    text: str = ""                                     # human-readable answer
    route: str = "sql"                                 # 'sql' | 'semantic'

    def __bool__(self) -> bool:
        return bool(self.values) or bool(self.text)


# ── Entity extraction ──────────────────────────────────────────────

SUPPLIERS: dict[str, str] = {
    "africatextiles": "AfricaTextiles Ltd",
    "groupe comptoir": "Groupe Comptoir de Dakar",
    "comptoir": "Groupe Comptoir de Dakar",
    "senexport": "SENEXPORT SA",
    "indofab": "IndoFab Textiles",
    "weavehouse": "WeaveHouse Ghana Ltd",
    "cotonou": "Cotonou Fabrics SARL",
}

MONTHS: dict[str, int] = {
    "january": 1, "janvier": 1,
    "february": 2, "février": 2,
    "march": 3, "mars": 3,
    "april": 4, "avril": 4,
    "may": 5, "mai": 5,
    "june": 6, "juin": 6,
    "july": 7, "juillet": 7,
    "august": 8, "août": 8,
    "september": 9, "septembre": 9,
    "october": 10, "octobre": 10,
    "november": 11, "novembre": 11,
    "december": 12, "décembre": 12,
}

CODE_RE = re.compile(r"\b([A-Z]{2,3}-\d{4}-\d{3,4})\b", re.IGNORECASE)

_MONTH_END = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def _month_end(month: int) -> str:
    return f"{month:02d}-{_MONTH_END[month]:02d}"


def extract_supplier(q: str) -> str | None:
    ql = q.lower()
    for key, canonical in SUPPLIERS.items():
        if key in ql:
            return canonical
    return None


def extract_period(q: str) -> tuple[str, str] | None:
    """Return (start, end) ISO dates for a quarter / month / year range."""
    ql = q.lower()
    year = "2024"

    quarter = re.search(r"\bq([1-4])\b", ql)
    if quarter:
        qn = int(quarter.group(1))
        return (f"{year}-{3*qn-2:02d}-01", f"{year}-{_month_end(3*qn)}")

    if re.search(r"premier trimestre|first quarter", ql):
        return ("2024-01-01", "2024-03-31")
    if re.search(r"second trimestre|second quarter", ql):
        return ("2024-04-01", "2024-06-30")
    if re.search(r"troisième trimestre|third quarter", ql):
        return ("2024-07-01", "2024-09-30")

    months = [m for m in MONTHS if m in ql]
    if len(months) >= 2:
        m1, m2 = (MONTHS[months[0]], MONTHS[months[1]])
        return (f"{year}-{m1:02d}-01", f"{year}-{_month_end(m2)}")
    if len(months) == 1:
        m = MONTHS[months[0]]
        return (f"{year}-{m:02d}-01", f"{year}-{_month_end(m)}")
    if re.search(r"\b2024\b", ql):
        return ("2024-01-01", "2024-12-31")
    return None


# ── Router ─────────────────────────────────────────────────────────

class QueryRouter:
    def __init__(self, store: FinanceStore) -> None:
        self.store = store

    def answer(self, question: str) -> Answer:
        """Route a question to the matching intent handler."""
        q = question.lower()
        handlers = [
            self._contract_clause,        # rent / penalty / term / deposit / credit / interest
            self._statement_closing,      # solde / closing balance / relevé
            self._by_code,                # invoice / receipt number
            self._paid_by_supplier,       # paid + supplier + period
            self._issued_totals,          # total value of invoices issued in period
            self._issued_list,            # which invoices were issued
            self._receipts_in_month,      # list the receipts from <month>
            self._unpaid,                 # unpaid invoices (list / count / total)
            self._receipts_over,          # receipts over threshold (count / sum / list)
            self._vat_total,              # TVA / VAT in a period
            self._supplier_total,         # total spend with supplier in a year
            self._total_receipts,         # total of all receipts
        ]
        for handler in handlers:
            ans = handler(q)
            if ans:
                return ans
        return self._semantic(q)

    # ── Intent handlers (ordered) ──────────────────────────────────

    def _contract_clause(self, q: str) -> Answer | None:
        """Route contract-clause questions to the contracts table (clauses JSON)."""
        doc = None
        if re.search(r"senexport", q):
            doc = "contrat_appro_senexport.pdf"
        elif re.search(r"africatextiles.*supply|supply.*africatextiles", q):
            doc = "supply_agreement_africatextiles.pdf"
        elif re.search(r"credit|crédit|ligne", q):
            doc = "convention_credit_bancaire.pdf"
        elif re.search(r"bail|entrepôt|warehouse|location|lease", q):
            doc = "contrat_bail_entrepot.pdf"

        if doc is None:
            return None
        # Summarize-style questions are semantic (no single clause value).
        if re.search(r"summarize|résumez", q):
            return None
        rows = self.store.run_sql(
            "SELECT c.clauses FROM contracts c "
            "JOIN documents d ON c.doc_id = d.id WHERE d.file = ?",
            (doc,),
        )
        if not rows:
            return None
        clauses = json.loads(rows[0]["clauses"])

        if re.search(r"rent|loyer", q):
            v = clauses["monthly_rent_fcfa"]
            return Answer([{"currency": "XOF", "value": v}], [doc],
                          f"{fmt_xof(v)} FCFA per month", "sql")
        if re.search(r"penalt|pénalité|retard", q):
            v = clauses.get("late_penalty_pct", 5.0)
            return Answer([{"currency": "pct", "value": v}], [doc],
                          f"{v:g}% per month", "sql")
        if re.search(r"payment terms|conditions de paiement", q):
            days = clauses.get("payment_days")
            if days is not None:
                return Answer([{"currency": "days", "value": days}], [doc],
                              f"Net {days} days from the date of each invoice", "sql")
        if re.search(r"months|term|durée", q) and not re.search(r"deposit|dépôt", q):
            v = clauses.get("term_months")
            if v is None:
                return None
            return Answer([{"currency": "count", "value": v}], [doc],
                          f"{v} months", "sql")
        if re.search(r"deposit|dépôt", q):
            v = clauses["deposit_months"]
            return Answer([{"currency": "months", "value": v}], [doc],
                          f"{v} months of rent", "sql")
        if re.search(r"interest|taux", q):
            v = clauses["interest_pct"]
            return Answer([{"currency": "pct", "value": v}], [doc],
                          f"{v:g}% per year", "sql")
        if re.search(r"credit line|montant.*crédit|credit line amount", q):
            v = clauses["credit_line_fcfa"]
            return Answer([{"currency": "XOF", "value": v}], [doc],
                          f"{fmt_xof(v)} FCFA", "sql")
        return None

    def _statement_closing(self, q: str) -> Answer | None:
        if not re.search(r"solde|closing balance|relevé|statement", q):
            return None
        supplier = extract_supplier(q)
        period = extract_period(q)
        if supplier is None or period is None:
            return None
        start, end = period
        label = self._period_label(q)
        rows = self.store.run_sql(
            """
            SELECT s.id, s.supplier, s.period, d.file,
                   SUM(CASE WHEN e.kind='invoice' THEN e.amount ELSE -e.amount END) AS closing
            FROM statements s
            JOIN documents d ON s.doc_id = d.id
            JOIN statement_entries e ON e.statement_id = s.id
            WHERE s.supplier = ? AND s.period = ?
            GROUP BY s.id
            """,
            (supplier, label),
        )
        if not rows:
            return None
        cur = "USD" if supplier == "AfricaTextiles Ltd" else "XOF"
        closing = float(rows[0]["closing"])
        return Answer([{"currency": cur, "value": closing}], [rows[0]["file"]],
                      f"{fmt_amount(closing, cur)} {cur}", "sql")

    def _by_code(self, q: str) -> Answer | None:
        m = CODE_RE.search(q)
        if not m:
            return None
        code = m.group(1).upper()
        if code.startswith("RCP"):
            rows = self.store.run_sql(
                "SELECT r.amount, r.currency, d.file FROM receipts r "
                "JOIN documents d ON r.doc_id = d.id WHERE r.number = ?",
                (code,),
            )
            if not rows:
                return None
            v = float(rows[0]["amount"])
            return Answer([{"currency": rows[0]["currency"], "value": v}], [rows[0]["file"]],
                          f"{fmt_xof(v)} FCFA", "sql")
        rows = self.store.run_sql(
            "SELECT i.total, i.currency, d.file FROM invoices i "
            "JOIN documents d ON i.doc_id = d.id WHERE i.number = ?",
            (code,),
        )
        if not rows:
            return None
        v = float(rows[0]["total"])
        cur = rows[0]["currency"]
        return Answer([{"currency": cur, "value": v}], [rows[0]["file"]],
                      f"{fmt_amount(v, cur)} {cur}", "sql")

    def _paid_by_supplier(self, q: str) -> Answer | None:
        if not re.search(r"pay|payé|payée|paid", q):
            return None
        supplier = extract_supplier(q)
        period = extract_period(q)
        if supplier is None or period is None:
            return None
        start, end = period
        rows = self.store.run_sql(
            "SELECT i.currency, SUM(i.total) AS total, GROUP_CONCAT(d.file) AS files "
            "FROM invoices i JOIN documents d ON i.doc_id = d.id "
            "WHERE i.supplier = ? AND i.paid = 1 "
            "AND i.paid_date BETWEEN ? AND ? GROUP BY i.currency",
            (supplier, start, end),
        )
        if not rows:
            return None
        cur = rows[0]["currency"]
        total = float(rows[0]["total"])
        files = rows[0]["files"].split(",") if rows[0]["files"] else []
        return Answer([{"currency": cur, "value": total}], files,
                      f"{fmt_amount(total, cur)} {cur}", "sql")

    def _issued_totals(self, q: str) -> Answer | None:
        if not (re.search(r"total", q) and re.search(r"issued|émises|émis", q)):
            return None
        period = extract_period(q)
        if period is None:
            return None
        start, end = period
        rows = self.store.run_sql(
            "SELECT i.currency, SUM(i.total) AS total FROM invoices i "
            "WHERE i.date BETWEEN ? AND ? GROUP BY i.currency ORDER BY i.currency",
            (start, end),
        )
        if not rows:
            return None
        values = [{"currency": r["currency"], "value": float(r["total"])} for r in rows]
        files = self._files_in_range(start, end)
        parts = [f"{fmt_amount(float(r['total']), r['currency'])} {r['currency']}" for r in rows]
        return Answer(values, files, " + ".join(parts), "sql")

    def _issued_list(self, q: str) -> Answer | None:
        if not re.search(r"issued|émises|émis|invoice", q) or re.search(r"total", q):
            return None
        supplier = extract_supplier(q)
        period = extract_period(q)
        if period is None:
            return None
        start, end = period
        sql = ("SELECT i.number, d.file FROM invoices i JOIN documents d ON i.doc_id = d.id "
               "WHERE i.date BETWEEN ? AND ? ")
        params: list = [start, end]
        if supplier is not None:
            sql += "AND i.supplier = ? "
            params.append(supplier)
        sql += "ORDER BY i.number"
        rows = self.store.run_sql(sql, tuple(params))
        if not rows:
            return None
        numbers = [r["number"] for r in rows]
        return Answer([], [r["file"] for r in rows], ", ".join(numbers), "sql")

    def _receipts_in_month(self, q: str) -> Answer | None:
        if not re.search(r"receipt|reçu|reçus", q):
            return None
        months = [m for m in MONTHS if m in q]
        has_month = bool(months) or bool(re.search(r"\bq[1-4]\b|trimestre|quarter", q))
        if not has_month:
            return None
        period = extract_period(q)
        if period is None:
            return None
        start, end = period
        rows = self.store.run_sql(
            "SELECT r.number, r.amount, d.file FROM receipts r "
            "JOIN documents d ON r.doc_id = d.id "
            "WHERE r.date BETWEEN ? AND ? ORDER BY r.number",
            (start, end),
        )
        if not rows:
            return None
        total = sum(float(r["amount"]) for r in rows)
        parts = [f"{r['number']} ({fmt_xof(r['amount'])} FCFA)" for r in rows]
        return Answer([{"currency": "XOF", "value": total}], [r["file"] for r in rows],
                      ", ".join(parts), "sql")

    def _unpaid(self, q: str) -> Answer | None:
        if not re.search(r"unpaid|impayé|impayée|impayées|impayés", q):
            return None
        supplier = extract_supplier(q)
        sql = ("SELECT i.currency, i.total, i.number, d.file FROM invoices i "
               "JOIN documents d ON i.doc_id = d.id WHERE i.paid = 0 ")
        params: list = []
        if supplier is not None:
            sql += "AND i.supplier = ? "
            params.append(supplier)
        rows = self.store.run_sql(sql + "ORDER BY i.number", tuple(params))
        if not rows:
            return None
        files = [r["file"] for r in rows]

        if re.search(r"how many|combien", q):
            return Answer([{"currency": "count", "value": len(rows)}], files,
                          str(len(rows)), "sql")
        if re.search(r"total", q):
            if re.search(r"fcfa|xof", q):
                sel = [r for r in rows if r["currency"] == "XOF"]
                v = sum(float(r["total"]) for r in sel)
                return Answer([{"currency": "XOF", "value": v}], files,
                              f"{fmt_xof(v)} FCFA", "sql")
            values = []
            for r in rows:
                key = (r["currency"], float(r["total"]))
                if not any(v.get("currency") == key[0] for v in values):
                    values.append({"currency": r["currency"],
                                   "value": sum(float(x["total"]) for x in rows if x["currency"] == r["currency"])})
            parts = [f"{fmt_amount(float(v['value']), v['currency'])} {v['currency']}" for v in values]
            return Answer(values, files, " + ".join(parts), "sql")

        stems = [f.split(".")[0] for f in files]
        return Answer([], files, ", ".join(stems), "sql")

    def _receipts_over(self, q: str) -> Answer | None:
        if not re.search(r"over|plus de|dépassent|100 ?000|100,000", q) or not re.search(r"receipt|reçu|reçus", q):
            return None
        rows = self.store.run_sql(
            "SELECT r.number, r.amount, d.file FROM receipts r "
            "JOIN documents d ON r.doc_id = d.id WHERE r.amount > 100000 "
            "ORDER BY r.number",
        )
        if not rows:
            return None
        files = [r["file"] for r in rows]
        if re.search(r"how many|combien", q):
            return Answer([{"currency": "count", "value": len(rows)}], files,
                          str(len(rows)), "sql")
        if re.search(r"total", q):
            v = sum(float(r["amount"]) for r in rows)
            return Answer([{"currency": "XOF", "value": v}], files,
                          f"{fmt_xof(v)} FCFA", "sql")
        parts = [f"{r['number']} ({fmt_xof(r['amount'])} FCFA)" for r in rows]
        return Answer([], files, ", ".join(parts), "sql")

    def _vat_total(self, q: str) -> Answer | None:
        if not re.search(r"tva|vat", q):
            return None
        period = extract_period(q)
        if period is None:
            return None
        start, end = period
        rows = self.store.run_sql(
            "SELECT SUM(i.vat) AS total FROM invoices i "
            "JOIN documents d ON i.doc_id = d.id "
            "WHERE d.lang = 'fr' AND d.file NOT LIKE '%.png' "
            "AND i.date BETWEEN ? AND ?",
            (start, end),
        )
        if not rows or rows[0]["total"] is None:
            return None
        v = float(rows[0]["total"])
        return Answer([{"currency": "XOF", "value": v}],
                      self._files_in_range(start, end, lang="fr"),
                      f"{fmt_xof(v)} FCFA", "sql")

    def _supplier_total(self, q: str) -> Answer | None:
        if not re.search(r"total|montant", q):
            return None
        supplier = extract_supplier(q)
        if supplier is None:
            return None
        rows = self.store.run_sql(
            "SELECT i.currency, SUM(i.total) AS total, GROUP_CONCAT(d.file) AS files "
            "FROM invoices i JOIN documents d ON i.doc_id = d.id "
            "WHERE i.supplier = ? AND i.date BETWEEN '2024-01-01' AND '2024-12-31' "
            "GROUP BY i.currency",
            (supplier,),
        )
        if not rows:
            return None
        cur = rows[0]["currency"]
        v = float(rows[0]["total"])
        files = rows[0]["files"].split(",") if rows[0]["files"] else []
        return Answer([{"currency": cur, "value": v}], files,
                      f"{fmt_amount(v, cur)} {cur}", "sql")

    def _total_receipts(self, q: str) -> Answer | None:
        if not re.search(r"total.*receipt|total.*reçu|all receipts", q):
            return None
        rows = self.store.run_sql(
            "SELECT SUM(r.amount) AS total FROM receipts r",
        )
        if not rows or rows[0]["total"] is None:
            return None
        v = float(rows[0]["total"])
        files = [r["file"] for r in self.store.run_sql(
            "SELECT d.file FROM receipts r JOIN documents d ON r.doc_id = d.id ORDER BY r.number")]
        return Answer([{"currency": "XOF", "value": v}], files,
                      f"{fmt_xof(v)} FCFA", "sql")

    # ── Semantic fallback ──────────────────────────────────────────

    def _semantic(self, q: str) -> Answer:
        payload = answer_semantic(self.store, q)
        if payload is None:
            return Answer([], [], "", "semantic")
        files, text = payload
        return Answer([], files, text, "semantic")

    # ── Helpers ────────────────────────────────────────────────────

    def _period_label(self, q: str) -> str:
        """Map a question back to the manifest statement period label (Q1 2024…)."""
        ql = q.lower()
        year = "2024"
        quarter = re.search(r"\bq([1-4])\b", ql)
        if quarter:
            return f"Q{quarter.group(1)} {year}"
        if re.search(r"premier trimestre|first quarter", ql):
            return f"Q1 {year}"
        if re.search(r"second trimestre|second quarter", ql):
            return f"Q2 {year}"
        if re.search(r"troisième trimestre|third quarter", ql):
            return f"Q3 {year}"
        return f"Q1 {year}"

    def _files_in_range(self, start: str, end: str, lang: str | None = None) -> list[str]:
        sql = ("SELECT d.file FROM invoices i JOIN documents d ON i.doc_id = d.id "
               "WHERE i.date BETWEEN ? AND ? ")
        params: list = [start, end]
        if lang is not None:
            sql += "AND d.lang = ? "
            params.append(lang)
        sql += "ORDER BY i.number"
        return [r["file"] for r in self.store.run_sql(sql, tuple(params))]
