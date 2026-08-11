from __future__ import annotations


def build_context(chunks: list[dict], max_chars: int = 4000) -> str:
    parts: list[str] = []
    used = 0
    for c in chunks:
        header = f"[{c['file']}" + (f" page {c['page']}" if c.get("page") else "") + "]"
        block = f"{header} {c['text']}"
        if parts and used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n\n".join(parts)
