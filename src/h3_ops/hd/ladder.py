from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class HdError(RuntimeError):
    pass


@dataclass
class Probe:
    width: int
    height: int
    duration: float | None
    has_audio: bool


def which(name: str) -> str | None:
    return shutil.which(name)


def probe_video(path: Path) -> Probe:
    if not path.is_file():
        raise HdError(f"base video not found: {path}")
    ffprobe = which("ffprobe")
    if not ffprobe:
        raise HdError("ffprobe not found")
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "stream=width,height,codec_type:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        raw = subprocess.check_output(cmd, text=True)
    except subprocess.CalledProcessError as e:
        raise HdError(f"ffprobe failed: {e}") from e
    data = json.loads(raw)
    width = height = 0
    has_audio = False
    for stream in data.get("streams") or []:
        if stream.get("codec_type") == "video" and not width:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
        if stream.get("codec_type") == "audio":
            has_audio = True
    duration = None
    fmt = data.get("format") or {}
    if fmt.get("duration") is not None:
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None
    if width < 1 or height < 1:
        raise HdError(f"could not read video size from {path}")
    return Probe(width=width, height=height, duration=duration, has_audio=has_audio)


def ladder_status() -> list[dict[str, Any]]:
    ffmpeg = which("ffmpeg")
    realesr = which("realesrgan-ncnn-vulkan")
    cloud = bool(os.environ.get("MINIMAX_API_KEY"))
    return [
        {
            "level": "native",
            "available": True,
            "method": "copy base mp4",
            "claims": ["native_h3"],
        },
        {
            "level": "upscale_1080",
            "available": bool(ffmpeg),
            "method": (
                "realesrgan-ncnn-vulkan"
                if realesr
                else ("ffmpeg lanczos" if ffmpeg else "unavailable")
            ),
            "claims": ["upscale", "not_cloud_regenerate_2k"],
        },
        {
            "level": "upscale_2k",
            "available": bool(ffmpeg),
            "method": (
                "realesrgan-ncnn-vulkan"
                if realesr
                else ("ffmpeg lanczos" if ffmpeg else "unavailable")
            ),
            "claims": ["upscale", "not_cloud_regenerate_2k"],
        },
        {
            "level": "cloud_2k",
            "available": cloud,
            "method": "MiniMax Regenerate-2K API (Phase 5 adapter)",
            "claims": ["cloud_regenerate_2k"] if cloud else ["unavailable"],
        },
    ]


def target_size(level: str, width: int, height: int) -> tuple[int, int]:
    """Scale so the longer side hits the level target; keep aspect; even dims."""
    if level == "native":
        return width, height
    long_target = 1080 if level == "upscale_1080" else 2048
    long_side = max(width, height)
    if long_side <= 0:
        raise HdError("invalid source size")
    if long_side >= long_target and level.startswith("upscale"):
        # already large enough — still re-encode to requested label path, keep size
        scale = 1.0
    else:
        scale = long_target / long_side
    tw = max(2, int(round(width * scale)))
    th = max(2, int(round(height * scale)))
    # yuv420p needs even
    tw -= tw % 2
    th -= th % 2
    return tw, th


def write_sidecar(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
