#!/bin/bash
cd /Users/zzz858aaa/h3-ops || exit 1
export PYTHONPATH=src
trap '' HUP
LOG=out/xuanhuan_alien_hq.queue.log
echo "==== QUEUE restart $(date -Iseconds) ====" >>"$LOG"

while true; do
  if [[ -f out/gothic_cathedral_duel_v2.mp4 ]]; then
    # gothic mp4 written — wait until its h3/python gone
    if ! pgrep -f 'out/gothic_cathedral_duel_v2.mp4' >/dev/null 2>&1 \
       && ! pgrep -f 'gothic_cathedral_duel_v2.prompt' >/dev/null 2>&1; then
      sleep 5
      if ! pgrep -f 'gothic_cathedral_duel_v2' >/dev/null 2>&1; then
        echo "$(date +%H:%M:%S) gothic_v2 finished — start alien HQ" >>"$LOG"
        break
      fi
    fi
  fi
  last=$(tail -c 240 out/gothic_cathedral_duel_v2.mp4.log 2>/dev/null | tr '\r' '\n' | grep denoise | tail -1)
  echo "$(date +%H:%M:%S) wait gothic | ${last:-…}" >>"$LOG"
  sleep 45
done

# clear other h3
for _ in $(seq 1 40); do
  pgrep -f '/src/h3.c/h3|./h3 -d' >/dev/null 2>&1 || break
  sleep 15
done

touch "$HOME/.mlx-serve/gpu-sched/HOLD_NO_PREEMPT"
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-serve.plist" 2>/dev/null || true
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-gpu-gate.plist" 2>/dev/null || true
pkill -9 -f 'mlx-serve serve' 2>/dev/null || true
pkill -9 -f 'mlx_gpu_gate' 2>/dev/null || true

echo "==== alien HQ start $(date -Iseconds) ====" >>"$LOG"
caffeinate -dims python3 -u -m h3_ops run --force --preset film_hero_clean \
  --prompt-file examples/xuanhuan_alien_hq.prompt.txt \
  -o out/xuanhuan_alien_hq.mp4 --profile --seed 20260919 >>"$LOG" 2>&1
ec=$?
echo "DONE_RC=$ec $(date -Iseconds)" >>"$LOG"
ls -lh out/xuanhuan_alien_hq.mp4 >>"$LOG" 2>&1 || true
rm -f "$HOME/.mlx-serve/gpu-sched/HOLD_NO_PREEMPT"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-serve.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-gpu-gate.plist" 2>/dev/null || true
exit $ec
