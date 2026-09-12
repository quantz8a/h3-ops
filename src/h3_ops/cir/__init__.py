from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SAFE_CANVAS = {(512, 512), (480, 832), (832, 480)}
CAUTION_CANVAS = {(576, 1024), (1024, 576)}


class CirError(RuntimeError):
    pass


def load_doc(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CirError(f"ContextDoc not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CirError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise CirError("ContextDoc must be a JSON object")
    return data


def save_doc(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _slug(text: str, fallback: str = "shot") -> str:
    s = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = fallback
    if not re.match(r"^[a-zA-Z0-9]", s):
        s = f"s_{s}"
    return s[:128]


def load_schema(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "docs" / "schemas" / "context_doc.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))
