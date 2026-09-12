from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class LLMError(RuntimeError):
    pass


def llm_configured(base: str | None = None) -> bool:
    return bool((base or os.environ.get("H3_OPS_LLM_BASE") or "").strip())


def chat_json(
    *,
    system: str,
    user: str,
    base: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """OpenAI-compatible chat → parse first JSON object from assistant content."""
    base = (base or os.environ.get("H3_OPS_LLM_BASE") or "").rstrip("/")
    if not base:
        raise LLMError("H3_OPS_LLM_BASE not set")
    model = model or os.environ.get("H3_OPS_LLM_MODEL") or "local"
    api_key = api_key or os.environ.get("H3_OPS_LLM_API_KEY") or os.environ.get(
        "OPENAI_API_KEY"
    ) or "EMPTY"

    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise LLMError(f"LLM HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise LLMError(f"LLM request failed: {e}") from e

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"unexpected LLM response shape: {body!r}"[:400]) from e
    return _extract_json_object(content)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        # strip markdown fence
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj
    raise LLMError("LLM did not return a JSON object")
