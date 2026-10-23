# Who guards the policy writer?

An audit of the LLM **policy writer** in [Progent](https://arxiv.org/abs/2504.11703) (Shi et al., 2025) on
[AgentDojo](https://github.com/ethz-spylab/agentdojo) (Debenedetti et al., 2024).

Progent has an LLM turn the user's query into a deterministic JSON-schema policy over tool calls, then *updates*
that policy from tool outputs during the run. Progent reports that this cuts GPT-4o's ASR from 39.9% to 1.0% at
similar utility. That result assumes the policy writer is reliable and cannot itself be injected. Yet in the
released AgentDojo integration, updates are computed from (possibly injected) tool outputs and applied without
confirmation, and the narrowing-only check is off by default (`SECAGENT_ONLY_ALLOW_NARROW` is commented out in
`run.sh`; `tool_execution.py` calls the update with `manual_check=False`).

We measure, with Progent's own code on AgentDojo suite v1.2:

| Experiment | What is checked | Metrics |
|---|---|---|
| **Static check** | Each initial policy against the ground-truth calls of its user task and of every injection task | false blocks, attacks blocked |
| **Update replay** | The tool outputs of shipped AgentDojo traces, fed through Progent's update step | attacker values entering the policy, attack calls newly allowed, replay ASR |
| **Ablations** | Policy model; narrowing-only updates on/off | all of the above |
| **Controls** | Allow-all, deny-all, and Progent's hand-written always-allowed list | sanity bounds |

## Status

| Step | State |
|---|---|
| Anchor: AgentDojo GPT-4o published numbers recomputed from shipped traces | ✅ exact (69.07 / 50.08 / 47.69) |
| Static ground-truth checker + controls | ✅ controls verified on banking |
| Policy-model servers (vLLM) | 🔄 loading |
| Static check, all models × suites | ⏳ |
| Update replay (narrow-only off / on) | ⏳ |
| Analysis, figures, report | ⏳ |

## Repository layout

```
pwaudit/              our code
  config.py           paths, suites, policy-model registry, published anchor values
  anchor.py           exact reproduction of AgentDojo's published GPT-4o numbers from shipped traces
  progent_env.py      loads Progent + its AgentDojo fork for one suite/model; Progent-exact call checker
  static_check.py     experiment 1: initial policies vs. ground-truth calls (+ controls)
scripts/
  fetch_traces.sh     sparse checkout of the shipped AgentDojo traces (pinned commit)
  serve_models.sh     one vLLM OpenAI-compatible server per open policy model
vendor/progent/       Progent (secagent + AgentDojo fork) @ 5be7b63, copied; local patches in vendor/PATCHES.md
results/              every number in the report is computed from files here
report/               ICLR-format LaTeX report (2 pages)
```

## Setup

```bash
uv venv venv --python 3.12 && . venv/bin/activate
uv pip install -e vendor/progent/agentdojo -e vendor/progent matplotlib pandas
scripts/fetch_traces.sh                 # shipped traces -> $PW_TRACES_ROOT
echo "OPENAI_API_KEY=..." > .env         # only for the gpt-4o policy model; .env is git-ignored
scripts/serve_models.sh                  # open policy models (needs vLLM; see script for GPUs/ports)
```

## Reproduce

```bash
python -m pwaudit.anchor                                           # results/anchor.json
python -m pwaudit.static_check --suite banking --model controls    # results/static/controls/
python -m pwaudit.static_check --suite banking --model qwen3-30b   # results/static/<model>/
```

Policy-model calls are cached in SQLite (`$PW_DATA_DIR/policy_cache.sqlite`), keyed by
sha256(model, prompts, temperature), so reruns are deterministic and free.

## Policy models (all ≤35B, plus Progent's GPT-4o)

| Key | Model | Served by |
|---|---|---|
| `gpt-4o` | gpt-4o-2024-08-06 (Progent's default) | OpenAI API |
| `qwen3-30b` | Qwen3-30B-A3B-Instruct-2507 | vLLM |
| `mistral-24b` | Mistral-Small-3.2-24B-Instruct-2506 | vLLM |
| `qwen3.5-9b` | Qwen3.5-9B (thinking disabled) | vLLM |
| `qwen2.5-7b` | Qwen2.5-7B-Instruct | vLLM |

## Conduct

Sandboxed AgentDojo environments only (simulated state). No live accounts or agents. Every reported number
traces to a file in `results/`. No API keys in the repo.
