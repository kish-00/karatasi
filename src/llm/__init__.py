"""LLM serving and prompt templates for form understanding."""

from src.llm.serve import LLMResult, LLMServer, get_server, unload_server
from src.llm.prompts import (
    detect_form_type_prompt,
    extract_fields_prompt,
    FormType,
)

__all__ = [
    "LLMServer",
    "LLMResult",
    "get_server",
    "unload_server",
    "detect_form_type_prompt",
    "extract_fields_prompt",
    "FormType",
]
