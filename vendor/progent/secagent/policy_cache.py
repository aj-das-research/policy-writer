"""[policy-writer patch] On-disk cache for policy-model requests.

Key = sha256 over (model, system prompt, user prompt, temperature). Only successful responses are stored;
exceptions propagate unchanged to Progent's own retry logic. The cache file is shared across worker
processes (SQLite WAL mode). Token usage is stored so API cost can be computed from the cache.
"""
import hashlib
import json
import os
import sqlite3
import sys
import time

_conn = None
_stats = {"hit": 0, "miss": 0}


def _db():
    global _conn
    if _conn is None:
        path = os.environ.get("SECAGENT_CACHE_PATH")
        if not path:
            raise RuntimeError("SECAGENT_CACHE_PATH is not set; refusing to run uncached policy requests.")
        _conn = sqlite3.connect(path, timeout=120)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, model TEXT, temperature REAL, "
            "sys_prompt TEXT, user_prompt TEXT, response TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, "
            "created REAL)"
        )
        _conn.commit()
        print(f"[policy_cache] using {path}", file=sys.stderr)
    return _conn


def request_key(model, sys_prompt, user_prompt, temperature):
    blob = json.dumps([model, sys_prompt, user_prompt, float(temperature)], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cached_request(model, sys_prompt, user_prompt, temperature, request_fn):
    key = request_key(model, sys_prompt, user_prompt, temperature)
    db = _db()
    row = db.execute("SELECT response FROM calls WHERE key=?", (key,)).fetchone()
    if row is not None:
        _stats["hit"] += 1
        return row[0]
    _stats["miss"] += 1
    t0 = time.time()
    text, usage = request_fn(sys_prompt, user_prompt, temperature)
    if text is None:
        raise RuntimeError(f"[policy_cache] model {model} returned no content (key={key[:12]})")
    usage = usage or {}
    db.execute(
        "INSERT OR REPLACE INTO calls VALUES (?,?,?,?,?,?,?,?,?)",
        (key, model, float(temperature), sys_prompt, user_prompt, text,
         usage.get("prompt_tokens"), usage.get("completion_tokens"), time.time()),
    )
    db.commit()
    n = _stats["hit"] + _stats["miss"]
    if n % 50 == 0:
        print(f"[policy_cache] pid={os.getpid()} hits={_stats['hit']} misses={_stats['miss']} "
              f"last_call={time.time() - t0:.1f}s", file=sys.stderr)
    return text


def stats():
    return dict(_stats)
