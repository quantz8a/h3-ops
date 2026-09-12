from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Preset:
    id: str
    width: int
    height: int
    frames: int
    steps: int
    ssd_streaming: bool = True
    layers: int | None = None
    reuse: int | None = None
    requires_gate: bool = False
    requires_i_know: bool = False
    notes: str = ""


def _parse_scalar(raw: str):
    text = raw.strip()
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    low = text.lower()
    if low in {"true", "yes"}:
        return True
    if low in {"false", "no"}:
        return False
    if low in {"null", "~", ""}:
        return None
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def load_preset_file(path: Path) -> Preset:
    data: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        key, _, val = s.partition(":")
        data[key.strip()] = _parse_scalar(val)
    missing = [k for k in ("id", "width", "height", "frames", "steps") if k not in data]
    if missing:
        raise ValueError(f"{path}: missing keys {missing}")
    return Preset(
        id=str(data["id"]),
        width=int(data["width"]),
        height=int(data["height"]),
        frames=int(data["frames"]),
        steps=int(data["steps"]),
        ssd_streaming=bool(data.get("ssd_streaming", True)),
        layers=data.get("layers"),
        reuse=data.get("reuse"),
        requires_gate=bool(data.get("requires_gate", False)),
        requires_i_know=bool(data.get("requires_i_know", False)),
        notes=str(data.get("notes") or ""),
    )


def load_preset(presets_dir: Path, name: str) -> Preset:
    path = presets_dir / f"{name}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in presets_dir.glob("*.yaml"))
        raise FileNotFoundError(
            f"preset '{name}' not found at {path}; available: {available}"
        )
    return load_preset_file(path)


def list_presets(presets_dir: Path) -> list[str]:
    return sorted(p.stem for p in presets_dir.glob("*.yaml"))
