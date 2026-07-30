"""llama.cpp model server for local LLM inference.

Loads and serves Qwen2.5-1.5B-Q4_K_M GGUF via llama-cpp-python.
Designed for CPU inference on 8GB RAM laptops.

Key design:
- Lazy loading: model loads on first inference
- Memory-mapped (mmap): keeps model on disk until needed
- Idle timeout: auto-unloads after period of inactivity
- Context window: 2048 tokens (sufficient for form text)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────

_MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
_MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

_CONTEXT_SIZE = 2048
_MAX_TOKENS = 512
_TEMPERATURE = 0.1
_TOP_P = 0.9

_IDLE_TIMEOUT_S = 300  # 5 minutes before unloading

# ── Types ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LLMResult:
    """Result from a single LLM inference."""

    text: str
    elapsed_ms: float = 0.0
    tokens_per_sec: float = 0.0
    model_loaded: bool = False


# ── Server ──────────────────────────────────────────────────────────


class LLMServer:
    """llama.cpp model server with lazy load and idle timeout."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._llm = None
        self._last_used: float = 0.0
        self._loaded = False
        self._model_path = _find_model()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_path(self) -> str | None:
        return self._model_path

    def load(self) -> bool:
        """Load the model into memory if not already loaded."""
        if self._loaded and self._llm is not None:
            return True

        with self._lock:
            if self._loaded:
                return True

            if self._model_path is None:
                logger.error("Model file not found at %s", _MODEL_DIR / _MODEL_FILENAME)
                return False

            logger.info("Loading LLM from %s...", self._model_path)
            t0 = time.perf_counter()
            try:
                from llama_cpp import Llama

                self._llm = Llama(
                    model_path=self._model_path,
                    n_ctx=_CONTEXT_SIZE,
                    n_threads=None,  # auto-detect CPU cores
                    n_gpu_layers=0,  # CPU only
                    verbose=False,
                )
                elapsed = (time.perf_counter() - t0) * 1000
                self._loaded = True
                self._last_used = time.perf_counter()
                logger.info("LLM loaded in %.0fms (~1GB RAM)", elapsed)
                return True
            except Exception:
                logger.exception("Failed to load LLM")
                self._llm = None
                return False

    def unload(self) -> None:
        """Unload the model from memory to free ~1GB RAM."""
        with self._lock:
            if self._llm is not None:
                logger.info("Unloading LLM (freeing ~1GB RAM)")
                del self._llm
                self._llm = None
                self._loaded = False
                import gc

                gc.collect()

    def infer(
        self,
        prompt: str,
        *,
        max_tokens: int = _MAX_TOKENS,
        temperature: float = _TEMPERATURE,
        top_p: float = _TOP_P,
    ) -> LLMResult:
        """Run inference on a prompt.

        Args:
            prompt: Input text for the model.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling parameter.

        Returns:
            LLMResult with generated text and timing.
        """
        if not self._loaded:
            ok = self.load()
            if not ok:
                return LLMResult(text="")

        was_loaded = self._loaded
        start = time.perf_counter()

        try:
            with self._lock:
                assert self._llm is not None
                self._last_used = time.perf_counter()

                output = self._llm(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=["</s>", "\n\n\n"],
                    echo=False,
                )

            elapsed_s = time.perf_counter() - start
            generated_text = output["choices"][0]["text"].strip()
            tokens = output.get("usage", {}).get("completion_tokens", 1)
            tokens_per_sec = tokens / elapsed_s if elapsed_s > 0 else 0.0

            return LLMResult(
                text=generated_text,
                elapsed_ms=elapsed_s * 1000,
                tokens_per_sec=tokens_per_sec,
                model_loaded=not was_loaded,
            )
        except Exception:
            logger.exception("LLM inference failed")
            return LLMResult(text="")


# ── Module-level singleton ──────────────────────────────────────────

_server: LLMServer | None = None
_server_lock = Lock()


def get_server() -> LLMServer:
    """Get or create the singleton LLM server."""
    global _server  # noqa: PLW0603
    if _server is None:
        with _server_lock:
            if _server is None:
                _server = LLMServer()
    return _server


def unload_server() -> None:
    """Unload the LLM server and free memory."""
    global _server  # noqa: PLW0603
    if _server is not None:
        _server.unload()
        _server = None


# ── Helpers ─────────────────────────────────────────────────────────


def _find_model() -> str | None:
    """Locate the GGUF model file in the models directory."""
    candidates = [
        _MODEL_DIR / _MODEL_FILENAME,
        _MODEL_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    ]
    for path in candidates:
        if path.is_file():
            logger.info("Found LLM at %s (%.1f MB)", path, path.stat().st_size / 1e6)
            return str(path)

    # Fallback: glob for any .gguf
    gguf_files = sorted(_MODEL_DIR.glob("*.gguf"))
    if gguf_files:
        path = gguf_files[0]
        logger.info("Found LLM at %s (fallback glob)", path)
        return str(path)

    logger.warning("No GGUF model found in %s", _MODEL_DIR)
    return None
