#!/bin/bash
# Fetch the shipped AgentDojo traces (sparse checkout, ~125 MB) used for the anchor and the replay.
set -euo pipefail
DEST=${PW_TRACES_ROOT:-/mnt/hdd2/Abhijit/policy-writer-data/agentdojo-upstream}
COMMIT=089ed468cf3ed0322acc66b0211f26d9d90dbf60
if [ ! -d "$DEST/.git" ]; then git clone --filter=blob:none --no-checkout https://github.com/ethz-spylab/agentdojo.git "$DEST"; fi
cd "$DEST"
git sparse-checkout set --no-cone 'runs/gpt-4o-2024-05-13/*' 'runs/meta-llama_Llama-3.3-70B-Instruct/*' 'docs/results-table.html'
git checkout "$COMMIT"
echo "traces at $DEST (agentdojo @ $COMMIT)"
