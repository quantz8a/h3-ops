# h3-ops

**Local ops companion for [antirez/h3.c](https://github.com/antirez/h3.c)** — check the Mac, structure the prompt, run Base, deliver with honest HD labels. No Metal fork.

[![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-arm64-black)](https://github.com/antirez/h3.c)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/quantz8a/h3-ops?label=release)](https://github.com/quantz8a/h3-ops/releases/tag/v0.1.0)
[![Site](https://img.shields.io/badge/site-quantz8a.github.io-0f1419)](https://quantz8a.github.io/h3-ops/)

### Value (read this first)

| Speeds up | Does **not** speed up |
|:---|:---|
| **Production velocity** — fewer wasted runs, less mlx/cwd thrash, revise-before-rerun, preset ladder before hero shots | **DiT wall-clock** — same `h3` binary, same steps / canvas / frames |
| Effective shots per day when ops pain and prompt churn dominate | Metal kernels, Turbo LoRA, parallel Base on one GPU |

`h3.c` alone: wrong cwd (no shaders), no revise/lock loop, and local upscale that looks like Regenerate-2K.  
`h3-ops` is the thin CLI that closes those gaps — without forking Metal / DiT.

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
h3ctl run --preset smoke --prompt-file examples/smoke.prompt.txt -o out/smoke.mp4
```

Needs: Apple Silicon, a **built** [h3.c](https://github.com/antirez/h3.c), MiniMax-H3 with `FL2VA/`, and `ffmpeg` / `ffprobe`.  
Without install: `PYTHONPATH=src python3 -m h3_ops …` or `./scripts/h3ctl …`.

Typical loop:

```bash
h3ctl cir compile --brief "剑气削叶" -o shot.cir.json
h3ctl cir validate shot.cir.json
h3ctl run --preset preview --doc shot.cir.json -o out/preview.mp4
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

Measured on **M3 Ultra 96GB** with `--ssd-streaming` (order of magnitude):

| preset | canvas | frames | steps | ~wall | use |
|:---|:---|:---:|:---:|:---|:---|
| `smoke` | 512² | 22 | 4 | ~66s (h3ctl) | path check |
| `draw` | 480×832 | 56 | 4–8 | ~2 min | vertical card pulls |
| `preview` | 480×832 | 124 | 8 | ~5 min | ≥5s review |
| `deliver` | 480×832 | 124 | 20–30 | 7–14 min | hero; gate must be green |
| `unsafe_hq` | ≥576×1024 | 124 | ≥20 | high | jetsam risk if mlx alive |

Field failures already seen: wrong cwd (no shaders), `mlx-serve` eating unified memory, free pages → 0 looking like a hang. Start with `h3ctl doctor`.

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

- Faster DiT / new kernels / redistributing weights  
- Vendor drama / looksheet business  
- Label local upscale as Regenerate-2K  
- Claiming “2× inference” — value is **fewer failed and overbuilt runs**, not a shorter denoise loop

## Docs

- Design SoT: [DESIGN.md](DESIGN.md)
- Landing: https://quantz8a.github.io/h3-ops/
- Release: https://github.com/quantz8a/h3-ops/releases/tag/v0.1.0
- Schema: [docs/schemas/context_doc.v1.json](docs/schemas/context_doc.v1.json)
- Example doc: [examples/leafcut.cir.json](examples/leafcut.cir.json)
- Discussions: https://github.com/quantz8a/h3-ops/discussions

## License

MIT (same spirit as `h3.c`). Model cards apply to weights.
