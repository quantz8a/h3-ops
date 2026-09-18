from __future__ import annotations

import json
import platform
import re
import socket
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from h3_ops.config import Config


class Level(str, Enum):
    OK = "ok"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class Check:
    name: str
    level: Level
    detail: str


@dataclass
class DoctorReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def worst(self) -> Level:
        if any(c.level == Level.RED for c in self.checks):
            return Level.RED
        if any(c.level == Level.YELLOW for c in self.checks):
            return Level.YELLOW
        return Level.OK

    def add(self, name: str, level: Level, detail: str) -> None:
        self.checks.append(Check(name, level, detail))

    def to_dict(self) -> dict:
        return {
            "worst": self.worst.value,
            "checks": [
                {"name": c.name, "level": c.level.value, "detail": c.detail}
                for c in self.checks
            ],
        }


def _free_pages_gb() -> float | None:
    if platform.system() != "Darwin":
        return None
    try:
        out = subprocess.check_output(["vm_stat"], text=True)
    except Exception:
        return None
    page_size = 4096
    m = re.search(r"page size of (\d+) bytes", out)
    if m:
        page_size = int(m.group(1))
    free = 0
    for key in ("Pages free", "Pages speculative"):
        mm = re.search(rf"{key}:\s+(\d+)\.", out)
        if mm:
            free += int(mm.group(1))
    return free * page_size / (1024**3)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False


def _pgrep_h3_rivals() -> list[str]:
    hits: list[str] = []
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    except Exception:
        return hits
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        cmd = parts[1]
        first = cmd.split()[0]
        base = Path(first).name
        if base != "h3":
            continue
        # skip our own wrappers
        if "h3_ops" in cmd or "h3ctl" in cmd:
            continue
        hits.append(line[:220])
    return hits


def _pgrep_mlx_serve() -> list[str]:
    hits: list[str] = []
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,rss=,command="], text=True)
    except Exception:
        return hits
    for line in out.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 3:
            continue
        cmd = parts[2]
        # Match the real binary, not shell wrappers mentioning the name.
        tokens = cmd.split()
        if not tokens:
            continue
        exe = tokens[0]
        if exe.endswith("/mlx-serve") or exe == "mlx-serve":
            hits.append(line.strip()[:220])
    return hits


def _pgrep_generate() -> list[str]:
    hits: list[str] = []
    try:
        out = subprocess.check_output(["ps", "-ax", "-o", "pid=,command="], text=True)
    except Exception:
        return hits
    for line in out.splitlines():
        if "minimax-h3-mlx-rebuild/generate.py" in line:
            hits.append(line.strip()[:220])
    return hits


def run_doctor(cfg: Config) -> DoctorReport:
    report = DoctorReport()

    arch = platform.machine()
    if arch == "arm64":
        report.add("arch", Level.OK, arch)
    else:
        report.add("arch", Level.RED, f"need arm64, got {arch}")

    if cfg.h3_bin.is_file() and os_access_exec(cfg.h3_bin):
        report.add("h3_bin", Level.OK, str(cfg.h3_bin))
    else:
        report.add("h3_bin", Level.RED, f"missing/not executable: {cfg.h3_bin}")

    if cfg.shaders.is_file():
        report.add("shaders", Level.OK, str(cfg.shaders))
    else:
        report.add("shaders", Level.RED, f"missing {cfg.shaders}")

    if cfg.fl2va.is_dir():
        report.add("fl2va", Level.OK, str(cfg.fl2va))
    else:
        report.add("fl2va", Level.RED, f"missing {cfg.fl2va}")

    free = _free_pages_gb()
    if free is None:
        report.add("free_pages", Level.YELLOW, "vm_stat unavailable")
    elif free < cfg.free_pages_red_gb:
        report.add("free_pages", Level.RED, f"{free:.2f} GiB free (< {cfg.free_pages_red_gb})")
    elif free < cfg.free_pages_warn_gb:
        report.add(
            "free_pages",
            Level.YELLOW,
            f"{free:.2f} GiB free (< warn {cfg.free_pages_warn_gb})",
        )
    else:
        report.add("free_pages", Level.OK, f"{free:.2f} GiB free")

    busy_ports = [p for p in cfg.mlx_ports if _port_open(p)]
    mlx_procs = _pgrep_mlx_serve()
    if busy_ports or mlx_procs:
        detail_parts = []
        if busy_ports:
            detail_parts.append(f"listeners on {busy_ports}")
        if mlx_procs:
            detail_parts.append(f"mlx-serve procs: {'; '.join(mlx_procs[:2])}")
        report.add(
            "mlx_ports",
            Level.YELLOW,
            " — ".join(detail_parts) + " — stop before heavy Base jobs",
        )
    else:
        report.add("mlx_ports", Level.OK, f"no listeners on {list(cfg.mlx_ports)}")

    rivals = _pgrep_h3_rivals() + _pgrep_generate()
    if rivals:
        report.add(
            "rival_procs",
            Level.RED,
            f"{len(rivals)} competing process(es): " + "; ".join(rivals[:3]),
        )
    else:
        report.add("rival_procs", Level.OK, "no competing h3/mlx generate")

    report.add(
        "ram",
        Level.OK if cfg.ram_gb >= 32 else Level.YELLOW,
        (
            f"{cfg.ram_gb:.0f} GiB; "
            f"ssd_streaming_default={cfg.ssd_streaming_default} "
            f"({'low-RAM SSD' if cfg.ssd_streaming_default else 'resident DiT — fast'})"
        ),
    )
    return report


def os_access_exec(path: Path) -> bool:
    import os

    return os.access(path, os.X_OK)


def print_report(report: DoctorReport, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return
    for c in report.checks:
        mark = {"ok": "OK", "yellow": "WARN", "red": "RED"}[c.level.value]
        print(f"[{mark:4}] {c.name}: {c.detail}")
    print(f"worst={report.worst.value}")
