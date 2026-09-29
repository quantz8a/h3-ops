#!/bin/bash
# Double-click / Terminal one-shot: topic → local h3.c video (Pixelle-style).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src
trap '' HUP

echo "==== h3-opt make (h3.c one-click) ===="
if [[ $# -ge 1 ]]; then
  TOPIC="$*"
else
  read -r -p "主题/剧本（回车用示例）: " TOPIC
  TOPIC=${TOPIC:-"破败哥特大教堂内，白甲女战士持蓝光刃与异形对决并绝杀"}
fi

QUALITY=${H3_MAKE_QUALITY:-hq}
OUT=${H3_MAKE_OUT:-}

ARGS=(make "$TOPIC" --quality "$QUALITY" --open --force)
if [[ -n "$OUT" ]]; then
  ARGS+=(-o "$OUT")
fi

python3 -u -m h3_ops doctor || true
python3 -u -m h3_ops "${ARGS[@]}"
ec=$?
echo "DONE_RC=$ec"
exit "$ec"
