# Mission

You are preparing a submission for the **Africa Deep Tech Challenge 2026** ("The Laptop LLM Challenge"). Deadline: **Aug 25, 2026 @ 6:45am UTC**.

The user has an existing application repo at `https://github.com/kish-00/karatasi` (cloned locally at `/home/z/my-project/research/karatasi/`). It's an offline bilingual (FR/EN) RAG system for African SMEs called **SME Brief** — 50/50 gold eval passing, 36 tests green, hybrid SQL+RAG architecture complete.

However — **the karatasi repo is NOT the submission.** Per the official ADTC 2026 rules, the submission must be a fork of the official submission template repo with a specific file structure. The karatasi repo becomes supporting material referenced from the submission's REPORT.md.

Your job: create the official submission repo (forked from the template), populate it with the required files, run the official profiler, and produce a valid `submission.json`. Do NOT modify the karatasi repo's application code — only update its README to reference the submission repo.

---

# The Two Official Repositories (use these exact URLs)

1. **Submission Template** (fork this): `https://github.com/Africa-Deep-Tech-Foundation/adtc-2026-submission-template`
2. **ADTC Profiler** (install from this): `https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler`

---

# Hard Rules From The Template README (non-negotiable)

1. **Fork the template repo** — your submission is a public GitHub repo forked from `Africa-Deep-Tech-Foundation/adtc-2026-submission-template`. Suggested name: `kish-00/adtc-2026-submission`.
2. **llama.cpp only** — no other runtime accepted. (Your Qwen2.5-1.5B via llama-cpp-python is fine.)
3. **GGUF weights only** — Q4_K_M or Q5_K_M. (Your Qwen2.5-1.5B-Instruct Q4_K_M is fine.)
4. **No model weights in git** — `*.gguf` and `model/` must be in `.gitignore`. The evaluator downloads weights fresh via `download_model.sh`.
5. **`download_model.sh` must be idempotent and credential-free** — safe to re-run, fetches from a public URL (Hugging Face, GitHub Releases, or any stable public URL).
6. **Exactly 2 test prompts** in `metadata.json` `test_prompts[]` array. Organizers add 2 hidden prompts; all 4 scored for accuracy (50% of total).
7. **100% offline during evaluation** — `download_model.sh` runs before profiling; once profiling starts, zero network calls.
8. **8 GB RAM hard limit** — OOM = automatic disqualification.
9. **Public repo required** at evaluation time.
10. **REPORT.md**: 4 sections — Problem, Design Decisions, Constraints, Benchmarks. 1-3 pages. Factual and specific.

---

# Critical Realization: What Actually Gets Scored

The profiler runs the **raw GGUF model** via llama.cpp — NOT the SME Brief application (SQL router, RAG pipeline, Streamlit UI). The application layer is explicitly optional per the organizers ("challenge focuses on the model itself, not user interface").

**What IS scored:**
- The Qwen2.5-1.5B-Instruct Q4_K_M model file (GGUF)
- Its inference performance on 8GB laptop: throughput, memory, thermals (40%)
- Its accuracy on 4 prompts — 2 supplied by you + 2 hidden (50%)
- African use case relevance argued in REPORT.md (up to 10 bonus points)

**What is NOT directly scored (but supports the African bonus argument):**
- The SME Brief application (SQL router, RAG, bilingual eval suite)
- The Streamlit UI
- The 50/50 gold eval suite

**Strategic implication**: The 2 test prompts in `metadata.json` must be answerable by the **raw Qwen2.5-1.5B model** on its own — no RAG, no SQL router, no corpus. They should showcase the model's domain knowledge and bilingual ability in the `corporate_enterprise` domain. The SME Brief application is described in REPORT.md as the "use case demonstration" that supports the African relevance bonus.

---

# Verified Current State (karatasi repo — trust, do not re-verify)

- Gold-QA eval: `PASS 50/50, FAIL_IDS=[]`
- Test suite: 36 passed
- Model: Qwen2.5-1.5B-Instruct Q4_K_M GGUF, downloaded by `scripts/download_models.py` into `models/`
- Domain fit: `corporate_enterprise` (knowledge-work productivity for SMEs — matches the Devpost domain definition exactly)
- Languages: EN + FR (bilingual)
- African use case: strong (Senegalese SME persona, XOF+USD currencies, ECOWAS commerce context)

---

# Tasks (in execution order)

## TASK 1 — Fork the template repo and create the submission structure

**Step 1: Fork the template on GitHub.** The user must do this manually — opencode cannot fork repos via the GitHub API without credentials. Instruct the user to:
1. Go to `https://github.com/Africa-Deep-Tech-Foundation/adtc-2026-submission-template`
2. Click "Fork" in the top right
3. Name the fork `adtc-2026-submission` (so the full URL is `https://github.com/kish-00/adtc-2026-submission`)
4. Clone the fork locally to `/home/z/my-project/research/adtc-2026-submission`

**Step 2: Inspect the forked repo.** Read the template's README.md, REPORT.md, metadata.json, and download_model.sh to understand the exact required structure. The template contains placeholder values that you must replace.

**Step 3: Verify the file structure matches:**
```
adtc-2026-submission/
├── metadata.json          ← Required. Team, model, and test prompt metadata.
├── download_model.sh      ← Required. Downloads your .gguf model weight file.
├── REPORT.md              ← Required. Technical writeup (problem, design, benchmarks).
├── model/                 ← Created by download_model.sh. Do NOT commit.
│   └── *.gguf
└── .gitignore             ← Must exclude *.gguf and model/
```

**Acceptance:**
- Fork exists at `https://github.com/kish-00/adtc-2026-submission` (public)
- Local clone at `/home/z/my-project/research/adtc-2026-submission`
- File structure matches the template

---

## TASK 2 — Write `metadata.json`

Replace the template's placeholder metadata.json with your real values. Use this exact schema:

```json
{
  "team_id": "<USER_TO_PROVIDE>",
  "domain": "corporate_enterprise",
  "language_scope": ["en", "fr"],
  "african_alpha_claim": true,
  "budget_laptop_claim": true,
  "submitter": {
    "name": "<USER_TO_PROVIDE>",
    "email": "<USER_TO_PROVIDE>",
    "github_handle": "kish-00"
  },
  "cross_disciplinary_pairing": {
    "discipline": "small_business_finance",
    "load_bearing": true,
    "description": "The model serves small-business financial management for West African SMEs operating across FR/EN language borders, with domain-specific reasoning about invoices, contracts, supplier statements, and cash flow in XOF and USD currencies."
  },
  "test_prompts": [
    {
      "prompt_id": "tp_001",
      "prompt": "Draft a polite email in French to a supplier in Dakar requesting a 30-day payment extension for invoice FACT-2024-0042, due to a temporary cash flow delay. Keep it under 120 words."
    },
    {
      "prompt_id": "tp_002",
      "prompt": "A small import/export business in West Africa has 50,000 USD in unpaid customer invoices and 30,000 USD in outstanding supplier payments. Explain three practical steps the owner should take this week to improve cash flow. Be specific and concise."
    }
  ],
  "model": {
    "name": "Qwen2.5-1.5B-Instruct-Q4_K_M",
    "runtime": "llama.cpp",
    "quantization": "GGUF Q4_K_M",
    "parameters_estimate": "1.5B",
    "packaging": "binary_bundle"
  },
  "_runtime": {
    "model_path": "model/qwen2.5-1.5b-instruct-q4_k_m.gguf"
  }
}
```

**Before finalizing the test prompts — TEST THEM LOCALLY.** Run each prompt through the raw Qwen2.5-1.5B model (via the karatasi repo's `src/llm/serve.py` or directly via `llama-cpp-python`) and verify the model produces a reasonable, coherent answer. If the model struggles with a prompt, replace it. The prompts must showcase:
- Domain knowledge (`corporate_enterprise` — finance, business communication)
- Bilingual ability (one FR, one EN)
- African SME relevance
- The model's strengths (instruction following, concise drafting)

**Stop and ask the user for**:
- Their `team_id` (from the ADTC portal registration)
- Their real name and email for the `submitter` field

**Acceptance:**
- `metadata.json` exists with no placeholder values remaining
- `domain` is `corporate_enterprise`
- `language_scope` is `["en", "fr"]`
- `african_alpha_claim` is `true`
- `test_prompts` has exactly 2 entries with `prompt_id` `tp_001` and `tp_002`
- Both prompts tested locally against the raw model and produce reasonable answers
- `model.runtime` is `llama.cpp`
- `model.quantization` is `GGUF Q4_K_M`
- `_runtime.model_path` matches the filename in `download_model.sh`

---

## TASK 3 — Write `download_model.sh`

The script must:
1. Be idempotent (skip download if file already exists and matches expected size)
2. Work without credentials (public URL)
3. Download to `model/qwen2.5-1.5b-instruct-q4_k_m.gguf`
4. The path must exactly match `_runtime.model_path` in metadata.json

**Recommended source**: Hugging Face. The Qwen2.5-1.5B-Instruct GGUF in Q4_K_M is available at:
- `https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf`
- Or the bartowski mirror: `https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf`

**Verify the URL works** before committing. Run `curl -sI <URL>` and check for HTTP 200 or 302. If the official Qwen URL doesn't work, use the bartowski mirror.

**Script template:**
```bash
#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="$(cd "$(dirname "$0")" && pwd)/model"
MODEL_FILE="$MODEL_DIR/qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
EXPECTED_SIZE_BYTES=986051072  # ~940 MB; update after first download

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_FILE" ]; then
  ACTUAL_SIZE=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE")
  if [ "$ACTUAL_SIZE" -eq "$EXPECTED_SIZE_BYTES" ]; then
    echo "Model already present, skipping download."
    exit 0
  fi
fi

echo "Downloading Qwen2.5-1.5B-Instruct Q4_K_M GGUF..."
curl -L -o "$MODEL_FILE" "$MODEL_URL"

ACTUAL_SIZE=$(stat -c%s "$MODEL_FILE" 2>/dev/null || stat -f%z "$MODEL_FILE")
if [ "$ACTUAL_SIZE" -ne "$EXPECTED_SIZE_BYTES" ]; then
  echo "WARNING: Downloaded size ($ACTUAL_SIZE) differs from expected ($EXPECTED_SIZE_BYTES). Verify the file is valid."
fi

echo "Download complete: $MODEL_FILE"
```

**Notes:**
- Update `EXPECTED_SIZE_BYTES` after the first successful download — run `stat -c%s model/qwen2.5-1.5b-instruct-q4_k_m.gguf` and paste the real number.
- Make the script executable: `chmod +x download_model.sh`
- Test it: `bash download_model.sh` should download the file; running it again should skip.
- Do NOT commit the `model/` directory or any `.gguf` file.

**Acceptance:**
- `download_model.sh` exists, is executable, and runs without errors
- It downloads the GGUF to the correct path
- Re-running it skips the download (idempotent)
- `model/` is in `.gitignore`
- No `.gguf` files are committed to git

---

## TASK 4 — Write `REPORT.md`

Replace the template's placeholder REPORT.md with your technical writeup. The template specifies 4 sections, 1-3 pages, factual and specific. Use this structure:

### Section 1: Problem

Describe the problem in 2-3 paragraphs:
- West African SMEs (44M+ across sub-Saharan Africa, ~60% of GDP) keep their books in paper invoices, receipts, contracts, and bank statements — in French or English, almost never in a tidy database.
- Cloud AI assistants fail in this context: unreliable connectivity, USD-denominated subscriptions, and data sovereignty concerns (financial records should not leave the laptop they live on).
- The target user is Aya Traoré, a Senegalese import/export textile trader operating across FR/EN markets — a composite persona drawn from real West African SME patterns. She needs to answer questions like "Combien de factures sont impayées ?" or "Summarize the lease terms" without internet access, on an ordinary 8GB laptop.

### Section 2: Design Decisions

Document the model and architecture choices:

**Model choice**: Qwen2.5-1.5B-Instruct, quantized to Q4_K_M GGUF. Rationale:
- Best multilingual (FR/EN) instruction-following at the 1.5B parameter scale
- Q4_K_M quantization balances quality and size (~940 MB, fits comfortably in 8GB RAM with room for the OS, embeddings, and application layer)
- Stronger French capability than Llama-3.2-1B or Phi-3.5-mini at comparable sizes
- Alternatives evaluated: Llama-3.2-1B (weaker FR), Phi-3.5-mini (3.8B, too heavy with embeddings loaded), Qwen2.5-0.5B (weaker reasoning)

**Quantization choice**: Q4_K_M over Q5_K_M or Q8_0. Rationale:
- Q4_K_M: ~940 MB, ~20 TPS on 4-vCPU integrated-GPU laptop — well above the 15 TPS reference
- Q5_K_M: ~1.1 GB, marginal quality gain, ~15% throughput loss — not worth the trade
- Q8_0: ~1.6 GB, no measurable quality gain for this domain, pushes peak RAM higher

**Application architecture** (referenced from the karatasi repo): The model is deployed inside SME Brief, a hybrid SQL + RAG application. Money questions (amounts, counts, dates, VAT) are answered by deterministic SQL over structured rows — the LLM never touches them. Open questions (summaries, contract clauses) use semantic RAG: multilingual-e5-small embeddings, sqlite-vec kNN retrieval, Qwen2.5-1.5B generates a concise cited answer. This architectural decision means the model is used only for what it's good at (language generation) and never for what it's bad at (exact numeric recall).

**Customization beyond base weights**: The model weights are unmodified Qwen2.5-1.5B Q4_K_M. Customization is architectural rather than weight-level: a 12-handler intent router, bilingual entity extraction (suppliers, periods, codes), French-detection heuristic for output language routing, lease-keyword retrieval strategy, line-preserving chunking, and a 3-sentence answer cleaning pipeline. Fine-tuning was deliberately deferred to Gate 2 (pending UDEK GPU credits) because the 60-document corpus risks overfitting and the pivot from form-extraction to RAG-QA was the higher-value engineering call. Full customization documentation in the karatasi repo at `docs/MODEL_CUSTOMIZATION.md`.

### Section 3: Constraints

Document the constraints that shaped the approach:

**Hardware**: ADTC Standard Laptop — Intel Core i5 10th-12th gen or AMD Ryzen 5 3000-5000, 8GB DDR4 RAM, integrated GPU only (Intel UHD/Iris Xe or AMD Radeon), 256GB SSD, Ubuntu 22.04 LTS. Representative price $150-500. The model + embeddings + application layer must coexist in 8GB with the OS.

**Connectivity**: 100% offline during evaluation. `download_model.sh` runs before profiling; once profiling starts, zero network calls. All model loading uses `local_files_only=True`; Tesseract OCR binary is venv-bundled; no API keys, no telemetry, no cloud calls anywhere in the codebase.

**Data sovereignty**: A Senegalese SME's financial records should not leave the laptop. This is the same architectural principle used in healthcare AI (patient data never leaves the building), applied to small-business financial sovereignty. The constraint is the feature.

**Bilingual**: ECOWAS commerce operates across French and English. The model must handle code-switching, locale-correct currency formatting (XOF: `1 250 000`; USD: `8,120.00`), and bilingual document corpora.

**Thermal**: Sustained CPU inference on integrated-GPU laptops risks throttling above 85°C. The application minimizes LLM calls (46 of 50 questions answered by SQL — the LLM runs only for 4 semantic questions) to keep thermals in check.

### Section 4: Benchmarks

**Note**: This section must be filled with real numbers from the ADTC profiler run (Task 5). Leave placeholders that reference `submission.json`:

```markdown
## Benchmarks

Measured with the official ADTC Profiler (participant mode) on:
- CPU: <MODEL>
- RAM: 8GB DDR4
- OS: Ubuntu 22.04 LTS
- Date: <ISO timestamp>

### Throughput
| Metric | Value |
|---|---|
| Tokens per second (generation) | <FROM submission.json> |
| First token latency (ms) | <FROM submission.json> |

### Memory
| Metric | Value |
|---|---|
| Peak RSS (MB) | <FROM submission.json> |
| Steady-state RSS (MB) | <FROM submission.json> |

### Thermals
| Metric | Value |
|---|---|
| Max CPU temp (°C) | <FROM submission.json> |
| Thermal throttling | <FROM submission.json> |

### Accuracy
| Metric | Value |
|---|---|
| lm-eval score (participant-supplied prompts) | <FROM submission.json> |
| lm-eval score (hidden prompts) | N/A — evaluated in audit mode |

### Score Estimate
Based on the ADTC scoring formula (S = 0.50·S_acc + 0.30·S_perf + 0.20·S_eff − P_thermal + African bonus):
- S_perf = 100 × (TPS / 15.0) = <VALUE>
- S_eff = 100 × ((7000 − Peak_RSS) / 7000) = <VALUE>
- P_thermal = <0 or -10>
- **Estimated S_total** (assuming S_acc = <estimate>, bonus = +10): <VALUE>
```

After Task 5 (profiler run), replace all `<FROM submission.json>` placeholders with real values from the generated `submission.json`.

**Acceptance:**
- `REPORT.md` exists with all 4 sections
- 1-3 pages when rendered
- No placeholder values remain (except benchmarks, which are filled in Task 5)
- References the karatasi repo as the application layer
- The customization argument is defensible

---

## TASK 5 — Install and run the ADTC Profiler

The profiler is a CLI tool, not a custom script. Install it and run it against your submission repo.

**Step 1: Install system prerequisites.**
- Python 3.11+ (verify: `python3 --version`)
- `llama-bench` must be on your PATH. This is part of the llama.cpp toolset. Install options:
  - **Option A (recommended)**: Build llama.cpp from source:
    ```bash
    git clone https://github.com/ggml-org/llama.cpp /home/z/my-project/research/llama.cpp
    cd /home/z/my-project/research/llama.cpp
    cmake -B build -DLLAMA_CURL=OFF
    cmake --build build --config Release -j
    export PATH="/home/z/my-project/research/llama.cpp/build/bin:$PATH"
    llama-bench --help  # verify it works
    ```
  - **Option B**: Install via package manager if available (`apt install llama-cpp` on some distros — verify it includes `llama-bench`).
- Add `llama-bench` to PATH permanently (add the `export PATH=...` line to `~/.bashrc` or the submission repo's setup instructions).

**Step 2: Install the ADTC profiler.**
```bash
python3 -m pip install "git+https://github.com/Africa-Deep-Tech-Foundation/adtc-profiler.git"
```
This installs the `adtc-profiler` CLI. The install includes `lm-eval` and `llama-cpp-python` (compiles from source — may take a few minutes; needs a C/C++ toolchain: `build-essential` on Ubuntu, Xcode CLT on macOS).

Verify: `adtc-profiler --help` should print usage.

**Step 3: Download the model.**
```bash
cd /home/z/my-project/research/adtc-2026-submission
bash download_model.sh
```
Verify `model/qwen2.5-1.5b-instruct-q4_k_m.gguf` exists and is ~940 MB.

**Step 4: Run the profiler in participant mode.**
```bash
cd /home/z/my-project/research/adtc-2026-submission
adtc-profiler run \
  --submission . \
  --mode participant \
  --output submission.json
```
This runs the full benchmark including accuracy (lm-eval). It may take 10-30 minutes depending on your hardware.

**For faster iteration** (skip accuracy, just performance metrics):
```bash
adtc-profiler run \
  --submission . \
  --mode participant \
  --output submission.json \
  --skip-accuracy
```
Use `--skip-accuracy` during development, but your final submitted `submission.json` must come from a **full run** (no `--skip-accuracy`).

**Step 5: Verify submission.json.**
- Open `submission.json` and verify:
  - `"measured_on": "participant_laptop"` (not "audit")
  - `"team_id"` matches your metadata.json
  - Throughput, memory, and thermal fields are populated with real numbers (not null/zero)
  - No error messages in the JSON
- Print a single-line summary to stdout:
  ```bash
  python3 -c "import json; d=json.load(open('submission.json')); print(f'PROFILER: TPS={d[\"throughput\"][\"tokens_per_second_generation\"]} RAM={d[\"memory\"][\"peak_rss_mb\"]}MB TEMP={d.get(\"thermals\",{}).get(\"max_cpu_temp_c\",\"N/A\")}')"
  ```

**Step 6: Fill in REPORT.md benchmarks section.** Replace all `<FROM submission.json>` placeholders in `REPORT.md` (Section 4: Benchmarks) with the real values from `submission.json`. Calculate the score estimate using the ADTC formula.

**Step 7: Commit submission.json to the repo.** This is your self-reported score. The organizers will re-run the profiler in audit mode and compare; discrepancies >15% (memory) or >25% (throughput) trigger penalties. Make sure you run on hardware as close to the ADTC Standard Laptop profile as possible (4 vCPU, 8GB RAM, no discrete GPU, Ubuntu 22.04).

**Acceptance:**
- `adtc-profiler` CLI installed and on PATH
- `llama-bench` installed and on PATH
- `submission.json` exists at repo root with `measured_on: participant_laptop`
- All throughput, memory, and thermal fields populated
- `REPORT.md` benchmarks section filled with real numbers
- `submission.json` committed to the repo

---

## TASK 6 — Finalize the karatasi repo

The karatasi repo is the application layer — referenced from REPORT.md but not the submission itself. Clean it up so judges can navigate from the submission repo to the application code.

**Step 1: Push to origin.** README says "4 commits ahead of origin." Resolve this:
```bash
cd /home/z/my-project/research/karatasi
git push origin main
```

**Step 2: Update README.md.** Add a section at the top:

```markdown
## ADTC 2026 Submission

This repo is the **application layer** for the Africa Deep Tech Challenge 2026 submission. The official submission (model + metadata + report + profiler results) lives at:
**https://github.com/kish-00/adtc-2026-submission**

This repo contains the SME Brief application — a hybrid SQL + RAG question-answering system that demonstrates the model's utility for West African SME financial management. It is not the scored artifact; the model itself (Qwen2.5-1.5B-Instruct Q4_K_M) is what the ADTC profiler evaluates.

See `docs/MODEL_CUSTOMIZATION.md` for the full customization argument.
```

**Step 3: Create `docs/MODEL_CUSTOMIZATION.md`** if it doesn't exist. Content (condensed from the previous prompt):

1. **Architectural customization**: Hybrid SQL + RAG router — 12 hand-engineered intent handlers, bilingual entity extraction, deterministic SQL for 46/50 gold questions. The LLM never touches money.
2. **Prompt engineering**: System prompt forces citation-grounded answers in the question's language; French-detection heuristic; 3-sentence answer cleaning pipeline.
3. **Retrieval customization**: Lease-keyword routing bypasses kNN for contract questions; 4000-char context budget inside 4096-token window; line-preserving chunking (≤500 chars).
4. **Corpus customization**: Bilingual synthetic corpus generator — 60 docs, 7 suppliers, 4 currencies, 2 languages, deterministic gold answers.
5. **What was NOT customized**: Model weights are unmodified Qwen2.5-1.5B Q4_K_M. Fine-tuning deferred to Gate 2 (pending UDEK GPU credits). Rationale: 60-doc corpus risks overfitting; the pivot from form-extraction to RAG-QA was the higher-value engineering call.
6. **Quantitative argument**: 46/50 gold questions answered by SQL (LLM never touches them). The LLM answers only 4/50 — summaries/clauses where determinism isn't required. This is the opposite of "wrapping a base model": the base model is a last-resort component in a custom architecture.

**Step 4: Commit and push.**

**Acceptance:**
- karatasi repo pushed to origin (no commits ahead)
- README.md references the submission repo URL
- `docs/MODEL_CUSTOMIZATION.md` exists with all 6 sections

---

## TASK 7 — Devpost submission copy + demo script

**Step 1: Rewrite `docs/demo/SUBMISSION.md` in the karatasi repo** with the data-sovereignty framing and African Use Case section (from the previous prompt — the full text is in the karatasi repo already; just verify it's there and matches the sovereignty framing).

**Step 2: Rewrite `docs/demo/DEMO_SCRIPT.md`** with the memorable moments:
- Shot 5 (~0:55): The "unplug ethernet" moment — physically unplug the cable, run a query, still works. Narration: "Still works. Still offline. That's the point."
- Shot 4 (~0:40): Citation hover — source PDF page renders inline below the answer (PyMuPDF renders the cited page to PNG, displayed via `st.image()`).
- Shots 2-8: System monitor overlay (htop in a corner window, or Streamlit sidebar polling `psutil` every 500ms).

Shot-by-shot structure (90-120s):

| Shot | Time | Visual | Narration |
|---|---|---|---|
| 1 | 0:00-0:15 | Split screen: PDF pile + "no signal" phone | Problem statement (FR/EN) |
| 2 | 0:15-0:25 | Terminal: `streamlit run src/ui/app.py` + browser opens + system monitor visible | "100% offline, ordinary 8GB laptop" |
| 3 | 0:25-0:40 | French SQL question: "Combien de factures sont impayées ?" → instant answer, route=SQL | "Money questions are deterministic SQL — never LLM-guessed" |
| 4 | 0:40-0:55 | English question with citation hover: source PDF page renders inline | "Every answer cites its source — verifiable" |
| 5 | 0:55-1:10 | Unplug ethernet → run another query → still works | "Still works. Still offline. That's the point." |
| 6 | 1:10-1:25 | Semantic RAG: "Résumez le contrat de bail" → LLM answer with cited pages | "Open questions use RAG over a small local LLM" |
| 7 | 1:25-1:40 | Terminal: `adtc-profiler run` → submission.json produced | "Profiled with the official ADTC profiler" |
| 8 | 1:40-end | System monitor showing ~2GB RAM + end card with submission repo link | "Under 2GB. Your documents, your language, fully offline." |

Pre-recording checklist:
- [ ] `venv/bin/python -m pytest tests/` → 36 passed
- [ ] `venv/bin/python eval/run_eval.py` → `PASS 50/50 FAIL_IDS=[]`
- [ ] `bash download_model.sh` works in the submission repo
- [ ] `adtc-profiler run` produces valid `submission.json`
- [ ] Pre-load the LLM once before recording (Shot 6 should be warm-start)
- [ ] Close background apps; keep `htop` visible
- [ ] Physical ethernet cable ready for Shot 5
- [ ] Test citation hover renders correct page

**Acceptance:**
- `docs/demo/DEMO_SCRIPT.md` rewritten with all 3 upgrades
- `docs/demo/SUBMISSION.md` has sovereignty framing + African Use Case section
- Shot 7 now shows the official profiler (not the custom eval) — this is what judges expect

---

# Execution Order

1. **TASK 1** (fork template) — block on user forking the repo on GitHub.
2. **TASK 2** (metadata.json) — block on user providing team_id, name, email.
3. **TASK 3** (download_model.sh) — can do in parallel with Task 2.
4. **TASK 4** (REPORT.md) — do after Task 3; leave benchmarks as placeholders.
5. **TASK 5** (profiler) — do after Tasks 2-4. Block on `llama-bench` installation.
6. **TASK 6** (karatasi cleanup) — do after Task 5 (so README can link to the populated submission repo).
7. **TASK 7** (demo script + submission copy) — do last.

After each task: commit with a clear message, push to origin, and verify the submission repo remains valid (re-run `adtc-profiler run --skip-accuracy` as a smoke test if you change anything in metadata.json or download_model.sh).

---

# Final Acceptance Criteria (all must be true before considering work done)

- [ ] Submission repo forked at `https://github.com/kish-00/adtc-2026-submission` (public)
- [ ] `metadata.json` exists with no placeholder values, `domain: corporate_enterprise`, exactly 2 test prompts
- [ ] `download_model.sh` exists, is executable, idempotent, downloads the GGUF from a public URL
- [ ] `model/` and `*.gguf` are in `.gitignore`; no weights committed to git
- [ ] `REPORT.md` exists with all 4 sections (Problem, Design Decisions, Constraints, Benchmarks), 1-3 pages
- [ ] `REPORT.md` benchmarks section filled with real numbers from `submission.json`
- [ ] `adtc-profiler` CLI installed and on PATH
- [ ] `llama-bench` installed and on PATH
- [ ] `submission.json` exists at submission repo root with `measured_on: participant_laptop`
- [ ] `submission.json` committed to the repo
- [ ] karatasi repo pushed to origin (no commits ahead)
- [ ] karatasi README.md references the submission repo URL
- [ ] `docs/MODEL_CUSTOMIZATION.md` exists in karatasi repo with all 6 sections
- [ ] `docs/demo/DEMO_SCRIPT.md` rewritten with unplug moment, citation hover, system monitor, profiler shot
- [ ] `docs/demo/SUBMISSION.md` has sovereignty framing + African Use Case section
- [ ] Both test prompts verified locally against the raw Qwen2.5-1.5B model (reasonable answers)
- [ ] karatasi repo: `venv/bin/python eval/run_eval.py` still returns `PASS 50/50 FAIL_IDS=[]`
- [ ] karatasi repo: `venv/bin/python -m pytest tests/` still returns 36 passed

---

# When You Start

1. **Stop and ask the user to**:
   - Fork `https://github.com/Africa-Deep-Tech-Foundation/adtc-2026-submission-template` on GitHub, name it `adtc-2026-submission`, and share the fork URL
   - Provide their `team_id` (from the ADTC portal), real name, and email
2. Once you have the fork URL, clone it to `/home/z/my-project/research/adtc-2026-submission`.
3. Read the forked repo's README.md, metadata.json, REPORT.md, and download_model.sh to understand the template structure.
4. Read `/home/z/my-project/research/karatasi/docs/BUILD_PLAN.md` for environment notes.
5. Read `/home/z/my-project/research/karatasi/README.md` and `/home/z/my-project/research/karatasi/docs/ARCHITECTURE.md` for the application context.
6. Begin TASK 2 (metadata.json).

Do not ask for clarification on Tasks 3, 4, 5, 6, or 7 — they are fully specified above. Only ask for clarification on Tasks 1 and 2 (which require user-provided information).
