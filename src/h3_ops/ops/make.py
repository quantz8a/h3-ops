"""One-shot topic → h3.c mp4 (Pixelle-style UX, Apple + h3.c engine)."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from h3_ops.config import Config
from h3_ops.ops.run import RunError, run_job
from h3_ops.presets import Preset, load_preset

# Pixelle: topic → video. Here the media engine is always local h3.c.
# Efficiency north star: hq/turbo → film_turbo (≥10× vs film_master wall).
QUALITY_PRESETS: dict[str, str] = {
    "hq": "film_turbo",
    "turbo": "film_turbo",
    "snap": "snap",
    "draft": "film_draft",
    "motion": "film_draft_motion",
    "master": "film_master",
    "hero": "film_hero",
    "clean": "film_hero_clean",
}


def slugify(text: str, *, max_len: int = 40) -> str:
    s = text.strip().lower()
    s = re.sub(r"[\s_/]+", "-", s)
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "shot"
    # Keep CJK; filesystem-safe enough on macOS
    return s[:max_len]


def wrap_topic_as_h3_prompt(
    topic: str,
    *,
    landscape: bool = True,
) -> str:
    """Turn a plain topic/script into an h3 multimodal prompt if needed."""
    raw = topic.strip()
    if not raw:
        raise RunError("empty topic / prompt")
    if "integrated_multimodal_description:" in raw:
        return raw if raw.endswith("\n") else raw + "\n"

    orient = (
        "16:9 cinematic landscape"
        if landscape
        else "9:16 vertical short-drama"
    )
    body = " ".join(raw.split())
    return (
        f"integrated_multimodal_description: [Shot] AI-native {orient}. "
        f"{body} Continuous full-body motion every frame, stable silhouettes, "
        f"smooth anti-aliased edges, no sparkle noise, no jagged spikes, "
        f"no temporal flicker, no readable text, no watermark.\n"
        f"overall_soundscape: cinematic ambience matching the scene.\n"
        f"non_diegetic_music: subtle underscore.\n"
    )


def resolve_quality_preset(cfg: Config, quality: str) -> Preset:
    key = (quality or "draft").strip().lower()
    preset_id = QUALITY_PRESETS.get(key)
    if preset_id is None:
        # allow raw preset id
        preset_id = key
    try:
        return load_preset(cfg.presets_dir, preset_id)
    except FileNotFoundError as e:
        known = ", ".join(sorted(QUALITY_PRESETS))
        raise RunError(
            f"unknown quality/preset {quality!r}; try one of: {known}"
        ) from e


def default_output_path(repo_root: Path, topic: str, preset_id: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"make_{slugify(topic)}_{preset_id}_{stamp}.mp4"
    return repo_root / "out" / name


def make_video(
    cfg: Config,
    *,
    topic: str | None = None,
    prompt_file: Path | None = None,
    quality: str = "hq",
    output: Path | None = None,
    seed: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    profile: bool = True,
    open_result: bool = False,
    landscape: bool = True,
    keep_prompt: bool = True,
) -> int:
    """Doctor-gated one-click: wrap topic → h3ctl run → optional open."""
    if prompt_file is None and not topic:
        raise RunError("pass a topic string or --prompt-file")
    if prompt_file is not None and topic:
        raise RunError("pass topic OR --prompt-file, not both")

    preset = resolve_quality_preset(cfg, quality or "hq")
    repo_root = Path(cfg.presets_dir).parent

    if prompt_file is not None:
        src = Path(prompt_file)
        if not src.is_file():
            raise RunError(f"prompt file missing: {src}")
        prompt_text = src.read_text(encoding="utf-8")
        label = src.stem
    else:
        assert topic is not None
        prompt_text = wrap_topic_as_h3_prompt(topic, landscape=landscape)
        label = topic

    out = (output or default_output_path(repo_root, label, preset.id)).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    work_prompt = out.with_suffix(".prompt.txt")
    if keep_prompt or prompt_file is None:
        work_prompt.write_text(prompt_text, encoding="utf-8")
        prompt_path = work_prompt
    else:
        prompt_path = Path(prompt_file)

    print(f"[make] quality={quality} preset={preset.id}", flush=True)
    print(f"[make] prompt={prompt_path}", flush=True)
    print(f"[make] output={out}", flush=True)

    rc = run_job(
        cfg,
        preset,
        prompt_file=prompt_path,
        output=out,
        seed=seed,
        force=force,
        dry_run=dry_run,
        profile=profile,
    )
    if rc != 0:
        return rc

    if open_result and out.is_file() and not dry_run:
        try:
            subprocess.run(["open", str(out)], check=False)
        except OSError:
            pass
    return 0
