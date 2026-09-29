"""Coordinate with mlx-serve / gpu-gate so H3 and Qwen/LTX never share unified memory.

h3-ops historically used only ``~/.cache/h3-ops/gpu.lock`` (JSON pid file).
Factory Qwen/gate uses flock on ``~/.mlx-serve/gpu.lock`` plus ``.h3_want``.
Without bridging them, mlx-serve can load 15–50 GB models while h3.c is
already resident → jetsam / OOM on a 96 GB Mac.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_MLX_LOCK = Path.home() / ".mlx-serve" / "gpu.lock"
DEFAULT_BACKENDS = (
    "http://127.0.0.1:11236",
    "http://127.0.0.1:11234",
    "http://127.0.0.1:11235",
)


def _want_path(lock: Path) -> Path:
    return Path(os.environ.get("MLX_GPU_LOCK_WANT") or f"{lock}.h3_want")


def mlx_lock_path() -> Path:
    return Path(os.environ.get("MLX_GPU_LOCK") or DEFAULT_MLX_LOCK).expanduser()


def _http_json(url: str, *, method: str = "GET", body: dict | None = None, timeout: float = 30.0):
    data = None
    headers: dict[str, str] = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))


def unload_mlx_models(backends: tuple[str, ...] = DEFAULT_BACKENDS) -> list[str]:
    """Best-effort unload of every loaded model on known mlx-serve ports."""
    unloaded: list[str] = []
    seen: set[str] = set()
    for base in backends:
        base = base.rstrip("/")
        try:
            payload = _http_json(f"{base}/v1/models", timeout=3.0)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for row in payload.get("data") or []:
            mid = row.get("id")
            if not mid or mid in seen:
                continue
            if not (row.get("loaded") or (row.get("bytes_resident") or 0)):
                continue
            seen.add(mid)
            try:
                _http_json(
                    f"{base}/v1/unload-model",
                    method="POST",
                    body={"model": mid},
                    timeout=120.0,
                )
                unloaded.append(f"{mid}@{base}")
                print(f"[mlx-coord] unloaded {mid} via {base}", flush=True)
            except Exception as e:
                print(f"[mlx-coord] WARN unload {mid} via {base}: {e}", flush=True)
    return unloaded


@dataclass
class MlxExclusiveHold:
    """Holds mlx flock + h3_want for the life of an h3-ops job."""

    lock_path: Path
    want_path: Path
    fd: int
    unloaded: list[str] = field(default_factory=list)

    def release(self) -> None:
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            self.want_path.unlink(missing_ok=True)
        except TypeError:
            if self.want_path.exists():
                self.want_path.unlink()
        except OSError:
            pass
        print("[mlx-coord] released mlx exclusive", flush=True)


def acquire_mlx_exclusive(
    *,
    holder: str,
    lock_path: Path | None = None,
    backends: tuple[str, ...] = DEFAULT_BACKENDS,
    wait_log_every: float = 15.0,
) -> MlxExclusiveHold:
    lock = (lock_path or mlx_lock_path()).expanduser()
    want = _want_path(lock)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.touch(exist_ok=True)

    # Signal gate ASAP: stop granting new Qwen shared locks.
    want.write_text(
        f"pid={os.getpid()}\nts={time.time()}\nholder={holder}\nsource=h3-ops\n",
        encoding="utf-8",
    )
    print(f"[mlx-coord] H3 want asserted → {want}", flush=True)

    fd = os.open(lock, os.O_RDWR | os.O_CREAT)
    t0 = time.monotonic()
    last = t0
    print(f"[mlx-coord] waiting for exclusive on {lock} ...", flush=True)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            now = time.monotonic()
            if now - last >= wait_log_every:
                print(
                    f"[mlx-coord] still waiting for exclusive ({int(now - t0)}s) …",
                    flush=True,
                )
                last = now
            time.sleep(0.25)

    print("[mlx-coord] acquired exclusive (H3)", flush=True)
    unloaded = unload_mlx_models(backends)
    return MlxExclusiveHold(lock_path=lock, want_path=want, fd=fd, unloaded=unloaded)
