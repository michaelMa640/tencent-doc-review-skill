"""Helpers for parsing structured JSON outputs from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any


def strip_code_fences(text: str) -> str:
    """Remove a surrounding markdown code fence when present."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def extract_json_payload(content: str) -> Any:
    """Parse the first valid JSON value embedded in a model response."""
    cleaned = strip_code_fences(content)
    if not cleaned:
        raise json.JSONDecodeError("Empty content", cleaned, 0)

    candidates = [
        cleaned,
        re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE),
    ]
    begin_marker = "BEGIN_JSON"
    end_marker = "END_JSON"
    if begin_marker in cleaned and end_marker in cleaned:
        between = cleaned.split(begin_marker, 1)[1].split(end_marker, 1)[0].strip()
        candidates.insert(0, between)

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        snippet = _extract_first_json_value(candidate)
        if snippet is None:
            continue
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError("No valid JSON payload found", cleaned, 0)


def _extract_first_json_value(text: str) -> str | None:
    starts = [(text.find("{"), "{"), (text.find("["), "[")]
    valid_starts = [(index, token) for index, token in starts if index >= 0]
    if not valid_starts:
        return None
    start, opening = min(valid_starts, key=lambda item: item[0])
    closing = "}" if opening == "{" else "]"

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
