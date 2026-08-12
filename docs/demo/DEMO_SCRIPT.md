# SME Brief — Demo Video Script & Storyboard

**Target length: 90–120 seconds.** Screen-record at 1080p, no music under narration. Keep a **system monitor
overlay (CPU / RAM / network)** pinned in the corner from Shot 2 through Shot 8 — it is the proof.

Suggested tooling: OBS Studio capturing a 1280×800 browser window + a small `btop` / `free -h` overlay.

---

## Shot 1 — Cold open: the problem (0:00–0:15)

**Visual**: split screen — left: a folder of `data/synthetic/documents/` (invoices, a lease PDF, scanned receipts);
right: a phone showing "no signal".

**Narration (EN)**: Small businesses keep their books in invoices, receipts, contracts — in their local language,
never in a database. And cloud AI is useless when the internet is unreliable.

**Narration (FR)**: Les petites entreprises gardent leurs comptes dans des factures, des reçus, des contrats —
dans leur langue, jamais dans une base de données. Et l'IA dans le cloud ne sert à rien sans connexion.

**On screen**: title card "SME Brief — Offline RAG for African SMEs".

---

## Shot 2 — Boot + system monitor (0:15–0:30)

**Visual**: terminal `python -m streamlit run src/ui/app.py`; browser opens on the SME Brief chat. A **system
monitor overlay** (RAM ~1.5 GB, 0% network) is pinned in the corner and stays for the rest of the video.

**Narration**: SME Brief answers questions about your own company documents. 100% offline, on an ordinary 8GB
laptop — no cloud, no API keys, no daemon. Watch the network meter: it stays at zero.

---

## Shot 3 — French SQL question (0:30–0:45)

**Action**: type `Combien de factures sont impayées ?` (or click the suggestion chip).

**Expected answer**: instant, deterministic. Route badge shows **SQL**.

**Narration**: Money questions are answered by deterministic SQL over the company's own rows — never guessed by the
LLM. In French or English.

**Narration (FR)**: Les questions d'argent sont répondues par du SQL déterministe — jamais inventées par le LLM.

---

## Shot 4 — English question + citation hover (0:45–1:00)

**Action**: type `What was invoice AT-2024-0007?` → exact value appears. **Hover the citation chip**; a panel
slides out showing the source PDF + the exact line.

**Expected answer**: `8,120.00 USD` + cited source file; hover reveals the page/line.

**Narration**: Every answer names its source. Hover it — you can verify the figure against the original document.
An auditor's dream.

---

## Shot 5 — THE UNPLUG MOMENT (1:00–1:15) ⭐

**Action**: physically **unplug the ethernet / disable Wi-Fi** on camera. Then immediately ask
`Quel est le solde du fournisseur Groupe Comptoir ?` (or any question). The answer returns, instantly, offline.

**Narration**: Watch — I just pulled the network cable. SME Brief doesn't notice. Your data never left the laptop.
This is what "sovereign AI" means for an African SME: the answer works even when the connection doesn't.

**On screen**: big caption "0 network calls. Your documents never leave the laptop."

---

## Shot 6 — Semantic RAG answer (1:15–1:30)

**Action**: type `Résumez le contrat de bail de l'entrepôt` — first call loads the LLM (~30s, show the spinner
honestly); then a summarized answer appears, route badge **Semantic (RAG)**, cited to the lease PDF.

**Narration**: Open questions — summaries, clauses — use retrieval-augmented generation over your own documents,
answered by a small local model. Still offline, still cited.

**Narration (FR)**: Les questions ouvertes — résumés, clauses — utilisent la génération augmentée par récupération :
les pages pertinentes sont retrouvées, passées à un petit LLM local, et la réponse cite ses sources. Toujours 100%
hors ligne.

---

## Shot 7 — The profiler (1:30–1:45)

**Visual**: terminal, `adtc-profiler run --submission . --mode participant --output submission.json --skip-accuracy`
→ prints **thermal / RAM / tokens-per-second** measured on the laptop.

**Narration**: The official ADTC profiler measures this exact machine: RAM under budget, tokens per second, thermal
— all logged in submission.json. No gaming the benchmark.

---

## Shot 8 — Memory + CTA (1:45–end)

**Visual**: the still-visible system monitor shows ~1.5–2 GB resident; end card: project name + repo link +
"Your documents. Your language. Your laptop."

**Narration**: Under two gigabytes of RAM. Fully offline. Bilingual. SME Brief turns an off-the-shelf 1.5B model
into a finance assistant that works where your business actually is.

---

## Checklist before recording

- [ ] `python -m pytest tests/` → green
- [ ] `python eval/run_eval.py` → `PASS 50/50` (the audit system re-runs this)
- [ ] `python -m streamlit run src/ui/app.py` (use `python -m streamlit`, not the `venv/bin/streamlit` shebang)
- [ ] Pre-load the LLM once so Shot 6 is fast, OR show the honest first-load spinner
- [ ] System monitor overlay ON for Shots 2–8; network meter visible
- [ ] For Shot 5: have the cable / disable-wifi ready; verify the answer still returns

## Suggested questions (pick 4–5 across the video)

| Question | Route | Why |
|---|---|---|
| Combien de factures sont impayées ? | SQL | FR, deterministic |
| What was invoice AT-2024-0007? | SQL | EN, cited + hover |
| Quel est le solde du fournisseur Groupe Comptoir ? | SQL | FR, used in unplug moment |
| Résumez le contrat de bail de l'entrepôt | Semantic | shows RAG + LLM |
| Montrez-moi les reçus de plus de 100 000 FCFA. | SQL | XOF formatting |
