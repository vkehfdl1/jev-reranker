"""Phase-2 benchmark on JQaRA (see jqara_data.py): decision models vs fast rerankers.

  python jqara_run.py run --systems jev14,jevnoul14,luna,lunanoul,cohere --concurrency 64
                          [--max-queries N] [--out results_jqara]
  python jqara_run.py latency --systems ... [--n 50]     # sequential, unloaded latency
  python jqara_run.py report

Every system sees all 100 candidates per query, untruncated, in the same seeded shuffle.
Result: {out}/{system}.jsonl, one record per query:
  {qid, system, ranked, scores, latency_s, cost_usd, tokens, error?}
latency_s = service latency of the final successful HTTP call (queueing excluded, see
clients.Client._post).
"""
import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import jqara_data as D
import metrics as M
from clients import Client, FatalAPIError
from run import DEEPINFRA_MODELS, JEV_INSTRUCTIONS, JEV_NOUL_INSTRUCTIONS, RERANK_MODELS

RESULTS = Path("results_jqara")

# decision-API systems: (primitive, model). `jev*` are pinned to 1.14 (alias moved 2026-10-14).
DECISION_MODELS = {
    "jev14": ("choice", "typesafe/jev-1.14"),
    "jevnoul14": ("noul", "typesafe/jev-1.14"),
    "luna": ("choice", "openai/gpt-6-luna-decisions"),
    "lunanoul": ("noul", "openai/gpt-6-luna-decisions"),
}


def shuffled_order(qid: str, n: int) -> list[int]:
    order = list(range(n))
    random.Random(f"{qid}|{n}").shuffle(order)
    return order


def load_done(path: Path) -> dict:
    done = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "error" not in r:  # errored queries are retried on rerun
                    done[r["qid"]] = r
    return done


async def score_query(client, system, q, texts):
    """Returns (rec fields, presented order) for one query."""
    order = shuffled_order(q["qid"], len(q["pool"]))
    dids = [q["pool"][i] for i in order]
    docs = [texts[d] for d in dids]
    if system in DECISION_MODELS:
        kind, model = DECISION_MODELS[system]
        labeled = {f"c{i:03d}": doc for i, doc in enumerate(docs)}
        if kind == "noul":
            probs, lat, usage = await client.jev_noul_batch(
                model, q["query"], labeled, JEV_NOUL_INSTRUCTIONS)
        else:
            probs, _choice, lat, usage = await client.jev_choice(
                model, q["query"], labeled, JEV_INSTRUCTIONS)
        scores = [probs.get(f"c{i:03d}", 0.0) for i in range(len(dids))]
    elif system in DEEPINFRA_MODELS:
        scores, lat, usage = await client.rerank_deepinfra(
            DEEPINFRA_MODELS[system], q["query"], docs)
    else:
        scores, lat, usage = await client.rerank(RERANK_MODELS[system], q["query"], docs)
    # stable: score desc, ties -> presented (shuffled) position
    rank_idx = sorted(range(len(dids)), key=lambda i: (-scores[i], i))
    return dict(
        ranked=[dids[i] for i in rank_idx],
        scores={dids[i]: round(scores[i], 6) for i in range(len(dids))},
        latency_s=round(lat, 4),
        cost_usd=usage.get("cost"),
        tokens=usage.get("input_tokens") or usage.get("total_tokens") or 0,
    ), dids


async def run_cell(client, system, queries, texts, out: Path, tag: str = ""):
    path = out / f"{system}{tag}.jsonl"
    done = load_done(path)
    todo = [q for q in queries if q["qid"] not in done]
    if not todo:
        print(f"[{system}] already complete ({len(done)})")
        return
    fout = open(path, "a", encoding="utf-8")
    lock = asyncio.Lock()
    stats0 = dict(client.stats)
    t0 = time.perf_counter()
    finished = errors = 0

    async def job(q):
        nonlocal finished, errors
        rec = {"qid": q["qid"], "system": system}
        try:
            fields, _ = await score_query(client, system, q, texts)
            rec.update(fields)
        except FatalAPIError as e:
            errors += 1
            rec.update(error=str(e)[:300])
        async with lock:
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()
            finished += 1
            if finished % 100 == 0 or finished == len(todo):
                el = time.perf_counter() - t0
                print(f"[{system}] {finished}/{len(todo)} ({el:.0f}s, {finished/el:.1f} q/s, "
                      f"err={errors})", flush=True)

    await asyncio.gather(*(job(q) for q in todo))
    fout.close()
    wall = time.perf_counter() - t0
    http = {str(k): v - stats0.get(k, 0) for k, v in client.stats.items()
            if v - stats0.get(k, 0)}
    meta_p = out / f"meta{tag}.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    # a resumed run (retrying errored queries) adds to the earlier totals
    prev = meta.get(system, {"wall_s": 0.0, "n_new": 0, "http": {}})
    merged_http = {k: prev["http"].get(k, 0) + http.get(k, 0)
                   for k in {*prev["http"], *http}}
    meta[system] = {"wall_s": round(prev["wall_s"] + wall, 1), "n_new": prev["n_new"] + len(todo),
                    "errors": errors, "http": merged_http, "ts": time.time()}
    meta_p.write_text(json.dumps(meta, indent=1))
    print(f"[{system}] done in {wall:.1f}s errors={errors} http={http}", flush=True)


def select_queries(manifest, max_queries: int, stride: bool = False):
    qs = manifest["queries"]
    if max_queries:
        step = max(1, len(qs) // max_queries) if stride else 1
        qs = qs[::step][:max_queries]
    return qs


async def amain(args):
    manifest, texts = D.load()
    queries = select_queries(manifest, args.max_queries, stride=args.cmd == "latency")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    conc = 1 if args.cmd == "latency" else args.concurrency
    tag = "_seq" if args.cmd == "latency" else ""
    client = Client(concurrency=conc)
    try:
        for system in args.systems.split(","):
            await run_cell(client, system.strip(), queries, texts, out, tag)
    finally:
        await client.close()


def _pct(sorted_v, p):
    return sorted_v[min(len(sorted_v) - 1, int(len(sorted_v) * p))]


def report(out: Path):
    import numpy as np
    manifest, _ = D.load()
    qs = {q["qid"]: q for q in manifest["queries"]}
    meta = json.loads((out / "meta.json").read_text()) if (out / "meta.json").exists() else {}
    meta_seq = (json.loads((out / "meta_seq.json").read_text())
                if (out / "meta_seq.json").exists() else {})

    def evaluate(recs):
        """Queries with no successful record are scored on the presented (shuffled) order —
        the no-op fallback a production caller would use — so every system covers all
        queries; latency/cost use successful calls only."""
        pq, lat, cost, toks, miss = {}, [], 0.0, 0, 0
        for r in recs:
            if "error" in r:
                continue
            pq[r["qid"]] = M.score_ranking([qs[r["qid"]]["rels"][d] for d in r["ranked"]])
            lat.append(r["latency_s"])
            toks += r.get("tokens") or 0
            if r.get("cost_usd") is None:
                miss += 1
            else:
                cost += r["cost_usd"]
        failed = {r["qid"] for r in recs} - set(pq)
        for qid in failed:
            q = qs[qid]
            order = shuffled_order(qid, len(q["pool"]))
            pq[qid] = M.score_ranking([q["rels"][q["pool"][i]] for i in order])
        return pq, sorted(lat), cost, toks, miss, len(failed)

    rows, per_query = [], {}
    for p in sorted(out.glob("*.jsonl")):
        if p.stem.endswith("_seq"):
            continue
        recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        pq, lat, cost, toks, miss, failed = evaluate(recs)
        n, n_ok = len(pq), len(lat)
        if not n:
            continue
        system = p.stem
        per_query[system] = pq
        row = {"system": system, "n": n, "errors": failed,
               "cost_missing": miss,
               **{m: float(np.mean([v[m] for v in pq.values()])) for m in M.METRICS},
               "cost_usd": cost, "per_1k": cost / n_ok * 1000, "tokens": toks,
               "lat_mean": sum(lat) / n_ok, "lat_p50": _pct(lat, 0.5),
               "lat_p95": _pct(lat, 0.95), "lat_p99": _pct(lat, 0.99),
               "wall_s": meta.get(system, {}).get("wall_s"),
               "http": meta.get(system, {}).get("http", {})}
        sp = out / f"{system}_seq.jsonl"
        if sp.exists():
            sq = [json.loads(l) for l in sp.read_text().splitlines() if l.strip()]
            _, slat, _, _, _, _ = evaluate(sq)
            if slat:
                row.update(seq_n=len(slat), seq_mean=sum(slat) / len(slat),
                           seq_p50=_pct(slat, 0.5), seq_p95=_pct(slat, 0.95))
        rows.append(row)

    # baseline: the shuffled presentation order every system received
    base = {}
    for qid, q in qs.items():
        order = shuffled_order(qid, len(q["pool"]))
        base[qid] = M.score_ranking([q["rels"][q["pool"][i]] for i in order])
    per_query["random-order"] = base
    rows.append({"system": "random-order", "n": len(base),
                 **{m: float(np.mean([v[m] for v in base.values()])) for m in M.METRICS}})
    rows.sort(key=lambda r: -r["ndcg@10"])

    rng = np.random.default_rng(0)
    nq = len(qs)
    idx = rng.integers(0, nq, size=(10_000, nq))
    qids = sorted(qs)

    def vec(system):
        return np.array([per_query[system][q]["ndcg@10"] for q in qids])

    for r in rows:
        if r["system"] in per_query and len(per_query[r["system"]]) == nq:
            lo, hi = np.percentile(vec(r["system"])[idx].mean(axis=1), [2.5, 97.5])
            r["ndcg_ci"] = (float(lo), float(hi))

    L = [f"# Phase 2: {D.NAME} — decision models vs fast rerankers\n",
         f"queries: {nq} | candidates/query: 100 (untruncated, same seeded shuffle for every "
         "system) | positives/query: "
         f"{np.mean([sum(v > 0 for v in q['rels'].values()) for q in qs.values()]):.1f}\n",
         "Latency columns: service latency of the successful HTTP call (queueing excluded), "
         "measured while 64 requests were in flight (`load`) and one at a time (`seq`).\n",
         "| system | n | err | ndcg@10 [95% CI] | ndcg@5 | map | mrr@10 | recall@10 | hit@1 "
         "| $/1Kq | lat load mean / p50 / p95 | lat seq mean / p50 / p95 | wall (n q) | q/s |",
         "|" + "---|" * 14]
    for r in rows:
        ci = r.get("ndcg_ci")
        ci_s = f" [{ci[0]:.4f}, {ci[1]:.4f}]" if ci else ""
        if r["system"] == "random-order":
            L.append(f"| random-order | {r['n']} | 0 | {r['ndcg@10']:.4f}{ci_s} | {r['ndcg@5']:.4f} "
                     f"| {r['map']:.4f} | {r['mrr@10']:.4f} | {r['recall@10']:.4f} "
                     f"| {r['hit@1']:.4f} | – | – | – | – | – |")
            continue
        seq = (f"{r['seq_mean']:.2f}s / {r['seq_p50']:.2f}s / {r['seq_p95']:.2f}s"
               if "seq_mean" in r else "–")
        qps = f"{r['n'] / r['wall_s']:.1f}" if r["wall_s"] else "–"
        L.append(f"| {r['system']} | {r['n']} | {r['errors']} | {r['ndcg@10']:.4f}{ci_s} "
                 f"| {r['ndcg@5']:.4f} | {r['map']:.4f} | {r['mrr@10']:.4f} "
                 f"| {r['recall@10']:.4f} | {r['hit@1']:.4f} | {r['per_1k']:.3f} "
                 f"| {r['lat_mean']:.2f}s / {r['lat_p50']:.2f}s / {r['lat_p95']:.2f}s | {seq} "
                 f"| {r['wall_s']}s ({r['n']}) | {qps} |")
    L.append("\n## HTTP outcomes per system (status code -> count, 429 = rate limit)\n")
    for r in rows:
        if r.get("http") is not None and r["system"] != "random-order":
            L.append(f"- {r['system']}: {r['http']} (cost field missing on "
                     f"{r['cost_missing']} records)")

    systems = [r["system"] for r in rows if len(per_query.get(r["system"], {})) == nq
               and r["system"] != "random-order"]
    L += ["\n## paired bootstrap on ndcg@10 (10k resamples): row − column\n",
          "| pair | Δ mean | 95% CI | significant |", "|---|---|---|---|"]
    for i, a in enumerate(systems):
        for b in systems[i + 1:]:
            dv = vec(a) - vec(b)
            lo, hi = np.percentile(dv[idx].mean(axis=1), [2.5, 97.5])
            L.append(f"| {a} − {b} | {dv.mean():+.4f} | [{lo:+.4f}, {hi:+.4f}] "
                     f"| {'yes' if lo > 0 or hi < 0 else 'no'} |")
    text = "\n".join(L) + "\n"
    (out / "REPORT.md").write_text(text)
    (out / "summary.json").write_text(json.dumps(rows, indent=1))
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "latency"):
        sp = sub.add_parser(name)
        sp.add_argument("--systems", required=True)
        sp.add_argument("--concurrency", type=int, default=64)
        sp.add_argument("--max-queries", type=int, default=50 if name == "latency" else 0)
        sp.add_argument("--out", default=str(RESULTS))
    pr = sub.add_parser("report")
    pr.add_argument("--out", default=str(RESULTS))
    a = ap.parse_args()
    if a.cmd == "report":
        report(Path(a.out))
    else:
        asyncio.run(amain(a))
