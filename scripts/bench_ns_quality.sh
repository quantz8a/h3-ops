#!/usr/bin/env bash
# Quality-preserving A/B bench for north-star (native 864×480, no render-down).
# Usage:
#   ./scripts/bench_ns_quality.sh                  # smoke 56f baseline
#   ./scripts/bench_ns_quality.sh smoke            # same
#   ./scripts/bench_ns_quality.sh hq               # full 362f (expensive)
#   LABEL=gpu_samp H3_GPU_SAMPLER=1 H3_DIT_COMMAND_BLOCKS=30 \
#     ./scripts/bench_ns_quality.sh smoke
#
# Writes out/bench/<stamp>-<preset>-<label>.{log,json,mp4}
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export H3_OPS_H3C_SRC="${H3_OPS_H3C_SRC:-$HOME/llm-lab/src/h3.c}"

MODE="${1:-smoke}"
case "$MODE" in
  smoke) PRESET=ns_480p_15s_hq_smoke ;;
  hq|full) PRESET=ns_480p_15s_hq ;;
  *) echo "usage: $0 [smoke|hq]" >&2; exit 2 ;;
esac

LABEL="${LABEL:-baseline}"
STAMP="$(date +%Y%m%dT%H%M%S)"
OUT_DIR="$ROOT/out/bench"
mkdir -p "$OUT_DIR"
BASE="$OUT_DIR/${STAMP}-${PRESET}-${LABEL}"
OUT_MP4="${BASE}.mp4"
PROMPT="$ROOT/examples/ns_480p_15s.prompt.txt"

LOCK="${H3_OPS_LOCK:-$HOME/.cache/h3-ops/gpu.lock}"
echo "[bench] preset=$PRESET label=$LABEL"
echo "[bench] env: H3_GPU_SAMPLER=${H3_GPU_SAMPLER:-} H3_CPU_SAMPLER=${H3_CPU_SAMPLER:-} H3_DIT_COMMAND_BLOCKS=${H3_DIT_COMMAND_BLOCKS:-} H3_NAX=${H3_NAX:-}"

echo "[bench] waiting for free GPU…"
while true; do
  # Match an actual h3 argv (`h3 -d`), not unrelated shells that merely
  # mention the binary path in their command text.
  if pgrep -f '(^|/)h3( |$)(.* )?-d ' >/dev/null 2>&1; then
    sleep 10
    continue
  fi
  if [[ -f "$LOCK" ]]; then
    pid="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('pid',''))" "$LOCK" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      sleep 10
      continue
    fi
  fi
  break
done

echo "[bench] cold run → $OUT_MP4"
"$ROOT/scripts/h3ctl" run \
  --preset "$PRESET" \
  --prompt-file "$PROMPT" \
  -o "$OUT_MP4" \
  --profile \
  --no-ssd-streaming \
  --force

# Parse profile into a compact JSON next to the report.
python3 - <<PY
import json, re
from pathlib import Path
from h3_ops.ops.report import parse_profile_log

base = Path("$BASE")
log = Path(str(base) + ".mp4.log")
report = Path(str(base) + ".mp4.report.json")
text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
phases = parse_profile_log(text)

# Fine-grained: h3 profile lines with wall=/encode=/wait=
detail = {}
for m in re.finditer(
    r"h3 profile:\s+(\S+(?:\s+\S+){0,3}?)\s+wall=\s*([0-9.]+)s\s+encode=\s*([0-9.]+)s\s+wait=\s*([0-9.]+)s",
    text,
):
    label = re.sub(r"[^a-z0-9]+", "_", m.group(1).strip().lower()).strip("_")
    detail[label] = {
        "wall_s": float(m.group(2)),
        "encode_s": float(m.group(3)),
        "wait_s": float(m.group(4)),
    }
# DiT sub-phase marks (QKV/SDPA/MLP) if present
for m in re.finditer(
    r"h3 profile:\s+DiT\s+(qkv|sdpa|attn_out|mlp)\s+wall=\s*([0-9.]+)s",
    text,
    re.I,
):
    phases[f"dit_{m.group(1).lower()}_s"] = float(m.group(2))

job = {}
if report.is_file():
    job = json.loads(report.read_text(encoding="utf-8"))

out = {
    "label": "$LABEL",
    "preset": "$PRESET",
    "stamp": "$STAMP",
    "wall_s": job.get("wall_s"),
    "phases": phases,
    "profile_detail": detail,
    "env": {
        "H3_GPU_SAMPLER": __import__("os").environ.get("H3_GPU_SAMPLER"),
        "H3_CPU_SAMPLER": __import__("os").environ.get("H3_CPU_SAMPLER"),
        "H3_DIT_COMMAND_BLOCKS": __import__("os").environ.get("H3_DIT_COMMAND_BLOCKS"),
        "H3_NAX": __import__("os").environ.get("H3_NAX"),
        "H3_SDPA_MAX_QUERY_ROWS": __import__("os").environ.get("H3_SDPA_MAX_QUERY_ROWS"),
    },
    "output_mp4": str(base) + ".mp4",
    "log": str(log),
}
bench_path = Path(str(base) + ".bench.json")
bench_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
print(f"[bench] wrote {bench_path}")
PY
