"""Load Progent + its AgentDojo fork for one suite and policy model, and check calls with Progent's own checker.

Progent configures itself from environment variables at import time (policy model, wrapped suite, update flags),
so `setup()` must run before anything imports `secagent` or `agentdojo` in this process.
"""
import copy
import json
import os
import sys

import jsonschema
from dotenv import load_dotenv

from . import config

T = None          # secagent.tool module (holds Progent's global policy state)
SUITE = None      # agentdojo TaskSuite (v1.2) whose tools are wrapped by Progent
FUNCS = None      # tool name -> agentdojo Function
HUMAN_POLICY = None  # Progent's hand-written always-allowed entries for this suite (priority 1)


def setup(suite_name: str, model_key: str, narrow_only: bool):
    global T, SUITE, FUNCS, HUMAN_POLICY
    for mod in ("secagent", "agentdojo"):
        if mod in sys.modules:
            raise RuntimeError(f"{mod} imported before progent_env.setup(); Progent env config would be ignored")
    served, base_url = config.POLICY_MODELS[model_key]
    load_dotenv(config.REPO / ".env")
    os.environ.update({
        "SECAGENT_SUITE": suite_name,
        "SECAGENT_POLICY_MODEL": served,
        "SECAGENT_CACHE_PATH": str(config.CACHE_PATH),
        # Released AgentDojo configuration (progent/agentdojo/run.sh)
        "SECAGENT_UPDATE": "True",
        "SECAGENT_IGNORE_UPDATE_ERROR": "True",
        "SECAGENT_ONLY_ALLOW_NARROW": "True" if narrow_only else "False",
    })
    if base_url is None:
        os.environ.pop("SECAGENT_POLICY_BASE_URL", None)
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(f"{model_key} needs OPENAI_API_KEY (.env)")
    else:
        os.environ["SECAGENT_POLICY_BASE_URL"] = base_url

    import secagent.tool as tool_mod
    from agentdojo.task_suite.load_suites import get_suite

    T = tool_mod
    SUITE = get_suite(config.BENCHMARK_VERSION, suite_name)
    FUNCS = {f.name: f for f in SUITE.tools}
    if T.policy_model != served:
        raise RuntimeError(f"secagent picked policy model {T.policy_model}, expected {served}")
    wrapped = {t["name"] for t in T.get_available_tools()}
    if wrapped != set(FUNCS):
        raise RuntimeError(f"Progent wrapped tools {sorted(wrapped)} != suite tools {sorted(FUNCS)}")
    HUMAN_POLICY = copy.deepcopy(T.security_policy)
    print(f"[progent_env] pid={os.getpid()} suite={suite_name} model={served} narrow_only={narrow_only} "
          f"tools={len(FUNCS)} human_allowed={sorted(HUMAN_POLICY)}", file=sys.stderr)


# ---------------------------------------------------------------- policies

def set_policy(policy):
    T.security_policy = copy.deepcopy(policy)
    T.sort_policy()


def get_policy():
    return copy.deepcopy(T.security_policy)


def control_policy(kind: str):
    if kind == "allow_all":
        return {name: [(1, 0, {}, 0)] for name in FUNCS}
    if kind == "deny_all":
        return {}
    if kind == "human_only":
        return copy.deepcopy(HUMAN_POLICY)
    raise ValueError(kind)


def generate_initial_policy(query: str):
    """Progent's initial policy: hand-written entries + LLM-generated entries (priority 100)."""
    set_policy(HUMAN_POLICY)
    T.generate_security_policy(query)
    return get_policy()


def policy_to_json(policy):
    return None if policy is None else {k: [list(p) for p in v] for k, v in policy.items()}


def generated_part(policy):
    """Only the LLM-written entries, as Progent passes them to the update prompt."""
    return [{"name": tool, "args": p[2]} for tool, ps in (policy or {}).items() for p in ps if p[0] == 100]


# ---------------------------------------------------------------- checking

def check_call(function: str, args: dict) -> dict:
    """Decide a call exactly as the Progent-wrapped AgentDojo runtime would.

    Mirrors FunctionsRuntime.run_function: pydantic validation (defaults filled), then the Progent wrapper's
    check_tool_call on the validated arguments.
    Returns {"status": allowed|blocked|invalid_args|unknown_tool, "reason": str|None, "block_kind": ...}.
    """
    if function not in FUNCS:
        return {"status": "unknown_tool", "reason": f"{function} not in suite", "block_kind": None}
    f = FUNCS[function]
    try:
        validated = f.parameters.model_validate(args).model_dump()
    except Exception as e:  # pydantic.ValidationError: runtime returns an error without running the tool
        return {"status": "invalid_args", "reason": f"{type(e).__name__}: {e}", "block_kind": None}
    try:
        T.check_tool_call(function, validated)
    except T.ValidationError as e:
        return {"status": "blocked", "reason": str(e), "block_kind": block_kind(function)}
    return {"status": "allowed", "reason": None, "block_kind": None}


def block_kind(function: str) -> str:
    """Classify a block from the policy structure: tool absent, malformed restriction, or argument violation."""
    entries = (T.security_policy or {}).get(function, [])
    if not entries:
        return "tool_not_listed"
    for _prio, _eff, restriction, _fb in entries:
        for schema in restriction.values():
            if isinstance(schema, dict):
                try:
                    jsonschema.validators.validator_for(schema).check_schema(schema)
                except jsonschema.SchemaError:
                    return "malformed_restriction"
    return "arg_violation"


def string_values(obj):
    """All string leaves of a JSON-like object."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from string_values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from string_values(v)


def dumps(obj):
    return json.dumps(obj, default=str, ensure_ascii=False)
