"""Experiment 2: replay shipped AgentDojo traces through Progent's policy-update step.

For each trace (an undefended v1.2.1 run), Progent writes the initial policy P0 from the trace's user prompt.
We then walk the trace's tool-call steps in order, as Progent's ToolsExecutor would:
  1. every call in the step is checked against the current policy (Progent's own checker);
  2. if a call is blocked, the trace diverges from what Progent would have produced -> stop (later steps are
     counterfactual);
  3. otherwise the step's calls and the trace's recorded tool outputs go to
     `generate_update_security_policy(calls, str(results), manual_check=False)`, exactly as in the released
     integration (`agent_pipeline/tool_execution.py`).
If no call is ever blocked, the agent saw byte-identical inputs to the undefended run, so the trace's recorded
outcome (utility / attack success) is what Progent would have produced, given the same agent outputs.

Per step we record whether attacker values (strings in the injection task's ground-truth arguments that occur
neither in the user prompt nor in the user task's ground truth) appear in the policy, and whether the injection
task's ground-truth calls are allowed by it.

Output: results/replay/<model>/<mode>/<suite>.jsonl, one line per trace. mode = default | narrow_only.
"""
import argparse
import json
import multiprocessing as mp
import re
import sys
import time
import traceback
from ast import literal_eval

from . import config


def _init(suite, model_key, narrow_only):
    from . import progent_env
    progent_env.setup(suite, model_key, narrow_only=narrow_only)


def text_of(content):
    """AgentDojo >=0.1.30 stores content as a list of text blocks; older traces store a string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(block["content"] for block in content if block["type"] == "text")


# Copied from agentdojo.agent_pipeline.tool_execution (Progent fork): input lists arrive as strings.
def is_string_list(s: str):
    try:
        parsed = literal_eval(s)
        return isinstance(parsed, list)
    except (ValueError, SyntaxError):
        return False


def normalize_args(args):
    out = dict(args)
    for k, v in out.items():
        if isinstance(v, str) and is_string_list(v):
            out[k] = literal_eval(v)
    return out


def attacker_strings(pe, user_task, injection_task, env, query):
    benign = set(pe.string_values([dict(c.args) for c in user_task.ground_truth(env.model_copy(deep=True))]))
    inj = set(pe.string_values([dict(c.args) for c in injection_task.ground_truth(env.model_copy(deep=True))]))
    return sorted(s for s in inj if len(s) >= 4 and s not in benign and s.lower() not in query.lower())


def strings_in_policy(strings, generated):
    """Attacker strings literally present in the LLM-written policy (raw, regex-escaped, or JSON-escaped)."""
    blob = json.dumps(generated, ensure_ascii=False)
    found = []
    for s in strings:
        forms = {s, re.escape(s), json.dumps(s)[1:-1], json.dumps(re.escape(s))[1:-1]}
        if any(f in blob for f in forms):
            found.append(s)
    return found


def check_calls(pe, calls):
    return [pe.check_call(c.function, dict(c.args))["status"] for c in calls]


def replay_trace(path):
    from . import progent_env as pe
    T = pe.T
    d = json.loads(open(path).read())
    suite = pe.SUITE
    msgs = d["messages"]
    query = text_of(next(m for m in msgs if m["role"] == "user")["content"])
    user_task = suite.user_tasks[d["user_task_id"]]
    attacked = d["injection_task_id"] is not None
    rec = {"suite": d["suite_name"], "user_task": d["user_task_id"], "injection_task": d["injection_task_id"],
           "trace": str(path), "trace_utility": bool(d["utility"]), "trace_security": bool(d["security"]),
           "prompt_matches_v1_2": query == user_task.PROMPT}
    t0 = time.time()
    for k in T.audit_counters:
        T.audit_counters[k] = 0
    try:
        policy = pe.generate_initial_policy(query)
    except Exception as e:
        print(f"[replay] initial policy FAILED {path}: {e!r}", file=sys.stderr)
        traceback.print_exc()
        rec.update(generation="failed", generation_error=repr(e))
        return rec
    rec["generation"] = "ok"
    rec["policy0"] = pe.generated_part(policy)
    env = suite.load_and_inject_default_environment({})
    if attacked:
        inj_task = suite.injection_tasks[d["injection_task_id"]]
        inj_calls = inj_task.ground_truth(env.model_copy(deep=True))
        atk = attacker_strings(pe, user_task, inj_task, env, query)
        rec["attacker_strings"] = atk
        rec["inj_gt_status0"] = check_calls(pe, inj_calls)
        rec["attacker_in_policy0"] = strings_in_policy(atk, rec["policy0"])
    steps, divergence = [], None
    i = 0
    while i < len(msgs):
        m = msgs[i]
        if m["role"] != "assistant" or not m.get("tool_calls"):
            i += 1
            continue
        tool_msgs = []
        j = i + 1
        while j < len(msgs) and msgs[j]["role"] == "tool":
            tool_msgs.append(msgs[j])
            j += 1
        if len(tool_msgs) != len(m["tool_calls"]):
            raise RuntimeError(f"{path}: step at msg {i} has {len(m['tool_calls'])} calls but {len(tool_msgs)} results")
        calls, results = [], []
        for tc, tm in zip(m["tool_calls"], tool_msgs):
            fn = tc["function"]
            if fn == "" or fn not in pe.FUNCS:  # ToolsExecutor skips these without running or logging them
                continue
            args = normalize_args(tc["args"])
            chk = pe.check_call(fn, args)
            if chk["status"] == "blocked":
                carries_attacker = attacked and any(s in pe.dumps(args) for s in rec["attacker_strings"])
                divergence = {"msg_index": i, "function": fn, "args": json.loads(pe.dumps(args)),
                              "block_kind": chk["block_kind"], "carries_attacker_value": carries_attacker}
                break
            calls.append({"name": fn, "args": args})
            results.append(text_of(tm["content"]))
        if divergence is not None:
            break
        if calls:
            before = pe.generated_part(pe.get_policy())
            T.generate_update_security_policy(calls, str(results), manual_check=False)
            after = pe.generated_part(pe.get_policy())
            step = {"msg_index": i, "calls": [c["name"] for c in calls], "changed": after != before}
            if attacked:
                step["attacker_in_policy"] = strings_in_policy(rec["attacker_strings"], after)
                step["inj_gt_status"] = check_calls(pe, inj_calls)
            steps.append(step)
        i = j
    final = pe.generated_part(pe.get_policy())
    rec.update(steps=steps, divergence=divergence, policy_final=final, counters=dict(T.audit_counters),
               seconds=round(time.time() - t0, 2))
    return rec


def trace_files(suite, attack):
    root = config.trace_dir(config.REPLAY_TRACES) / suite
    files = sorted(root.glob(f"user_task_*/{attack}/*.json"))
    if not files:
        raise FileNotFoundError(f"no {attack} traces under {root}")
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=config.SUITES)
    ap.add_argument("--model", required=True, choices=list(config.POLICY_MODELS))
    ap.add_argument("--mode", required=True, choices=["default", "narrow_only"])
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--limit", type=int, default=None, help="debug: first N traces of each attack type")
    a = ap.parse_args()
    files = trace_files(a.suite, "none") + trace_files(a.suite, config.ATTACK)
    if a.limit:
        files = trace_files(a.suite, "none")[: a.limit] + trace_files(a.suite, config.ATTACK)[: a.limit]
    print(f"[replay] suite={a.suite} model={a.model} mode={a.mode} traces={len(files)} workers={a.workers}")
    ctx = mp.get_context("spawn")
    out, t0 = [], time.time()
    with ctx.Pool(a.workers, initializer=_init, initargs=(a.suite, a.model, a.mode == "narrow_only")) as pool:
        for n, rec in enumerate(pool.imap_unordered(replay_trace, files), 1):
            out.append(rec)
            if n % 25 == 0 or n == len(files):
                fails = sum(r["generation"] == "failed" for r in out)
                print(f"[replay] {a.suite}/{a.model}/{a.mode}: {n}/{len(files)} ({time.time() - t0:.0f}s) "
                      f"init-policy failures={fails}", flush=True)
    d = config.RESULTS / "replay" / a.model / a.mode
    d.mkdir(parents=True, exist_ok=True)
    path = d / (f"{a.suite}.jsonl" if not a.limit else f"{a.suite}.debug.jsonl")
    with open(path, "w") as f:
        for r in sorted(out, key=lambda r: r["trace"]):
            f.write(json.dumps(r) + "\n")
    print(f"[replay] wrote {len(out)} records -> {path}")


if __name__ == "__main__":
    main()
