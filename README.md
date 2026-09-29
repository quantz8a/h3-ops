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
| **Goal** | **高质量视频产出效率 ≥10×**（相对冷启动 `film_master` 墙钟） |
| **How** | `film_turbo`（成片画幅 + 低内渲染 + 少步）+ `warm` 常驻 + GPU 独占 |
| **Not** | CUDA / Comfy 通用栈；不重写 Metal；不是 Pixelle 口播长链路 |
| **Today** | `film_master` ~23–41 min；`film_turbo` 目标 **~2–4 min** 同画幅交付 — 见 [docs/efficiency.md](docs/efficiency.md) |
| **Speed rules** | ≥64GB **禁止默认 SSD stream**；秒出用 `snap`/`warm`；成片效率默认 `make --quality hq` |

```bash
h3ctl doctor
# 效率成片（默认 hq → film_turbo，相对 master ~10×）
h3ctl make "哥特教堂女战士光刃斩异形" --open
h3ctl run --preset film_turbo --prompt-file examples/smoke.prompt.txt -o out/turbo.mp4 --profile
h3ctl warm --preset film_turbo   # 多镜：首镜冷，之后接近 denoise
h3ctl chain --manifest examples/wuxia_chain.json --preset film_draft -o out/wuxia_chain
```

`h3.c` alone: wrong cwd、无锁、容易一上来就跑 14–40 分钟 hero。  
**h3-opt** 默认走 **效率成片**（`film_turbo`），需要封顶质量再爬 `film_master` / `film_hero`。

### One-click (`h3ctl make`)

参考 [Pixelle-Video](https://github.com/ATH-MaaS/Pixelle-Video) 的「输入主题 → 成片」体验；媒体引擎固定本地 **h3.c**。产品定位是 **HQ 效率**，不是口播工厂。

| | Pixelle-Video | h3-opt `make` |
|:---|:---|:---|
| 输入 | 主题 / 固定脚本 | 主题、剧本、或 `--prompt-file` |
| 引擎 | Comfy / API / TTS / BGM | **仅 antirez/h3.c** |
| 默认质量 | 模板 | **`hq` → `film_turbo`（≥10× vs master）** |
| 封顶 | — | `master` / `hero` / `clean` |

```bash
h3ctl make "三线城市夜空功夫大战异形" --open          # default hq
h3ctl make "…" --quality master -o out/master.mp4   # 质量封顶
open scripts/h3-make.command
```


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
| `snap` | 512² | 22 | 4 | layers40·**reuse1**·rw384·**resident** | cold ~35s / denoise ~秒级；**warm 后接近 denoise** | 秒级试片 |
| `snap256` | 256² | 22 | 4 | layers40·reuse1·resident | fastest composition | 构图闪看 |
| `smoke` | 512² | 22 | 4 | layers45·reuse1·resident | path check | 冒烟 |
| `draw` | 480×832 | 56 | 6 | layers45·reuse2·**token-reduction** | ~1–2 min | vertical card |
| `film_draft` | 832×480 | 56 | 4 | layers45·reuse1·token-reduction | ~1–2 min | 16:9 电影卡 |
| **`film_turbo`** | **1248×704** (render 832×480) | 56 | 4 | L40·TR·int8·resident | **目标 ~2–4 min（≥10× vs master）** | **效率成片默认** |
| `film_master` | 1248×704 | 124 | 8 | layers45·resident | **~22–40 min** | 16:9 质量封顶 |
| `film_hero` | 1248×704 | 124 | 12 | layers50 | ~25–45 min | 开场/高潮 |
| `preview` | 480×832 | 124 | 8 | layers45·reuse2·token-reduction | ~3–5 min | ≥5s review |
| `deliver` | 480×832 | 124 | 24 | layers50·reuse1·resident | 7–14 min | hero |
| `unsafe_hq` | ≥576×1024 | 124 | ≥20 | resident | high | jetsam if mlx alive |

Upstream: M5 Max denoise ≈ **3.5s** @ 512²·22f·4step ([h3.c](https://github.com/antirez/h3.c)).  
**冷启动瓶颈是 TE + DiT load，不是 denoise。** 迭代请用 `h3ctl warm --preset snap`（interactive 常驻），不要每镜新进程 + `--ssd-streaming`。

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
- Claiming deliver-quality 5s clips in one second — **秒出 is snap; HQ efficiency is film_turbo (~10× master); hero stays slow on purpose**

## Docs

- [efficiency.md](docs/efficiency.md) — **≥10× HQ path** (`film_turbo` vs `film_master`)
- [bench/ns-480p-perf-compare.md](docs/bench/ns-480p-perf-compare.md) — native 864×480 engine A/B + FLOP eye-check
- [DESIGN.md](DESIGN.md) — architecture SoT

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
