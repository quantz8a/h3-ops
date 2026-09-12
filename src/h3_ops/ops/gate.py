from __future__ import annotations

from h3_ops.config import Config
from h3_ops.ops.doctor import DoctorReport, Level, run_doctor
from h3_ops.presets import Preset


class GateError(RuntimeError):
    pass


def gate(
    cfg: Config,
    *,
    preset: Preset | None = None,
    i_know: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> DoctorReport:
    """Refuse when doctor is red, unless --force. unsafe presets need --i-know."""
    report = run_doctor(cfg)
    if report.worst == Level.RED and not force and not dry_run:
        reds = [c for c in report.checks if c.level == Level.RED]
        detail = "; ".join(f"{c.name}: {c.detail}" for c in reds)
        raise GateError(f"doctor RED — refuse run ({detail}). Use --force to override.")
    if preset and preset.requires_i_know and not i_know:
        raise GateError(
            f"preset '{preset.id}' requires --i-know (memory/jetsam risk)."
        )
    return report
