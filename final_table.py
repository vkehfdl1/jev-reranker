"""Final cross-dataset table: MIRACLReranking (252 q) + JQaRAReranking (1,667 q).

  python final_table.py     -> results_final/FINAL.md, results_final/final.json

Inputs (all produced with the latency-fixed client, same systems on both datasets):
  results_miracl_v2/{system}_k100.jsonl (+ seq/ for sequential latency, meta.json for wall)
  results_jqara/{system}.jsonl          (+ {system}_seq.jsonl, meta.json)
Queries without a successful record are scored on the presented order (the no-op fallback).
"""
import json
import random
from pathlib import Path

import numpy as np

import data as D_miracl
import jqara_data as D_jqara
import metrics as M
from jqara_run import shuffled_order

SYSTEMS = ["jevnoul14", "jev14", "lunanoul", "luna", "cohere", "cohere35", "coherefast"]
LABEL = {
    "jevnoul14": "jev-1.14 pointwise (noul)", "jev14": "jev-1.14 listwise (choice)",
    "lunanoul": "gpt-6-luna pointwise (noul)", "luna": "gpt-6-luna listwise (choice)",
    "cohere": "cohere rerank-4-pro", "cohere35": "cohere rerank-v3.5",
    "coherefast": "cohere rerank-4-fast",
}
OUT = Path("results_final")


def read(path: Path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def pct(v, p):
    return v[min(len(v) - 1, int(len(v) * p))]


class Dataset:
    def __init__(self, name, qrels, path_fn, seq_fn, wall_fn, baseline):
        self.name, self.qrels = name, qrels
        self.path_fn, self.seq_fn, self.wall_fn, self.baseline = path_fn, seq_fn, wall_fn, baseline


def miracl():
    """Returns (Dataset, presented): presented = the seeded shuffle every system received."""
    manifest, _ = D_miracl.load_sample()
    qrels, pools, presented = {}, {}, {}
    for q in manifest["queries"]:
        key = f"{q['lang']}:{q['qid']}"
        pool = q["pool"][:100]
        qrels[key], pools[key] = q["rels"], pool
        order = list(range(len(pool)))
        random.Random(f"{q['qid']}|100").shuffle(order)  # same seed as run.run_cell
        presented[key] = [pool[i] for i in order]
    meta = json.loads(Path("results_miracl_v2/meta.json").read_text())
    return Dataset(
        "MIRACLReranking (252 q, 18 langs)", qrels,
        lambda s: Path(f"results_miracl_v2/{s}_k100.jsonl"),
        lambda s: Path(f"results_miracl_v2/seq/{s}_k100.jsonl"),
        lambda s: meta.get(f"{s}_k100", {}).get("wall_s"),
        ("bm25 first-stage order", pools)), presented


def jqara():
    manifest, _ = D_jqara.load()
    qrels, base = {}, {}
    for q in manifest["queries"]:
        qrels[q["qid"]] = q["rels"]
        order = shuffled_order(q["qid"], 100)
        base[q["qid"]] = [q["pool"][i] for i in order]
    meta = json.loads(Path("results_jqara/meta.json").read_text())
    return Dataset(
        "JQaRAReranking (1,667 q, ja)", qrels,
        lambda s: Path(f"results_jqara/{s}.jsonl"),
        lambda s: Path(f"results_jqara/{s}_seq.jsonl"),
        lambda s: meta.get(s, {}).get("wall_s"),
        ("random order (as presented)", base)), base


def evaluate(ds: Dataset, recs, presented):
    """-> per-query metrics {qid: {...}}, sorted latencies, cost, failed count."""
    pq, lat, cost = {}, [], 0.0
    for r in recs:
        if "error" in r:
            continue
        pq[r["qid"]] = M.score_ranking([ds.qrels[r["qid"]][d] for d in r["ranked"]])
        lat.append(r["latency_s"])
        cost += r.get("cost_usd") or 0.0
    failed = {r["qid"] for r in recs} - set(pq)
    for qid in failed:
        order = presented[qid]
        pq[qid] = M.score_ranking([ds.qrels[qid][d] for d in order])
    return pq, sorted(lat), cost, len(failed)


def build(ds: Dataset, presented):
    rows, per_query = {}, {}
    qids = sorted(ds.qrels)
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(qids), size=(10_000, len(qids)))
    for s in SYSTEMS:
        recs = read(ds.path_fn(s))
        pq, lat, cost, failed = evaluate(ds, recs, presented)
        assert set(pq) == set(qids), (ds.name, s, len(pq), len(qids))
        per_query[s] = np.array([pq[q]["ndcg@10"] for q in qids])
        lo, hi = np.percentile(per_query[s][idx].mean(axis=1), [2.5, 97.5])
        seq = sorted(r["latency_s"] for r in read(ds.seq_fn(s)) if "error" not in r)
        wall = ds.wall_fn(s)
        rows[s] = {
            **{m: float(np.mean([pq[q][m] for q in qids])) for m in M.METRICS},
            "ndcg_ci": (float(lo), float(hi)), "failed": failed, "n": len(qids),
            "per_1k": cost / len(lat) * 1000,
            "load_mean": sum(lat) / len(lat), "load_p95": pct(lat, 0.95),
            "seq_mean": sum(seq) / len(seq), "seq_p95": pct(seq, 0.95), "seq_n": len(seq),
            "wall_s": wall, "qps": len(qids) / wall if wall else None}
    bname, bpools = ds.baseline
    base = [M.score_ranking([ds.qrels[q][d] for d in bpools[q]]) for q in qids]
    rows["__baseline__"] = {"name": bname,
                            **{m: float(np.mean([b[m] for b in base])) for m in M.METRICS}}
    pairs = []
    for i, a in enumerate(SYSTEMS):
        for b in SYSTEMS[i + 1:]:
            dv = per_query[a] - per_query[b]
            lo, hi = np.percentile(dv[idx].mean(axis=1), [2.5, 97.5])
            pairs.append((a, b, float(dv.mean()), float(lo), float(hi)))
    return rows, pairs


def fmt_dataset(ds, rows):
    L = [f"### {ds.name}\n",
         "| system | nDCG@10 [95% CI] | nDCG@5 | MAP | MRR@10 | Recall@10 | Hit@1 | $/1Kq "
         "| lat seq mean / p95 | lat 64-way mean / p95 | wall | q/s | failed |",
         "|" + "---|" * 13]
    order = sorted(SYSTEMS, key=lambda s: -rows[s]["ndcg@10"])
    for s in order:
        r = rows[s]
        L.append(f"| {LABEL[s]} | {r['ndcg@10']:.4f} [{r['ndcg_ci'][0]:.3f}, {r['ndcg_ci'][1]:.3f}] "
                 f"| {r['ndcg@5']:.4f} | {r['map']:.4f} | {r['mrr@10']:.4f} | {r['recall@10']:.4f} "
                 f"| {r['hit@1']:.4f} | {r['per_1k']:.3f} "
                 f"| {r['seq_mean']:.2f}s / {r['seq_p95']:.2f}s | {r['load_mean']:.2f}s / {r['load_p95']:.2f}s "
                 f"| {r['wall_s']}s | {r['qps']:.1f} | {r['failed']} |")
    b = rows["__baseline__"]
    L.append(f"| *{b['name']}* | {b['ndcg@10']:.4f} | {b['ndcg@5']:.4f} | {b['map']:.4f} "
             f"| {b['mrr@10']:.4f} | {b['recall@10']:.4f} | {b['hit@1']:.4f} | – | – | – | – | – | – |")
    return L


def main():
    OUT.mkdir(exist_ok=True)
    (m_ds, m_pres), (j_ds, j_pres) = miracl(), jqara()
    m_rows, m_pairs = build(m_ds, {q: p for q, p in m_pres.items()})
    j_rows, j_pairs = build(j_ds, j_pres)

    L = ["# Final results: decision models vs Cohere rerankers on two datasets\n",
         "Same 7 systems, same prompts, K=100, run through the latency-fixed client "
         "(latency = successful HTTP round-trip, no queueing). Voyage is excluded "
         "(heavy 429 rate limiting). `lat seq` = one request at a time (50 queries); "
         "`lat 64-way` = 64 requests in flight (all queries); `failed` queries are scored "
         "on the presented order.\n",
         "## Summary across datasets\n",
         "| system | MIRACL nDCG@10 | JQaRA nDCG@10 | mean | rank M / J | $/1Kq M / J "
         "| seq latency M / J (mean) |", "|" + "---|" * 7]
    mean = {s: (m_rows[s]["ndcg@10"] + j_rows[s]["ndcg@10"]) / 2 for s in SYSTEMS}
    rk = lambda rows: {s: i + 1 for i, s in enumerate(sorted(SYSTEMS, key=lambda s: -rows[s]["ndcg@10"]))}
    mr, jr = rk(m_rows), rk(j_rows)
    for s in sorted(SYSTEMS, key=lambda s: -mean[s]):
        L.append(f"| {LABEL[s]} | {m_rows[s]['ndcg@10']:.4f} | {j_rows[s]['ndcg@10']:.4f} | "
                 f"{mean[s]:.4f} | {mr[s]} / {jr[s]} | {m_rows[s]['per_1k']:.3f} / {j_rows[s]['per_1k']:.3f} "
                 f"| {m_rows[s]['seq_mean']:.2f}s / {j_rows[s]['seq_mean']:.2f}s |")
    L.append("\nmean = unweighted average of the two datasets' nDCG@10.\n")
    L.append("## Per-dataset detail\n")
    L += fmt_dataset(m_ds, m_rows) + [""] + fmt_dataset(j_ds, j_rows)
    for ds, pairs in ((m_ds, m_pairs), (j_ds, j_pairs)):
        L += [f"\n## Paired bootstrap, nDCG@10 (10k resamples): {ds.name}\n",
              "| a − b | Δ | 95% CI | significant |", "|---|---|---|---|"]
        for a, b, d, lo, hi in pairs:
            L.append(f"| {a} − {b} | {d:+.4f} | [{lo:+.4f}, {hi:+.4f}] | {'yes' if lo > 0 or hi < 0 else 'no'} |")
    L += ["\n## Notes\n",
          "- Rank reversal for Jev pointwise: 4th on MIRACL (significantly below cohere 4-pro and "
          "v3.5, tied with cohere 4-fast and Jev listwise) but 1st on JQaRA (+0.066 vs cohere 4-pro).",
          "- cohere rerank-4-pro is the only system in the top 2 on both datasets; v3.5 and 4-fast "
          "are 1st/3rd on MIRACL but 4th/6th on JQaRA.",
          "- gpt-6-luna is significantly below Jev in the same mode on both datasets, at 1.5-3.2x "
          "the $/1Kq (pointwise 3.2x, listwise 1.5-1.9x).",
          "- Pointwise vs listwise: Jev not significant on MIRACL (+0.002, 2.2 positives/query), "
          "+0.186 on JQaRA (9.7 positives/query); luna +0.036 / +0.230.",
          "- Sequential latency: Jev is lowest at 0.46-0.49s (both modes, both datasets); cohere "
          "0.55-0.92s; luna listwise 0.58-0.61s; luna pointwise 1.11-1.14s. Under 64 in flight "
          "Jev listwise on JQaRA degrades to 2.78s mean / 6.84s p95.",
          "- MIRACL was re-run for this table with the latency-fixed client, so quality numbers "
          "differ slightly from the phase-1 REPORT (run-to-run variation, e.g. jev-1.14 pointwise "
          "0.7496 vs 0.7552). MIRACL wall times (2-6s for 252 queries) are short and noisy; HTTP "
          "status counters were not recorded for that run (0 failed queries).",
          "- JQaRA luna listwise wall time (745s) is retry backoff on 5 queries OpenAI refuses "
          "deterministically (502); it is not throughput. Those 5 queries use the fallback order.",
          "- One run per system and dataset. Voyage models excluded: 429 rate limiting "
          "(`results_jqara/SUMMARY.md`, probe)."]
    (OUT / "FINAL.md").write_text("\n".join(L) + "\n")
    (OUT / "final.json").write_text(json.dumps(
        {"miracl": m_rows, "jqara": j_rows, "miracl_pairs": m_pairs, "jqara_pairs": j_pairs}, indent=1))
    print("\n".join(L))


if __name__ == "__main__":
    main()
