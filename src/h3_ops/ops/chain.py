"""Episode chain: lock identity on openers, hand off tail → next first-frame.

h3.c cannot mix Ref2VA (--ref-image) and FL2VA (--first-frame) in one call.
The product rule is:

- opener / hard cut → looksheet via --ref-image (锁脸)
- following shots in the same chain → previous mp4 tail via --first-frame (接戏)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from h3_ops.config import Config
from h3_ops.ops.run import RunError, run_job
from h3_ops.presets import Preset


def has_ref2va(cfg: Config) -> bool:
    return (cfg.model_dir / "Ref2VA").is_dir()


@dataclass
class PlannedShot:
    id: str
    prompt: str
    mode: str  # lock | handoff | t2v
    seed: int | None
    output: Path


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("shots"), list):
        raise RunError(f"manifest needs a shots array: {path}")
    if not data["shots"]:
        raise RunError(f"manifest has no shots: {path}")
    return data


def plan_shots(
    manifest: dict,
    *,
    out_dir: Path,
    manifest_dir: Path,
) -> tuple[Path | None, list[PlannedShot]]:
    look_raw = manifest.get("looksheet")
    looksheet = None
    if look_raw:
        looksheet = Path(look_raw)
        if not looksheet.is_absolute():
            looksheet = (manifest_dir / looksheet).resolve()
    default_seed = manifest.get("seed")
    if default_seed is not None and not isinstance(default_seed, int):
        default_seed = None

    planned: list[PlannedShot] = []
    for i, shot in enumerate(manifest["shots"]):
        if not isinstance(shot, dict):
            raise RunError(f"shot {i} is not an object")
        sid = str(shot.get("id") or f"{i + 1:02d}")
        prompt = str(shot.get("prompt") or "").strip()
        if not prompt and shot.get("prompt_file"):
            pf = Path(shot["prompt_file"])
            if not pf.is_absolute():
                pf = manifest_dir / pf
            if not pf.is_file():
                raise RunError(f"prompt file missing: {pf}")
            prompt = pf.read_text(encoding="utf-8").strip()
        if not prompt:
            raise RunError(f"shot {sid} has empty prompt")
        mode = shot.get("mode")
        if mode not in (None, "lock", "handoff", "t2v"):
            raise RunError(f"shot {sid}: mode must be lock|handoff|t2v")
        if mode is None:
            if shot.get("hard_cut"):
                mode = "lock" if looksheet else "t2v"
            elif i == 0:
                mode = "lock" if looksheet else "t2v"
            else:
                mode = "handoff"
        if mode == "lock" and looksheet is None and not shot.get("ref_image"):
            raise RunError(f"shot {sid}: lock mode needs looksheet or ref_image")
        if mode == "handoff" and i == 0:
            raise RunError(f"shot {sid}: handoff needs a previous shot")
        seed = shot.get("seed", default_seed)
        if seed is not None and not isinstance(seed, int):
            seed = None
        planned.append(
            PlannedShot(
                id=sid,
                prompt=prompt,
                mode=str(mode),
                seed=seed,
                output=out_dir / f"{sid}.mp4",
            )
        )
    return looksheet, planned


def extract_last_frame(mp4: Path, png: Path) -> Path:
    if not mp4.is_file():
        raise RunError(f"cannot hand off — missing previous video: {mp4}")
    png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-sseof",
        "-0.08",
        "-i",
        str(mp4),
        "-frames:v",
        "1",
        str(png),
    ]
    try:
        subprocess.check_call(cmd)
    except (OSError, subprocess.CalledProcessError) as e:
        raise RunError(f"ffmpeg failed extracting tail from {mp4}: {e}") from e
    if not png.is_file() or png.stat().st_size < 500:
        raise RunError(f"tail frame empty: {png}")
    return png


def run_chain(
    cfg: Config,
    preset: Preset,
    *,
    manifest_path: Path,
    out_dir: Path,
    dry_run: bool = False,
    force: bool = False,
    i_know: bool = False,
    stitch: bool = True,
) -> int:
    manifest = load_manifest(manifest_path)
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    looksheet, shots = plan_shots(
        manifest, out_dir=out_dir, manifest_dir=manifest_path.parent
    )
    if looksheet is not None and not looksheet.is_file() and not dry_run:
        raise RunError(f"looksheet not found: {looksheet}")

    use_ref2va = has_ref2va(cfg)
    if not use_ref2va and any(s.mode == "lock" for s in shots):
        print(
            "note: Ref2VA weights missing — lock shots fall back to "
            "FL2VA --first-frame=looksheet (install Ref2VA for true identity lock)",
            flush=True,
        )

    print(
        f"chain preset={preset.id} shots={len(shots)} "
        f"looksheet={looksheet or 'none'} ref2va={use_ref2va}",
        flush=True,
    )
    outputs: list[Path] = []
    for i, shot in enumerate(shots):
        prompt_path = out_dir / f"{shot.id}.prompt.txt"
        prompt_path.write_text(shot.prompt + "\n", encoding="utf-8")
        first: Path | None = None
        refs: list[Path] = []
        if shot.mode == "lock":
            ref = looksheet
            raw = manifest["shots"][i].get("ref_image")
            if raw:
                ref = Path(raw)
                if not ref.is_absolute():
                    ref = (manifest_path.parent / ref).resolve()
            if ref is None:
                raise RunError(f"shot {shot.id}: lock without ref")
            if use_ref2va:
                refs = [ref]
                print(f"[{shot.id}] lock --ref-image {ref.name}", flush=True)
            else:
                first = ref
                print(
                    f"[{shot.id}] lock-fallback --first-frame {ref.name}",
                    flush=True,
                )
        elif shot.mode == "handoff":
            prev = shots[i - 1].output
            tail = out_dir / "_handoff" / f"{shots[i - 1].id}_tail.png"
            if dry_run:
                first = tail
                print(f"[{shot.id}] handoff (planned) {prev.name} → {tail.name}", flush=True)
            else:
                first = extract_last_frame(prev, tail)
                print(f"[{shot.id}] handoff --first-frame {first.name}", flush=True)
        else:
            print(f"[{shot.id}] t2v (no anchor)", flush=True)

        rc = run_job(
            cfg,
            preset,
            prompt_file=prompt_path,
            output=shot.output,
            seed=shot.seed,
            dry_run=dry_run,
            force=force,
            i_know=i_know,
            first_frame=first,
            ref_images=refs or None,
        )
        if rc != 0:
            return rc
        outputs.append(shot.output)

    if stitch and len(outputs) >= 2:
        stitched = out_dir / "chain.mp4"
        if dry_run:
            print(f"DRY-RUN stitch → {stitched}", flush=True)
            return 0
        from h3_ops.hd.stitch import stitch as hd_stitch

        hd_stitch(outputs, stitched)
        print(f"stitched {stitched}", flush=True)
    return 0
