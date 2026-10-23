#!/bin/bash
# Run every experiment for one policy model: static check, then replay (default and narrow_only).
# Suites run in parallel; each suite's steps run in order. Logs: $PW_DATA_DIR/logs/run_<model>_<suite>.log
# Usage: scripts/run_model.sh <model-key> [workers-per-suite] [suites...]
set -euo pipefail
MODEL=$1; WORKERS=${2:-16}; shift $(( $# >= 2 ? 2 : 1 ))
SUITES=${*:-"banking slack travel workspace"}
PY=${PY:-/mnt/hdd2/Abhijit/projects/policy-writer/venv/bin/python}
LOGS=${PW_DATA_DIR:-/mnt/nvme2/abhijit/projects/policy-writer}/logs
mkdir -p "$LOGS"
cd "$(dirname "$0")/.."
for s in $SUITES; do
  (
    set -e
    $PY -m pwaudit.static_check --suite "$s" --model "$MODEL" --workers "$WORKERS"
    $PY -m pwaudit.replay --suite "$s" --model "$MODEL" --mode default --workers "$WORKERS"
    $PY -m pwaudit.replay --suite "$s" --model "$MODEL" --mode narrow_only --workers "$WORKERS"
    echo "[run_model] DONE $MODEL $s"
  ) > "$LOGS/run_${MODEL}_${s}.log" 2>&1 || echo "[run_model] FAILED $MODEL $s (see $LOGS/run_${MODEL}_${s}.log)" &
done
wait
echo "[run_model] finished $MODEL"
