# h3-opt

**主打：苹果平台极致性能** — Mac Ultra / Apple Silicon 上把 [MiniMax-H3](https://github.com/MiniMax-AI/MiniMax-H3) + [antirez/h3.c](https://github.com/antirez/h3.c) 拧到 **秒级试片**，再按需爬升到可交付。不 fork Metal。

> 仓库名 `h3-ops` · CLI `h3ctl` · 产品名 **h3-opt**（optimize for Apple）。

[![Apple Silicon](https://img.shields.io/badge/Apple%20Silicon-极致性能-black)](https://github.com/antirez/h3.c)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/quantz8a/h3-ops?label=release)](https://github.com/quantz8a/h3-ops/releases/tag/v0.1.0)
[![Site](https://img.shields.io/badge/site-quantz8a.github.io-0f1419)](https://quantz8a.github.io/h3-ops/)

### Goal → reality (read this first)

| | |
|:---|:---|
| **Brand** | **h3-opt** — Apple-first extreme performance for local H3 |
| **Goal** | Mac Ultra 上 MiniMax-H3 **秒级出图/试片**（再升到可交付） |
| **How** | Pin `h3.c` fast knobs (`snap` / warm session), exclusive GPU, zero mlx fight, measure denoise vs e2e |
| **Not** | CUDA / Comfy 通用栈；不重写 Metal 内核（antirez 管算子，我们管极致路径） |
| **Today** | M3 Ultra 96GB: `snap` cold e2e **35.2s**（TE 7.8 + DiT load 15.2 + denoise **5.6** + VAE）。Gap → **warm DiT** |

```bash
h3ctl doctor          # mlx / rivals must be clear — 性能第一原则
h3ctl run --preset snap --prompt-file examples/smoke.prompt.txt -o out/snap.mp4 --profile
```

`h3.c` alone: wrong cwd、无锁、容易一上来就跑 14 分钟 hero。  
**h3-opt** 把苹果上的 **极致快路径**做成默认产品（`snap` → `draw` → `preview` → `deliver`）。


<p align="center">
  <img src="docs/demo/xuanhuan_film.gif" alt="h3-opt wuxia film_master on Mac Ultra" width="640" />
</p>

<p align="center"><sub>h3-opt · 武侠横幅 · <code>film_master</code> 1248×704 · Ultra · <code>h3ctl run --preset film_master</code></sub></p>

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
| `snap` | 512² | 22 | 4 | layers40·reuse3·rw384 | **35s cold e2e** / **~5.6s denoise** (Ultra) | 秒级试片目标档 |
| `snap256` | 256² | 22 | 4 | layers40·reuse3 | fastest composition pull | 构图闪看 |
| `smoke` | 512² | 22 | 4 | default | ~66s cold e2e | path check |
| `draw` | 480×832 | 56 | 4–8 | — | ~2–3 min | vertical card |
| `film_draft` | 832×480 | 56 | 4 | layers45 | ~2 min | 16:9 电影卡 |
| `film_master` | 1248×704 | 124 | 8 | layers45 | **~22 min** (Ultra measured) | 16:9 成片 |
| `film_hero` | 1248×704 | 124 | 12 | layers50 | ~25–45 min | 开场/高潮 |
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

- **Why h3-opt（必要性参考）:** [docs/why-h3-opt.md](docs/why-h3-opt.md)
- **Best practices:** [docs/best-practices.md](docs/best-practices.md) · [site §最佳实践](https://quantz8a.github.io/h3-ops/#best-practices)
- Design SoT: [DESIGN.md](DESIGN.md)
- Landing: https://quantz8a.github.io/h3-ops/
- Release: https://github.com/quantz8a/h3-ops/releases/tag/v0.1.0
- Schema: [docs/schemas/context_doc.v1.json](docs/schemas/context_doc.v1.json)
- Example docs: [examples/leafcut.cir.json](examples/leafcut.cir.json) · [examples/xuanhuan_film.prompt.txt](examples/xuanhuan_film.prompt.txt)
- Demos: [docs/demo/snap.gif](docs/demo/snap.gif) · [docs/demo/xuanhuan_film.gif](docs/demo/xuanhuan_film.gif)
- Discussions: https://github.com/quantz8a/h3-ops/discussions

## License

MIT (same spirit as `h3.c`). Model cards apply to weights.
