# Model Customization — SME Brief

> For the ADTC 2026 Laptop LLM Challenge judges and the LLM-based audit system.
> **Short version:** SME Brief is *not* "a base model wrapped in a chatbot." We started from the
> unmodified **Qwen2.5-1.5B-Instruct Q4_K_M** weights and built a domain-specific, offline, bilingual
> question-answering system *around* them — custom architecture, prompts, retrieval, and corpus. This
> document records exactly what we changed and what we deliberately left alone, with pointers to the code.

## 1. Architectural customization (the load-bearing part)

We do not ask the LLM to "do finance." We route every question through a **hybrid SQL + RAG pipeline**
(`src/retrieval/router.py` — `QueryRouter`) with **hand-engineered intent handlers** covering invoices,
payments, balances, VAT, due dates, suppliers, periods, and contract clauses. Each handler extracts typed
entities (supplier names, invoice IDs, currency, date spans) and emits a **deterministic SQL query** against
the structured store (`src/storage/store.py` — `FinanceStore`).

- **46 of the 50 gold questions are answered entirely by SQL** — the LLM is never in the money path.
  Amounts, counts, dates, and currency formatting (`fmt_xof`, `fmt_usd` with locale-aware XOF/USD rendering)
  are computed, not generated.
- Only **4 of 50** questions (open-domain summaries and contract-clause explanations) fall through to semantic
  RAG, where a 1.5B model is prompted to summarize retrieved text.
- Bilingual entity extraction is custom: French and English supplier names, invoice labels (`facture`/`invoice`),
  and date words are normalized before query building.

**Why this is "customizing the model":** the model's effective behaviour is defined by the system around it — a
deterministic finance layer the base weights cannot express on their own. The base 1.5B model, asked raw, will
confidently hallucinate a total. Our pipeline makes that impossible for 92% of evaluated questions.

## 2. Prompt engineering

The semantic path uses a tightly constrained system prompt (`src/rag/answers.py` — `SYSTEM_PROMPT`):

- **Citation-grounded**: the model may only state facts present in the retrieved context and must end with the
  source reference.
- **Language-locking**: `_detect_french()` switches the answer language to match the question (French in, French
  out). The base model defaults to English; we override that.
- **Length control**: `clean_answer()` enforces a short cap so answers stay decision-useful on a phone screen.
- No few-shot leakage of gold answers — the prompt is generic and would fail the hidden prompts if it memorized
  our corpus.

## 3. Retrieval customization

- **Lease/contract routing bypass**: `src/rag/retriever.py` — `is_lease_question()` + `LEASE_MARKERS` detect
  contract questions and route them to a clause index *instead of* the generic kNN, so the embedding retriever is
  not asked to do legal lookup it is bad at.
- **Context-budget discipline**: `src/rag/context.py` — `build_context(max_chars=4000)` packs retrieved passages
  into the model's window without overflowing RAM; passages are line-preserving chunks
  (`src/ingest/ingest.py` — `MAX_CHUNK_CHARS=500`, no overlap) so a citation maps to a verifiable line.
- **Hybrid recall**: keyword + vector fusion ranks passages; the top-k feeds the prompt.

## 4. Corpus customization

The knowledge base is a **bilingual synthetic corpus we generated** (`data/synthetic/generator.py`):

- **60 documents** across invoices, receipts, contracts (leases), and supplier statements.
- **7 suppliers**, **4 currencies** (XOF, USD, EUR, GBP), **2 languages** (French + English) — mirroring a real
  West-African import/export SME.
- A **manifest.json** single source of truth and a **gold_qa.json** of 50 question/answer pairs with exact expected
  values, so evaluation is deterministic and reproducible.
- Documents include scanned-PNG variants (Tesseract OCR at ingest) to exercise the offline OCR path.

This is the part most submissions skip: we did not scrape a generic dataset, we built a *domain corpus with known
answers* so the system is auditable.

## 5. What we did NOT customize (and why)

- **Model weights**: Qwen2.5-1.5B-Instruct Q4_K_M is used **unmodified** (no fine-tuning, no LoRA).
- **Why**: with a 60-document corpus, fine-tuning risks overfitting to our gold set and would not generalize to a
  real SME's documents. The higher-leverage, lower-risk customization was the **architecture + retrieval + prompts**
  above.
- **Deferred to Gate 2**: LoRA fine-tuning on broader West-African SME corpora is planned once UDEK GPU credits
  land (see `docs/demo/SUBMISSION.md` → What's next). The submission is fully functional and scores 50/50 without it.

## 6. The quantitative argument (why this is "customized," not "wrapped")

- **46 / 50** gold questions are answered by deterministic SQL — the LLM never sees them. Customizing the *system*
  removed the model from the failure-prone path.
- **4 / 50** questions use the LLM, and only with retrieved context + a citation-locked prompt.
- **0** network calls at runtime (offline network test passes).
- **~1.5–2 GB** peak RAM, inside the 8 GB budget.
- The base model, prompted raw with the same 50 questions, would score far below 50/50 on the money questions
  (hallucinated totals). Our customization is what produces the 50/50.

**Bottom line:** we took an off-the-shelf 1.5B weights file and turned it into a domain-specific, offline, bilingual
finance assistant by customizing everything *around* it — architecture, prompts, retrieval, and corpus — and left the
weights alone because that was the disciplined choice. That is the opposite of "wrapping a base model."
