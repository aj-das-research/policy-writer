"""Render the report's figure and table from results/summary.json (run pwaudit.analyze first).

Color = policy model (fixed categorical order, validated palette); texture = update mode
(solid = Progent default, hatched = narrowing-only). Dashed gray = the undefended trace.
"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import config  # noqa: E402
from .analyze import LABEL, MODEL_ORDER  # noqa: E402

COLORS = dict(zip(MODEL_ORDER, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
GRAY, INK, MUTED = "#8a8985", "#0b0b0b", "#52514e"
SHORT = {"gpt-4o": "4o", "qwen3-30b": "Q30B", "mistral-24b": "M24B", "qwen3.5-9b": "Q9B", "qwen2.5-7b": "Q7B"}
FIG_DIR = config.REPO / "report" / "figs"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
    "font.size": 6.5, "axes.titlesize": 7, "axes.labelsize": 6.5, "xtick.labelsize": 6, "ytick.labelsize": 6,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.5, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "hatch.linewidth": 0.6, "pdf.fonttype": 42,
})


def _bars(ax, models, values_default, values_narrow, reference=None, ref_label=None, ylim=None, fmt="{:.0f}"):
    w = 0.38
    for i, m in enumerate(models):
        for off, v, hatch, alpha in [(-w / 2, values_default[i], None, 1.0), (w / 2, values_narrow[i], "////", 0.55)]:
            if v is None:
                continue
            ax.bar(i + off, v, w * 0.92, color=COLORS[m], alpha=alpha, hatch=hatch, edgecolor=COLORS[m],
                   linewidth=0.4)
            ax.text(i + off, v + (ylim[1] if ylim else max(values_default)) * 0.015, fmt.format(v),
                    ha="center", va="bottom", fontsize=4.8, color=INK)
    if reference is not None:
        ax.axhline(reference, color=GRAY, lw=0.7, ls=(0, (3, 2)), zorder=0)
        ax.text(len(models) - 0.5, reference, ref_label, ha="right", va="bottom", fontsize=5, color=MUTED)
    ax.set_xticks(range(len(models)), [SHORT[m] for m in models])
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color="#e6e5e1", lw=0.4)
    ax.set_axisbelow(True)
    if ylim:
        ax.set_ylim(*ylim)


def main_figure(summary):
    st, rp = summary["static"], summary["replay"]
    models = [m for m in MODEL_ORDER if m in st and m in rp and {"default", "narrow_only"} <= set(rp[m])]
    if not models:
        raise RuntimeError("no model has complete static + replay results")
    fig, axes = plt.subplots(1, 4, figsize=(5.5, 1.55), gridspec_kw={"width_ratios": [1.15, 1, 1, 1]})

    # (a) static trade-off
    ax = axes[0]
    for k, mk in [("allow_all", "s"), ("deny_all", "s"), ("human_only", "D")]:
        ax.scatter(st[k]["false_block"], st[k]["attacks_blocked"], marker=mk, s=14, color=GRAY, zorder=3,
                   edgecolor="white", linewidth=0.5)
    ctrl_pos = {"allow_all": (6, 4), "deny_all": (-6, -9), "human_only": (-4, -9)}
    for k, (dx, dy) in ctrl_pos.items():
        ax.annotate({"allow_all": "allow-all", "deny_all": "deny-all", "human_only": "hand-written"}[k],
                    (st[k]["false_block"], st[k]["attacks_blocked"]), xytext=(dx, dy), textcoords="offset points",
                    fontsize=5, color=MUTED, ha="left" if dx > 0 else "right")
    for m in models:
        ax.scatter(st[m]["false_block"], st[m]["attacks_blocked"], s=16, color=COLORS[m], zorder=4,
                   edgecolor="white", linewidth=0.5)
        ax.annotate(SHORT[m], (st[m]["false_block"], st[m]["attacks_blocked"]), xytext=(3, 2),
                    textcoords="offset points", fontsize=5, color=INK)
    ax.set_xlim(-5, 105), ax.set_ylim(-5, 108)
    ax.set_xlabel("false blocks (% user tasks)")
    ax.set_ylabel("attacks blocked (% pairs)")
    ax.set_title("(a) initial policy vs. ground truth", loc="left")
    ax.grid(color="#e6e5e1", lw=0.4), ax.set_axisbelow(True)

    any_m = rp[models[0]]["default"]
    # (b) replay utility on benign traces
    _bars(axes[1], models, [rp[m]["default"]["replay_utility"] for m in models],
          [rp[m]["narrow_only"]["replay_utility"] for m in models], any_m["trace_utility"],
          f"no defense {any_m['trace_utility']:.1f}", ylim=(0, 70))
    axes[1].set_title("(b) utility, benign replay (%)", loc="left")
    # (c) replay ASR
    _bars(axes[2], models, [rp[m]["default"]["replay_asr"] for m in models],
          [rp[m]["narrow_only"]["replay_asr"] for m in models], None, None, ylim=(0, 6), fmt="{:.1f}")
    axes[2].set_title(f"(c) ASR, attacked replay (%)", loc="left")
    axes[2].text(0.98, 0.97, f"no defense: {any_m['trace_asr']:.1f}", transform=axes[2].transAxes, ha="right",
                 va="top", fontsize=5, color=MUTED)
    # (d) attacker values entering the policy
    _bars(axes[3], models, [rp[m]["default"]["attacker_in_policy"] for m in models],
          [rp[m]["narrow_only"]["attacker_in_policy"] for m in models], None, None, ylim=(0, 10), fmt="{:.1f}")
    axes[3].set_title("(d) attacker value in policy (%)", loc="left")
    from matplotlib.patches import Patch
    axes[3].legend(handles=[Patch(facecolor=GRAY, label="default"),
                            Patch(facecolor=GRAY, alpha=0.55, hatch="////", label="narrow-only")],
                   fontsize=5, frameon=False, loc="upper right", handlelength=1.2)
    fig.tight_layout(pad=0.2, w_pad=0.6)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / "main.pdf"
    fig.savefig(out)
    fig.savefig(FIG_DIR / "main.png", dpi=200)
    print(f"[figures] wrote {out} (models: {models})")


def f(v, nd=1):
    return "--" if v is None else f"{v:.{nd}f}"


def main_table(summary):
    st, rp = summary["static"], summary["replay"]
    rows = []
    for m in MODEL_ORDER:
        if m not in st:
            continue
        r = rp.get(m, {})
        d, n = r.get("default", {}), r.get("narrow_only", {})
        rows.append(f"{LABEL[m]} & {f(st[m]['false_block'])} & {f(st[m]['attacks_blocked'])} & "
                    f"{f(d.get('replay_utility'))} & {f(d.get('replay_asr'))} & {f(d.get('attacker_in_policy'))} & "
                    f"{f(d.get('attack_unblocked'))} & {f(n.get('replay_utility'))} & {f(n.get('replay_asr'))} & "
                    f"{f(n.get('attacker_in_policy'))} & {f(n.get('attack_unblocked'))} \\\\")
    ctrl = [f"{LABEL[k]} & {f(st[k]['false_block'])} & {f(st[k]['attacks_blocked'])} & \\multicolumn{{8}}{{c}}{{}} \\\\"
            for k in ["allow_all", "deny_all", "human_only"]]
    any_m = next(iter(rp.values()))["default"]
    ref = (f"No defense (trace) & -- & -- & {f(any_m['trace_utility'])} & {f(any_m['trace_asr'])} & -- & -- & "
           f"{f(any_m['trace_utility'])} & {f(any_m['trace_asr'])} & -- & -- \\\\")
    tex = "\n".join(rows) + "\n\\midrule\n" + "\n".join(ctrl) + "\n" + ref + "\n"
    (config.RESULTS / "table_main.tex").write_text(tex)
    print(f"[figures] wrote {config.RESULTS / 'table_main.tex'}")


def cache_stats():
    """Token counts and wall-clock span per policy model, from the policy-call cache."""
    import sqlite3
    con = sqlite3.connect(config.CACHE_PATH)
    rows = con.execute("SELECT model, COUNT(*), SUM(prompt_tokens), SUM(completion_tokens), MAX(completion_tokens), "
                       "MIN(created), MAX(created) FROM calls GROUP BY model").fetchall()
    return {r[0]: {"calls": r[1], "prompt_tokens": r[2], "completion_tokens": r[3], "max_completion": r[4],
                   "hours": (r[6] - r[5]) / 3600} for r in rows}


# gpt-4o-2024-08-06 list price, USD per 1M tokens (input, output)
GPT4O_PRICE = (2.50, 10.00)


def numbers_tex(summary):
    """LaTeX macros for every number quoted in the report text."""
    macros = {}
    a = summary["anchor"]
    for k, v in a["recomputed"].items():
        if isinstance(v, float):
            macros[f"anchor{k.replace('_', '')}"] = f"{v:.2f}"
    st, rp = summary["static"], summary["replay"]
    tag = {"gpt-4o": "Gpt", "qwen3-30b": "Qthirty", "mistral-24b": "Mistral", "qwen3.5-9b": "Qnine",
           "qwen2.5-7b": "Qseven", "allow_all": "Allow", "deny_all": "Deny", "human_only": "Human"}
    for k, v in st.items():
        macros[f"st{tag[k]}FB"] = f(v["false_block"])
        macros[f"st{tag[k]}Blk"] = f(v["attacks_blocked"])
    for m, modes in rp.items():
        for mode, v in modes.items():
            mt = "D" if mode == "default" else "N"
            for key, name in [("replay_utility", "Util"), ("replay_asr", "ASR"), ("attacker_in_policy", "AtkPol"),
                              ("attack_unblocked", "Unblk"), ("benign_false_block", "BFB"),
                              ("excluded_replay_asr", "ExclASR")]:
                macros[f"rp{tag[m]}{mt}{name}"] = f(v[key])
            macros[f"rp{tag[m]}{mt}Applied"] = str(v["counters"]["update_applied"])
            macros[f"rp{tag[m]}{mt}Rejected"] = str(v["counters"]["update_rejected_narrow"])
    any_m = next(iter(rp.values()))["default"]
    macros.update(traceASR=f(any_m["trace_asr"]), traceUtil=f(any_m["trace_utility"]),
                  nAttacked=str(any_m["n_attacked"]), nExcluded=str(any_m["n_excluded"]),
                  exclTraceASR=f(any_m["excluded_trace_asr"]))
    cs = cache_stats()
    g = cs.get("gpt-4o-2024-08-06")
    if g:
        cost = g["prompt_tokens"] / 1e6 * GPT4O_PRICE[0] + g["completion_tokens"] / 1e6 * GPT4O_PRICE[1]
        macros.update(gptCost=f"{cost:.2f}", gptMTokIn=f"{g['prompt_tokens'] / 1e6:.1f}",
                      gptMTokOut=f"{g['completion_tokens'] / 1e6:.2f}", gptCalls=f"{g['calls']:,}".replace(",", "{,}"))
    macros["totalCalls"] = f"{sum(v['calls'] for v in cs.values()):,}".replace(",", "{,}")
    macros["maxCompletion"] = str(max(v["max_completion"] for v in cs.values()))
    import sqlite3
    macros["nTruncated"] = str(sqlite3.connect(config.CACHE_PATH).execute(
        "SELECT COUNT(*) FROM calls WHERE completion_tokens >= ?", (config.LOCAL_MAX_TOKENS,)).fetchone()[0])
    tex = "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(macros.items())) + "\n"
    (config.RESULTS / "numbers.tex").write_text(tex)
    (config.RESULTS / "cache_stats.json").write_text(json.dumps(cs, indent=2))
    print(f"[figures] wrote {len(macros)} macros -> {config.RESULTS / 'numbers.tex'}")


def main():
    summary = json.loads((config.RESULTS / "summary.json").read_text())
    main_figure(summary)
    main_table(summary)
    numbers_tex(summary)


if __name__ == "__main__":
    main()
