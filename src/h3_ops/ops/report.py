from __future__ import annotations

import hashlib
import json
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


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
