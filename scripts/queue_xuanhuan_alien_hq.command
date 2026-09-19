#!/bin/bash
# Wait for gothic_cathedral_duel_v2 to finish, then render xuanhuan_alien HQ.
set -uo pipefail
cd /Users/zzz858aaa/h3-ops || exit 1
export PYTHONPATH=src
trap '' HUP
LOG=out/xuanhuan_alien_hq.queue.log
mkdir -p out
echo "==== QUEUE start $(date -Iseconds) — wait gothic_v2 then alien HQ ====" | tee -a "$LOG"

wait_gothic() {
  local i=0
  while true; do
    i=$((i + 1))
    # Done when mp4 exists and no gothic h3_ops / h3 still running
    if [[ -f out/gothic_cathedral_duel_v2.mp4 ]] \
      && ! pgrep -f 'gothic_cathedral_duel_v2|film_hero_clean.*gothic' >/dev/null 2>&1 \
      && ! pgrep -f './h3 -d.*Gothic cathedral' >/dev/null 2>&1; then
      # also wait for terminal DONE if present
      if grep -q 'DONE_RC=' out/gothic_cathedral_duel_v2.terminal.log 2>/dev/null; then
        echo "$(date +%H:%M:%S) gothic_v2 done" | tee -a "$LOG"
        return 0
      fi
      # mp4 exists and no process — accept after short settle
      sleep 8
      if ! pgrep -f 'h3_ops run.*gothic|./h3 -d.*Gothic' >/dev/null 2>&1; then
        echo "$(date +%H:%M:%S) gothic_v2 mp4 ready (no DONE line yet)" | tee -a "$LOG"
        return 0
      fi
    fi
    # Still waiting — gothic alive
    last=$(tail -c 200 out/gothic_cathedral_duel_v2.mp4.log 2>/dev/null | tr '\r' '\n' | grep -E 'denoise|VAE|FFmpeg|wrote' | tail -1)
    if (( i % 6 == 1 )); then
      echo "$(date +%H:%M:%S) waiting gothic_v2 | ${last:-…}" | tee -a "$LOG"
    fi
    # Safety: if gothic process died without mp4 for >5 min after denoise start, continue anyway? No — keep waiting up to 3h
    if (( i > 360 )); then
      echo "TIMEOUT waiting gothic_v2 $(date -Iseconds)" | tee -a "$LOG"
      return 1
    fi
    sleep 30
  done
}

wait_gothic || exit 1

# Ensure GPU free of other h3
for _ in $(seq 1 60); do
  if pgrep -f '/src/h3.c/h3|./h3 -d' >/dev/null 2>&1; then
    echo "$(date +%H:%M:%S) extra h3 still up — wait" | tee -a "$LOG"
    sleep 20
  else
    break
  fi
done

touch "$HOME/.mlx-serve/gpu-sched/HOLD_NO_PREEMPT"
# Keep mlx off for heavy Base
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-serve.plist" 2>/dev/null || true
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-gpu-gate.plist" 2>/dev/null || true
pkill -9 -f 'mlx-serve serve' 2>/dev/null || true
pkill -9 -f 'mlx_gpu_gate' 2>/dev/null || true
sleep 2

echo "==== xuanhuan_alien HQ film_hero_clean $(date -Iseconds) ====" | tee -a "$LOG"
python3 -u -m h3_ops doctor 2>&1 | tee -a "$LOG" || true
caffeinate -dims python3 -u -m h3_ops run --force --preset film_hero_clean \
  --prompt-file examples/xuanhuan_alien_hq.prompt.txt \
  -o out/xuanhuan_alien_hq.mp4 --profile --seed 20260919
ec=$?
echo "DONE_RC=$ec $(date -Iseconds)" | tee -a "$LOG"
ls -lh out/xuanhuan_alien_hq.mp4 2>/dev/null | tee -a "$LOG" || true
rm -f "$HOME/.mlx-serve/gpu-sched/HOLD_NO_PREEMPT"
# Restore mlx agents
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-serve.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.xuanji.mlx-gpu-gate.plist" 2>/dev/null || true
exit "$ec"
