from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from h3_ops.cir import CirError
from h3_ops.cir.llm import LLMError, chat_json, llm_configured
from h3_ops.cir.validate import require_valid

LOCK_KEYS = ("character", "wardrobe", "weapon", "palette", "camera")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _append_log(doc: dict[str, Any], notes: str, backend: str) -> None:
    log = list(doc.get("revise_log") or [])
    log.append({"ts": _now(), "notes": notes, "backend": backend})
    doc["revise_log"] = log


def _freeze_locks(
    original: dict[str, Any],
    updated: dict[str, Any],
    unlock: set[str],
) -> None:
    src = original.get("locks") or {}
    dst = dict(updated.get("locks") or {})
    for key in LOCK_KEYS:
        if key in unlock:
            continue
        if key in src:
            dst[key] = copy.deepcopy(src[key])
    updated["locks"] = dst
    # identity fields stay stable
    updated["schema_version"] = "context_doc.v1"
    updated["id"] = original.get("id", updated.get("id"))


def revise_template(
    doc: dict[str, Any],
    notes: str,
    *,
    unlock: set[str] | None = None,
) -> dict[str, Any]:
    """Offline revise: append must-fix into brief/beats note; freeze locks."""
    notes = notes.strip()
    if not notes:
        raise CirError("revise notes are empty")
    unlock = unlock or set()
    bad = unlock - set(LOCK_KEYS)
    if bad:
        raise CirError(f"unknown unlock groups: {sorted(bad)}")

    out = copy.deepcopy(doc)
    # Light heuristic: push notes into a trailing beat + brief suffix
    brief = str(out.get("brief") or "")
    if notes not in brief:
        out["brief"] = f"{brief.rstrip()}（修订：{notes}）"
    beats = list(out.get("beats") or [])
    beats.append(
        {
            "id": f"rev{len(beats) + 1}",
            "action": f"必须体现修订：{notes}",
        }
    )
    out["beats"] = beats

    # Template path only mutates unlocked lock groups (append note tag).
    locks = copy.deepcopy(out.get("locks") or {})
    for key in unlock:
        vals = list(locks.get(key) or [])
        tag = f"修订:{notes[:32]}"
        if tag not in vals:
            vals.append(tag)
        locks[key] = vals
    out["locks"] = locks

    _freeze_locks(doc, out, unlock)
    _append_log(out, notes, "template")
    return out


def revise_llm(
    doc: dict[str, Any],
    notes: str,
    *,
    unlock: set[str] | None = None,
    schema: dict[str, Any] | None = None,
    base: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    notes = notes.strip()
    if not notes:
        raise CirError("revise notes are empty")
    unlock = unlock or set()
    system = (
        "You revise a ContextDoc JSON for MiniMax-H3 local video generation. "
        "Return ONLY a single JSON object matching schema_version context_doc.v1. "
        "Do not invent unrelated story. Respect locks unless told they are unlocked."
    )
    user = (
        f"Unlocked lock groups: {sorted(unlock) or 'none (freeze all locks)'}\n"
        f"Revision notes:\n{notes}\n\n"
        f"Current ContextDoc:\n{__import__('json').dumps(doc, ensure_ascii=False)}"
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            repaired = ""
            if last_err:
                repaired = f"\nPrevious error to fix: {last_err}\n"
            updated = chat_json(
                system=system,
                user=user + repaired,
                base=base,
                model=model,
            )
            _freeze_locks(doc, updated, unlock)
            _append_log(updated, notes, "local_llm")
            if schema is not None:
                require_valid(updated, schema)
            return updated
        except (LLMError, CirError, ValueError) as e:
            last_err = e
    raise CirError(f"LLM revise failed after retries: {last_err}")


def revise_doc(
    doc: dict[str, Any],
    notes: str,
    *,
    backend: str = "auto",
    unlock: set[str] | None = None,
    schema: dict[str, Any] | None = None,
    base: str | None = None,
    model: str | None = None,
) -> tuple[dict[str, Any], str]:
    """
    backend: template | llm | auto
    Returns (doc, backend_used).
    """
    if backend == "auto":
        backend = "llm" if llm_configured(base) else "template"
    if backend == "template":
        return revise_template(doc, notes, unlock=unlock), "template"
    if backend == "llm":
        return (
            revise_llm(
                doc, notes, unlock=unlock, schema=schema, base=base, model=model
            ),
            "local_llm",
        )
    raise CirError(f"unknown revise backend: {backend}")
