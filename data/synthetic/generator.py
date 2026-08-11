"""SME Brief — synthetic document corpus + gold QA generator.

Persona: Aya Traoré, import/export textile trader in Dakar, Senegal.
Produces 50 documents (40 clean PDFs + 10 scanned-style PNGs) in FR + EN,
plus manifest.json (single source of truth) and gold_qa.json (50 gold
questions across 5 categories, every answer derived from manifest).

Run:  venv/bin/python data/synthetic/generator.py [--force]
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]  # repo root
OUT = BASE / "data" / "synthetic" / "documents"
MANIFEST_PATH = BASE / "data" / "synthetic" / "manifest.json"
GOLD_PATH = BASE / "data" / "synthetic" / "gold_qa.json"

# ── Formatting helpers ──────────────────────────────────────────────

def fmt_xof(n: float) -> str:
    """'1250000' -> '1 250 000' (French space-thousands, no decimals)."""
    n = int(round(n))
    s = f"{n:,}".replace(",", " ")
    return s


def fmt_usd(n: float) -> str:
    """'8120.0' -> '8,120.00' (US thousands + 2 decimals)."""
    return f"{n:,.2f}"


def fmt_amount(n: float, currency: str) -> str:
    return fmt_xof(n) if currency == "XOF" else fmt_usd(n)


def disp_date(iso: str, lang: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}" if lang == "fr" else f"{y}-{m}-{d}"


# ── Invoice spec builder ────────────────────────────────────────────

def _inv(
    code: str, iso: str, supplier: str, buyer: str, currency: str,
    items: list[tuple[str, int, float]], paid: bool,
    paid_date: str | None = None, terms: str | None = None,
    lang: str = "en", scanned: bool = False,
) -> dict:
    amount = round(sum(q * p for _, q, p in items), 2)
    rate = 18.0 if currency == "XOF" else 16.0
    vat = round(amount * rate / 100, 2)
    return dict(
        code=code, date=iso, supplier=supplier, buyer=buyer, currency=currency,
        items=items, amount=amount, vat=vat, vat_rate=rate, total=round(amount + vat, 2),
        paid=paid, paid_date=paid_date, terms=terms or ("Paiement à 60 jours" if lang == "fr" else "Net 30 days"),
        lang=lang, scanned=scanned,
        file=f"{'facture' if lang == 'fr' else 'invoice'}_{code}.{'png' if scanned else 'pdf'}",
    )


# ── Corpus definition ───────────────────────────────────────────────
# All facts are explicit (no randomness) so manifest/gold stay exact.
# scanned=True docs use NEW suppliers and dates >= April so the demo
# aggregates (Q1 TVA, Q1 paid, unpaid list, receipts >100k) are stable.

BUYER = "Aya Traoré (Import/Export)"

INVOICES: list[dict] = [
    # AfricaTextiles Ltd (EN, USD, VAT 16%) — Q1 window drives demo Q1
    _inv("AT-2024-0007", "2024-01-15", "AfricaTextiles Ltd", BUYER, "USD",
         [("Wax fabric 6 yards", 10, 400.00), ("Polyester blend", 25, 120.00)],
         True, "2024-01-20", "Net 30 days", "en"),
    _inv("AT-2024-0012", "2024-02-12", "AfricaTextiles Ltd", BUYER, "USD",
         [("Cotton print", 30, 150.00), ("Silk rolls", 8, 550.00)],
         True, "2024-02-18", "Net 30 days", "en"),
    _inv("AT-2024-0019", "2024-03-08", "AfricaTextiles Ltd", BUYER, "USD",
         [("Wax fabric 6 yards", 20, 400.00), ("Lace fabric", 12, 300.00)],
         True, "2024-03-15", "Net 30 days", "en"),
    _inv("AT-2024-0027", "2024-03-28", "AfricaTextiles Ltd", BUYER, "USD",
         [("Denim rolls", 15, 220.00), ("Chiffon", 10, 180.00)],
         True, "2024-04-05", "Net 30 days", "en"),
    _inv("AT-2024-0041", "2024-06-18", "AfricaTextiles Ltd", BUYER, "USD",
         [("Wax fabric 6 yards", 25, 420.00), ("Kente print", 10, 260.00)],
         True, "2024-06-25", "Net 30 days", "en"),
    _inv("AT-2024-0060", "2024-11-05", "AfricaTextiles Ltd", BUYER, "USD",
         [("Wool suiting", 20, 310.00)],
         False, None, "Net 30 days", "en"),
    # Groupe Comptoir de Dakar (FR, XOF, TVA 18%)
    _inv("GCD-2024-001", "2024-01-10", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Tissu wax 6 yards", 12, 45000), ("Coton imprimé", 20, 18500)],
         True, "2024-01-18", "Paiement à 60 jours", "fr"),
    _inv("GCD-2024-008", "2024-02-05", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Pagne tissé", 15, 38000), ("Soie", 6, 62000)],
         True, "2024-02-12", "Paiement à 60 jours", "fr"),
    _inv("GCD-2024-014", "2024-03-15", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Tissu wax 6 yards", 18, 45000), ("Coton brodé", 10, 24000)],
         True, "2024-03-22", "Paiement à 60 jours", "fr"),
    _inv("GCD-2024-021", "2024-05-20", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Lin", 14, 30000), ("Pagne tissé", 12, 38000)],
         True, "2024-05-28", "Paiement à 60 jours", "fr"),
    _inv("GCD-2024-030", "2024-07-10", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Tissu wax 6 yards", 10, 47000), ("Mousseline", 8, 29000)],
         False, None, "Paiement à 60 jours", "fr"),
    _inv("GCD-2024-038", "2024-09-02", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Velours", 9, 54000), ("Coton imprimé", 25, 18500)],
         True, "2024-09-10", "Paiement à 60 jours", "fr"),
    _inv("GCD-2024-046", "2024-12-12", "Groupe Comptoir de Dakar", BUYER, "XOF",
         [("Tissu wax 6 yards", 22, 47000)],
         False, None, "Paiement à 60 jours", "fr"),
    # SENEXPORT SA (FR, XOF, TVA 18%)
    _inv("SX-2024-003", "2024-01-22", "SENEXPORT SA", BUYER, "XOF",
         [("Satin", 10, 36000), ("Taffetas", 12, 28000)],
         True, "2024-02-01", "Paiement à 60 jours", "fr"),
    _inv("SX-2024-011", "2024-02-25", "SENEXPORT SA", BUYER, "XOF",
         [("Coton piqué", 20, 16000)],
         True, "2024-03-05", "Paiement à 60 jours", "fr"),
    _inv("SX-2024-018", "2024-04-14", "SENEXPORT SA", BUYER, "XOF",
         [("Bazin riche", 8, 75000), ("Pagne tissé", 10, 38000)],
         True, "2024-04-22", "Paiement à 60 jours", "fr"),
    _inv("SX-2024-026", "2024-08-08", "SENEXPORT SA", BUYER, "XOF",
         [("Satin", 15, 36000)],
         False, None, "Paiement à 60 jours", "fr"),
    _inv("SX-2024-035", "2024-11-18", "SENEXPORT SA", BUYER, "XOF",
         [("Taffetas", 18, 28000), ("Coton piqué", 10, 16000)],
         False, None, "Paiement à 60 jours", "fr"),
    # Cotonou Fabrics SARL (FR, XOF, TVA 18%)
    _inv("CF-2024-002", "2024-01-30", "Cotonou Fabrics SARL", BUYER, "XOF",
         [("Tissu imprimé", 25, 12000), ("Voile", 10, 21000)],
         True, "2024-02-08", "Paiement à 45 jours", "fr"),
    _inv("CF-2024-009", "2024-03-20", "Cotonou Fabrics SARL", BUYER, "XOF",
         [("Coton gaufré", 14, 15500)],
         True, "2024-03-28", "Paiement à 45 jours", "fr"),
    _inv("CF-2024-017", "2024-06-05", "Cotonou Fabrics SARL", BUYER, "XOF",
         [("Tissu imprimé", 30, 12000), ("Lurex", 6, 48000)],
         False, None, "Paiement à 45 jours", "fr"),
    _inv("CF-2024-024", "2024-10-19", "Cotonou Fabrics SARL", BUYER, "XOF",
         [("Voile", 15, 21000)],
         False, None, "Paiement à 45 jours", "fr"),
    # IndoFab Textiles (EN, USD, VAT 16%)
    _inv("IF-2024-005", "2024-04-09", "IndoFab Textiles", BUYER, "USD",
         [("Rayon challis", 40, 85.00), ("Crepe", 15, 140.00)],
         True, "2024-04-19", "Net 30 days", "en"),
    _inv("IF-2024-016", "2024-07-22", "IndoFab Textiles", BUYER, "USD",
         [("Silk twill", 12, 480.00)],
         True, "2024-07-30", "Net 30 days", "en"),
    _inv("IF-2024-029", "2024-10-03", "IndoFab Textiles", BUYER, "USD",
         [("Rayon challis", 25, 85.00), ("Jacquard", 10, 260.00)],
         False, None, "Net 30 days", "en"),
    # WeaveHouse Ghana (EN, USD, VAT 16%)
    _inv("WH-2024-004", "2024-05-14", "WeaveHouse Ghana Ltd", BUYER, "USD",
         [("Kente strips", 20, 180.00), ("Adinkra print", 15, 95.00)],
         True, "2024-05-20", "Net 30 days", "en"),
    _inv("WH-2024-013", "2024-08-26", "WeaveHouse Ghana Ltd", BUYER, "USD",
         [("Kente strips", 12, 180.00)],
         True, "2024-09-03", "Net 30 days", "en"),
    _inv("WH-2024-022", "2024-11-28", "WeaveHouse Ghana Ltd", BUYER, "USD",
         [("Adinkra print", 20, 95.00), ("Fugu fabric", 8, 210.00)],
         True, "2024-12-06", "Net 30 days", "en"),
    # ── Scanned (photo) invoices: NEW suppliers, paid, dates >= Apr ──
    _inv("TP-2024-010", "2024-05-06", "Tissus du Plateau SARL", BUYER, "XOF",
         [("Tissu wax 6 yards", 6, 48000), ("Coton imprimé", 15, 19000)],
         True, "2024-05-16", "Paiement à 30 jours", "fr", scanned=True),
    _inv("TP-2024-020", "2024-08-21", "Tissus du Plateau SARL", BUYER, "XOF",
         [("Pagne tissé", 8, 39000)],
         True, "2024-08-30", "Paiement à 30 jours", "fr", scanned=True),
    _inv("ACM-2024-007", "2024-06-27", "Atelier Cousu-Main", BUYER, "XOF",
         [("Robes cousues", 12, 25000), ("Chemises", 15, 18000)],
         True, "2024-07-05", "Paiement à 30 jours", "fr", scanned=True),
    _inv("TE-2024-014", "2024-10-09", "TransExpress Sénégal", BUYER, "XOF",
         [("Transport conteneur 20ft", 1, 850000)],
         True, "2024-10-18", "Paiement à 15 jours", "fr", scanned=True),
    _inv("LTM-2024-011", "2024-07-11", "Lagos Textile Mart", BUYER, "USD",
         [("Ankara print", 18, 95.00), ("Tulle", 10, 60.00)],
         True, "2024-07-19", "Net 15 days", "en", scanned=True),
    _inv("AF-2024-006", "2024-09-25", "Ashanti Fabrics", BUYER, "USD",
         [("Kente strips", 10, 185.00)],
         True, "2024-10-02", "Net 30 days", "en", scanned=True),
]

RECEIPTS: list[dict] = [
    dict(code="RCP-2024-002", date="2024-01-12", amount=45000, currency="XOF",
         from_name="Boutique Chez Fatou", method="Virement bancaire", lang="fr"),
    dict(code="RCP-2024-006", date="2024-02-09", amount=85000, currency="XOF",
         from_name="Marché Sandaga (Stall 42)", method="Espèces", lang="fr"),
    dict(code="RCP-2024-011", date="2024-03-15", amount=125000, currency="XOF",
         from_name="Boutique Chez Fatou", method="Virement bancaire", lang="fr"),
    dict(code="RCP-2024-019", date="2024-04-03", amount=65000, currency="XOF",
         from_name="Aminata Sow", method="Espèces", lang="fr"),
    dict(code="RCP-2024-023", date="2024-05-30", amount=150000, currency="XOF",
         from_name="Mamadou Diallo", method="Virement bancaire", lang="fr"),
    dict(code="RCP-2024-031", date="2024-08-14", amount=240000, currency="XOF",
         from_name="Boutique Chez Fatou", method="Virement bancaire", lang="fr"),
    dict(code="RCP-2024-037", date="2024-10-22", amount=95000, currency="XOF",
         from_name="Marché Sandaga (Stall 42)", method="Espèces", lang="fr"),
    dict(code="RCP-2024-015", date="2024-04-18", amount=110000, currency="XOF",
         from_name="Mamadou Diallo", method="Bank transfer", lang="en"),
    dict(code="RCP-2024-026", date="2024-07-05", amount=75000, currency="XOF",
         from_name="Aminata Sow", method="Cash", lang="en"),
    dict(code="RCP-2024-033", date="2024-09-12", amount=90000, currency="XOF",
         from_name="Boutique Chez Fatou", method="Bank transfer", lang="en"),
    # scanned receipts (<= 100k so the >100k count stays 4)
    dict(code="RCP-2024-040", date="2024-11-07", amount=55000, currency="XOF",
         from_name="Marché Sandaga (Stall 42)", method="Espèces", lang="fr", scanned=True),
    dict(code="RCP-2024-044", date="2024-12-03", amount=78000, currency="XOF",
         from_name="Boutique Chez Fatou", method="Virement bancaire", lang="fr", scanned=True),
    dict(code="RCP-2024-048", date="2024-12-19", amount=62000, currency="XOF",
         from_name="Aminata Sow", method="Espèces", lang="fr", scanned=True),
    dict(code="RCP-2024-050", date="2024-11-25", amount=88000, currency="XOF",
         from_name="Mamadou Diallo", method="Bank transfer", lang="en", scanned=True),
]

CONTRACTS: list[dict] = [
    dict(file="contrat_bail_entrepot.pdf", type="warehouse_lease", lang="fr",
         clauses=dict(monthly_rent_fcfa=850000, term_months=36, deposit_months=2,
                      due_day=5, late_penalty_pct=5.0, currency="XOF"),
         title="CONTRAT DE LOCATION D'ENTREPÔT",
         body=[
             "Entre les soussignés :",
             "- Bailleur : SODIA Immobilier, 45 Avenue Léopold Sédar Senghor, Dakar",
             "- Preneur : Aya Traoré (Import/Export), Zone Industrielle de Diamniadio",
             "",
             "Article 1 — Objet : location d'un entrepôt de 500 m² sis à la Zone",
             "Industrielle de Diamniadio, destiné au stockage de tissus et de marchandises.",
             "Article 2 — Durée : 36 mois à compter du 1er janvier 2024, renouvelable.",
             "Article 3 — Loyer : 850 000 FCFA par mois, payable le 5 de chaque mois",
             "par virement bancaire.",
             "Article 4 — Dépôt de garantie : 2 mois de loyer, restitué en fin de bail.",
             "Article 5 — Pénalité de retard : 5% par mois sur les loyers impayés.",
             "Article 6 — Charges : l'eau et l'électricité sont à la charge du preneur.",
         ]),
    dict(file="contrat_appro_senexport.pdf", type="supply_agreement", lang="fr",
         clauses=dict(late_penalty_pct=2.0, payment_days=60, currency="XOF"),
         title="CONTRAT D'APPROVISIONNEMENT",
         body=[
             "Entre SENEXPORT SA, 8 Rue Carnot, Plateau, Dakar et",
             "Aya Traoré (Import/Export), Dakar.",
             "",
             "Article 1 — Objet : fourniture de tissus et de pagnes en gros.",
             "Article 2 — Conditions de paiement : paiement à 60 jours à compter",
             "de la date de facturation.",
             "Article 3 — Pénalité de retard : 2% par mois sur tout montant impayé",
             "après l'échéance.",
             "Article 4 — Livraison : franco domicile, Zone Industrielle de Diamniadio.",
             "Article 5 — Litiges : Tribunal de Commerce de Dakar.",
         ]),
    dict(file="supply_agreement_africatextiles.pdf", type="supply_agreement", lang="en",
         clauses=dict(late_penalty_pct=2.0, payment_days=30, currency="USD"),
         title="SUPPLY AGREEMENT",
         body=[
             "This Supply Agreement is made between AfricaTextiles Ltd, 12 Marina",
             "Road, Lagos, Nigeria and Aya Traoré (Import/Export), Dakar, Senegal.",
             "",
             "1. Subject: supply of wax prints, kente and assorted fabrics.",
             "2. Payment terms: Net 30 days from the date of each invoice.",
             "3. Late payment: a penalty of 2% per month applies to any amount",
             "outstanding beyond the due date.",
             "4. Delivery: FOB Lagos; freight and insurance for the buyer's account.",
             "5. Governing law: Federal Republic of Nigeria.",
         ]),
    dict(file="contrat_transport.pdf", type="transport_contract", lang="fr",
         clauses=dict(container_rate_fcfa=850000, currency="XOF"),
         title="CONTRAT DE TRANSPORT",
         body=[
             "Contrat de transport de marchandises entre TransExpress Sénégal,",
             "Port Autonome de Dakar et Aya Traoré (Import/Export).",
             "",
             "Article 1 — Objet : transport de conteneurs entre le port de Dakar et",
             "la Zone Industrielle de Diamniadio.",
             "Article 2 — Tarif : 850 000 FCFA par conteneur de 20 pieds,",
             "dédouanement inclus.",
             "Article 3 — Délai : livraison sous 48 heures après déchargement.",
             "Article 4 — Responsabilité : couverture pour perte et avarie de",
             "marchandises jusqu'à 5 000 000 FCFA.",
         ]),
    dict(file="convention_credit_bancaire.pdf", type="bank_credit_line", lang="fr",
         clauses=dict(credit_line_fcfa=5000000, interest_pct=9.0, currency="XOF"),
         title="CONVENTION DE LIGNE DE CRÉDIT",
         body=[
             "Convention de ligne de crédit entre la Banque Atlantique Sénégal,",
             "Place de l'Indépendance, Dakar et Aya Traoré (Import/Export).",
             "",
             "Article 1 — Montant : ligne de crédit de 5 000 000 FCFA.",
             "Article 2 — Taux : intérêts au taux annuel de 9%.",
             "Article 3 — Durée : 12 mois renouvelable.",
             "Article 4 — Garantie : nantissement du stock de marchandises.",
             "Article 5 — Utilisation : par décaissements successifs sur présentation",
             "de factures proforma.",
         ]),
    dict(file="distribution_agreement_weavehouse.pdf", type="distribution_agreement", lang="en",
         clauses=dict(term_years=5, currency="USD"),
         title="EXCLUSIVE DISTRIBUTION AGREEMENT",
         body=[
             "Exclusive Distribution Agreement between WeaveHouse Ghana Ltd,",
             "Accra, Ghana and Aya Traoré (Import/Export), Dakar, Senegal.",
             "",
             "1. Territory: the Republic of Senegal.",
             "2. Term: five (5) years from January 1, 2024.",
             "3. Products: kente strips, adinkra prints and fugu fabrics.",
             "4. Minimum purchase: USD 40,000 per calendar year.",
             "5. Termination: 90 days written notice by either party.",
         ]),
]


def statement_specs(invoices: list[dict]) -> list[dict]:
    """Build 6 supplier statements from the invoice corpus."""
    by_supplier: dict[str, list[dict]] = {}
    for inv in invoices:
        if inv["scanned"] or inv["supplier"] not in {
            "AfricaTextiles Ltd", "Groupe Comptoir de Dakar", "SENEXPORT SA",
        }:
            continue
        by_supplier.setdefault(inv["supplier"], []).append(inv)

    periods = {
        "AfricaTextiles Ltd": [("Q1 2024", "2024-01-01", "2024-03-31"),
                               ("Q2 2024", "2024-04-01", "2024-06-30")],
        "Groupe Comptoir de Dakar": [("Q1 2024", "2024-01-01", "2024-03-31"),
                                     ("Q2 2024", "2024-04-01", "2024-06-30")],
        "SENEXPORT SA": [("Q2 2024", "2024-04-01", "2024-06-30"),
                         ("Q3 2024", "2024-07-01", "2024-09-30")],
    }
    out: list[dict] = []
    for supplier, plist in periods.items():
        invs = sorted(by_supplier.get(supplier, []), key=lambda i: i["date"])
        for label, start, end in plist:
            period_invs = [i for i in invs if start <= i["date"] <= end]
            period_payments = [i for i in invs if i["paid"] and start <= (i["paid_date"] or "") <= end]
            issued = sum(i["total"] for i in period_invs)
            received = sum(i["total"] for i in period_payments)
            entries: list[dict] = []
            for i in period_invs:
                entries.append(dict(date=i["date"], ref=i["code"], amount=i["total"], kind="invoice"))
            for i in period_payments:
                entries.append(dict(date=i["paid_date"], ref=i["code"], amount=i["total"], kind="payment"))
            entries.sort(key=lambda e: e["date"])
            lang = "fr" if supplier != "AfricaTextiles Ltd" else "en"
            out.append(dict(
                supplier=supplier, period=label, start=start, end=end,
                lang=lang, entries=entries, issued=issued, received=received,
                closing=round(issued - received, 2),
                file=f"releve_{supplier.split()[0].lower()}_{label.replace(' ', '').lower()}.pdf",
            ))
    return out


# ── Text rendering (PDF + scanned) ─────────────────────────────────

def invoice_lines(inv: dict) -> list[str]:
    fr = inv["lang"] == "fr"
    cur = inv["currency"]
    amt = fmt_amount
    lines = ["FACTURE" if fr else "INVOICE"]
    lines.append(f"N° {inv['code']}" if fr else f"No. {inv['code']}")
    lines.append(f"Date : {disp_date(inv['date'], 'fr')}" if fr else f"Date: {disp_date(inv['date'], 'en')}")
    lines.append("")
    lines.append(f"Fournisseur : {inv['supplier']}" if fr else f"Supplier: {inv['supplier']}")
    lines.append("Adresse : Dakar, Sénégal" if fr else "Address: Lagos/Dakar")
    lines.append(f"Client : {inv['buyer']}" if fr else f"Buyer: {inv['buyer']}")
    lines.append("")
    lines.append("Désignation                  Qté   PU (FCFA)    Montant" if fr
                 else "Item                      Qty  Unit (USD)    Amount")
    for desc, qty, price in inv["items"]:
        p = fmt_xof(price) if cur == "XOF" else fmt_usd(price)
        m = fmt_xof(qty * price) if cur == "XOF" else fmt_usd(qty * price)
        d = desc if len(desc) <= 22 else desc[:22]
        lines.append(f"{d:<26} {qty:>3}   {p:>11}   {m:>12}")
    lines.append("")
    lines.append(f"Sous-total                         {amt(inv['amount'], cur):>14}" if fr
                 else f"Subtotal                                    {amt(inv['amount'], cur):>12}")
    lines.append(f"TVA ({int(inv['vat_rate'])}%)                           {amt(inv['vat'], cur):>14}" if fr
                 else f"VAT ({int(inv['vat_rate'])}%)                                       {amt(inv['vat'], cur):>12}")
    lines.append(f"TOTAL                               {amt(inv['total'], cur):>14} {cur}" if fr
                 else f"TOTAL                                       {amt(inv['total'], cur):>12} {cur}")
    lines.append("")
    lines.append(f"Conditions de paiement : {inv['terms']}" if fr else f"Payment terms: {inv['terms']}")
    if inv["paid"]:
        lines.append(f"Statut : PAYÉE le {disp_date(inv['paid_date'], 'fr')}" if fr
                     else f"Status: PAID on {disp_date(inv['paid_date'], 'en')}")
    else:
        lines.append("Statut : EN ATTENTE DE PAIEMENT" if fr else "Status: UNPAID")
    return lines


def receipt_lines(r: dict) -> list[str]:
    fr = r["lang"] == "fr"
    amt = fmt_xof(r["amount"])
    lines = ["REÇU DE PAIEMENT" if fr else "PAYMENT RECEIPT"]
    lines.append(f"N° {r['code']}" if fr else f"No. {r['code']}")
    lines.append(f"Date : {disp_date(r['date'], 'fr')}" if fr else f"Date: {disp_date(r['date'], 'en')}")
    lines.append("")
    lines.append(f"Reçu de : {r['from_name']}" if fr else f"Received from: {r['from_name']}")
    lines.append(f"Montant : {amt} FCFA" if fr else f"Amount: {amt} FCFA")
    lines.append(f"Mode : {r['method']}" if fr else f"Method: {r['method']}")
    return lines


def contract_lines(c: dict) -> list[str]:
    return [c["title"], ""] + list(c["body"])


def statement_lines(s: dict) -> list[str]:
    fr = s["lang"] == "fr"
    lines = ["RELEVÉ DE COMPTE" if fr else "SUPPLIER STATEMENT"]
    lines.append(f"Fournisseur : {s['supplier']}" if fr else f"Supplier: {s['supplier']}")
    lines.append(f"Période : {s['period']}" if fr else f"Period: {s['period']}")
    lines.append("")
    lines.append("Date        Référence        Montant      Type" if fr
                 else "Date        Reference         Amount       Type")
    for e in s["entries"]:
        amt = fmt_xof(e["amount"])
        kind = "Facture" if e["kind"] == "invoice" else "Paiement"
        if fr:
            lines.append(f"{disp_date(e['date'], 'fr')}   {e['ref']:<16} {amt:>11}   {kind}")
        else:
            kind_e = "Invoice" if e["kind"] == "invoice" else "Payment"
            lines.append(f"{disp_date(e['date'], 'en')}   {e['ref']:<16} {amt:>11}   {kind_e}")
    lines.append("")
    cur = "FCFA" if s["supplier"] != "AfricaTextiles Ltd" else "USD"
    amt = fmt_amount(s["closing"], cur)
    lines.append(f"Solde au {disp_date(s['end'], 'fr')} : {amt} {cur}" if fr
                 else f"Closing balance at {disp_date(s['end'], 'en')}: {amt} {cur}")
    return lines


# ── File emission ──────────────────────────────────────────────────

def make_pdf(lines: list[str], path: Path) -> None:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    x, y, step = 60.0, 70.0, 15.0
    for line in lines:
        if y > 800:
            page = doc.new_page(width=595, height=842)
            y = 70.0
        page.insert_text((x, y), line, fontname="helv", fontsize=11)
        y += step
    doc.save(str(path))
    doc.close()


def make_image(lines: list[str], path: Path) -> None:
    """Render an invoice/receipt as a slightly noisy, rotated photo."""
    from PIL import Image, ImageDraw, ImageFont
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 30) if font_path.exists() else ImageFont.load_default()
    font_bold = ImageFont.truetype(str(font_path), 36) if font_path.exists() else font
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    y = 120
    for i, line in enumerate(lines):
        f = font_bold if i == 0 else font
        draw.text((90, y), line, fill="black", font=f)
        y += 52 if i == 0 else 46
    # slight rotation
    img = img.rotate(random.uniform(-1.5, 1.5), expand=True, fillcolor=(255, 255, 255))
    # noise
    import numpy as np
    arr = np.asarray(img, dtype=np.float32)
    arr += np.random.normal(0, 6, arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    img.save(str(path))


def emit_docs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    n_pdf = n_img = 0
    for inv in INVOICES:
        lines = invoice_lines(inv)
        stem = f"{'facture' if inv['lang'] == 'fr' else 'invoice'}_{inv['code']}"
        if inv["scanned"]:
            make_image(lines, OUT / f"{stem}.png")
            inv["file"] = f"{stem}.png"
            n_img += 1
        else:
            make_pdf(lines, OUT / f"{stem}.pdf")
            inv["file"] = f"{stem}.pdf"
            n_pdf += 1
    for r in RECEIPTS:
        lines = receipt_lines(r)
        stem = f"{'recu' if r['lang'] == 'fr' else 'receipt'}_{r['code']}"
        if r.get("scanned"):
            make_image(lines, OUT / f"{stem}.png")
            r["file"] = f"{stem}.png"
            n_img += 1
        else:
            make_pdf(lines, OUT / f"{stem}.pdf")
            r["file"] = f"{stem}.pdf"
            n_pdf += 1
    for c in CONTRACTS:
        make_pdf(contract_lines(c), OUT / c["file"])
        n_pdf += 1
    stats = statement_specs(INVOICES)
    for s in stats:
        make_pdf(statement_lines(s), OUT / s["file"])
        n_pdf += 1
    print(f"emitted {n_pdf} PDFs + {n_img} scanned PNGs")


# ── Manifest ───────────────────────────────────────────────────────

def _quarter_of(iso: str) -> str:
    m = int(iso[5:7])
    return f"Q{(m - 1) // 3 + 1}"


def build_manifest() -> dict:
    invs = sorted(INVOICES, key=lambda i: i["code"])
    recs = sorted(RECEIPTS, key=lambda r: r["code"])
    for r in recs:
        r.setdefault("file", f"{'recu' if r['lang'] == 'fr' else 'receipt'}_{r['code']}."
                             f"{'png' if r.get('scanned') else 'pdf'}")
    stats = statement_specs(INVOICES)

    def paid_in(supplier: str, start: str, end: str) -> list[dict]:
        return [i for i in invs if i["supplier"] == supplier and i["paid"]
                and start <= i["paid_date"] <= end]

    at_q1 = paid_in("AfricaTextiles Ltd", "2024-01-01", "2024-03-31")
    q1_fr_invs = [i for i in invs if i["lang"] == "fr" and not i["scanned"]
                  and "2024-01-01" <= i["date"] <= "2024-03-31"]
    unpaid = [i for i in invs if not i["paid"]]
    over100k = [r for r in recs if r["amount"] > 100000]
    q2_by_supplier = {
        sup: [i for i in invs if i["supplier"] == sup and i["paid"]
              and "2024-04-01" <= i["paid_date"] <= "2024-06-30"]
        for sup in ("AfricaTextiles Ltd", "Groupe Comptoir de Dakar", "SENEXPORT SA")
    }
    q3_invs = [i for i in invs if "2024-07-01" <= i["date"] <= "2024-09-30"]
    june_invs = [i for i in invs if "2024-06-01" <= i["date"] <= "2024-06-30"]

    return dict(
        meta=dict(
            seed=42,
            counts=dict(invoices=len(invs), receipts=len(recs),
                        contracts=len(CONTRACTS), statements=len(stats),
                        total=len(invs) + len(recs) + len(CONTRACTS) + len(stats)),
        ),
        invoices=[dict(inv, items=[[d, q, p] for d, q, p in inv["items"]]) for inv in invs],
        receipts=recs,
        contracts=[dict(c, body=[]) for c in CONTRACTS],  # clauses only, drop long body
        statements=stats,
        computed=dict(
            africatextiles_q1_2024_paid=dict(
                files=[i["file"] for i in at_q1],
                total_paid=round(sum(i["total"] for i in at_q1), 2),
            ),
            africatextiles_q1_2024_issued=[i["file"] for i in invs
                                           if i["supplier"] == "AfricaTextiles Ltd"
                                           and "2024-01-01" <= i["date"] <= "2024-03-31"],
            q1_2024_tva_total=round(sum(i["vat"] for i in q1_fr_invs), 2),
            q1_2024_tva_invoices=[i["file"] for i in q1_fr_invs],
            unpaid_invoices=[i["file"] for i in unpaid],
            unpaid_total_fcfa=round(sum(i["total"] for i in unpaid if i["currency"] == "XOF"), 2),
            unpaid_total_usd=round(sum(i["total"] for i in unpaid if i["currency"] == "USD"), 2),
            receipts_over_100k=[dict(file=r["file"], amount=r["amount"], code=r["code"]) for r in over100k],
            receipts_over_100k_total=round(sum(r["amount"] for r in over100k), 2),
            q2_2024_paid_by_supplier={
                sup: dict(files=[i["file"] for i in rows],
                          total=round(sum(i["total"] for i in rows), 2),
                          currency=rows[0]["currency"] if rows else None)
                for sup, rows in q2_by_supplier.items()
            },
            q3_2024_issued_invoices=[i["file"] for i in q3_invs],
            q3_2024_issued_total_fcfa=round(sum(i["total"] for i in q3_invs if i["currency"] == "XOF"), 2),
            q3_2024_issued_total_usd=round(sum(i["total"] for i in q3_invs if i["currency"] == "USD"), 2),
            june_2024_issued_invoices=[i["file"] for i in june_invs],
            total_receipts_2024=round(sum(r["amount"] for r in recs), 2),
            total_2024_spend_by_supplier={
                sup: round(sum(i["total"] for i in invs if i["supplier"] == sup), 2)
                for sup in sorted({i["supplier"] for i in invs})
            },
            total_2024_senexport=round(sum(i["total"] for i in invs if i["supplier"] == "SENEXPORT SA"), 2),
            total_2024_gcd=round(sum(i["total"] for i in invs if i["supplier"] == "Groupe Comptoir de Dakar"), 2),
        ),
    )


# ── Gold QA set ────────────────────────────────────────────────────

def _gold(qid: str, category: str, question: str, lang: str, answer: str,
          values: list[dict] | None, source: str, files: list[str],
          sql_path: str) -> dict:
    return dict(id=qid, category=category, question=question, lang=lang,
                gold_answer=answer, gold_values=values or [], gold_source=source,
                gold_files=files, sql_path=sql_path)


def build_gold_qa(m: dict) -> list[dict]:
    inv = {i["code"]: i for i in m["invoices"]}
    rec = {r["code"]: r for r in m["receipts"]}
    comp = m["computed"]
    st_at_q1 = next(s for s in m["statements"]
                    if s["supplier"] == "AfricaTextiles Ltd" and s["period"] == "Q1 2024")
    g: list[dict] = []

    # 1. numeric_extraction (10)
    g += [
        _gold("num_01", "numeric_extraction", "How much was invoice AT-2024-0007?", "en",
              f"{fmt_usd(inv['AT-2024-0007']['total'])} USD",
              [dict(currency="USD", value=inv["AT-2024-0007"]["total"])],
              inv["AT-2024-0007"]["file"], [inv["AT-2024-0007"]["file"]], "sql"),
        _gold("num_02", "numeric_extraction", "Quel est le montant total de la facture GCD-2024-014 ?", "fr",
              f"{fmt_xof(inv['GCD-2024-014']['total'])} FCFA",
              [dict(currency="XOF", value=inv["GCD-2024-014"]["total"])],
              inv["GCD-2024-014"]["file"], [inv["GCD-2024-014"]["file"]], "sql"),
        _gold("num_03", "numeric_extraction", "What is the total of invoice WH-2024-004?", "en",
              f"{fmt_usd(inv['WH-2024-004']['total'])} USD",
              [dict(currency="USD", value=inv["WH-2024-004"]["total"])],
              inv["WH-2024-004"]["file"], [inv["WH-2024-004"]["file"]], "sql"),
        _gold("num_04", "numeric_extraction", "Quel est le montant de la facture SX-2024-011 ?", "fr",
              f"{fmt_xof(inv['SX-2024-011']['total'])} FCFA",
              [dict(currency="XOF", value=inv["SX-2024-011"]["total"])],
              inv["SX-2024-011"]["file"], [inv["SX-2024-011"]["file"]], "sql"),
        _gold("num_05", "numeric_extraction", "How much was invoice IF-2024-029?", "en",
              f"{fmt_usd(inv['IF-2024-029']['total'])} USD",
              [dict(currency="USD", value=inv["IF-2024-029"]["total"])],
              inv["IF-2024-029"]["file"], [inv["IF-2024-029"]["file"]], "sql"),
        _gold("num_06", "numeric_extraction", "Quel est le montant du reçu RCP-2024-031 ?", "fr",
              f"{fmt_xof(rec['RCP-2024-031']['amount'])} FCFA",
              [dict(currency="XOF", value=rec["RCP-2024-031"]["amount"])],
              rec["RCP-2024-031"]["file"], [rec["RCP-2024-031"]["file"]], "sql"),
        _gold("num_07", "numeric_extraction", "What is the amount of receipt RCP-2024-015?", "en",
              f"{fmt_xof(rec['RCP-2024-015']['amount'])} FCFA",
              [dict(currency="XOF", value=rec["RCP-2024-015"]["amount"])],
              rec["RCP-2024-015"]["file"], [rec["RCP-2024-015"]["file"]], "sql"),
        _gold("num_08", "numeric_extraction", "Combien coûte la facture CF-2024-009 ?", "fr",
              f"{fmt_xof(inv['CF-2024-009']['total'])} FCFA",
              [dict(currency="XOF", value=inv["CF-2024-009"]["total"])],
              inv["CF-2024-009"]["file"], [inv["CF-2024-009"]["file"]], "sql"),
        _gold("num_09", "numeric_extraction", "What is the total amount of invoice AT-2024-0060?", "en",
              f"{fmt_usd(inv['AT-2024-0060']['total'])} USD",
              [dict(currency="USD", value=inv["AT-2024-0060"]["total"])],
              inv["AT-2024-0060"]["file"], [inv["AT-2024-0060"]["file"]], "sql"),
        _gold("num_10", "numeric_extraction", "Quel est le montant de la facture GCD-2024-046 ?", "fr",
              f"{fmt_xof(inv['GCD-2024-046']['total'])} FCFA",
              [dict(currency="XOF", value=inv["GCD-2024-046"]["total"])],
              inv["GCD-2024-046"]["file"], [inv["GCD-2024-046"]["file"]], "sql"),
    ]

    # 2. temporal (10)
    at_q1_files = ", ".join(f.split(".")[0] for f in comp["africatextiles_q1_2024_paid"]["files"])
    g += [
        _gold("tmp_01", "temporal",
              "What did we pay AfricaTextiles Ltd between January and March 2024?", "en",
              f"{fmt_usd(comp['africatextiles_q1_2024_paid']['total_paid'])} USD "
              f"(invoices {at_q1_files})",
              [dict(currency="USD", value=comp["africatextiles_q1_2024_paid"]["total_paid"])],
              comp["africatextiles_q1_2024_paid"]["files"][0],
              comp["africatextiles_q1_2024_paid"]["files"], "sql"),
        _gold("tmp_02", "temporal",
              "Which AfricaTextiles invoices were issued in Q1 2024?", "en",
              ", ".join(f.split(".")[0] for f in comp["africatextiles_q1_2024_issued"]),
              [], comp["africatextiles_q1_2024_issued"][0],
              comp["africatextiles_q1_2024_issued"], "sql"),
        _gold("tmp_03", "temporal",
              "How much did we pay Groupe Comptoir de Dakar in Q2 2024?", "en",
              f"{fmt_xof(comp['q2_2024_paid_by_supplier']['Groupe Comptoir de Dakar']['total'])} FCFA",
              [dict(currency="XOF", value=comp["q2_2024_paid_by_supplier"]["Groupe Comptoir de Dakar"]["total"])],
              comp["q2_2024_paid_by_supplier"]["Groupe Comptoir de Dakar"]["files"][0],
              comp["q2_2024_paid_by_supplier"]["Groupe Comptoir de Dakar"]["files"], "sql"),
        _gold("tmp_04", "temporal",
              "What did we pay SENEXPORT SA between January and March 2024?", "en",
              f"{fmt_xof(821280 + 377600)} FCFA (invoices SX-2024-003, SX-2024-011)",
              [dict(currency="XOF", value=821280 + 377600)],
              inv["SX-2024-003"]["file"], [inv["SX-2024-003"]["file"], inv["SX-2024-011"]["file"]], "sql"),
        _gold("tmp_05", "temporal", "List the receipts from March 2024.", "en",
              "RCP-2024-011 (125 000 FCFA)",
              [dict(currency="XOF", value=125000)],
              rec["RCP-2024-011"]["file"], [rec["RCP-2024-011"]["file"]], "sql"),
        _gold("tmp_06", "temporal",
              "Which invoices were issued between July and September 2024?", "en",
              ", ".join(f.split(".")[0] for f in comp["q3_2024_issued_invoices"]),
              [], comp["q3_2024_issued_invoices"][0],
              comp["q3_2024_issued_invoices"], "sql"),
        _gold("tmp_07", "temporal", "Which invoices were issued in June 2024?", "en",
              ", ".join(f.split(".")[0] for f in comp["june_2024_issued_invoices"]),
              [], comp["june_2024_issued_invoices"][0],
              comp["june_2024_issued_invoices"], "sql"),
        _gold("tmp_08", "temporal",
              "What did we pay IndoFab Textiles in Q2 2024?", "en",
              f"{fmt_usd(6380.0)} USD (invoice IF-2024-005)",
              [dict(currency="USD", value=6380.0)],
              inv["IF-2024-005"]["file"], [inv["IF-2024-005"]["file"]], "sql"),
        _gold("tmp_09", "temporal",
              "Quelles factures Groupe Comptoir ont été émises au premier trimestre 2024 ?", "fr",
              "GCD-2024-001, GCD-2024-008, GCD-2024-014",
              [], inv["GCD-2024-001"]["file"],
              [inv["GCD-2024-001"]["file"], inv["GCD-2024-008"]["file"], inv["GCD-2024-014"]["file"]], "sql"),
        _gold("tmp_10", "temporal",
              "What was the closing balance on the AfricaTextiles Q1 2024 statement?", "en",
              f"{fmt_usd(st_at_q1['closing'])} USD",
              [dict(currency="USD", value=st_at_q1["closing"])],
              st_at_q1["file"], [st_at_q1["file"]], "sql"),
    ]

    # 3. aggregation (10)
    g += [
        _gold("agg_01", "aggregation",
              "What is our total VAT paid in Q1 2024?", "en",
              f"{fmt_xof(comp['q1_2024_tva_total'])} FCFA",
              [dict(currency="XOF", value=comp["q1_2024_tva_total"])],
              comp["q1_2024_tva_invoices"][0], comp["q1_2024_tva_invoices"], "sql"),
        _gold("agg_02", "aggregation",
              "What is the total amount of all unpaid invoices?", "en",
              f"{fmt_xof(comp['unpaid_total_fcfa'])} FCFA + {fmt_usd(comp['unpaid_total_usd'])} USD",
              [dict(currency="XOF", value=comp["unpaid_total_fcfa"]),
               dict(currency="USD", value=comp["unpaid_total_usd"])],
              comp["unpaid_invoices"][0], comp["unpaid_invoices"], "sql"),
        _gold("agg_03", "aggregation", "How many receipts are over 100,000 FCFA?", "en",
              "4", [dict(currency="count", value=4)],
              comp["receipts_over_100k"][0]["file"],
              [r["file"] for r in comp["receipts_over_100k"]], "sql"),
        _gold("agg_04", "aggregation",
              "What is the total amount of receipts over 100,000 FCFA?", "en",
              f"{fmt_xof(comp['receipts_over_100k_total'])} FCFA",
              [dict(currency="XOF", value=comp["receipts_over_100k_total"])],
              comp["receipts_over_100k"][0]["file"],
              [r["file"] for r in comp["receipts_over_100k"]], "sql"),
        _gold("agg_05", "aggregation",
              "What is the total of all invoices from Groupe Comptoir de Dakar in 2024?", "en",
              f"{fmt_xof(comp['total_2024_gcd'])} FCFA",
              [dict(currency="XOF", value=comp["total_2024_gcd"])],
              inv["GCD-2024-001"]["file"],
              [i["file"] for i in m["invoices"] if i["supplier"] == "Groupe Comptoir de Dakar"], "sql"),
        _gold("agg_06", "aggregation",
              "What is our total spend with AfricaTextiles in 2024?", "en",
              f"{fmt_usd(comp['total_2024_spend_by_supplier']['AfricaTextiles Ltd'])} USD",
              [dict(currency="USD", value=comp["total_2024_spend_by_supplier"]["AfricaTextiles Ltd"])],
              inv["AT-2024-0007"]["file"],
              [i["file"] for i in m["invoices"] if i["supplier"] == "AfricaTextiles Ltd"], "sql"),
        _gold("agg_07", "aggregation", "Combien de reçus dépassent 100 000 FCFA ?", "fr",
              "4", [dict(currency="count", value=4)],
              comp["receipts_over_100k"][0]["file"],
              [r["file"] for r in comp["receipts_over_100k"]], "sql"),
        _gold("agg_08", "aggregation",
              "What is the total amount of unpaid invoices in FCFA?", "en",
              f"{fmt_xof(comp['unpaid_total_fcfa'])} FCFA",
              [dict(currency="XOF", value=comp["unpaid_total_fcfa"])],
              comp["unpaid_invoices"][0], comp["unpaid_invoices"], "sql"),
        _gold("agg_09", "aggregation",
              "What is the total value of all invoices issued in Q3 2024?", "en",
              f"{fmt_xof(comp['q3_2024_issued_total_fcfa'])} FCFA + {fmt_usd(comp['q3_2024_issued_total_usd'])} USD",
              [dict(currency="XOF", value=comp["q3_2024_issued_total_fcfa"]),
               dict(currency="USD", value=comp["q3_2024_issued_total_usd"])],
              comp["q3_2024_issued_invoices"][0], comp["q3_2024_issued_invoices"], "sql"),
        _gold("agg_10", "aggregation", "What is the total of all receipts in 2024?", "en",
              f"{fmt_xof(comp['total_receipts_2024'])} FCFA",
              [dict(currency="XOF", value=comp["total_receipts_2024"])],
              rec["RCP-2024-002"]["file"], [r["file"] for r in m["receipts"]], "sql"),
    ]

    # 4. contract (10)
    lease = next(c for c in m["contracts"] if c["type"] == "warehouse_lease")
    senexp = next(c for c in m["contracts"] if c["file"] == "contrat_appro_senexport.pdf")
    at_agr = next(c for c in m["contracts"] if c["file"] == "supply_agreement_africatextiles.pdf")
    credit = next(c for c in m["contracts"] if c["type"] == "bank_credit_line")
    g += [
        _gold("con_01", "contract",
              "What is the monthly rent in the warehouse lease?", "en",
              "850 000 FCFA per month",
              [dict(currency="XOF", value=850000)], lease["file"], [lease["file"]], "sql"),
        _gold("con_02", "contract",
              "What is the late payment penalty in the SENEXPORT supply agreement?", "en",
              "2% per month",
              [dict(currency="pct", value=2.0)], senexp["file"], [senexp["file"]], "sql"),
        _gold("con_03", "contract",
              "How many months is the warehouse lease term?", "en",
              "36 months", [dict(currency="count", value=36)], lease["file"], [lease["file"]], "sql"),
        _gold("con_04", "contract",
              "What is the credit line amount in the bank agreement?", "en",
              "5 000 000 FCFA",
              [dict(currency="XOF", value=5000000)], credit["file"], [credit["file"]], "sql"),
        _gold("con_05", "contract",
              "What deposit is required for the warehouse lease?", "en",
              "2 months of rent", [dict(currency="months", value=2)],
              lease["file"], [lease["file"]], "sql"),
        _gold("con_06", "contract",
              "What are the payment terms in the AfricaTextiles supply agreement?", "en",
              "Net 30 days from the date of each invoice",
              [dict(currency="days", value=30)], at_agr["file"], [at_agr["file"]], "sql"),
        _gold("con_07", "contract",
              "Quelle est la pénalité de retard dans le contrat SENEXPORT ?", "fr",
              "2% par mois", [dict(currency="pct", value=2.0)],
              senexp["file"], [senexp["file"]], "sql"),
        _gold("con_08", "contract",
              "Summarize the payment terms in the warehouse lease.", "en",
              "Rent of 850 000 FCFA per month, payable by the 5th of each month; "
              "a 5% per month penalty applies to late payments; a 2-month deposit is required.",
              [], lease["file"], [lease["file"]], "semantic"),
        _gold("con_09", "contract",
              "What is the interest rate on the bank credit line?", "en",
              "9% per year", [dict(currency="pct", value=9.0)],
              credit["file"], [credit["file"]], "sql"),
        _gold("con_10", "contract",
              "Quelles sont les conditions de paiement du bail de l'entrepôt ?", "fr",
              "Loyer de 850 000 FCFA par mois payable le 5 de chaque mois, "
              "pénalité de retard de 5% par mois, dépôt de garantie de 2 mois.",
              [], lease["file"], [lease["file"]], "semantic"),
    ]

    # 5. multilingual (10, FR)
    unpaid_list = ", ".join(f.split(".")[0] for f in comp["unpaid_invoices"])
    over100k_list = ", ".join(f"{r['code']} ({fmt_xof(r['amount'])} FCFA)" for r in comp["receipts_over_100k"])
    senexport_total = comp["total_2024_senexport"]
    g += [
        _gold("mul_01", "multilingual", "Quelles factures sont encore impayées ?", "fr",
              unpaid_list, [], comp["unpaid_invoices"][0], comp["unpaid_invoices"], "sql"),
        _gold("mul_02", "multilingual",
              "Combien avons-nous payé à AfricaTextiles entre janvier et mars 2024 ?", "fr",
              f"{fmt_usd(comp['africatextiles_q1_2024_paid']['total_paid'])} USD",
              [dict(currency="USD", value=comp["africatextiles_q1_2024_paid"]["total_paid"])],
              comp["africatextiles_q1_2024_paid"]["files"][0],
              comp["africatextiles_q1_2024_paid"]["files"], "sql"),
        _gold("mul_03", "multilingual", "Quel est le loyer mensuel de l'entrepôt ?", "fr",
              "850 000 FCFA par mois", [dict(currency="XOF", value=850000)],
              lease["file"], [lease["file"]], "sql"),
        _gold("mul_04", "multilingual", "Montrez-moi les reçus de plus de 100 000 FCFA.", "fr",
              over100k_list, [], comp["receipts_over_100k"][0]["file"],
              [r["file"] for r in comp["receipts_over_100k"]], "sql"),
        _gold("mul_05", "multilingual",
              "Quelles sont les conditions de paiement du bail de l'entrepôt ?", "fr",
              "Loyer de 850 000 FCFA par mois payable le 5 de chaque mois, "
              "pénalité de retard de 5% par mois, dépôt de garantie de 2 mois.",
              [], lease["file"], [lease["file"]], "semantic"),
        _gold("mul_06", "multilingual",
              "Combien de factures Groupe Comptoir sont impayées ?", "fr",
              "2", [dict(currency="count", value=2)],
              inv["GCD-2024-030"]["file"],
              [inv["GCD-2024-030"]["file"], inv["GCD-2024-046"]["file"]], "sql"),
        _gold("mul_07", "multilingual",
              "Quel est le montant total des factures de SENEXPORT en 2024 ?", "fr",
              f"{fmt_xof(senexport_total)} FCFA",
              [dict(currency="XOF", value=senexport_total)],
              inv["SX-2024-003"]["file"],
              [i["file"] for i in m["invoices"] if i["supplier"] == "SENEXPORT SA"], "sql"),
        _gold("mul_08", "multilingual",
              "Quel est le solde du relevé AfricaTextiles au premier trimestre 2024 ?", "fr",
              f"{fmt_usd(st_at_q1['closing'])} USD", [dict(currency="USD", value=st_at_q1["closing"])],
              st_at_q1["file"], [st_at_q1["file"]], "sql"),
        _gold("mul_09", "multilingual",
              "Résumez les pénalités de retard dans le contrat de location.", "fr",
              "5% par mois sur les loyers impayés.", [], lease["file"], [lease["file"]], "semantic"),
        _gold("mul_10", "multilingual",
              "Quel est le montant du reçu RCP-2024-023 ?", "fr",
              "150 000 FCFA", [dict(currency="XOF", value=150000)],
              rec["RCP-2024-023"]["file"], [rec["RCP-2024-023"]["file"]], "sql"),
    ]
    return g


# ── main ───────────────────────────────────────────────────────────

def main() -> None:
    force = "--force" in sys.argv
    if OUT.exists() and any(OUT.iterdir()) and not force:
        print("documents/ already populated (use --force to regenerate)")
    else:
        emit_docs()
    m = build_manifest()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    g = build_gold_qa(m)
    GOLD_PATH.write_text(json.dumps(g, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"manifest -> {MANIFEST_PATH}")
    print(f"gold_qa ({len(g)} questions) -> {GOLD_PATH}")
    c = m["computed"]
    print("\n=== KEY COMPUTED VALUES ===")
    print("AT paid Jan-Mar 2024:", c["africatextiles_q1_2024_paid"]["total_paid"], "USD")
    print("Q1 2024 TVA total:", c["q1_2024_tva_total"], "FCFA")
    print("Unpaid invoices:", len(c["unpaid_invoices"]), "| XOF:", c["unpaid_total_fcfa"], "USD:", c["unpaid_total_usd"])
    print("Receipts >100k:", len(c["receipts_over_100k"]), "total:", c["receipts_over_100k_total"])
    print("Q2 paid GCD:", c["q2_2024_paid_by_supplier"]["Groupe Comptoir de Dakar"]["total"])
    print("Q2 paid AT:", c["q2_2024_paid_by_supplier"]["AfricaTextiles Ltd"]["total"])
    print("SENEXPORT 2024 total:", c["total_2024_senexport"])
    print("Total receipts 2024:", c["total_receipts_2024"])


if __name__ == "__main__":
    main()
