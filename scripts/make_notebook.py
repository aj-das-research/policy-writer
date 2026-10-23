"""Build notebooks/reproduce_numbers.ipynb: recomputes every reported number from results/ (no LLM calls).

Run: python scripts/make_notebook.py && jupyter nbconvert --to notebook --execute --inplace notebooks/reproduce_numbers.ipynb
"""
from pathlib import Path

import nbformat as nbf

cells = [
    nbf.v4.new_markdown_cell(
        "# Who guards the policy writer? Reproduce every reported number\n"
        "This notebook only reads `results/` (written by `pwaudit.static_check` / `pwaudit.replay`) and AgentDojo's "
        "shipped traces; it makes no LLM calls. Policy-model calls are cached in `policy_cache.sqlite`."),
    nbf.v4.new_code_cell("import os, sys, json\nos.chdir('..') if os.path.basename(os.getcwd()) == 'notebooks' else None\n"
                         "sys.path.insert(0, os.getcwd())\nfrom pwaudit import anchor, analyze, figures, config"),
    nbf.v4.new_markdown_cell("## Anchor: AgentDojo's published GPT-4o row from its shipped traces"),
    nbf.v4.new_code_cell("anchor.main()"),
    nbf.v4.new_markdown_cell("## All metrics (static check, update replay, controls)"),
    nbf.v4.new_code_cell("summary = analyze.main.__wrapped__() if hasattr(analyze.main, '__wrapped__') else None\n"
                         "sys.argv = ['analyze']\nsummary = analyze.main()"),
    nbf.v4.new_code_cell(
        "import pandas as pd\n"
        "st = pd.DataFrame({k: {m: v[m] for m in ['false_block', 'attacks_blocked', 'generation_failed', 'n_user_tasks', 'n_pairs']}\n"
        "                   for k, v in summary['static'].items()}).T\nst.round(1)"),
    nbf.v4.new_code_cell(
        "rows = {}\nfor m, modes in summary['replay'].items():\n    for mode, v in modes.items():\n"
        "        rows[(m, mode)] = {k: v[k] for k in ['replay_utility', 'benign_false_block', 'replay_asr', 'trace_asr',\n"
        "                          'attacker_in_policy', 'attack_unblocked', 'excluded_trace_asr', 'excluded_replay_asr',\n"
        "                          'n_attacked', 'n_attacked_with_gt', 'n_excluded']}\n"
        "        rows[(m, mode)].update({f'ctr_{k}': c for k, c in v['counters'].items()})\n"
        "pd.DataFrame(rows).T.round(1)"),
    nbf.v4.new_markdown_cell("## Per-suite replay metrics (default updates)"),
    nbf.v4.new_code_cell(
        "pd.DataFrame({(m, s): {k: v[k] for k in ['replay_utility', 'replay_asr', 'attacker_in_policy', 'attack_unblocked']}\n"
        "              for m, modes in summary['replay'].items() for s, v in modes['default']['per_suite'].items()}).T.round(1)"),
    nbf.v4.new_markdown_cell("## Figure, table and the LaTeX number macros used in the report"),
    nbf.v4.new_code_cell("figures.main()\nfrom IPython.display import Image, display\ndisplay(Image(str(figures.FIG_DIR / 'main.png')))"),
    nbf.v4.new_code_cell("print((config.RESULTS / 'numbers.tex').read_text())"),
    nbf.v4.new_code_cell("print(json.dumps(figures.cache_stats(), indent=1))"),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"}})
out = Path(__file__).resolve().parent.parent / "notebooks" / "reproduce_numbers.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print(f"wrote {out}")
