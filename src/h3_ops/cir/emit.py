from __future__ import annotations

from typing import Any


def emit_prompt(doc: dict[str, Any]) -> str:
    profile = doc.get("emit_profile") or "h3c_dense"
    lines: list[str] = []
    style = doc.get("style_anchor") or ""
    canvas = doc.get("canvas") or {}
    w = canvas.get("w", "?")
    h = canvas.get("h", "?")
    duration = doc.get("duration", "?")
    fps = doc.get("fps", 24)
    lines.append(f"[style] {style}")
    lines.append(f"[canvas] {w}x{h} ~{duration}s @{fps}fps")
    lines.append(f"[brief] {doc.get('brief', '')}")

    if profile == "h3c_dense":
        locks = doc.get("locks") or {}
        lines.append("[locks]")
        for key in ("character", "wardrobe", "weapon", "palette", "camera"):
            vals = locks.get(key) or []
            if vals:
                lines.append(f"{key}: " + ", ".join(str(v) for v in vals))

    lines.append("[beats]")
    for i, beat in enumerate(doc.get("beats") or [], start=1):
        t0 = beat.get("t0")
        t1 = beat.get("t1")
        timing = ""
        if t0 is not None or t1 is not None:
            timing = f" ({t0 if t0 is not None else '?'}-{t1 if t1 is not None else '?'})"
        lines.append(f"{i}.{timing} {beat.get('action', '')}".rstrip())

    negatives = doc.get("negatives") or []
    if negatives:
        lines.append("[negatives]")
        for n in negatives:
            lines.append(f"- {n}")

    revise = doc.get("revise_log") or []
    if revise:
        lines.append("[must_fix]")
        for entry in revise:
            notes = entry.get("notes") if isinstance(entry, dict) else str(entry)
            lines.append(f"- {notes}")

    return "\n".join(lines).strip() + "\n"
