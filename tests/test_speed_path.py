"""Unit checks for speed-path argv construction."""

from __future__ import annotations

from pathlib import Path

from h3_ops.config import Config
from h3_ops.ops.report import parse_profile_log
from h3_ops.ops.run import build_argv, resolve_ssd_streaming, warm_argv
from h3_ops.presets import Preset, load_preset


def test_ultra_defaults_resident() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    if cfg.ram_gb >= 64:
        assert cfg.ssd_streaming_default is False


def test_snap_argv_no_ssd_reuse1() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    preset = load_preset(cfg.presets_dir, "snap")
    argv = build_argv(
        cfg,
        preset,
        prompt="leaf",
        output=root / "out" / "t.mp4",
        seed=1,
    )
    assert "--ssd-streaming" not in argv
    assert "--reuse" in argv and argv[argv.index("--reuse") + 1] == "1"
    assert "--layers" in argv and argv[argv.index("--layers") + 1] == "40"
    assert "--token-reduction" not in argv


def test_draw_token_reduction() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    preset = load_preset(cfg.presets_dir, "draw")
    argv = build_argv(
        cfg,
        preset,
        prompt="x",
        output=root / "out" / "t.mp4",
        seed=None,
    )
    assert "--token-reduction" in argv
    assert "--ssd-streaming" not in argv


def test_resolve_ssd_cli_override() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    preset = Preset("t", 512, 512, 22, 4, ssd_streaming=False)
    assert resolve_ssd_streaming(cfg, preset, ssd_streaming=True) is True
    assert resolve_ssd_streaming(cfg, preset, ssd_streaming=False) is False


def test_warm_argv_interactive() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    preset = load_preset(cfg.presets_dir, "snap")
    argv = warm_argv(cfg, preset)
    assert "-p" not in argv
    assert "-o" not in argv
    assert "--ssd-streaming" not in argv


def test_ref_exclusive_with_first_frame() -> None:
    from h3_ops.ops.run import RunError, build_argv

    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    preset = load_preset(cfg.presets_dir, "snap")
    look = root / "examples" / "wuxia_look.png"
    try:
        build_argv(
            cfg,
            preset,
            prompt="x",
            output=root / "out" / "t.mp4",
            seed=1,
            first_frame=look,
            ref_images=[look],
        )
    except RunError as e:
        assert "mutually exclusive" in str(e)
    else:
        raise AssertionError("expected exclusive error")


def test_chain_plan_lock_then_handoff() -> None:
    import json
    import tempfile

    from h3_ops.ops.chain import plan_shots

    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "examples" / "wuxia_chain.json").read_text())
    with tempfile.TemporaryDirectory() as td:
        look, shots = plan_shots(
            manifest, out_dir=Path(td), manifest_dir=root / "examples"
        )
    assert look is not None and look.name == "wuxia_look.png"
    assert [s.mode for s in shots] == ["lock", "handoff"]


def test_parse_profile_log() -> None:
    text = "text encoder 7.8s\nDiT load 15.2s\ndenoise 5.6s\nVAE decode 2.1s\n"
    phases = parse_profile_log(text)
    assert phases.get("denoise_s") == 5.6
    assert phases.get("text_encoder_s") == 7.8


if __name__ == "__main__":
    test_ultra_defaults_resident()
    test_snap_argv_no_ssd_reuse1()
    test_draw_token_reduction()
    test_resolve_ssd_cli_override()
    test_warm_argv_interactive()
    test_ref_exclusive_with_first_frame()
    test_chain_plan_lock_then_handoff()
    test_parse_profile_log()
    print("ok")
