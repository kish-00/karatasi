#!/usr/bin/env python3
"""
Model download script for SME Brief.

Downloads:
1. Qwen2.5-1.5B-Instruct Q4_K_M GGUF — semantic answer LLM
2. multilingual-e5-small — FR/EN embeddings (384-dim, offline)

The embedding model is saved as models/multilingual-e5-small (the plain
name, matching src/embeddings.py's MODEL_DIR — not the HF hub "--" form).

Usage:
    python scripts/download_models.py
"""

import os
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def download_gguf(url: str, dest: Path) -> None:
    """Download a GGUF model file with progress display."""
    import urllib.request
    import shutil

    if dest.exists():
        print(f"  ✅ {dest.name} already exists, skipping")
        return

    print(f"  ⬇️  Downloading {dest.name}...")
    print(f"     From: {url}")

    # Streaming download with progress
    with urllib.request.urlopen(url) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 8192

        with open(dest, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = int(downloaded / total * 100)
                    sys.stdout.write(f"\r     Progress: {pct}%")
                    sys.stdout.flush()

    print(f"\n     Saved to: {dest}")
    print(f"     Size: {dest.stat().st_size / 1e9:.2f} GB")


def main():
    MODELS_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("SME Brief — Downloading Models")
    print("=" * 60)
    print(f"Models directory: {MODELS_DIR}")
    print()

    # Using HuggingFace hub for GGUF models
    print("[1/2] Answer LLM (Qwen2.5-1.5B-Instruct Q4_K_M)")
    llm_url = (
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
        "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    )
    llm_dest = MODELS_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    download_gguf(llm_url, llm_dest)
    print()

    print("[2/2] Embeddings (multilingual-e5-small)")
    e5_dest = MODELS_DIR / "multilingual-e5-small"
    if e5_dest.exists():
        print(f"  ✅ multilingual-e5-small already exists at {e5_dest}, skipping")
    else:
        print(f"  ⬇️  Downloading multilingual-e5-small...")
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="intfloat/multilingual-e5-small",
            local_dir=e5_dest,
            allow_patterns=["*.json", "*.safetensors", "*.model", "*.bin", "*.txt"],
            ignore_patterns=["*.h5", "*.ot", "*.msgpack"],
        )
        print(f"     Saved to: {e5_dest}")
    print()

    print("=" * 60)
    print("All models downloaded!")
    print(f"Total models size: ~1.2 GB")
    print()
    print("Next steps:")
    print("  venv/bin/python data/synthetic/generator.py   # regenerate corpus")
    print("  venv/bin/python -m src.ingest --force          # build data/smebrief.db")
    print("  venv/bin/python eval/run_eval.py               # expect PASS 50/50")
    print("=" * 60)


if __name__ == "__main__":
    main()
