#!/usr/bin/env python3
"""
Model download script for Karatasi.

Downloads:
1. Qwen2.5-1.5B-Q4_K_M GGUF — form understanding LLM
2. TrOCR base handwritten — handwriting OCR
3. all-MiniLM-L6-v2 — embeddings for template matching

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


def download_hf_model(model_id: str, subfolder: str = "") -> None:
    """Download a HuggingFace model to local directory."""
    from huggingface_hub import snapshot_download

    dest = MODELS_DIR / model_id.replace("/", "--")
    if dest.exists():
        print(f"  ✅ {model_id} already exists at {dest}, skipping")
        return

    print(f"  ⬇️  Downloading {model_id}...")
    snapshot_download(
        repo_id=model_id,
        local_dir=dest,
        allow_patterns=["*.json", "*.safetensors", "*.model", "*.bin"],
        ignore_patterns=["*.h5", "*.ot", "*.msgpack"],
    )
    print(f"     Saved to: {dest}")


def main():
    MODELS_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("Karatasi — Downloading Models")
    print("=" * 60)
    print(f"Models directory: {MODELS_DIR}")
    print()

    # 1. LLM for form understanding (Qwen2.5-1.5B GGUF, Q4_K_M)
    # Using HuggingFace hub for GGUF models
    print("[1/3] Form Understanding LLM (Qwen2.5-1.5B-Q4_K_M)")
    llm_url = (
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
        "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    )
    llm_dest = MODELS_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    download_gguf(llm_url, llm_dest)
    print()

    # 2. TrOCR for handwriting recognition
    print("[2/3] Handwriting OCR (TrOCR base)")
    download_hf_model("microsoft/trocr-base-handwritten")
    print()

    # 3. Sentence transformer for embeddings
    print("[3/3] Embeddings (all-MiniLM-L6-v2)")
    download_hf_model("sentence-transformers/all-MiniLM-L6-v2")
    print()

    print("=" * 60)
    print("All models downloaded!")
    print(f"Total models size: ~1.5 GB")
    print()
    print("Run the app:")
    print("  streamlit run src/app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
