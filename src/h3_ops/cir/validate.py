from __future__ import annotations

from typing import Any

from h3_ops.cir import CAUTION_CANVAS, SAFE_CANVAS, CirError


def _type_ok(value: Any, expected: Any) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == ["integer", "null"]:
        return value is None or (
            isinstance(value, int) and not isinstance(value, bool)
        )
    return True


def validate_against_schema(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Minimal Draft-2020 subset for context_doc.v1 (no external deps)."""
    errors: list[str] = []
    required = schema.get("required", [])
    props = schema.get("properties", {})
    for key in required:
        if key not in doc:
            errors.append(f"missing required field: {key}")
    if schema.get("additionalProperties") is False:
        for key in doc:
            if key not in props:
                errors.append(f"unknown field: {key}")
    for key, prop in props.items():
        if key not in doc:
            continue
        val = doc[key]
        expected = prop.get("type")
        if expected is not None and not _type_ok(val, expected):
            errors.append(f"{key}: expected {expected}, got {type(val).__name__}")
            continue
        if "const" in prop and val != prop["const"]:
            errors.append(f"{key}: must be {prop['const']!r}")
        if "enum" in prop and val not in prop["enum"]:
            errors.append(f"{key}: must be one of {prop['enum']}")
        if isinstance(val, str):
            if "minLength" in prop and len(val) < prop["minLength"]:
                errors.append(f"{key}: too short")
            if "maxLength" in prop and len(val) > prop["maxLength"]:
                errors.append(f"{key}: too long")
            if "pattern" in prop:
                import re

                if not re.match(prop["pattern"], val):
                    errors.append(f"{key}: does not match pattern")
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            if "minimum" in prop and val < prop["minimum"]:
                errors.append(f"{key}: below minimum {prop['minimum']}")
            if "maximum" in prop and val > prop["maximum"]:
                errors.append(f"{key}: above maximum {prop['maximum']}")
            if "multipleOf" in prop and isinstance(val, int):
                if val % prop["multipleOf"] != 0:
                    errors.append(f"{key}: must be multiple of {prop['multipleOf']}")
        if isinstance(val, list):
            if "minItems" in prop and len(val) < prop["minItems"]:
                errors.append(f"{key}: need at least {prop['minItems']} items")
            if "maxItems" in prop and len(val) > prop["maxItems"]:
                errors.append(f"{key}: too many items")
            item = prop.get("items", {})
            for i, el in enumerate(val):
                if item.get("type") == "string" and not isinstance(el, str):
                    errors.append(f"{key}[{i}]: expected string")
                if item.get("type") == "object" and isinstance(el, dict):
                    for rk in item.get("required", []):
                        if rk not in el:
                            errors.append(f"{key}[{i}]: missing {rk}")
        if isinstance(val, dict) and prop.get("type") == "object":
            sub_req = prop.get("required", [])
            sub_props = prop.get("properties", {})
            for rk in sub_req:
                if rk not in val:
                    errors.append(f"{key}.{rk}: missing")
            if prop.get("additionalProperties") is False:
                for sk in val:
                    if sk not in sub_props:
                        errors.append(f"{key}.{sk}: unknown")
            for sk, sp in sub_props.items():
                if sk not in val:
                    continue
                sv = val[sk]
                if sp.get("type") == "array" and not isinstance(sv, list):
                    errors.append(f"{key}.{sk}: expected array")
                if sp.get("type") == "integer" and not (
                    isinstance(sv, int) and not isinstance(sv, bool)
                ):
                    errors.append(f"{key}.{sk}: expected integer")
                if (
                    isinstance(sv, int)
                    and not isinstance(sv, bool)
                    and "multipleOf" in sp
                    and sv % sp["multipleOf"] != 0
                ):
                    errors.append(f"{key}.{sk}: must be multiple of {sp['multipleOf']}")
                if isinstance(sv, list) and "minItems" in sp and len(sv) < sp["minItems"]:
                    errors.append(f"{key}.{sk}: need at least {sp['minItems']} items")
    return errors


def validate_semantic(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    beats = doc.get("beats") or []
    last_t1: float | None = None
    for i, beat in enumerate(beats):
        if not isinstance(beat, dict):
            errors.append(f"beats[{i}]: not an object")
            continue
        t0 = beat.get("t0")
        t1 = beat.get("t1")
        if t0 is not None and t1 is not None and t0 > t1:
            errors.append(f"beats[{i}]: t0 > t1")
        if t1 is not None:
            if last_t1 is not None and t1 < last_t1:
                errors.append(f"beats[{i}]: t1 decreases vs previous")
            last_t1 = t1
    duration = doc.get("duration")
    if last_t1 is not None and isinstance(duration, (int, float)) and duration < last_t1:
        errors.append(f"duration {duration} < last beat t1 {last_t1}")

    fps = doc.get("fps", 24) or 24
    if isinstance(duration, (int, float)):
        frames = round(float(duration) * int(fps))
        if frames < 22:
            errors.append(f"duration*fps => {frames} frames (< 22 floor)")

    canvas = doc.get("canvas") or {}
    w, h = canvas.get("w"), canvas.get("h")
    unsafe = bool(doc.get("unsafe"))
    if isinstance(w, int) and isinstance(h, int):
        size = (w, h)
        if size not in SAFE_CANVAS and size not in CAUTION_CANVAS and not unsafe:
            errors.append(
                f"canvas {w}x{h} not in allowlist; set unsafe=true and pass --i-know"
            )

    locks = doc.get("locks") or {}
    lock_strings: set[str] = set()
    for group in locks.values():
        if isinstance(group, list):
            lock_strings.update(str(x) for x in group)
    for neg in doc.get("negatives") or []:
        if neg in lock_strings:
            errors.append(f"negative {neg!r} identical to a lock string")

    if doc.get("emit_profile") == "h3c_dense":
        if not (locks.get("character") or []):
            errors.append("h3c_dense requires locks.character")
        if not (locks.get("camera") or []):
            errors.append("h3c_dense requires locks.camera")
    return errors


def validate_doc(
    doc: dict[str, Any],
    schema: dict[str, Any] | None = None,
    *,
    draft: bool = False,
) -> list[str]:
    errors: list[str] = []
    if schema is not None:
        errors.extend(validate_against_schema(doc, schema))
    if not draft:
        errors.extend(validate_semantic(doc))
    return errors


def require_valid(
    doc: dict[str, Any], schema: dict[str, Any] | None = None, *, draft: bool = False
) -> None:
    errors = validate_doc(doc, schema, draft=draft)
    if errors:
        raise CirError("ContextDoc invalid:\n- " + "\n- ".join(errors))
