"""Experiment 1: check each initial policy against ground-truth calls (no agent, no updates).

For every v1.2 user task u: Progent writes the initial policy P_u from u's prompt. We then check
  * every ground-truth call of u          -> a blocked call is a false block (utility cost);
  * every ground-truth call of every injection task i -> a blocked call means the attack cannot complete
    as specified (security benefit).
Controls (allow_all, deny_all, human_only = Progent's hand-written always-allowed list) use the same checker.

Output: results/static/<model>/<suite>.jsonl, one line per user task.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
import traceback

from . import config

CONTROLS = ["allow_all", "deny_all", "human_only"]


def _init(suite, model_key):
    from . import progent_env
    progent_env.setup(suite, model_key, narrow_only=False)


def _check_all(pe, policy, calls):
    pe.set_policy(policy)
    return [{"function": c.function, "args": json.loads(pe.dumps(dict(c.args))), **pe.check_call(c.function, dict(c.args))}
            for c in calls]


def _gt(task, env):
    return task.ground_truth(env.model_copy(deep=True))


def run_user_task(args):
    user_task_id, policy_source = args
    from . import progent_env as pe
    suite = pe.SUITE
    task = suite.user_tasks[user_task_id]
    env = suite.load_and_inject_default_environment({})
    rec = {"suite": suite.name, "user_task": user_task_id, "policy_source": policy_source, "prompt": task.PROMPT}
    t0 = time.time()
    if policy_source in CONTROLS:
        policy = pe.control_policy(policy_source)
        rec["generation"] = "control"
    else:
        try:
            policy = pe.generate_initial_policy(task.PROMPT)
            rec["generation"] = "ok"
        except Exception as e:
            # Progent raises after 6 failed attempts; in a live run the task would crash. Record it as such.
            print(f"[static] policy generation FAILED {suite.name}/{user_task_id}: {e!r}", file=sys.stderr)
            traceback.print_exc()
            rec.update(generation="failed", generation_error=repr(e), policy=None, user_gt=None, injections=None)
            return rec
    rec["policy"] = pe.policy_to_json(policy)
    rec["user_gt"] = _check_all(pe, policy, _gt(task, env))
    rec["injections"] = {iid: _check_all(pe, policy, _gt(itask, env)) for iid, itask in suite.injection_tasks.items()}
    rec["seconds"] = round(time.time() - t0, 2)
    return rec


def run(suite, model_key, workers, sources):
    # Progent stores its always-allowed tools via set(), whose order (and hence the update prompt) depends on
    # the string hash seed. Pin it so spawned workers build identical prompts across runs.
    os.environ["PYTHONHASHSEED"] = "0"
    ctx = mp.get_context("spawn")
    from agentdojo.task_suite.load_suites import get_suite  # noqa: only for task ids; tools not wrapped here
    user_ids = list(get_suite(config.BENCHMARK_VERSION, suite).user_tasks)
    jobs = [(u, s) for s in sources for u in user_ids]
    print(f"[static] suite={suite} model={model_key} sources={sources} jobs={len(jobs)} workers={workers}")
    out = []
    with ctx.Pool(workers, initializer=_init, initargs=(suite, model_key)) as pool:
        for i, rec in enumerate(pool.imap_unordered(run_user_task, jobs), 1):
            out.append(rec)
            if i % 10 == 0 or i == len(jobs):
                fails = sum(r["generation"] == "failed" for r in out)
                print(f"[static] {suite}/{model_key}: {i}/{len(jobs)} done, generation failures={fails}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=config.SUITES)
    ap.add_argument("--model", required=True, choices=list(config.POLICY_MODELS) + ["controls"])
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    # Controls need no LLM; any model key works for loading the suite.
    model_key = "qwen2.5-7b" if a.model == "controls" else a.model
    sources = CONTROLS if a.model == "controls" else ["llm"]
    recs = run(a.suite, model_key, a.workers, sources)
    d = config.RESULTS / "static" / a.model
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{a.suite}.jsonl"
    with open(path, "w") as f:
        for r in sorted(recs, key=lambda r: (r["policy_source"], int(r["user_task"].split("_")[-1]))):
            f.write(json.dumps(r) + "\n")
    print(f"[static] wrote {len(recs)} records -> {path}")


if __name__ == "__main__":
    main()
