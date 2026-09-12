from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LockInfo:
    pid: int
    started_at: str
    argv_hash: str = ""
    holder: str = ""


class LockError(RuntimeError):
    pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_lock(path: Path) -> LockInfo | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return LockInfo(
            pid=int(data["pid"]),
            started_at=str(data.get("started_at", "")),
            argv_hash=str(data.get("argv_hash", "")),
            holder=str(data.get("holder", "")),
        )
    except Exception:
        return None


def acquire_lock(
    path: Path,
    *,
    holder: str,
    argv_hash: str = "",
    steal_stale: bool = True,
) -> LockInfo:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_lock(path)
    if existing and _pid_alive(existing.pid):
        raise LockError(
            f"GPU lock held by pid={existing.pid} since {existing.started_at} "
            f"({existing.holder or 'unknown'})"
        )
    if existing and steal_stale:
        # dead pid — steal
        pass
    info = LockInfo(
        pid=os.getpid(),
        started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        argv_hash=argv_hash,
        holder=holder,
    )
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(
            {
                "pid": info.pid,
                "started_at": info.started_at,
                "argv_hash": info.argv_hash,
                "holder": info.holder,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
    # re-read race: if someone else won, bail
    again = read_lock(path)
    if again is None or again.pid != os.getpid():
        raise LockError("failed to acquire GPU lock (race)")
    return info


def release_lock(path: Path, *, force: bool = False) -> bool:
    """Release lock. By default only if held by this PID; force clears any."""
    existing = read_lock(path)
    if existing is None:
        return False
    if not force and existing.pid != os.getpid():
        return False
    try:
        path.unlink(missing_ok=True)
    except TypeError:
        if path.exists():
            path.unlink()
    return True
