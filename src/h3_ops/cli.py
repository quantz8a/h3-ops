from __future__ import annotations

import argparse
import sys
from pathlib import Path

from h3_ops import __version__
from h3_ops.cir import CirError, load_doc, load_schema, save_doc
from h3_ops.cir.backend import compile_doc
from h3_ops.cir.emit import emit_prompt
from h3_ops.cir.revise import LOCK_KEYS, revise_doc
from h3_ops.cir.validate import require_valid, validate_doc
from h3_ops.config import Config
from h3_ops.hd.deliver import deliver as hd_deliver
from h3_ops.hd.ladder import HdError, ladder_status
from h3_ops.hd.stitch import stitch as hd_stitch
from h3_ops.ops.doctor import print_report, run_doctor
from h3_ops.ops.gate import GateError
from h3_ops.ops.lock import LockError, acquire_lock, read_lock, release_lock
from h3_ops.ops.run import RunError, run_job, warm_argv
from h3_ops.presets import list_presets, load_preset


def _cfg() -> Config:
    return Config.from_env()


def _repo_root(cfg: Config) -> Path:
    return Path(cfg.presets_dir).parent


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = _cfg()
    report = run_doctor(cfg)
    print_report(report, as_json=args.json)
    if report.worst.value == "red":
        return 2
    if report.worst.value == "yellow":
        return 1
    return 0


def cmd_presets(_args: argparse.Namespace) -> int:
    cfg = _cfg()
    for name in list_presets(cfg.presets_dir):
        p = load_preset(cfg.presets_dir, name)
        ssd = "ssd" if p.ssd_streaming else ("res" if p.ssd_streaming is False else "auto")
        knobs = []
        if p.layers is not None:
            knobs.append(f"L{p.layers}")
        if p.reuse is not None:
            knobs.append(f"r{p.reuse}")
        if p.token_reduction:
            knobs.append("tr")
        print(
            f"{p.id:12} {p.width}x{p.height} f={p.frames} s={p.steps} "
            f"{ssd:4} {' '.join(knobs):12} gate={p.requires_gate}"
        )
    return 0


def _ssd_override(args: argparse.Namespace) -> bool | None:
    if getattr(args, "ssd_streaming", False):
        return True
    if getattr(args, "no_ssd_streaming", False):
        return False
    return None


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _cfg()
    try:
        preset = load_preset(cfg.presets_dir, args.preset)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    prompt_file = Path(args.prompt_file) if args.prompt_file else None
    doc_path = Path(args.doc) if args.doc else None
    try:
        return run_job(
            cfg,
            preset,
            prompt_file=prompt_file,
            doc_path=doc_path,
            output=Path(args.output),
            seed=args.seed,
            i_know=args.i_know,
            force=args.force,
            dry_run=args.dry_run,
            profile=args.profile,
            from_duration=args.from_duration,
            first_frame=Path(args.first_frame) if args.first_frame else None,
            last_frame=Path(args.last_frame) if args.last_frame else None,
            ref_images=[Path(p) for p in (args.ref_image or [])] or None,
            ssd_streaming=_ssd_override(args),
        )
    except (GateError, RunError, LockError, CirError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 3


def cmd_warm(args: argparse.Namespace) -> int:
    """Start interactive h3 — DiT stays resident; type prompts for second-scale denoise."""
    import os

    cfg = _cfg()
    try:
        preset = load_preset(cfg.presets_dir, args.preset)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    if not cfg.h3_bin.is_file():
        print(f"error: h3 binary missing at {cfg.h3_bin}", file=sys.stderr)
        return 2
    try:
        argv = warm_argv(cfg, preset, ssd_streaming=_ssd_override(args))
    except RunError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    print(
        f"h3-opt warm · preset={preset.id} · resident DiT session\n"
        f"cwd={cfg.h3c_src}\n"
        f"argv={' '.join(argv)}\n"
        "Type prompts at h3> ; !quit to exit. First prompt still pays load.",
        file=sys.stderr,
    )
    if args.dry_run:
        return 0
    os.chdir(cfg.h3c_src)
    bin_path = str(cfg.h3_bin.resolve())
    os.execv(bin_path, [bin_path, *argv[1:]])
    return 0  # pragma: no cover


def cmd_chain(args: argparse.Namespace) -> int:
    from h3_ops.ops.chain import run_chain

    cfg = _cfg()
    try:
        preset = load_preset(cfg.presets_dir, args.preset)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    try:
        return run_chain(
            cfg,
            preset,
            manifest_path=Path(args.manifest),
            out_dir=Path(args.output),
            dry_run=args.dry_run,
            force=args.force,
            i_know=args.i_know,
            stitch=not args.no_stitch,
        )
    except (GateError, RunError, LockError, CirError, HdError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 3


def cmd_lock(args: argparse.Namespace) -> int:
    cfg = _cfg()
    if args.action == "status":
        info = read_lock(cfg.lock_path)
        if not info:
            print("unlocked")
            return 0
        alive = True
        try:
            import os

            os.kill(info.pid, 0)
        except ProcessLookupError:
            alive = False
        except PermissionError:
            alive = True
        print(
            f"locked pid={info.pid} alive={alive} since={info.started_at} "
            f"holder={info.holder}"
        )
        return 0
    if args.action == "acquire":
        try:
            info = acquire_lock(cfg.lock_path, holder=args.holder or "h3ctl-lock")
        except LockError as e:
            print(f"error: {e}", file=sys.stderr)
            return 3
        print(f"acquired pid={info.pid}")
        return 0
    if args.action == "release":
        ok = release_lock(cfg.lock_path, force=True)
        print("released" if ok else "already unlocked")
        return 0
    return 2


def cmd_cir_validate(args: argparse.Namespace) -> int:
    cfg = _cfg()
    path = Path(args.doc)
    try:
        doc = load_doc(path)
        schema = load_schema(_repo_root(cfg))
        errors = validate_doc(doc, schema, draft=args.draft)
    except CirError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    if errors:
        print("INVALID")
        for err in errors:
            print(f"- {err}")
        return 1
    print(f"OK {path} id={doc.get('id')}")
    return 0


def cmd_cir_compile(args: argparse.Namespace) -> int:
    cfg = _cfg()
    brief = args.brief
    if args.brief_file:
        brief = Path(args.brief_file).read_text(encoding="utf-8")
    if not brief:
        print("error: provide --brief or --brief-file", file=sys.stderr)
        return 2
    chars = [c for c in (args.character or []) if c]
    cams = [c for c in (args.camera or []) if c]
    try:
        schema = load_schema(_repo_root(cfg))
        doc, used = compile_doc(
            brief,
            schema=schema,
            backend=args.backend,
            title=args.title,
            doc_id=args.id,
            characters=chars or None,
            camera=cams or None,
            style_anchor=args.style,
            width=args.width,
            height=args.height,
            duration=args.duration,
            fps=args.fps,
            draft=args.draft,
            base=cfg.llm_base or None,
            model=cfg.llm_model,
        )
    except CirError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    out = Path(args.output)
    save_doc(out, doc)
    print(f"wrote {out} id={doc['id']} backend={used}")
    return 0


def cmd_cir_revise(args: argparse.Namespace) -> int:
    cfg = _cfg()
    path = Path(args.doc)
    notes = args.notes
    if args.notes_file:
        notes = Path(args.notes_file).read_text(encoding="utf-8")
    if not notes or not str(notes).strip():
        print("error: provide --notes or --notes-file", file=sys.stderr)
        return 2
    unlock = set(args.unlock or [])
    try:
        doc = load_doc(path)
        schema = load_schema(_repo_root(cfg))
        require_valid(doc, schema)
        updated, used = revise_doc(
            doc,
            str(notes),
            backend=args.backend,
            unlock=unlock,
            schema=schema,
            base=cfg.llm_base or None,
            model=cfg.llm_model,
        )
        require_valid(updated, schema)
    except CirError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    out = Path(args.output) if args.output else path
    save_doc(out, updated)
    print(f"wrote {out} id={updated.get('id')} backend={used} unlock={sorted(unlock)}")
    return 0


def cmd_cir_emit(args: argparse.Namespace) -> int:
    cfg = _cfg()
    path = Path(args.doc)
    try:
        doc = load_doc(path)
        schema = load_schema(_repo_root(cfg))
        require_valid(doc, schema)
        text = emit_prompt(doc)
    except CirError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    out = Path(args.output) if args.output else path.with_suffix(".prompt.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text)} chars)")
    return 0


def cmd_hd_ladder(_args: argparse.Namespace) -> int:
    import json

    rows = ladder_status()
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


def cmd_hd_deliver(args: argparse.Namespace) -> int:
    try:
        side = hd_deliver(
            base=Path(args.base),
            output=Path(args.output),
            target=args.target,
            doc_path=Path(args.doc) if args.doc else None,
            allow_fallback=not args.no_fallback,
        )
    except HdError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    print(
        f"level={side['level_achieved']} tool={side['tool']} "
        f"{side['source']['w']}x{side['source']['h']} -> "
        f"{side['output']['w']}x{side['output']['h']}"
    )
    print(f"output={side['output_mp4']}")
    print(f"sidecar={side['sidecar']}")
    print(f"claims={side['claims']}")
    return 0


def cmd_hd_stitch(args: argparse.Namespace) -> int:
    try:
        result = hd_stitch([Path(p) for p in args.inputs], Path(args.output))
    except HdError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    print(
        f"stitched {result['count']} clips -> {result['output_mp4']} "
        f"{result['canvas']['w']}x{result['canvas']['h']} "
        f"duration={result['duration']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="h3ctl", description="h3-opt — Apple extreme performance CLI")
    p.add_argument("--version", action="version", version=f"h3-ops {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="environment / model / rivalry checks")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_doctor)

    pr = sub.add_parser("presets", help="list generation presets")
    pr.set_defaults(func=cmd_presets)

    r = sub.add_parser("run", help="run h3.c with preset + prompt file or ContextDoc")
    r.add_argument("--preset", required=True)
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt-file")
    src.add_argument("--doc", help="ContextDoc JSON (validate + emit)")
    r.add_argument("-o", "--output", required=True)
    r.add_argument("--seed", type=int, default=None)
    r.add_argument(
        "--from-duration",
        action="store_true",
        help="derive --frames from doc.duration * fps",
    )
    r.add_argument("--i-know", action="store_true")
    r.add_argument("--force", action="store_true", help="override doctor RED")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--profile", action="store_true", help="pass --profile to h3")
    r.add_argument("--first-frame", help="FL2VA first-frame conditioning image")
    r.add_argument("--last-frame", help="FL2VA last-frame conditioning image")
    r.add_argument(
        "--ref-image",
        action="append",
        default=[],
        help="Ref2VA identity image (repeatable; exclusive with first/last)",
    )
    ssd = r.add_mutually_exclusive_group()
    ssd.add_argument(
        "--no-ssd-streaming",
        action="store_true",
        help="force memory-resident DiT (default on ≥64GB)",
    )
    ssd.add_argument(
        "--ssd-streaming",
        action="store_true",
        help="stream DiT from SSD (low-RAM only; slower on Ultra)",
    )
    r.set_defaults(func=cmd_run)

    w = sub.add_parser(
        "warm",
        help="interactive h3 session — keep DiT resident for 秒出 after first load",
    )
    w.add_argument("--preset", default="snap", help="knob pack (default: snap)")
    w.add_argument("--dry-run", action="store_true")
    ws = w.add_mutually_exclusive_group()
    ws.add_argument("--no-ssd-streaming", action="store_true")
    ws.add_argument("--ssd-streaming", action="store_true")
    w.set_defaults(func=cmd_warm)

    ch = sub.add_parser(
        "chain",
        help="episode chain: looksheet lock, then tail→next first-frame",
    )
    ch.add_argument("--manifest", required=True, help="JSON shots + optional looksheet")
    ch.add_argument("--preset", default="snap")
    ch.add_argument("-o", "--output", required=True, help="directory for shot mp4s")
    ch.add_argument("--dry-run", action="store_true")
    ch.add_argument("--force", action="store_true")
    ch.add_argument("--i-know", action="store_true")
    ch.add_argument("--no-stitch", action="store_true", help="do not concat into chain.mp4")
    ch.set_defaults(func=cmd_chain)

    lk = sub.add_parser("lock", help="GPU lock status / acquire / release")
    lk.add_argument("action", choices=["status", "acquire", "release"])
    lk.add_argument("--holder", default="")
    lk.set_defaults(func=cmd_lock)

    cir = sub.add_parser("cir", help="Context-IR: compile / validate / emit")
    cir_sub = cir.add_subparsers(dest="cir_cmd", required=True)

    cv = cir_sub.add_parser("validate", help="validate ContextDoc")
    cv.add_argument("doc")
    cv.add_argument("--draft", action="store_true", help="schema only, skip semantic")
    cv.set_defaults(func=cmd_cir_validate)

    cc = cir_sub.add_parser("compile", help="brief → ContextDoc")
    cc.add_argument("--brief", default="")
    cc.add_argument("--brief-file")
    cc.add_argument("-o", "--output", required=True)
    cc.add_argument("--title")
    cc.add_argument("--id")
    cc.add_argument("--character", action="append", default=[])
    cc.add_argument("--camera", action="append", default=[])
    cc.add_argument("--style")
    cc.add_argument("--width", type=int, default=480)
    cc.add_argument("--height", type=int, default=832)
    cc.add_argument("--duration", type=float, default=5.0)
    cc.add_argument("--fps", type=int, default=24)
    cc.add_argument(
        "--backend",
        choices=["auto", "template", "llm"],
        default="auto",
        help="auto uses LLM if H3_OPS_LLM_BASE set",
    )
    cc.add_argument("--draft", action="store_true")
    cc.set_defaults(func=cmd_cir_compile)

    cr = cir_sub.add_parser("revise", help="revise ContextDoc; locks frozen by default")
    cr.add_argument("doc")
    cr.add_argument("--notes", default="")
    cr.add_argument("--notes-file")
    cr.add_argument("-o", "--output", help="default: overwrite doc")
    cr.add_argument(
        "--unlock",
        action="append",
        choices=list(LOCK_KEYS),
        default=[],
        help="allow editing a lock group (repeatable)",
    )
    cr.add_argument(
        "--backend",
        choices=["auto", "template", "llm"],
        default="auto",
    )
    cr.set_defaults(func=cmd_cir_revise)

    ce = cir_sub.add_parser("emit", help="ContextDoc → h3 prompt text")
    ce.add_argument("doc")
    ce.add_argument("-o", "--output")
    ce.set_defaults(func=cmd_cir_emit)

    hd = sub.add_parser("hd", help="honest HD delivery ladder")
    hd_sub = hd.add_subparsers(dest="hd_cmd", required=True)

    hl = hd_sub.add_parser("ladder", help="show available HD levels")
    hl.set_defaults(func=cmd_hd_ladder)

    hd_del = hd_sub.add_parser("deliver", help="base mp4 → deliverable + sidecar")
    hd_del.add_argument("--base", required=True, help="Base H3 mp4")
    hd_del.add_argument("-o", "--output", required=True)
    hd_del.add_argument(
        "--target",
        default="upscale_1080",
        choices=["native", "upscale_1080", "upscale_2k", "cloud_2k"],
    )
    hd_del.add_argument("--doc", help="optional ContextDoc for provenance")
    hd_del.add_argument(
        "--no-fallback",
        action="store_true",
        help="do not fall back when cloud_2k unavailable",
    )
    hd_del.set_defaults(func=cmd_hd_deliver)

    hs = hd_sub.add_parser("stitch", help="concat same-canvas mp4 clips")
    hs.add_argument("inputs", nargs="+", help="input mp4 files in order")
    hs.add_argument("-o", "--output", required=True)
    hs.set_defaults(func=cmd_hd_stitch)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
