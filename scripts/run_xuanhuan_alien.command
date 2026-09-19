#!/bin/bash
cd /Users/zzz858aaa/h3-ops || exit 1
export PYTHONPATH=src
trap '' HUP
echo "==== xuanhuan_alien film_master $(date -Iseconds) ====" | tee -a out/xuanhuan_alien.terminal.log
# Factory LTX must not reclaim mid-render
touch "$HOME/.mlx-serve/gpu-sched/HOLD_NO_PREEMPT"
python3 -u -m h3_ops doctor || true
caffeinate -dims python3 -u -m h3_ops run --force --preset film_master \
  --prompt-file examples/xuanhuan_alien.prompt.txt \
  -o out/xuanhuan_alien.mp4 --profile
ec=$?
echo "DONE_RC=$ec $(date -Iseconds)" | tee -a out/xuanhuan_alien.terminal.log
ls -lh out/xuanhuan_alien.mp4 2>/dev/null | tee -a out/xuanhuan_alien.terminal.log
echo "==== finished $(date -Iseconds) ===="
# keep window open briefly
sleep 3
exit "$ec"
