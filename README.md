# h3-ops

**North star:** on **Mac Ultra + MiniMax-H3**, make local pulls feel like **秒出** — via [antirez/h3.c](https://github.com/antirez/h3.c) fast paths, warm residency, and an ops ladder. No Metal fork.

[![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-arm64-black)](https://github.com/antirez/h3.c)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/quantz8a/h3-ops?label=release)](https://github.com/quantz8a/h3-ops/releases/tag/v0.1.0)
[![Site](https://img.shields.io/badge/site-quantz8a.github.io-0f1419)](https://quantz8a.github.io/h3-ops/)

### Goal → reality (read this first)

| | |
|:---|:---|
| **Goal** | Mac Ultra 上 MiniMax-H3 **秒级出图/试片**（再升到可交付） |
| **How** | Pin the `h3.c` fast knobs (`snap` / warm session), kill wasted cold starts (doctor / GPU lock / no mlx fight), only then spend minutes on `preview`/`deliver` |
| **Not** | Replacing Metal kernels inside `h3.c`. We orchestrate the second-scale path; antirez owns the denoise math |
| **Today** | M3 Ultra 96GB measured: `snap` cold e2e **35.2s** (TE 7.8 + DiT load 15.2 + denoise **5.6** + VAE). Cold `smoke` ≈ **66s**. Gap to 秒出 ≈ **warm DiT residency** (interactive / `h3ctl warm`) |


```bash
h3ctl doctor          # mlx / rivals must be clear
h3ctl run --preset snap --prompt-file examples/smoke.prompt.txt -o out/snap.mp4 --profile
```

`h3.c` alone: wrong cwd (no shaders), no revise/lock loop, easy to accidentally run 14‑min hero shots while iterating.  
`h3-ops` makes the **秒出 ladder** the default path — without forking Metal / DiT.


<p align="center">
  <img src="docs/demo/smoke.gif" alt="h3-ops smoke preset (~1s, 512²) via h3ctl run" width="360" />
</p>

<p align="center"><sub>smoke preset · ~1s · 512² · <code>h3ctl run</code> on Apple Silicon</sub></p>

[![flow](docs/assets/hero-flow.svg)](https://quantz8a.github.io/h3-ops/)

| Official module | Open? | Local stand-in |
|:---|:---|:---|
| H3-Context-IR | API only | `cir` — compile / validate / revise / emit |
| H3-Base | weights open | `ops` — doctor / gate / run / batch |
| H3-Regenerate-2K | API only | `hd` — native → upscale → optional cloud 2K |

**Truth artifact:** `ContextDoc` JSON ([schema](docs/schemas/context_doc.v1.json)). MP4 is a projection of doc + seed + preset.  
**Status:** Phase 0–4 MVP shipped (ops + cir + hd). Phase 5 = cloud adapters. See [DESIGN.md](DESIGN.md).

## Quick start

```bash
git clone https://github.com/quantz8a/h3-ops.git
cd h3-ops
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .

export H3_OPS_H3C_SRC=/path/to/h3.c          # tree that contains h3_shaders.metal
export H3_OPS_MODEL_DIR=/path/to/MiniMax-H3   # must include FL2VA/
h3ctl doctor
h3ctl run --preset snap --prompt-file examples/smoke.prompt.txt -o out/snap.mp4 --profile
# or: smoke / draw / preview / deliver
```

Needs: Apple Silicon, a **built** [h3.c](https://github.com/antirez/h3.c), MiniMax-H3 with `FL2VA/`, and `ffmpeg` / `ffprobe`.  
Without install: `PYTHONPATH=src python3 -m h3_ops …` or `./scripts/h3ctl …`.

Typical loop:

```bash
h3ctl cir compile --brief "剑气削叶" -o shot.cir.json
h3ctl cir validate shot.cir.json
h3ctl run --preset preview --doc shot.cir.json -o out/preview.mp4
# factory / FL2VA:
# h3ctl run --preset draw --prompt-file shot.txt -o out.mp4 \
#   --first-frame start.png --no-ssd-streaming
h3ctl cir revise shot.cir.json --notes "剑气线不可读" -o shot.cir.json
h3ctl hd deliver --doc shot.cir.json --base out/preview.mp4 \
  --target upscale_1080 -o out/deliver_1080.mp4
```

Working now: `doctor`, `presets`, `lock`, `run`, `cir *`, `hd ladder|deliver|stitch`.  
Demo ContextDoc: [examples/leafcut.cir.json](examples/leafcut.cir.json). Drop real clips under [examples/renders/](examples/renders/) (see README there).

### Optional LLM (cir only)

```bash
export H3_OPS_LLM_BASE=http://127.0.0.1:11236/v1
export H3_OPS_LLM_MODEL=local
h3ctl cir compile --brief "..." --backend llm -o shot.cir.json
# never run LLM parallel with h3ctl run on the same GPU
```

## Requirements

| Need | Notes |
|:---|:---|
| Apple Silicon | `arm64` |
| Built `h3.c` | spawn **must** `chdir` to the tree that has `h3_shaders.metal` |
| MiniMax-H3 BF16 | local path with `FL2VA/` — not shipped here |
| `ffmpeg` / `ffprobe` | stitch / probe |
| Optional LLM | OpenAI-compatible for `cir.compile` |
| Optional API key | cloud CIR / Regenerate-2K adapters only |

## Presets & wall-clock anchors

Measured on **M3 Ultra 96GB** unless noted. **秒出 starts at `snap`**, not `deliver`.

| preset | canvas | frames | steps | knobs | ~wall | use |
|:---|:---|:---:|:---:|:---|:---|:---|
| `snap` | 512² | 22 | 4 | layers40·reuse3·rw384 | **target: seconds denoise (warm)**; cold e2e TBD | 秒级试片 |
| `snap256` | 256² | 22 | 4 | layers40·reuse3 | fastest composition pull | 构图闪看 |
| `smoke` | 512² | 22 | 4 | default | ~66s cold e2e | path check |
| `draw` | 480×832 | 56 | 4–8 | — | ~2 min | vertical card |
| `preview` | 480×832 | 124 | 8 | — | ~5 min | ≥5s review |
| `deliver` | 480×832 | 124 | 20–30 | — | 7–14 min | hero; gate green |
| `unsafe_hq` | ≥576×1024 | 124 | ≥20 | — | high | jetsam if mlx alive |

Upstream reference: M5 Max denoise ≈ **3.5s** for 512²·22f·4step ([h3.c](https://github.com/antirez/h3.c)). Ultra cold e2e is dominated by load + text-encoder unless DiT stays resident (interactive / future `h3ctl warm`).

Field failures: wrong cwd (no shaders), `mlx-serve` eating unified memory, free pages → 0 looking like a hang. **秒出 requires `h3ctl doctor` green/yellow without rival `./h3` and preferably without mlx Base fight.**

## Config

| Env | Default idea |
|:---|:---|
| `H3_OPS_H3C_SRC` | path to h3.c checkout |
| `H3_OPS_MODEL_DIR` | MiniMax-H3 root (`FL2VA/`) |
| `H3_OPS_LOCK` | `~/.cache/h3-ops/gpu.lock` |
| `H3_OPS_LLM_BASE` | OpenAI-compatible base URL (cir only) |
| `H3_OPS_LLM_MODEL` | model id (default `local`) |
| `MINIMAX_API_KEY` | cloud adapters only |

## Non-goals

- Forking / reimplementing Metal DiT or redistributing weights  
- Vendor drama / looksheet business  
- Label local upscale as Regenerate-2K  
- Claiming deliver-quality 5s clips in one second — **秒出 is the snap ladder; hero stays slow on purpose**

## Docs

- Design SoT: [DESIGN.md](DESIGN.md)
- Landing: https://quantz8a.github.io/h3-ops/
- Release: https://github.com/quantz8a/h3-ops/releases/tag/v0.1.0
- Schema: [docs/schemas/context_doc.v1.json](docs/schemas/context_doc.v1.json)
- Example doc: [examples/leafcut.cir.json](examples/leafcut.cir.json)
- Discussions: https://github.com/quantz8a/h3-ops/discussions

## License

MIT (same spirit as `h3.c`). Model cards apply to weights.
