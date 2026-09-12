from __future__ import annotations

import json
from typing import Any

from h3_ops.cir import CirError, _slug
from h3_ops.cir.compile import compile_template
from h3_ops.cir.llm import LLMError, chat_json, llm_configured
from h3_ops.cir.validate import require_valid


def compile_llm(
    brief: str,
    *,
    schema: dict[str, Any],
    title: str | None = None,
    doc_id: str | None = None,
    width: int = 480,
    height: int = 832,
    duration: float = 5.0,
    fps: int = 24,
    base: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    brief = brief.strip()
    if not brief:
        raise CirError("brief is empty")
    title = (title or brief[:40]).strip()
    doc_id = doc_id or _slug(title)
    system = (
        "You compile a creator brief into ContextDoc JSON for MiniMax-H3. "
        "Return ONLY JSON with schema_version context_doc.v1. "
        "Include locks.character, locks.camera, beats with actions, negatives, "
        "canvas, duration, fps, style_anchor, emit_profile=h3c_dense, "
        "hd_intent=native, unsafe=false, revise_log=[]."
    )
    user = (
        f"id: {doc_id}\n"
        f"title: {title}\n"
        f"canvas: {width}x{height}\n"
        f"duration: {duration}s @ {fps}fps\n"
        f"brief:\n{brief}"
    )
    last_err: Exception | None = None
    for _ in range(3):
        try:
            repaired = f"\nFix validation error: {last_err}\n" if last_err else ""
            doc = chat_json(system=system, user=user + repaired, base=base, model=model)
            doc["schema_version"] = "context_doc.v1"
            doc["id"] = doc_id
            doc["title"] = doc.get("title") or title
            doc.setdefault("canvas", {"w": width, "h": height})
            doc.setdefault("duration", duration)
            doc.setdefault("fps", fps)
            doc.setdefault("revise_log", [])
            doc.setdefault("unsafe", False)
            doc.setdefault("emit_profile", "h3c_dense")
            doc.setdefault("hd_intent", "native")
            doc.setdefault("seed", None)
            require_valid(doc, schema)
            return doc
        except (LLMError, CirError, ValueError, json.JSONDecodeError) as e:
            last_err = e
    raise CirError(f"LLM compile failed after retries: {last_err}")


def compile_doc(
    brief: str,
    *,
    schema: dict[str, Any],
    backend: str = "auto",
    title: str | None = None,
    doc_id: str | None = None,
    characters: list[str] | None = None,
    camera: list[str] | None = None,
    style_anchor: str | None = None,
    width: int = 480,
    height: int = 832,
    duration: float = 5.0,
    fps: int = 24,
    draft: bool = False,
    base: str | None = None,
    model: str | None = None,
) -> tuple[dict[str, Any], str]:
    if backend == "auto":
        backend = "llm" if llm_configured(base) else "template"
    if backend == "template":
        doc = compile_template(
            brief,
            title=title,
            doc_id=doc_id,
            characters=characters,
            camera=camera,
            style_anchor=style_anchor,
            width=width,
            height=height,
            duration=duration,
            fps=fps,
        )
        require_valid(doc, schema, draft=draft)
        return doc, "template"
    if backend == "llm":
        doc = compile_llm(
            brief,
            schema=schema,
            title=title,
            doc_id=doc_id,
            width=width,
            height=height,
            duration=duration,
            fps=fps,
            base=base,
            model=model,
        )
        return doc, "local_llm"
    raise CirError(f"unknown compile backend: {backend}")
