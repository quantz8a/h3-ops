from __future__ import annotations

import re
from typing import Any

from h3_ops.cir import _slug


def compile_template(
    brief: str,
    *,
    title: str | None = None,
    doc_id: str | None = None,
    characters: list[str] | None = None,
    camera: list[str] | None = None,
    style_anchor: str | None = None,
    width: int = 480,
    height: int = 832,
    duration: float = 5.0,
    fps: int = 24,
    emit_profile: str = "h3c_dense",
    hd_intent: str = "native",
) -> dict[str, Any]:
    brief = brief.strip()
    if not brief:
        raise ValueError("brief is empty")
    title = (title or brief[:40]).strip()
    doc_id = doc_id or _slug(title)
    # Split brief into crude beats by ；;。or newlines
    parts = [
        p.strip()
        for p in re.split(r"[；;。\n]+", brief)
        if p.strip()
    ]
    if not parts:
        parts = [brief]
    beats = []
    step = duration / max(len(parts), 1)
    for i, action in enumerate(parts):
        beats.append(
            {
                "id": f"b{i + 1}",
                "action": action,
                "t0": round(i * step, 3),
                "t1": round(min(duration, (i + 1) * step), 3),
            }
        )
    chars = characters or ["主体角色"]
    cams = camera or ["竖屏 9:16"]
    return {
        "schema_version": "context_doc.v1",
        "id": doc_id,
        "title": title,
        "brief": brief,
        "locks": {
            "character": chars,
            "wardrobe": [],
            "weapon": [],
            "palette": [],
            "camera": cams,
        },
        "beats": beats,
        "negatives": ["logo", "字幕烧录", "水印", "多头畸变"],
        "canvas": {"w": width, "h": height},
        "duration": float(duration),
        "fps": int(fps),
        "style_anchor": style_anchor
        or "chinese manhua cinematic, coherent motion, no text overlay",
        "seed": None,
        "emit_profile": emit_profile,
        "hd_intent": hd_intent,
        "unsafe": False,
        "revise_log": [],
    }
