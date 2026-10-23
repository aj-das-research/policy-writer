"""Paths and the policy-model registry. Everything else reads from here."""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PW_DATA_DIR", "/mnt/nvme2/abhijit/projects/policy-writer"))
TRACES_ROOT = Path(os.environ.get("PW_TRACES_ROOT", "/mnt/hdd2/Abhijit/policy-writer-data/agentdojo-upstream"))
RESULTS = REPO / "results"
CACHE_PATH = DATA_DIR / "policy_cache.sqlite"

BENCHMARK_VERSION = "v1.2"  # Progent's AgentDojo fork ships suites up to v1.2
SUITES = ["banking", "slack", "travel", "workspace"]
ATTACK = "important_instructions"

# Shipped AgentDojo traces. `replay` is the v1.2.1 undefended run we replay; `anchor` is the v1 GPT-4o run
# whose published numbers we reproduce exactly.
REPLAY_TRACES = "meta-llama_Llama-3.3-70B-Instruct"
ANCHOR_TRACES = "gpt-4o-2024-05-13"
# AgentDojo docs/results-table.html, row: openai / gpt-4o-2024-05-13 / None / important_instructions
ANCHOR_PUBLISHED = {"utility": 69.07, "utility_under_attack": 50.08, "targeted_asr": 47.69}

# Output cap for locally served policy models (upstream sets none for OpenAI-compatible endpoints). Greedy
# replies shorter than this are unaffected; no GPT-4o/Mistral/Qwen2.5 reply observed exceeded ~1.1k tokens.
LOCAL_MAX_TOKENS = 4096

# key -> (served model name, base_url or None for the OpenAI API). Ports match scripts/serve_models.sh.
POLICY_MODELS = {
    "gpt-4o": ("gpt-4o-2024-08-06", None),
    "qwen3-30b": ("Qwen/Qwen3-30B-A3B-Instruct-2507", "http://127.0.0.1:8001/v1"),
    "mistral-24b": ("mistralai/Mistral-Small-3.2-24B-Instruct-2506", "http://127.0.0.1:8002/v1"),
    "qwen3.5-9b": ("Qwen/Qwen3.5-9B", "http://127.0.0.1:8003/v1"),
    "qwen2.5-7b": ("Qwen/Qwen2.5-7B-Instruct", "http://127.0.0.1:8004/v1"),
}


def trace_dir(run_name: str) -> Path:
    d = TRACES_ROOT / "runs" / run_name
    if not d.is_dir():
        raise FileNotFoundError(f"trace dir {d} missing; run scripts/fetch_traces.sh")
    return d
