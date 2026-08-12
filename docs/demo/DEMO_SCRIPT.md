# SME Brief — Demo Video Script & Storyboard

**Target length: 90–120 seconds** (hackathon demo sweet spot). Screen-record at 1080p, no music under narration.
Suggested tooling: OBS Studio (free) capturing a 1280×800 browser window at 60fps.

---

## Shot 1 — Cold open: the problem (0:00–0:15)

**Visual**: split screen — left: a pile of PDFs/invoices on a desk (or a folder of `data/synthetic/documents/`); right: a phone with "no signal".

**Narration (EN)**:
> Small businesses keep their books in invoices, receipts, contracts — in their local language, never in a database. And cloud AI assistants are useless when the internet is unreliable.

**Narration (FR version)**:
> Les petites entreprises gardent leurs comptes dans des factures, des reçus et des contrats — dans leur langue locale, jamais dans une base de données. Et les assistants IA dans le cloud ne servent à rien quand la connexion est instable.

**On screen**: title card "SME Brief — Offline RAG for African SMEs".

---

## Shot 2 — Boot (0:15–0:25)

**Visual**: terminal, `venv/bin/streamlit run src/ui/app.py`, then the browser opens on the SME Brief chat. Show `free -h` / system monitor proving it runs on a normal laptop.

**Narration**:
> SME Brief is a question-answering assistant for your company's documents. It runs 100% offline, on an ordinary 8GB laptop — no cloud, no API keys, no daemon.

---

## Shot 3 — French SQL question (0:25–0:40)

**Action**: type `Combien de factures sont impayées ?` (or click the suggestion chip).

**Expected answer**: instant, deterministic. Route badge shows **SQL**.

**Narration**:
> Money questions are answered by deterministic SQL over the company's structured rows — never guessed by the LLM. In French or English.

**Narration (FR)**:
> Les questions d'argent sont répondues par du SQL déterministe sur les données structurées — jamais inventées par le LLM. En français comme en anglais.

---

## Shot 4 — English question (0:40–0:55)

**Action**: type `What was invoice AT-2024-0007?` (or `What did we pay AfricaTextiles Ltd between January and March 2024?`).

**Expected answer**: exact value + **cited source file** below the answer.

**Narration**:
> Every answer names its source document — an auditor can verify every figure.

---

## Shot 5 — Semantic RAG answer (0:55–1:15)

**Action**: type `Résumez le contrat de bail de l'entrepôt` — *first call loads the LLM (~30s), show the spinner honestly*; then the summarized answer appears, route badge **Semantic (RAG)**, cited to the lease PDF.

**Narration**:
> Open questions — summaries, contract clauses — use retrieval-augmented generation: the relevant pages are found, fed to a small local LLM, and answered with sources. Still fully offline.

**Narration (FR)**:
> Les questions ouvertes — résumés, clauses de contrat — utilisent la génération augmentée par récupération : les pages pertinentes sont retrouvées, passées à un petit LLM local, et la réponse cite ses sources. Toujours 100% hors ligne.

---

## Shot 6 — Proof: the eval suite (1:15–1:30)

**Visual**: terminal, `venv/bin/python eval/run_eval.py` → **`PASS 50/50 FAIL_IDS=[]`**.

**Narration**:
> A gold suite of 50 bilingual question/answer pairs scores the system: 50 out of 50, exit code 0.

---

## Shot 7 — Memory check + CTA (1:30–end)

**Visual**: system monitor showing ~1.5–2GB resident; end card with project name + link.

**Narration**:
> Total memory footprint: under two gigabytes — inside the challenge's 8GB budget. SME Brief: your documents, your language, fully offline.

---

## Checklist before recording

- [ ] `venv/bin/python -m pytest tests/` → 36 passed (optional; ~3 min)
- [ ] `venv/bin/python eval/run_eval.py` → `PASS 50/50 FAIL_IDS=[]` (filmed in Shot 6)
- [ ] `venv/bin/python -m streamlit run src/ui/app.py` (note: `venv/bin/streamlit` has a stale `karatasi` shebang — use `python -m streamlit`)
- [ ] Pre-load the LLM once (ask any semantic question) so Shot 5 is fast, OR intentionally show the honest first-load spinner
- [ ] Close background apps; keep `free -h` visible for Shot 7

## Suggested questions (pick 3–4)

| Question | Route | Why |
|---|---|---|
| Combien de factures sont impayées ? | SQL | FR, deterministic |
| What was invoice AT-2024-0007? | SQL | EN, cited value |
| What did we pay AfricaTextiles Ltd between January and March 2024? | SQL | EN, supplier+period |
| Résumez le contrat de bail de l'entrepôt | Semantic | shows RAG + LLM |
| Quelles sont les conditions de paiement du bail ? | SQL | FR contract clause |
| Montrez-moi les reçus de plus de 100 000 FCFA. | SQL | XOF formatting |
