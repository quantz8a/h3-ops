# Efficiency north star — high-quality video, ≥10× faster than film_master

## Goal

**产出高质量视频的效率提升 ≥10×**（相对冷启动 `film_master` 墙钟），引擎仍是本地 [antirez/h3.c](https://github.com/antirez/h3.c)。

不是 Pixelle 式「主题→口播→BGM」长链路；是把 **成片画幅的试片/交付** 从 20–40 分钟压到约 **2–4 分钟**。

## Measured baseline (M3 Ultra 96GB)

| preset | canvas | knobs | wall (obs.) | role |
|:---|:---|:---|:---|:---|
| `film_master` | 1248×704 native · f124 · s8 · L45 | resident | **~23–41 min** | quality ceiling |
| `film_hero` / `_clean` | same · s12–20 | resident | **~50–60 min** | climax |
| `film_draft` | 832×480 · f56 · s4 | TR | **~2 min** | card |
| **`film_turbo`** | **out 1248×704** · render 832×480 · f56 · s4 · L40 · TR · int8 | resident | **target ≤ ~2–4 min** | **efficiency HQ** |

Denoise dominates (≥90% of master wall). TE+DiT load ~15–30s — win is **less denoise work**, then **warm** for shot 2+.

## How `film_turbo` gets ~10×

Approx cost ∝ `steps × render_pixels × frames` (layers/token-reduction secondary):

| factor | master | turbo | ratio |
|:---|:---|:---|:---|
| steps | 8 | 4 | 0.50 |
| render px | 1248×704 | 832×480 | ~0.45 |
| frames | 124 | 56 | ~0.45 |
| **product** | 1 | **~0.10** | **~10×** |

Output stays **1248×704** (h3 upscales from `--render-width/height`).  
`token_reduction` + `layers40` + `use_int8_row_fc2` shave more without leaving Apple path.

## Product defaults

```bash
# one-click HQ-fast (default quality=hq → film_turbo)
h3ctl make "三线城市夜空功夫大战异形" --quality hq --open

# explicit
h3ctl run --preset film_turbo --prompt-file shot.txt -o out/turbo.mp4 --profile

# multi-shot: keep DiT hot
h3ctl warm --preset film_turbo
```

| quality | preset | when |
|:---|:---|:---|
| `hq` / `turbo` | `film_turbo` | **default** — 效率成片 |
| `draft` | `film_draft` | 更快卡片 |
| `master` | `film_master` | 质量封顶 |
| `hero` / `clean` | `film_hero*` | 开场/去毛刺 |

## Honest limits

- Turbo is **not** `film_hero` face-lock; mid-fight ghosting may remain — climb steps only when needed.
- First shot still pays cold load; **10× is denoise-bound**, warm makes shot 2+ closer to denoise-only.
- Fighting `mlx-serve` / second `./h3` destroys the gain — `doctor` + mlx exclusive stay mandatory.

## Native 864×480 FLOP curve (M3 Ultra, smoke 56f)

BF16 GEMM is already ~19 TFLOPS-capped; further wins are **less DiT work**. Eye-check 2026-09-29:

| preset / knobs | denoise | vs reuse1 baseline | eye |
|:---|---:|---:|:---|
| `ns_480p_15s_hq_smoke` (S8 L50 r1) | ~155s | 1.0× | gold |
| `reuse=2` only | ~97s | ~1.6× | accepted |
| token_reduction | ~99s | ~1.6× | **rejected** (ghosting) |
| **`hq_fast` = r2+S6** | **~78s** | **~2.0×** | **accepted delivery** |

```bash
# 科教成片（推荐）
h3ctl run --preset ns_480p_15s_hq_fast --prompt-file examples/ns_480p_15s.prompt.txt \
  -o out/ns_fast.mp4 --profile --no-ssd-streaming
```

Alias presets: `ns_480p_15s_hq_r2` (r2 only), `ns_480p_15s_hq_fast_s6` (same knobs as hq_fast).  
Full 362f still far from ≤60s; no TR for diagram-heavy 科教.
