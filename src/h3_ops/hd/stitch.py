from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from h3_ops.hd.ladder import HdError, probe_video, which


def stitch(inputs: list[Path], output: Path) -> dict:
    if len(inputs) < 2:
        raise HdError("stitch needs at least 2 input mp4 files")
    for p in inputs:
        if not p.is_file():
            raise HdError(f"missing input: {p}")
    ffmpeg = which("ffmpeg")
    if not ffmpeg:
        raise HdError("ffmpeg not found")

    probes = [probe_video(p) for p in inputs]
    w0, h0 = probes[0].width, probes[0].height
    for i, pr in enumerate(probes[1:], start=1):
        if pr.width != w0 or pr.height != h0:
            raise HdError(
                f"canvas mismatch: {inputs[0].name}={w0}x{h0} vs "
                f"{inputs[i].name}={pr.width}x{pr.height}"
            )

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as listf:
        for p in inputs:
            # concat demuxer requires escaped paths
            path = p.resolve().as_posix().replace("'", r"'\''")
            listf.write(f"file '{path}'\n")
        list_path = Path(listf.name)

    try:
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(output),
        ]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError:
            # re-encode fallback
            cmd = [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(output),
            ]
            subprocess.check_call(cmd)
    finally:
        list_path.unlink(missing_ok=True)

    out = probe_video(output)
    return {
        "output_mp4": str(output),
        "inputs": [str(p.resolve()) for p in inputs],
        "count": len(inputs),
        "canvas": {"w": out.width, "h": out.height},
        "duration": out.duration,
    }
