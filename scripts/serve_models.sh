#!/bin/bash
# Launch one OpenAI-compatible vLLM server per policy model (2 GPUs each, data parallel).
# Usage: scripts/serve_models.sh            (all four)
#        scripts/serve_models.sh qwen3-30b  (one)
# Env: VLLM_BIN (vllm executable), DATA_DIR (logs + HF cache root).
set -euo pipefail
VLLM_BIN=${VLLM_BIN:-/mnt/hdd2/Abhijit/envs/gencp/bin/vllm}
DATA_DIR=${DATA_DIR:-/mnt/hdd2/Abhijit/projects/policy-writer}
export HF_HOME=${HF_HOME:-$DATA_DIR/hf_cache}
mkdir -p "$DATA_DIR/logs"

# name | served model name | weights (HF id or local path) | GPUs | port | extra args
MODELS=(
  "qwen3-30b|Qwen/Qwen3-30B-A3B-Instruct-2507|Qwen/Qwen3-30B-A3B-Instruct-2507|0,1|8001|"
  "mistral-24b|mistralai/Mistral-Small-3.2-24B-Instruct-2506|mistralai/Mistral-Small-3.2-24B-Instruct-2506|2,3|8002|--tokenizer-mode mistral"
  "qwen3.5-9b|Qwen/Qwen3.5-9B|/mnt/nvme2/timeagent/hf_cache/models--Qwen--Qwen3.5-9B/snapshots/c202236235762e1c871ad0ccb60c8ee5ba337b9a|4,5|8003|--default-chat-template-kwargs {\"enable_thinking\":false}"
  "qwen2.5-7b|Qwen/Qwen2.5-7B-Instruct|/mnt/nvme2/timeagent/hf_cache/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28|6,7|8004|"
)

for entry in "${MODELS[@]}"; do
  IFS='|' read -r name served weights gpus port extra <<< "$entry"
  if [[ $# -gt 0 && "$1" != "$name" ]]; then continue; fi
  log="$DATA_DIR/logs/vllm_$name.log"
  echo "[serve] $name ($served) on GPUs $gpus port $port -> $log"
  # shellcheck disable=SC2086
  CUDA_VISIBLE_DEVICES=$gpus nohup "$VLLM_BIN" serve "$weights" --served-model-name "$served" \
    --port "$port" --data-parallel-size 2 --max-model-len 32768 --gpu-memory-utilization 0.90 \
    --seed 0 $extra > "$log" 2>&1 &
done
