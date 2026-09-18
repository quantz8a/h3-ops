from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


def _expand(path: str | None) -> Path | None:
    if not path:
        return None
    return Path(os.path.expanduser(path)).resolve()


@dataclass(frozen=True)
class Config:
    h3c_src: Path
    model_dir: Path
    lock_path: Path
    mlx_ports: tuple[int, ...]
    free_pages_warn_gb: float
    free_pages_red_gb: float
    presets_dir: Path
    llm_base: str
    llm_model: str

    @staticmethod
    def from_env(repo_root: Path | None = None) -> "Config":
        root = repo_root or Path(__file__).resolve().parents[2]
        home = Path.home()
        h3c = _expand(os.environ.get("H3_OPS_H3C_SRC")) or (
            home / "llm-lab" / "src" / "h3.c"
        )
        model = _expand(os.environ.get("H3_OPS_MODEL_DIR")) or (
            home / "llm-lab" / "src" / "minimax-h3-mlx-rebuild" / "official"
        )
        lock = _expand(os.environ.get("H3_OPS_LOCK")) or (
            home / ".cache" / "h3-ops" / "gpu.lock"
        )
        ports_raw = os.environ.get("H3_OPS_MLX_PORTS", "11234,11235,11236")
        ports = tuple(
            int(p.strip()) for p in ports_raw.split(",") if p.strip().isdigit()
        )
        return Config(
            h3c_src=h3c,
            model_dir=model,
            lock_path=lock,
            mlx_ports=ports,
            free_pages_warn_gb=float(os.environ.get("H3_OPS_FREE_WARN_GB", "2.0")),
            free_pages_red_gb=float(os.environ.get("H3_OPS_FREE_RED_GB", "0.5")),
            presets_dir=root / "presets",
            llm_base=(os.environ.get("H3_OPS_LLM_BASE") or "").rstrip("/"),
            llm_model=os.environ.get("H3_OPS_LLM_MODEL") or "local",
        )

    @property
    def h3_bin(self) -> Path:
        return self.h3c_src / "h3"

    @property
    def shaders(self) -> Path:
        return self.h3c_src / "h3_shaders.metal"

    @property
    def fl2va(self) -> Path:
        return self.model_dir / "FL2VA"

    @property
    def ram_gb(self) -> float:
        if platform.system() != "Darwin":
            return 0.0
        try:
            import subprocess

            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True
            ).strip()
            return int(out) / (1024**3)
        except Exception:
            return 0.0

    @property
    def ssd_streaming_default(self) -> bool:
        """SSD streaming is a memory/speed tradeoff — slower when RAM is ample.

        h3.c does NOT enable it by default. We only default it ON below 64 GiB
        so low-memory Macs survive; Ultra / 96GB stay memory-resident (fast).
        """
        return 0.0 < self.ram_gb < 64.0
