#!/usr/bin/env bash
# Wait for GPU lock, then cold-profile the north-star probe (864·rw288·362).
# Warm path (preferred): after this, run `h3ctl warm --preset ns_480p_15s`
# and paste the prompt twice / !again — second wall is the real score.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export H3_OPS_H3C_SRC="${H3_OPS_H3C_SRC:-$HOME/llm-lab/src/h3.c}"

OUT="${1:-$ROOT/out/ns_480p_15s_cold.mp4}"
LOCK="${H3_OPS_LOCK:-$HOME/.cache/h3-ops/gpu.lock}"
mkdir -p "$(dirname "$OUT")"

echo "[probe] waiting for free GPU (no live h3 / empty lock)…"
while true; do
  if pgrep -f '/src/h3.c/h3|./h3 -d' >/dev/null 2>&1; then
    sleep 15
    continue
  fi
  if [[ -f "$LOCK" ]]; then
    # stale lock if holder pid is dead
    pid="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('pid',''))" "$LOCK" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      sleep 15
      continue
    fi
  fi
  break
done

echo "[probe] cold one-shot → $OUT"
exec "$ROOT/scripts/h3ctl" run \
  --preset ns_480p_15s \
  --prompt-file "$ROOT/examples/ns_480p_15s.prompt.txt" \
  -o "$OUT" \
  --profile \
  --no-ssd-streaming \
  --force
