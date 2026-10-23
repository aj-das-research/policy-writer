# Who guards the policy writer?

An audit of the LLM **policy writer** in [Progent](https://arxiv.org/abs/2504.11703) (Shi et al., 2025) on
[AgentDojo](https://github.com/ethz-spylab/agentdojo) (Debenedetti et al., 2024). The 2-page report is in
[`report/report.pdf`](report/report.pdf).

Progent has an LLM turn the user's query into a deterministic JSON-schema policy over tool calls, then *updates*
that policy from tool outputs during the run. Progent reports that this cuts GPT-4o's ASR on AgentDojo from 39.9% to
1.0%. That result assumes the policy writer is reliable and cannot itself be injected. In the released AgentDojo
integration, updates are computed from (possibly injected) tool outputs and applied without confirmation
(`tool_execution.py` calls the update with `manual_check=False`), and the narrowing-only check is off
(`SECAGENT_ONLY_ALLOW_NARROW` is commented out in `run.sh`).

## Results (all numbers from `results/summary.json`)

| Policy writer | FB | Blk | Util (default) | ASR (default) | AtkPol (default) | Unblk (default) | ASR (narrow) | Unblk (narrow) |
|---|---|---|---|---|---|---|---|---|
| GPT-4o | 17.5 | 96.1 | 44.3 | 0.7 | 1.2 | 1.9 | 0.1 | 0.0 |
| Qwen3-30B-A3B | 44.3 | 99.5 | 37.1 | 5.1 | 24.1 | 15.8 | 0.0 | 0.0 |
| Mistral-Small-24B | 30.9 | 97.1 | 40.2 | 3.7 | 25.3 | 15.8 | 0.3 | 0.2 |
| Qwen3.5-9B | 25.8 | 93.5 | 42.3 | 2.8 | 13.2 | 14.1 | 0.4 | 0.0 |
| Qwen2.5-7B | 45.4 | 99.3 | 32.0 | 0.3 | 3.1 | 1.2 | 0.1 | 0.0 |
| *No defense (trace)* | – | – | 57.7 | 22.3 | – | – | 22.3 | – |

* Initial policies block most attacks but falsely block 17–45% of user tasks, so utility depends on updates written
  from tool outputs, which is the attacker's channel.
* With the released defaults (unconfirmed updates), attacker values enter the policy: rarely for GPT-4o (1.2%), but in
  13–25% of attacked traces for the open writers, unblocking 14–16% of attacks.
* Narrowing-only removes almost all of this (ASR ≤0.4%) for 1–4 utility points. The one remaining unblock comes from a
  soundness gap in Progent's narrowing check (`pwaudit/subset_bug.py`).

## What we measure

| Experiment | What is checked | Metrics |
|---|---|---|
| **Static check** | Each initial policy against the ground-truth calls of its user task and of every injection task | false blocks (FB), attacks blocked (Blk) |
| **Update replay** | The tool outputs of shipped AgentDojo traces (Llama-3.3-70B, v1.2.1) fed through Progent's update step | replay utility/ASR, attacker value in policy (AtkPol), attacks unblocked by an update (Unblk) |
| **Ablations** | Policy model (GPT-4o + 4 open models ≤30B); narrowing-only updates on/off | all of the above |
| **Controls** | Allow-all, deny-all, Progent's hand-written always-allowed list | sanity bounds |
| **Anchor** | AgentDojo's published GPT-4o row recomputed from its shipped traces | exact: 69.07 / 50.08 / 47.69 |

## Audit findings about the released code (independent of the LLM)

* The AgentDojo fork **comments out travel injection tasks 2 and 6** (40 of 949 cases). Task 6 succeeds through the
  agent's text alone, so no tool-call policy can block it.
* The fork's `scripts/benchmark.py` changes the default benchmark version to **v1.1.2** (upstream: v1.2), and `run.sh`
  passes no version flag.
* Progent stores its hand-written always-allowed tools via `set()`, so the policy's key order, and therefore the
  update prompt, depends on `PYTHONHASHSEED`. Unpinned, runs are not reproducible. We pin it to 0.
* **Narrowing-check soundness gap:** `security_policy_subset_check` ignores an empty `enum`, so
  `{"enum": []}` → `{"enum": ["13"]}` is accepted as narrowing, although enforcement (jsonschema) blocks `"13"` before and
  allows it after. Reproduced by `python -m pwaudit.subset_bug` (`results/subset_bug.json`), and seen in the replay
  (Mistral, workspace user task 35 / injection task 1: the attacker's file id).
* AgentDojo v1.2 workspace injection tasks 6–13 have no ground-truth calls, so the static check excludes them
  (they still count in the replay ASR).

## Repository layout

```
pwaudit/              our code
  config.py           paths, suites, policy-model registry, published anchor values
  anchor.py           exact reproduction of AgentDojo's published GPT-4o numbers from shipped traces
  progent_env.py      loads Progent + its AgentDojo fork for one suite/model; Progent-exact call checker
  static_check.py     experiment 1: initial policies vs. ground-truth calls (+ controls)
  replay.py           experiment 2: shipped traces through Progent's update step (default / narrow_only)
  analyze.py          results/*.jsonl -> results/summary.json (all metrics, per suite)
  subset_bug.py       reproduces the soundness gap in Progent's narrowing-only check
  figures.py          summary.json -> report/figs/main.pdf, results/table_main.tex, results/numbers.tex
scripts/
  fetch_traces.sh     sparse checkout of the shipped AgentDojo traces (pinned commit)
  serve_models.sh     one vLLM OpenAI-compatible server per open policy model
  run_model.sh        static check + both replay modes for one model, suites in parallel
vendor/progent/       Progent (secagent + AgentDojo fork) @ 5be7b63, copied; patches listed in vendor/PATCHES.md
results/              every number in the report is computed from files here
notebooks/            reproduce_numbers.ipynb: executed; recomputes every reported number from results/
report/               ICLR-2026-format LaTeX report (2 pages); numbers come from results/numbers.tex
```

## Setup

```bash
uv venv venv --python 3.12 && . venv/bin/activate
uv pip install -e vendor/progent/agentdojo -e vendor/progent matplotlib pandas
scripts/fetch_traces.sh                  # shipped traces -> $PW_TRACES_ROOT
echo "OPENAI_API_KEY=..." > .env          # only for the gpt-4o policy model; .env is git-ignored
scripts/serve_models.sh                   # open policy models (vLLM; GPUs/ports inside the script)
```

## Reproduce

```bash
python -m pwaudit.anchor                                   # results/anchor.json
python -m pwaudit.static_check --suite banking --model controls
scripts/run_model.sh gpt-4o 8                              # static + replay (default, narrow_only), all suites
scripts/run_model.sh qwen3-30b 16                          # ... for each policy model
python -m pwaudit.analyze && python -m pwaudit.figures     # summary.json, figure, table, number macros
cd report && pdflatex report.tex && pdflatex report.tex
```

Policy-model calls are cached in SQLite (`$PW_DATA_DIR/policy_cache.sqlite`), keyed by
sha256(model, prompts, temperature). With the hash seed pinned, a rerun makes zero new calls and gives
byte-identical records.

## Policy models

| Key | Model | Served by |
|---|---|---|
| `gpt-4o` | gpt-4o-2024-08-06 (Progent's default) | OpenAI API |
| `qwen3-30b` | Qwen3-30B-A3B-Instruct-2507 | vLLM |
| `mistral-24b` | Mistral-Small-3.2-24B-Instruct-2506 | vLLM |
| `qwen3.5-9b` | Qwen3.5-9B (thinking disabled) | vLLM |
| `qwen2.5-7b` | Qwen2.5-7B-Instruct | vLLM |

## Conduct

Sandboxed AgentDojo environments only (simulated state); no live accounts or agents. Every reported number traces to a
file in `results/`. No API keys in the repo (`.env` is git-ignored and a pre-commit hook blocks key-like strings).
