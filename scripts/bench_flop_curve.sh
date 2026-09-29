#!/usr/bin/env bash
# FLOP-reduction speed curve on native smoke geometry (no render-down).
# Usage: ./scripts/bench_flop_curve.sh
# Writes out/bench/* and a summary table at the end.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export H3_OPS_H3C_SRC="${H3_OPS_H3C_SRC:-$HOME/llm-lab/src/h3.c}"
export H3_OPS_MODEL_DIR="${H3_OPS_MODEL_DIR:-$HOME/llm-lab/src/minimax-h3-mlx-rebuild/official}"
export H3_NAX="${H3_NAX:-0}"
export H3_FORCE_MPS_LINEAR="${H3_FORCE_MPS_LINEAR:-1}"
export H3_METAL_SDPA="${H3_METAL_SDPA:-0}"
export H3_DIT_COMMAND_BLOCKS="${H3_DIT_COMMAND_BLOCKS:-10}"

PROMPT="$ROOT/examples/ns_480p_15s.prompt.txt"
OUT_DIR="$ROOT/out/bench"
mkdir -p "$OUT_DIR"
LOCK="${H3_OPS_LOCK:-$HOME/.cache/h3-ops/gpu.lock}"
rm -f "$LOCK" "$HOME/.mlx-serve/gpu.lock.h3_want" 2>/dev/null || true

wait_gpu() {
  while true; do
    if pgrep -f '(^|/)h3( |$)(.* )?-d ' >/dev/null 2>&1; then
      sleep 10; continue
    fi
    if [[ -f "$LOCK" ]]; then
      pid="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('pid',''))" "$LOCK" 2>/dev/null || true)"
      if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
        sleep 10; continue
      fi
    fi
    break
  done
}

run_one() {
  local preset="$1" label="$2"
  local stamp base out
  stamp="$(date +%Y%m%dT%H%M%S)"
  base="$OUT_DIR/${stamp}-${preset}-${label}"
  out="${base}.mp4"
  echo "======== ${label} preset=${preset} ========"
  wait_gpu
  echo "[bench] → $out"
  "$ROOT/scripts/h3ctl" run \
    --preset "$preset" \
    --prompt-file "$PROMPT" \
    -o "$out" \
    --profile \
    --no-ssd-streaming \
    --force || echo "[bench] FAILED $label exit=$?"
  python3 - <<PY
import json, re
from pathlib import Path
from h3_ops.ops.report import parse_profile_log
base = Path("$base")
log = Path(str(base) + ".mp4.log")
report = Path(str(base) + ".mp4.report.json")
text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
phases = parse_profile_log(text)
detail = {}
for m in re.finditer(
    r"h3 profile:\s+(\S+(?:\s+\S+){0,3}?)\s+wall=\s*([0-9.]+)s\s+encode=\s*([0-9.]+)s\s+wait=\s*([0-9.]+)s",
    text,
):
    key = re.sub(r"[^a-z0-9]+", "_", m.group(1).strip().lower()).strip("_")
    detail[key] = {"wall_s": float(m.group(2)), "encode_s": float(m.group(3)), "wait_s": float(m.group(4))}
job = json.loads(report.read_text()) if report.is_file() else {}
out = {
    "label": "$label",
    "preset": "$preset",
    "stamp": "$stamp",
    "wall_s": job.get("wall_s"),
    "phases": phases,
    "profile_detail": detail,
    "output_mp4": str(base) + ".mp4",
    "log": str(log),
}
path = Path(str(base) + ".bench.json")
path.write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({"label": out["label"], "wall_s": out["wall_s"], "denoise_s": phases.get("denoise_s")}, indent=2))
print(f"[bench] wrote {path}")
PY
}

# Baseline first (hq_smoke knobs), then single-knob, then combo.
run_one ns_480p_15s_hq_smoke flop_baseline
run_one ns_smoke_tr           flop_tr
run_one ns_smoke_s6           flop_s6
run_one ns_smoke_s4           flop_s4
run_one ns_smoke_l45          flop_l45
run_one ns_smoke_l40          flop_l40
run_one ns_smoke_r2           flop_r2
run_one ns_smoke_tr_s6_l45    flop_combo_2x

echo '======== FLOP CURVE SUMMARY ========'
python3 - <<'PY'
import json, glob
rows = []
for f in sorted(glob.glob("/Users/zzz858aaa/h3-ops/out/bench/*-flop_*.bench.json")):
    d = json.load(open(f))
    tot = (d.get("profile_detail") or {}).get("h3_dit_total") or {}
    rows.append((d["label"], d.get("preset"), d.get("wall_s"), (d.get("phases") or {}).get("denoise_s"), tot.get("encode_s"), tot.get("wait_s"), d.get("output_mp4")))
# Keep latest per label
latest = {}
for r in rows:
    latest[r[0]] = r
print(f"{'label':22} {'preset':22} {'wall':>7} {'denoise':>8} {'enc':>7} {'wait':>7}")
base_den = None
for label in ["flop_baseline","flop_tr","flop_s6","flop_s4","flop_l45","flop_l40","flop_r2","flop_combo_2x"]:
    if label not in latest:
        print(f"{label:22} MISSING")
        continue
    _, preset, wall, den, enc, wait, mp4 = latest[label]
    if label == "flop_baseline" and den:
        base_den = den
    speed = f"{base_den/den:.2f}x" if base_den and den else ""
    print(f"{label:22} {preset:22} {wall or 0:7.1f} {den or 0:8.1f} {enc or 0:7.1f} {wait or 0:7.1f}  {speed}")
print("\nMP4s for eye-check:")
for label in ["flop_baseline","flop_tr","flop_s6","flop_s4","flop_l45","flop_l40","flop_r2","flop_combo_2x"]:
    if label in latest:
        print(f"  {label}: {latest[label][6]}")
PY
echo '======== FLOP CURVE DONE ========'
