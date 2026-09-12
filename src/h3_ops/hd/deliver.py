from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from h3_ops.cir import CirError, load_doc
from h3_ops.hd.ladder import (
    HdError,
    ladder_status,
    probe_video,
    target_size,
    which,
    write_sidecar,
)


def _ffmpeg_scale(src: Path, dst: Path, width: int, height: int) -> str:
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise HdError("ffmpeg not found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={width}:{height}:flags=lanczos"
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        str(dst),
    ]
    # If no audio, -c:a copy can fail — retry without audio map
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(dst),
        ]
        subprocess.check_call(cmd)
    return "ffmpeg-lanczos"


def deliver(
    *,
    base: Path,
    output: Path,
    target: str = "upscale_1080",
    doc_path: Path | None = None,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    if target not in {"native", "upscale_1080", "upscale_2k", "cloud_2k"}:
        raise HdError(f"unknown target level: {target}")

    status = {row["level"]: row for row in ladder_status()}
    probe = probe_video(base)
    doc_id = None
    hd_intent = None
    if doc_path is not None:
        try:
            doc = load_doc(doc_path)
            doc_id = doc.get("id")
            hd_intent = doc.get("hd_intent")
        except CirError as e:
            raise HdError(str(e)) from e

    level_requested = target
    level_achieved = target
    tool = "copy"
    scale = 1.0
    claims: list[str] = []
    warnings: list[str] = []

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if target == "cloud_2k":
        if not status["cloud_2k"]["available"]:
            if not allow_fallback:
                raise HdError(
                    "cloud_2k unavailable (no MINIMAX_API_KEY); Phase 5 adapter"
                )
            warnings.append("cloud_2k unavailable — falling back to upscale_2k")
            target = "upscale_2k"
            level_achieved = "upscale_2k"
        else:
            raise HdError(
                "cloud_2k adapter not implemented yet (Phase 5). "
                "Use --target upscale_2k."
            )

    if target == "native":
        shutil.copy2(base, output)
        claims = ["native_h3"]
        tw, th = probe.width, probe.height
        level_achieved = "native"
    else:
        if not status[target]["available"]:
            raise HdError(f"{target} unavailable (need ffmpeg)")
        tw, th = target_size(target, probe.width, probe.height)
        tool = _ffmpeg_scale(base, output, tw, th)
        scale = max(tw / probe.width, th / probe.height)
        claims = ["upscale", "not_cloud_regenerate_2k"]
        level_achieved = target
        if tool.startswith("ffmpeg"):
            warnings.append(
                "local ffmpeg lanczos upscale — not MiniMax Regenerate-2K"
            )

    out_probe = probe_video(output)
    sidecar = {
        "doc_id": doc_id,
        "hd_intent": hd_intent,
        "base_mp4": str(base.resolve()),
        "output_mp4": str(output),
        "level_requested": level_requested,
        "level_achieved": level_achieved,
        "tool": tool,
        "scale": round(scale, 4),
        "source": {"w": probe.width, "h": probe.height, "duration": probe.duration},
        "output": {
            "w": out_probe.width,
            "h": out_probe.height,
            "duration": out_probe.duration,
        },
        "claims": claims,
        "warnings": warnings,
    }
    side_path = output.with_suffix(output.suffix + ".hd.json")
    write_sidecar(side_path, sidecar)
    sidecar["sidecar"] = str(side_path)
    return sidecar
