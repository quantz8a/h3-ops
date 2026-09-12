# h3-ops

Companion for [antirez/h3.c](https://github.com/antirez/h3.c): **ContextDoc → Base (`h3`) → honest HD**, without forking Metal / DiT.

| Official module | Open? | Local stand-in |
|:---|:---|:---|
| H3-Context-IR | API only | `cir` — compile / validate / revise / emit |
| H3-Base | weights open | `ops` — doctor / gate / run / batch |
| H3-Regenerate-2K | API only | `hd` — native → upscale → optional cloud 2K |

**Truth artifact:** `ContextDoc` JSON ([schema](docs/schemas/context_doc.v1.json)). MP4 is a projection of doc + seed + preset.

**Status:** Phase 0–4 MVP — ops + cir + hd. Phase 5 = cloud adapters. See [DESIGN.md](DESIGN.md).

## Requirements

| Need | Notes |
|:---|:---|
| Apple Silicon | `arm64` |
| Built `h3.c` | spawn **must** `chdir` to the tree that has `h3_shaders.metal` |
| MiniMax-H3 BF16 | local path with `FL2VA/` — not shipped here |
| `ffmpeg` / `ffprobe` | stitch / probe |
| Optional LLM | OpenAI-compatible for `cir.compile` (never parallel with Base) |
| Optional API key | only for cloud CIR / Regenerate-2K adapters |

## Planned flow

```bash
export PATH="/Users/zzz858aaa/h3-ops/scripts:$PATH"   # or: PYTHONPATH=src python3 -m h3_ops
h3ctl doctor
h3ctl run --preset smoke --prompt-file examples/smoke.prompt.txt -o out/smoke.mp4
# later:
h3ctl cir compile --brief "剑气削叶" -o shot.cir.json
h3ctl cir validate shot.cir.json
h3ctl run --preset preview --doc shot.cir.json -o out/preview.mp4
h3ctl cir revise shot.cir.json --notes "剑气线不可读" -o shot.cir.json
h3ctl hd deliver --doc shot.cir.json --base out/preview.mp4 \
  --target upscale_1080 -o out/deliver_1080.mp4
```

Working now: `doctor`, `presets`, `lock`, `run`, `cir *`, `hd ladder|deliver|stitch`.  
Phase 5: optional cloud CIR / Regenerate-2K adapters.

LLM (optional):
```bash
export H3_OPS_LLM_BASE=http://127.0.0.1:11236/v1
export H3_OPS_LLM_MODEL=local
h3ctl cir compile --brief "..." --backend llm -o shot.cir.json
h3ctl cir revise shot.cir.json --notes "剑气线不可读" --backend llm
# never run LLM parallel with h3ctl run on the same GPU
```

## Presets & wall-clock anchors

Measured on **M3 Ultra 96GB** with `--ssd-streaming` (order of magnitude):

| preset | canvas | frames | steps | ~wall | use |
|:---|:---|:---:|:---:|:---|:---|
| `smoke` | 512² | 22 | 4 | ~66s (h3ctl) | path check |
| `draw` | 480×832 | 56 | 4–8 | ~2 min | vertical card pulls |
| `preview` | 480×832 | 124 | 8 | ~5 min | ≥5s review |
| `deliver` | 480×832 | 124 | 20–30 | 7–14 min | hero; gate must be green |
| `unsafe_hq` | ≥576×1024 | 124 | ≥20 | high | jetsam risk if mlx alive |

Field failures already seen: wrong cwd (no shaders), `mlx-serve` eating unified memory, free pages → 0 looking like a hang.

## Config (planned env)

| Env | Default idea |
|:---|:---|
| `H3_OPS_H3C_SRC` | path to h3.c checkout |
| `H3_OPS_MODEL_DIR` | MiniMax-H3 root (`FL2VA/`) |
| `H3_OPS_LOCK` | `~/.cache/h3-ops/gpu.lock` |
| `H3_OPS_LLM_BASE` | OpenAI-compatible base URL (cir only) |
| `H3_OPS_LLM_MODEL` | model id (default `local`) |
| `MINIMAX_API_KEY` | cloud adapters only |

## Non-goals

- Reimplement DiT or redistribute weights  
- Vendor drama / looksheet business  
- Label local upscale as Regenerate-2K  

## Docs & example

- Design SoT: [DESIGN.md](DESIGN.md)  
- Schema: [docs/schemas/context_doc.v1.json](docs/schemas/context_doc.v1.json)  
- Example doc: [examples/leafcut.cir.json](examples/leafcut.cir.json)  

## License

MIT (same spirit as `h3.c`). Model cards apply to weights.
