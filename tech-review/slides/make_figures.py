"""Figures and the Pareto analysis for the slide deck.

  python tech-review/slides/make_figures.py
  -> tech-review/slides/figs/{quality_cost_latency,score_profile,example_listwise,example_pointwise}.svg
  -> results_final/PARETO.md

Inputs: results_final/final.json (+ per-query records via final_table for the score profiles).
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
import seaborn as sns  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import final_table as F  # noqa: E402

FIGS = Path(__file__).resolve().parent / "figs"
FIGS.mkdir(exist_ok=True)
D = json.loads((ROOT / "results_final" / "final.json").read_text())
M, J = D["miracl"], D["jqara"]

fm.fontManager.addfont("/System/Library/Fonts/Palatino.ttc")
sns.set_theme(style="whitegrid")
plt.rcParams.update({
    "font.family": "Palatino", "svg.fonttype": "path",
    "axes.edgecolor": "#444", "axes.linewidth": 0.8, "grid.color": "#e4e4e4", "grid.linewidth": 0.7,
    "axes.titleweight": "bold", "axes.titlesize": 12.5, "axes.labelsize": 11, "xtick.labelsize": 10,
    "ytick.labelsize": 10, "legend.fontsize": 10,
})

SYS = F.SYSTEMS  # jevnoul14, jev14, lunanoul, luna, cohere, cohere35, coherefast
SHORT = {"jevnoul14": "Jev pointwise", "jev14": "Jev listwise", "lunanoul": "luna pointwise",
         "luna": "luna listwise", "cohere": "Cohere 4-pro", "cohere35": "Cohere v3.5",
         "coherefast": "Cohere 4-fast"}
NAVY, BLUE, ORANGE = "#1f3a5f", "#4f9ad0", "#c4622d"
STYLE = {  # color, marker
    "jevnoul14": (NAVY, "o"), "jev14": (NAVY, "s"), "lunanoul": (BLUE, "o"), "luna": (BLUE, "s"),
    "cohere": (ORANGE, "D"), "cohere35": (ORANGE, "D"), "coherefast": (ORANGE, "D"),
}
PAIRS = {}
for ds, key in (("M", "miracl_pairs"), ("J", "jqara_pairs")):
    for a, b, d, lo, hi in D[key]:
        PAIRS[(ds, a, b)] = (d, lo, hi)


def diff(ds, t, s):
    """paired bootstrap (mean, lo, hi) of nDCG@10(t) - nDCG@10(s)"""
    if (ds, t, s) in PAIRS:
        return PAIRS[(ds, t, s)]
    d, lo, hi = PAIRS[(ds, s, t)]
    return -d, -hi, -lo


def pareto(xs, ys):
    """indices not dominated (lower x better, higher y better)"""
    keep = []
    for i in range(len(xs)):
        dom = any((xs[j] <= xs[i] and ys[j] >= ys[i]) and (xs[j] < xs[i] or ys[j] > ys[i])
                  for j in range(len(xs)) if j != i)
        if not dom:
            keep.append(i)
    return keep


# ------------------------------------------------------------------ figure A: quality vs cost / latency
OFFS = {  # (dx, dy) label offsets in points, per (panel, system)
    ("cost", "M"): {"jevnoul14": (26, -26), "jev14": (-2, -26), "lunanoul": (0, -17), "luna": (12, -3),
                    "cohere": (-2, 12), "cohere35": (-4, 12), "coherefast": (0, -17)},
    ("cost", "J"): {"jevnoul14": (11, -2), "jev14": (-2, -20), "lunanoul": (0, -16), "luna": (0, -16),
                    "cohere": (-4, 13), "cohere35": (10, 12), "coherefast": (0, -16)},
    ("lat", "M"): {"jevnoul14": (36, -32), "jev14": (-10, -26), "lunanoul": (0, -17), "luna": (0, -16),
                   "cohere": (0, 12), "cohere35": (-6, 13), "coherefast": (0, -17)},
    ("lat", "J"): {"jevnoul14": (11, 0), "jev14": (-8, -22), "lunanoul": (0, -16), "luna": (11, -3),
                   "cohere": (-6, 13), "cohere35": (16, 11), "coherefast": (8, -17)},
}


def panel(ax, ds, kind):
    data = M if ds == "M" else J
    xk = "per_1k" if kind == "cost" else "seq_mean"
    xs = [data[s][xk] for s in SYS]
    ys = [data[s]["ndcg@10"] for s in SYS]
    front = pareto(xs, ys)
    order = sorted(front, key=lambda i: xs[i])
    ax.step([xs[i] for i in order], [ys[i] for i in order], where="post", color="#9a9a9a", lw=1.1,
            ls="--", zorder=1)
    for i, s in enumerate(SYS):
        c, m = STYLE[s]
        lo, hi = data[s]["ndcg_ci"]
        ax.errorbar(xs[i], ys[i], yerr=[[ys[i] - lo], [hi - ys[i]]], fmt="none", ecolor=c, elinewidth=1.2,
                    capsize=2.5, alpha=.85, zorder=2)
        ax.scatter(xs[i], ys[i], s=70, color=c, marker=m, zorder=3,
                   edgecolor="white", linewidth=0.9)
        if i in front:
            ax.scatter(xs[i], ys[i], s=190, facecolor="none", edgecolor="#222", linewidth=1.0, zorder=3)
        dx, dy = OFFS[(kind, ds)][s]
        label = SHORT[s]
        if ds == "M" and s == "jev14":
            continue  # the two Jev points overlap on MIRACL: one shared label
        if ds == "M" and s == "jevnoul14":
            label, dx, dy = "Jev listwise + pointwise", (12 if kind == "cost" else 10), -25
        ha = "center" if dx == 0 else ("left" if dx > 0 else "right")
        if label.startswith("Jev listwise +"):
            ha = "left"
        ax.annotate(label, (xs[i], ys[i]), xytext=(dx, dy), textcoords="offset points", fontsize=9, ha=ha,
                    va="center", color=c if s not in ("luna", "lunanoul") else "#2c6e9e",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85), zorder=5,
                    fontweight="bold" if s in ("jevnoul14", "cohere") else "normal",
                    arrowprops=dict(arrowstyle="-", color="#b0b0b0", lw=0.6, shrinkA=1, shrinkB=5) if (abs(dy) > 14 or abs(dx) > 14) else None)
    ax.set_xlabel("$ per 1,000 queries" if kind == "cost" else "sequential latency, mean (s)")
    if kind == "cost":
        ax.set_xlim(0.4, 3.85)
    else:
        ax.set_xlim(0.35, 1.3)
    lo_y = min(data[s]["ndcg_ci"][0] for s in SYS) - 0.02
    hi_y = max(data[s]["ndcg_ci"][1] for s in SYS) + 0.02
    ax.set_ylim(lo_y, hi_y)
    ax.set_ylabel("nDCG@10" if ds == "M" else "")
    ax.set_title(("MIRACLReranking" if ds == "M" else "JQaRAReranking") +
                 (" \u2014 quality vs. cost" if kind == "cost" else " \u2014 quality vs. latency"), loc="left")


fig, axes = plt.subplots(2, 2, figsize=(8.6, 6.0))
for r, kind in enumerate(("cost", "lat")):
    for c, ds in enumerate(("M", "J")):
        panel(axes[r][c], ds, kind)
from matplotlib.lines import Line2D  # noqa: E402
handles = [
    Line2D([], [], marker="o", color="w", markerfacecolor=NAVY, markersize=9, label="Jev 1.14"),
    Line2D([], [], marker="o", color="w", markerfacecolor=BLUE, markersize=9, label="gpt-6-luna"),
    Line2D([], [], marker="D", color="w", markerfacecolor=ORANGE, markersize=8, label="Cohere Rerank"),
    Line2D([], [], marker="o", color="w", markerfacecolor="#777", markersize=8, label="circle = pointwise"),
    Line2D([], [], marker="s", color="w", markerfacecolor="#777", markersize=8, label="square = listwise"),
    Line2D([], [], marker="o", color="w", markerfacecolor="none", markeredgecolor="#222", markersize=12,
           label="Pareto-optimal (point estimates)"),
]
fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.005), fontsize=9.5)
fig.tight_layout(rect=(0, 0.075, 1, 1), h_pad=2.0, w_pad=1.6)
fig.savefig(FIGS / "quality_cost_latency.svg", format="svg")
plt.close(fig)


# ------------------------------------------------------------------ figure B: score profiles
def mean_sorted(ds, system):
    recs = [r for r in F.read(ds.path_fn(system)) if "error" not in r]
    arr = np.array([sorted(r["scores"].values(), reverse=True) for r in recs])
    return arr.mean(axis=0)


m_ds, _ = F.miracl()
j_ds, _ = F.jqara()
fig, axes = plt.subplots(1, 2, figsize=(7.7, 3.25), sharey=True)
LS = {"jev14": ("-", NAVY, "Jev listwise"), "luna": ("-", BLUE, "luna listwise"),
      "jevnoul14": ("--", NAVY, "Jev pointwise"), "lunanoul": ("--", BLUE, "luna pointwise")}
for ax, ds, name in ((axes[0], m_ds, "MIRACLReranking"), (axes[1], j_ds, "JQaRAReranking")):
    for s, (ls, col, lab) in LS.items():
        y = mean_sorted(ds, s)
        ax.plot(np.arange(1, 101), y, ls=ls, color=col, lw=2.1, label=lab)
    ax.set_xscale("log")
    ax.set_xlim(1, 100)
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100])
    ax.set_xticklabels(["1", "2", "5", "10", "20", "50", "100"])
    ax.set_xlabel("candidate rank by own score (log)", fontsize=10)
    ax.set_title(name, loc="left")
    ax.set_ylim(-0.02, 1.02)
axes[0].set_ylabel("mean score of k-th ranked candidate", fontsize=10)
axes[1].legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#ddd", fontsize=9)
fig.tight_layout()
fig.savefig(FIGS / "score_profile.svg", format="svg")
plt.close(fig)

# ------------------------------------------------------------------ figure C: one real query, presented order
recs_lw = {r["qid"]: r for r in F.read(j_ds.path_fn("jev14")) if "error" not in r}
recs_pw = {r["qid"]: r for r in F.read(j_ds.path_fn("jevnoul14")) if "error" not in r}
cands = []
for qid, r in recs_lw.items():
    npos = sum(v > 0 for v in j_ds.qrels[qid].values())
    support = sum(v > 0 for v in r["scores"].values())
    if 8 <= npos <= 11 and 5 <= support <= 7:
        cands.append(qid)
qid = sorted(cands, key=lambda q: int(q.removeprefix("test_query")))[len(cands) // 2]
presented = F.jqara()[1][qid]  # doc ids in the order the models received them
manifest_q = j_ds.qrels[qid]
for tag, recs, title in (("listwise", recs_lw, "Jev listwise (Choice): probability per passage"),
                         ("pointwise", recs_pw, "Jev pointwise (Noul): P(yes) per passage")):
    fig, ax = plt.subplots(figsize=(5.6, 2.15))
    sc = np.array([recs[qid]["scores"][d] for d in presented])
    pos = np.array([manifest_q[d] > 0 for d in presented])
    ax.bar(np.arange(100), sc, width=0.85, color=np.where(pos, NAVY, "#c9c9c9"), linewidth=0)
    ax.set_xlim(-1, 100)
    ax.set_ylim(0, 1.04)
    ax.set_xlabel("candidate position as presented to the model (0\u201399)", fontsize=9.5)
    ax.set_ylabel("score", fontsize=9.5)
    ax.set_title(title, loc="left", fontsize=10.5)
    ax.tick_params(labelsize=9)
    fig.tight_layout(pad=0.6)
    fig.savefig(FIGS / f"example_{tag}.svg", format="svg")
    plt.close(fig)
EXAMPLE_QID = qid

# ------------------------------------------------------------------ Pareto / price-performance analysis
lines = ["# Price-performance and latency-performance: decision models vs. rerankers\n",
         "Generated by `tech-review/slides/make_figures.py` from `results_final/final.json`. "
         "Quality = nDCG@10; cost = billed $/1K queries; latency = mean service latency, one request at a time. "
         f"Example query used in the slide figures: `{EXAMPLE_QID}` (JQaRA).\n"]
FAM = {"jevnoul14": "decision", "jev14": "decision", "lunanoul": "decision", "luna": "decision",
       "cohere": "reranker", "cohere35": "reranker", "coherefast": "reranker"}
for ds, data, name in (("M", M, "MIRACLReranking"), ("J", J, "JQaRAReranking")):
    for axis, key, unit in (("cost", "per_1k", "$/1Kq"), ("latency", "seq_mean", "s")):
        xs = [data[s][key] for s in SYS]
        ys = [data[s]["ndcg@10"] for s in SYS]
        front = {SYS[i] for i in pareto(xs, ys)}
        lines.append(f"\n## {name}: quality vs. {axis}\n")
        lines.append(f"| system | family | {axis} ({unit}) | nDCG@10 | Pareto-optimal | dominated by (point estimate) | significantly dominated by |")
        lines.append("|---|---|---|---|---|---|---|")
        for s in sorted(SYS, key=lambda s: data[s][key]):
            dom_pt = [t for t in SYS if t != s and data[t][key] <= data[s][key] and data[t]["ndcg@10"] >= data[s]["ndcg@10"]
                      and (data[t][key] < data[s][key] or data[t]["ndcg@10"] > data[s]["ndcg@10"])]
            dom_sig = [t for t in dom_pt if diff(ds, t, s)[1] > 0]
            # also: cheaper/faster-or-equal and significantly better quality, even if point rule above already covers it
            lines.append(f"| {SHORT[s]} | {FAM[s]} | {data[s][key]:.3f} | {data[s]['ndcg@10']:.4f} | "
                         f"{'yes' if s in front else 'no'} | {', '.join(SHORT[t] for t in dom_pt) or '-'} | "
                         f"{', '.join(SHORT[t] for t in dom_sig) or '-'} |")
        fams = {f: [s for s in SYS if FAM[s] == f and s in front] for f in ("decision", "reranker")}
        lines.append(f"\nFrontier members: decision models: {', '.join(SHORT[s] for s in fams['decision']) or 'none'}; "
                     f"rerankers: {', '.join(SHORT[s] for s in fams['reranker']) or 'none'}.")

lines.append("\n## Exchange rate: Jev pointwise vs. Cohere 4-pro\n")
for ds, data, name in (("M", M, "MIRACL"), ("J", J, "JQaRA")):
    d, lo, hi = diff(ds, "jevnoul14", "cohere")
    saved = data["cohere"]["per_1k"] - data["jevnoul14"]["per_1k"]
    faster = data["cohere"]["seq_mean"] - data["jevnoul14"]["seq_mean"]
    lines.append(f"- {name}: nDCG@10 difference {d:+.3f} [{lo:+.3f}, {hi:+.3f}]; Jev pointwise is ${saved:.2f} per 1K queries cheaper "
                 f"and {faster:.2f} s faster per request" +
                 (f" \u2014 i.e. ${saved / (-d * 100):.2f} saved per 0.01 nDCG@10 given up." if d < 0 else
                  " \u2014 better, cheaper and faster (no trade-off)."))
(ROOT / "results_final" / "PARETO.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
print("example query:", EXAMPLE_QID)
