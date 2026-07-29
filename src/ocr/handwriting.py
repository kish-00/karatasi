"""Handwriting OCR using TrOCR (Transformer-based OCR).

Recognizes handwritten text from cropped field regions using
Microsoft's TrOCR base handwritten model.

Key design:
- Lazy loading: model loads only on first inference
- Aggressive unloading: model is freed after inference to save RAM
- Crop field regions → run inference → return text
- Works on CPU with reasonable speed (~1-3s per field)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

if TYPE_CHECKING:
    import torch
    from transformers import TrOCRProcessor

logger = logging.getLogger(__name__)

ImageArray = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class HandwritingResult:
    """Result of handwriting recognition on a field."""

    text: str
    confidence: float
    elapsed_ms: float = 0.0
    model_loaded: bool = False


# ── TrOCR Model Manager ────────────────────────────────────────────

_MODEL_LOCAL_PATH: str | None = None
"""Path to local TrOCR model directory. Resolved once on first access."""


def _get_model_path() -> str | None:
    """Resolve and return the TrOCR model path (local dir or HF hub ID)."""
    global _MODEL_LOCAL_PATH  # noqa: PLW0603
    if _MODEL_LOCAL_PATH is not None:
        return _MODEL_LOCAL_PATH

    # Prefer local model directory (no download needed)
    local_path = (
        Path(__file__).resolve().parents[2] / "models" / "trocr-base-handwritten"
    )
    if local_path.is_dir() and (local_path / "pytorch_model.bin").exists():
        _MODEL_LOCAL_PATH = str(local_path)
        logger.info("Using local TrOCR model at %s", _MODEL_LOCAL_PATH)
        return _MODEL_LOCAL_PATH

    # Fallback: HuggingFace hub (requires download)
    _MODEL_LOCAL_PATH = "microsoft/trocr-base-handwritten"
    logger.info("Local model not found, falling back to HuggingFace hub")
    return _MODEL_LOCAL_PATH


_processor: "TrOCRProcessor | None" = None
_processor_lock: bool = False

_model: "torch.nn.Module | None" = None
_model_lock: bool = False

_loaded: bool = False
"""Whether the model is currently loaded in memory."""


def _load_processor() -> "TrOCRProcessor":
    """Load the TrOCR processor (tokenizer + image processor).

    The processor is small (~100MB) and can stay loaded.
    """
    global _processor, _processor_lock  # noqa: PLW0603
    if _processor is not None:
        return _processor

    if _processor_lock:
        raise RuntimeError("Processor already loading")

    _processor_lock = True
    try:
        from transformers import (
            TrOCRProcessor,
            RobertaTokenizer,
            ViTImageProcessor,
        )

        model_path = _get_model_path()
        logger.info("Loading TrOCR processor from %s...", model_path)
        tokenizer = RobertaTokenizer.from_pretrained(model_path)
        image_processor = ViTImageProcessor.from_pretrained(model_path)
        _processor = TrOCRProcessor(
            image_processor=image_processor, tokenizer=tokenizer
        )
        logger.info("TrOCR processor loaded")
    finally:
        _processor_lock = False

    assert _processor is not None
    return _processor


def _load_model() -> "torch.nn.Module":
    """Load the TrOCR model onto CPU.

    The model is ~300MB and is the main memory consumer.
    It should be loaded on-demand and unloaded after inference.
    """
    global _model, _model_lock, _loaded  # noqa: PLW0603
    if _model is not None:
        _loaded = True
        return _model

    if _model_lock:
        raise RuntimeError("Model already loading")

    _model_lock = True
    try:
        from transformers import VisionEncoderDecoderModel

        model_path = _get_model_path()
        logger.info("Loading TrOCR model from %s...", model_path)
        _model = VisionEncoderDecoderModel.from_pretrained(model_path)
        _model.to("cpu")
        _model.eval()
        _loaded = True
        logger.info("TrOCR model loaded (~300MB)")
    finally:
        _model_lock = False

    assert _model is not None
    return _model


def unload_model() -> None:
    """Unload the TrOCR model from memory.

    Call this after batch processing to free ~300MB RAM.
    The model will be reloaded on the next inference.
    """
    global _model, _loaded  # noqa: PLW0603
    import gc

    if _model is not None:
        logger.info("Unloading TrOCR model (freeing ~300MB)")
        del _model
        _model = None
        _loaded = False
        gc.collect()

        # Also clear CUDA cache if CUDA was ever used
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass


def unload_processor() -> None:
    """Unload the TrOCR processor from memory."""
    global _processor  # noqa: PLW0603
    if _processor is not None:
        logger.info("Unloading TrOCR processor")
        _processor = None
        unload_model()


def is_loaded() -> bool:
    """Check if the TrOCR model is currently loaded."""
    return _loaded


# ── Handwriting Recognition ─────────────────────────────────────────


def _prepare_image(crop: ImageArray) -> Image.Image:
    """Prepare a cropped image region for TrOCR inference.

    Converts to grayscale, inverts if needed, and returns a PIL Image
    suitable for the processor.
    """
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop

    # Invert if text is lighter than background (common in scans)
    mean_intensity = np.mean(gray)
    if mean_intensity > 127:
        gray = 255 - gray

    # Convert to PIL RGB (processor expects 3-channel)
    pil_image = Image.fromarray(gray).convert("RGB")
    return pil_image


def recognize_handwriting(
    image_crop: ImageArray,
    *,
    unload_after: bool = False,
) -> HandwritingResult:
    """Recognize handwritten text from a cropped image region.

    Model stays loaded after inference by default so consecutive calls
    are fast (~1s instead of ~17s). Call `unload_model()` explicitly
    when done with a batch to free ~300MB RAM.

    Args:
        image_crop: Cropped image of a handwritten field (grayscale or BGR).
        unload_after: If True, unload model after inference to free RAM.

    Returns:
        HandwritingResult with recognized text and confidence.
    """
    if _get_model_path() is None:
        return HandwritingResult(text="", confidence=0.0)

    start = time.perf_counter()
    was_loaded = is_loaded()

    try:
        processor = _load_processor()
        model = _load_model()

        pil_image = _prepare_image(image_crop)

        _torch = _import_and_get_torch()
        with (_torch.no_grad() if _torch is not None else _noop_context()):
            pixel_values = processor(images=pil_image, return_tensors="pt").pixel_values
            generated_ids = model.generate(pixel_values, max_new_tokens=64)
            generated_text = processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]

        text = generated_text.strip()
        # Heuristic confidence: TrOCR doesn't output confidence natively.
        # Use sequence length as a rough proxy (longer = more confident).
        confidence = min(1.0, len(text) / 20.0) if text else 0.0

        elapsed = (time.perf_counter() - start) * 1000
        return HandwritingResult(
            text=text,
            confidence=confidence,
            elapsed_ms=elapsed,
            model_loaded=not was_loaded,
        )
    except Exception:
        logger.exception("TrOCR inference failed")
        elapsed = (time.perf_counter() - start) * 1000
        return HandwritingResult(text="", confidence=0.0, elapsed_ms=elapsed)
    finally:
        if unload_after:
            unload_model()


def recognize_batch(
    crops: list[ImageArray],
    *,
    unload_after: bool = True,
) -> list[HandwritingResult]:
    """Recognize handwriting from multiple cropped field regions.

    Loads the model once, processes all crops, then unloads.

    Args:
        crops: List of cropped field images.
        unload_after: If True, unload model after batch.

    Returns:
        List of HandwritingResult in the same order as crops.
    """
    if not crops:
        return []

    start = time.perf_counter()

    results: list[HandwritingResult] = []
    try:
        # Load once for the batch
        processor = _load_processor()
        model = _load_model()
        _torch = _import_and_get_torch()

        for crop in crops:
            pil_image = _prepare_image(crop)

            with (_torch.no_grad() if _torch is not None else _noop_context()):
                pixel_values = processor(images=pil_image, return_tensors="pt").pixel_values
                generated_ids = model.generate(pixel_values, max_new_tokens=64)
                generated_text = processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0]

            text = generated_text.strip()
            confidence = min(1.0, len(text) / 20.0) if text else 0.0

            elapsed = (time.perf_counter() - start) * 1000
            results.append(
                HandwritingResult(
                    text=text,
                    confidence=confidence,
                    elapsed_ms=elapsed / len(crops) if crops else 0,
                    model_loaded=False,
                )
            )
    except Exception:
        logger.exception("Batch TrOCR inference failed")
    finally:
        if unload_after:
            unload_model()

    return results


# ── Helpers ─────────────────────────────────────────────────────────


def _import_and_get_torch():
    """Import torch for TYPE_CHECKING-only usage at runtime."""
    try:
        import torch as _torch  # noqa: F811

        return _torch
    except ImportError:
        return None


class _noop_context:
    """Fallback context manager when torch is not available."""

    def __enter__(self):
        return None

    def __exit__(self, *args):
        pass
