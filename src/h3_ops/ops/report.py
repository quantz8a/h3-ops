from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class JobReport:
    job_id: str
    doc_id: str | None
    preset: str
    argv: list[str]
    cwd: str
    started_at: str
    ended_at: str | None = None
    exit_code: int | None = None
    wall_s: float | None = None
    output_mp4: str | None = None
    log_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    phases: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def parse_profile_log(text: str) -> dict[str, float]:
    """Extract coarse phase seconds from h3 --profile log lines."""
    phases: dict[str, float] = {}
    # Match common labels: "text encoder", "DiT load", "denoise", "VAE", etc.
    patterns = {
        "text_encoder_s": re.compile(
            r"(?i)(?:text[_\s-]*encoder|TE)\D{0,40}?(\d+(?:\.\d+)?)\s*s"
        ),
        "dit_load_s": re.compile(
            r"(?i)(?:DiT\s*(?:load|map|weights)|load(?:ing)?\s*DiT)\D{0,40}?(\d+(?:\.\d+)?)\s*s"
        ),
        "denoise_s": re.compile(
            r"(?i)(?:denois(?:e|ing)|diffusion)\D{0,40}?(\d+(?:\.\d+)?)\s*s"
        ),
        "vae_s": re.compile(
            r"(?i)(?:VAE|decoder)\D{0,40}?(\d+(?:\.\d+)?)\s*s"
        ),
    }
    for key, pat in patterns.items():
        m = pat.search(text)
        if m:
            phases[key] = float(m.group(1))
    # Fallback: "phase_name: 1.23s" style
    for m in re.finditer(
        r"(?im)^\s*([A-Za-z][\w\s/-]{1,40}?):\s*(\d+(?:\.\d+)?)\s*s\b", text
    ):
        label = re.sub(r"[^a-z0-9]+", "_", m.group(1).strip().lower()).strip("_")
        if label and label not in phases and len(phases) < 16:
            phases[f"{label}_s"] = float(m.group(2))
    return phases


def new_job_id(preset: str) -> str:
    stamp = time.strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{preset}-{hashlib.sha1(stamp.encode()).hexdigest()[:6]}"


def argv_hash(argv: list[str]) -> str:
    return hashlib.sha1("\0".join(argv).encode()).hexdigest()[:12]


def start_report(
    *,
    job_id: str,
    preset: str,
    argv: list[str],
    cwd: str,
    output_mp4: str,
    log_path: str,
    warnings: list[str] | None = None,
) -> JobReport:
    return JobReport(
        job_id=job_id,
        doc_id=None,
        preset=preset,
        argv=argv,
        cwd=cwd,
        started_at=_now(),
        output_mp4=output_mp4,
        log_path=log_path,
        warnings=list(warnings or []),
    )
