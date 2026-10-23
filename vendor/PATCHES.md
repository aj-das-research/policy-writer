# Local patches to vendored Progent (upstream sunblaze-ucb/progent @ 5be7b63)

All patches are marked `[policy-writer patch]` in the source. Policy logic and prompts are unchanged.

1. `secagent/tool.py` — `SECAGENT_POLICY_BASE_URL`: route policy requests to any OpenAI-compatible
   local server (vLLM). Upstream routes only `meta-llama/` and `Qwen/` names to a fixed localhost:8000.
   Models served this way get upstream's open-model output-format hint (the same branch as Llama/Qwen).
2. `secagent/tool.py` + `secagent/policy_cache.py` — `api_request` goes through an SQLite cache keyed by
   sha256(model, system prompt, user prompt, temperature), storing token usage. Only successful responses are
   cached; exceptions still reach upstream's retry loop.
3. `secagent/tool.py` — `audit_counters`: counts update-step outcomes (decide yes/no, declined — extract_json returns None for a reply starting with "No" —, rejected by
   narrowing-only, applied, error ignored). Instrumentation only.
4. `secagent/tool.py` — local-endpoint calls send `max_tokens=$SECAGENT_POLICY_MAX_TOKENS` (4096, set by
   `pwaudit/config.py`) and print a warning on truncation. Upstream sets no cap for OpenAI-compatible endpoints;
   Qwen3.5-9B produced runaway generations without one. Truncated replies go through Progent's own retry loop.
