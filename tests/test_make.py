"""Tests for one-click make prompt wrapping."""

from __future__ import annotations

from pathlib import Path

from h3_ops.config import Config
from h3_ops.ops.make import (
    QUALITY_PRESETS,
    resolve_quality_preset,
    slugify,
    wrap_topic_as_h3_prompt,
)


def test_wrap_plain_topic() -> None:
    p = wrap_topic_as_h3_prompt("哥特教堂女战士斩异形")
    assert p.startswith("integrated_multimodal_description:")
    assert "哥特教堂" in p
    assert "16:9" in p


def test_wrap_preserves_raw_h3_prompt() -> None:
    raw = "integrated_multimodal_description: [Shot] already wrapped.\noverall_soundscape: x.\n"
    assert wrap_topic_as_h3_prompt(raw) == raw


def test_slugify_cjk() -> None:
    assert "哥特" in slugify("哥特 教堂!!")
    assert slugify("") == "shot"


def test_quality_maps() -> None:
    root = Path(__file__).resolve().parents[1]
    cfg = Config.from_env(root)
    for q, pid in QUALITY_PRESETS.items():
        if pid == "film_draft_motion" and not (cfg.presets_dir / f"{pid}.yaml").is_file():
            continue
        if not (cfg.presets_dir / f"{pid}.yaml").is_file():
            continue
        preset = resolve_quality_preset(cfg, q)
        assert preset.id == pid
