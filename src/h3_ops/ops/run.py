from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from h3_ops.cir import CirError, load_doc, load_schema
from h3_ops.cir.emit import emit_prompt
from h3_ops.cir.validate import require_valid
from h3_ops.config import Config
from h3_ops.ops.gate import GateError, gate
from h3_ops.ops.lock import LockError, acquire_lock, release_lock
from h3_ops.ops.report import argv_hash, new_job_id, start_report
from h3_ops.presets import Preset


class RunError(RuntimeError):
    pass


def build_argv(
    cfg: Config,
    preset: Preset,
    *,
    prompt: str,
    output: Path,
    seed: int | None,
    width: int | None = None,
    height: int | None = None,
    frames: int | None = None,
    extra: list[str] | None = None,
    first_frame: Path | None = None,
    last_frame: Path | None = None,
    ssd_streaming: bool | None = None,
) -> list[str]:
    # Always invoke as ./h3 from h3c_src so relative Metal shaders resolve.
    argv = [
        "./h3",
        "-d",
        str(cfg.model_dir),
        "-p",
        prompt,
        "--width",
        str(width if width is not None else preset.width),
        "--height",
        str(height if height is not None else preset.height),
        "--frames",
        str(frames if frames is not None else preset.frames),
        "--steps",
        str(preset.steps),
        "-o",
        str(output.resolve()),
    ]
    if ssd_streaming is None:
        use_ssd = (
            preset.ssd_streaming
            if preset.ssd_streaming is not None
            else bool(cfg.ssd_streaming_default)
        )
    else:
        use_ssd = bool(ssd_streaming)
    if use_ssd:
        argv.append("--ssd-streaming")
    if first_frame is not None:
        argv.extend(["--first-frame", str(first_frame.resolve())])
    if last_frame is not None:
        argv.extend(["--last-frame", str(last_frame.resolve())])
    if preset.render_width is not None or preset.render_height is not None:
        rw = preset.render_width
        rh = preset.render_height
        if rw is None and rh is not None:
            rw = rh
        if rh is None and rw is not None:
            # keep output aspect
            out_w = width if width is not None else preset.width
            out_h = height if height is not None else preset.height
            rh = max(64, int(round(rw * out_h / out_w)))
        argv.extend(["--render-width", str(int(rw)), "--render-height", str(int(rh))])
    if preset.reuse is not None:
        argv.extend(["--reuse", str(int(preset.reuse))])
    if preset.core_reuse is not None:
        argv.extend(["--core-reuse", str(int(preset.core_reuse))])
    if preset.layers is not None:
        argv.extend(["--layers", str(int(preset.layers))])
    if seed is not None:
        argv.extend(["--seed", str(seed)])
    if extra:
        argv.extend(extra)
    return argv


def _resolve_prompt_and_doc(
    cfg: Config,
    *,
    prompt_file: Path | None,
    doc_path: Path | None,
    output: Path,
    from_duration: bool,
) -> tuple[str, str | None, int | None, int | None, int | None, int | None, list[str]]:
    """Return prompt, doc_id, seed, width, height, frames, extra_warnings."""
    warnings: list[str] = []
    if bool(prompt_file) == bool(doc_path):
        raise RunError("provide exactly one of --prompt-file or --doc")

    if prompt_file is not None:
        if not prompt_file.is_file():
            raise RunError(f"prompt file not found: {prompt_file}")
        prompt = prompt_file.read_text(encoding="utf-8").strip()
        if not prompt:
            raise RunError(f"empty prompt file: {prompt_file}")
        return prompt, None, None, None, None, None, warnings

    assert doc_path is not None
    try:
        doc = load_doc(doc_path)
        schema = load_schema(Path(cfg.presets_dir).parent)
        require_valid(doc, schema)
    except CirError as e:
        raise RunError(str(e)) from e

    prompt = emit_prompt(doc)
    prompt_out = output.with_suffix(".prompt.txt")
    prompt_out.write_text(prompt, encoding="utf-8")
    warnings.append(f"emitted prompt → {prompt_out}")

    canvas = doc.get("canvas") or {}
    width = canvas.get("w")
    height = canvas.get("h")
    frames = None
    if from_duration and isinstance(doc.get("duration"), (int, float)):
        fps = int(doc.get("fps") or 24)
        frames = max(22, round(float(doc["duration"]) * fps))
    seed = doc.get("seed")
    if seed is not None and not isinstance(seed, int):
        seed = None
    if doc.get("unsafe"):
        warnings.append("doc.unsafe=true — still requires --i-know for unsafe presets")
    return prompt, str(doc.get("id")), seed, width, height, frames, warnings


def run_job(
    cfg: Config,
    preset: Preset,
    *,
    output: Path,
    prompt_file: Path | None = None,
    doc_path: Path | None = None,
    seed: int | None = None,
    i_know: bool = False,
    force: bool = False,
    dry_run: bool = False,
    profile: bool = False,
    from_duration: bool = False,
    first_frame: Path | None = None,
    last_frame: Path | None = None,
    ssd_streaming: bool | None = None,
) -> int:
    prompt, doc_id, doc_seed, width, height, frames, emit_warnings = (
        _resolve_prompt_and_doc(
            cfg,
            prompt_file=prompt_file,
            doc_path=doc_path,
            output=output.resolve(),
            from_duration=from_duration,
        )
    )
    if seed is None:
        seed = doc_seed

    # unsafe canvas on doc needs --i-know even for safe presets
    if doc_path is not None:
        try:
            doc = load_doc(doc_path)
        except CirError as e:
            raise RunError(str(e)) from e
        if doc.get("unsafe") and not i_know:
            raise RunError("ContextDoc has unsafe=true; pass --i-know")

    report_doc = gate(
        cfg, preset=preset, i_know=i_know, force=force, dry_run=dry_run
    )
    warnings = [
        f"{c.name}: {c.detail}"
        for c in report_doc.checks
        if c.level.value != "ok"
    ]
    warnings.extend(emit_warnings)

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix(output.suffix + ".log")
    report_path = output.with_suffix(output.suffix + ".report.json")

    argv = build_argv(
        cfg,
        preset,
        prompt=prompt,
        output=output,
        seed=seed,
        width=width,
        height=height,
        frames=frames,
        extra=["--profile"] if profile else None,
        first_frame=first_frame,
        last_frame=last_frame,
        ssd_streaming=ssd_streaming,
    )
    job_id = new_job_id(preset.id)
    job = start_report(
        job_id=job_id,
        preset=preset.id,
        argv=[a if a != prompt else f"<prompt {len(prompt)} chars>" for a in argv],
        cwd=str(cfg.h3c_src),
        output_mp4=str(output),
        log_path=str(log_path),
        warnings=warnings,
    )
    job.doc_id = doc_id

    if dry_run:
        print("DRY-RUN cwd=", cfg.h3c_src)
        print("DRY-RUN argv=", " ".join(job.argv))
        if doc_id:
            print("DRY-RUN doc_id=", doc_id)
        job.exit_code = 0
        job.ended_at = job.started_at
        job.wall_s = 0.0
        job.write(report_path)
        print(f"wrote {report_path}")
        return 0

    try:
        acquire_lock(
            cfg.lock_path,
            holder=f"h3ctl-run:{preset.id}:{output.name}",
            argv_hash=argv_hash(argv),
        )
    except LockError as e:
        raise RunError(str(e)) from e

    import time
    from datetime import datetime, timezone

    t0 = time.time()
    try:
        with log_path.open("w", encoding="utf-8") as logf:
            logf.write(f"# job_id={job_id}\n# cwd={cfg.h3c_src}\n")
            if doc_id:
                logf.write(f"# doc_id={doc_id}\n")
            logf.write("# argv=" + " ".join(job.argv) + "\n")
            logf.flush()
            proc = subprocess.Popen(
                argv,
                cwd=str(cfg.h3c_src),
                stdout=logf,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            rc = proc.wait()
    finally:
        release_lock(cfg.lock_path)

    t1 = time.time()
    job.exit_code = rc
    job.wall_s = round(t1 - t0, 3)
    job.ended_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if rc != 0:
        job.warnings.append(f"h3 exited {rc}")
    if rc == 0 and not output.is_file():
        job.warnings.append("exit 0 but output mp4 missing")
        rc = 2
        job.exit_code = rc
    job.write(report_path)
    print(f"exit={rc} wall_s={job.wall_s} report={report_path}", file=sys.stderr)
    return rc
