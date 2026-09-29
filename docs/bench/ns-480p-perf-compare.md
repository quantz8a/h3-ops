# Native 864×480 performance compare (M3 Ultra)

**Date:** 2026-09-28 → 2026-09-29  
**Machine:** Apple M3 Ultra 96GB · local `quantz8a/h3.c` + `h3-ops`  
**Geometry:** native **864×480** (no render-down) · smoke **56f** (~2.3s @24fps)  
**Prompt:** `examples/ns_480p_15s.prompt.txt`（蛋黄糯米科教）  
**Raw JSON:** this directory (`*.bench.json` / `*-eye.mp4.report.json`)

Goal: quality-preserving speed toward full **362f (~15s) ≤60s**. Engine path hit BF16 GEMM ~19 TFLOPS ceiling; further wins are **less DiT work** (reuse / steps / TR), then eye-check.

## 1. Engine path A/B (same knobs: S8 L50 r1)

Cold-ish `ns_480p_15s_hq_smoke` runs. Denoise ≈ encode + wait.

| label | denoise (s) | encode | wait | wall (s) | verdict |
|:---|---:|---:|---:|---:|:---|
| `old_cpu_mps` | 153.3 | 125.1 | 27.4 | 214.3 | baseline |
| `new_gpu_sampler_mps` | 155.3 | 126.5 | 28.1 | 207.4 | ~flat (~−3% wall) |
| `s3_mps_sdpa` | 157.2 | 128.8 | 27.7 | 205.4 | MPS SDPA wins vs Metal FA |
| `cb_10` (cmd-split) | 154.2 | 123.6 | 27.8 | 203.5 | mild encode overlap |
| `t0_nax0` / NAX on | ~156–162 | — | — | ~208–214 | **no 2–3×** |
| `s4_sg32_metal` | **403.9** | 0.06 | 403.9 | **454** | **regress** — tiled Metal wait-bound |

**Takeaway:** Ultra defaults keep MPSGraph BF16 + GPU sampler + mild cmd-split. NAX/SG32/Metal flash SDPA do not unlock 2–3× on this smoke; bottleneck is DiT encode FLOP.

## 2. FLOP-reduction curve (same geometry)

| preset / knobs | steps | reuse | TR | denoise (s) | vs baseline | wall (s) |
|:---|---:|---:|:---:|---:|---:|---:|
| `ns_480p_15s_hq_smoke` **baseline** | 8 | 1 | no | **155.4** | 1.00× | 204.5 |
| `ns_smoke_r2` | 8 | **2** | no | **96.5** | **1.61×** | 150.2 |
| `ns_smoke_tr` | 8 | 1 | **yes** | 99.3 | 1.56× | 150.7 |
| `ns_smoke_s6` | **6** | 1 | no | 115.8 | 1.34× | 167.6 |
| `ns_smoke_s4` | **4** | 1 | no | 77.5 | 2.00× | 128.9 |
| `ns_smoke_l45` / `l40` | 8 | 1 | no | 139 / 124 | 1.12–1.25× | 190 / 171 |
| `ns_smoke_tr_s6_l45` combo | 6 | 1 | yes | 69.0 | 2.25× | 121.6 |

Artifacts: `*-flop_*.bench.json` in this folder.

## 3. Eye-check (科教) — 2026-09-29

| clip | knobs | denoise | wall | eye |
|:---|:---|---:|---:|:---|
| baseline smoke | S8 L50 r1 | 155.4 | 204.5 | **gold** |
| r2 only (`flop_r2`) | S8 r2 | 96.5 | 150.2 | **accepted** |
| TR (`*-smoke_fast-eye` had TR+r2) | r2+TR S8 | 61.7 | 109.6 | **rejected** — diagram ghosting |
| **r2+S6 no TR** (`…smoke_fast_s6-eye`) | **S6 r2** | **77.6** | **121.4** | **accepted delivery** |

TR alone on the FLOP curve was also rejected for the same ghosting reason on 科教 diagrams. Combo with TR not used for delivery.

## 4. Locked delivery defaults

| role | preset | knobs |
|:---|:---|:---|
| gold / QC | `ns_480p_15s_hq` (+ `_smoke`) | S8 L50 r1, no TR |
| **效率成片** | **`ns_480p_15s_hq_fast`** | **S6 L50 r2, no TR** |
| aliases | `hq_r2`, `hq_fast_s6` | r2-only / same as fast |

```bash
h3ctl run --preset ns_480p_15s_hq_fast \
  --prompt-file examples/ns_480p_15s.prompt.txt \
  -o out/ns_fast.mp4 --profile --no-ssd-streaming
```

Smoke speedup vs gold: denoise **~2.0×** (77.6 / 155.4), wall **~1.7×** (121 / 204).  
Full **362f** still far from ≤60s wall; next wins need still-cheaper DiT work or warm-amortized load, not more Metal matmul tuning.

## 5. Reproduce

```bash
./scripts/bench_flop_curve.sh          # FLOP knobs table
./scripts/bench_ns_quality.sh smoke    # engine A/B baseline
LABEL=eye ./scripts/bench_ns_quality.sh smoke   # with LABEL + preset override as needed
```
