#!/bin/bash
cd /Users/zzz858aaa/h3-ops || exit 1
export PYTHONPATH=src
trap '' HUP
echo "==== gothic_cathedral_duel film_hero $(date -Iseconds) ====" | tee -a out/gothic_cathedral_duel.terminal.log
touch "$HOME/.mlx-serve/gpu-sched/HOLD_NO_PREEMPT"
python3 -u -m h3_ops doctor || true
caffeinate -dims python3 -u -m h3_ops run --force --preset film_hero \
  --prompt-file examples/gothic_cathedral_duel.prompt.txt \
  -o out/gothic_cathedral_duel.mp4 --profile
ec=$?
echo "DONE_RC=$ec $(date -Iseconds)" | tee -a out/gothic_cathedral_duel.terminal.log
ls -lh out/gothic_cathedral_duel.mp4 2>/dev/null | tee -a out/gothic_cathedral_duel.terminal.log
echo "==== finished $(date -Iseconds) ===="
sleep 3
exit "$ec"
