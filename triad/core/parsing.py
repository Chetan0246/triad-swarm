"""Robust JSON extraction helpers for LLM-generated content.

LLMs frequently wrap JSON in prose or markdown code fences, and their payloads
often contain nested objects. A naive non-greedy regular expression truncates
those payloads at the first closing brace. This module extracts the first
complete JSON value using brace matching that is aware of strings and escapes.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Tuple

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*\s*([\s\S]*?)```")


def _find_json_span(text: str) -> Optional[Tuple[int, int]]:
    """Return the (start, end) span of the first balanced JSON object/array."""
    start = -1
    for idx, char in enumerate(text):
        if char in "{[":
            start = idx
            break
    if start == -1:
        return None

    stack = []
    in_string = False
    escaped = False

    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append(char)
        elif char in "}]":
            if not stack:
                return None
            opening = stack.pop()
            if (opening == "{" and char != "}") or (opening == "[" and char != "]"):
                return None
            if not stack:
                return start, idx + 1

    return None


def extract_json(content: str) -> Any:
    """Parse the first complete JSON value from an LLM response.

    Handles raw JSON, markdown-fenced JSON, and JSON embedded in prose. Raises
    ``ValueError`` when no complete JSON value can be found.
    """
    if not content or not content.strip():
        raise ValueError("Empty LLM response; expected a JSON object or array.")

    text = content.strip()

    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    span = _find_json_span(text)
    if span is None:
        raise ValueError("No complete JSON object or array found in LLM response.")

    start, end = span
    return json.loads(text[start:end])
