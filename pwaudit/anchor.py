"""Anchor: recompute AgentDojo's published GPT-4o (no defense) numbers from the shipped traces.

Utility = mean over user tasks of `utility` in the no-attack traces (none/none.json).
Utility under attack / targeted ASR = mean of `utility` / `security` over all (user, injection) traces;
in AgentDojo traces `security=True` means the injection task succeeded.
"""
import json

from . import config


def load_runs(run_name, attack):
    root = config.trace_dir(run_name)
    rows = []
    for suite in config.SUITES:
        files = sorted((root / suite).glob(f"user_task_*/{attack}/*.json"))
        if not files:
            raise FileNotFoundError(f"no {attack} traces for {run_name}/{suite}")
        for f in files:
            d = json.loads(f.read_text())
            rows.append({"suite": suite, "user_task": d["user_task_id"], "injection_task": d["injection_task_id"],
                         "utility": bool(d["utility"]), "security": bool(d["security"]),
                         "error": d.get("error"), "path": str(f)})
    return rows


def summarize(run_name):
    benign = load_runs(run_name, "none")
    attacked = load_runs(run_name, config.ATTACK)
    out = {
        "n_user_tasks": len(benign),
        "n_attack_cases": len(attacked),
        "utility": 100 * sum(r["utility"] for r in benign) / len(benign),
        "utility_under_attack": 100 * sum(r["utility"] for r in attacked) / len(attacked),
        "targeted_asr": 100 * sum(r["security"] for r in attacked) / len(attacked),
        "n_errors": sum(r["error"] is not None for r in benign + attacked),
    }
    return out


def main():
    config.RESULTS.mkdir(exist_ok=True)
    result = {"anchor_run": config.ANCHOR_TRACES, "published": config.ANCHOR_PUBLISHED,
              "recomputed": summarize(config.ANCHOR_TRACES),
              "replay_run": config.REPLAY_TRACES, "replay_run_stats": summarize(config.REPLAY_TRACES)}
    rec = result["recomputed"]
    for k, v in config.ANCHOR_PUBLISHED.items():
        ok = abs(round(rec[k], 2) - v) < 1e-9
        print(f"[anchor] {k}: recomputed {rec[k]:.2f}% vs published {v:.2f}% -> {'EXACT' if ok else 'MISMATCH'}")
    print(f"[anchor] replay run {config.REPLAY_TRACES}: {result['replay_run_stats']}")
    (config.RESULTS / "anchor.json").write_text(json.dumps(result, indent=2))
    print(f"[anchor] wrote {config.RESULTS / 'anchor.json'}")


if __name__ == "__main__":
    main()
