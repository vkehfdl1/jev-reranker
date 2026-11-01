"""Benchmark runner + report.

  python run.py run [--systems jev,voyage] [--ks 20,50,100] [--concurrency 64]
                    [--max-queries N] [--langs en,de]
  python run.py report

Results: results/{system}_k{K}.jsonl, one record per query:
  {qid, lang, system, K, ranked, scores, latency_s, cost_usd, tokens, error?}
"""
import argparse
import asyncio
import json
import random
import time
from pathlib import Path

import data as D
import metrics as M
from clients import Client, FatalAPIError

RESULTS = Path("results")

# pinned versions: the ~typesafe/jev-latest alias moved 1.13 -> 1.14 on 2026-10-14
JEV_MODELS = {
    "jev": "typesafe/jev-1.13",        # listwise: one choice over all candidates
    "jevnoul": "typesafe/jev-1.13",    # batched pointwise: one noul per candidate, one request
    "jev14": "typesafe/jev-1.14",
    "jevnoul14": "typesafe/jev-1.14",
    "luna": "openai/gpt-6-luna-decisions",       # same decision primitives, OpenAI model
    "lunanoul": "openai/gpt-6-luna-decisions",
}
RERANK_MODELS = {
    "voyage": "voyageai/rerank-2.5",
    "voyagelite": "voyageai/rerank-2.5-lite",
    "voyage3": "voyageai/rerank-3",
    "voyage3lite": "voyageai/rerank-3-lite",
    "cohere": "cohere/rerank-4-pro",
    "coherefast": "cohere/rerank-4-fast",
    "cohere35": "cohere/rerank-v3.5",
    "qwen3": "qwen/qwen3-reranker-8b",
    "nemotron": "nvidia/nemotron-3.5-rerank-8b:free",
    "nemotronvl": "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
}
# served directly by DeepInfra (needs DEEPINFRA_API_KEY), not via OpenRouter
DEEPINFRA_MODELS = {"diqwen3": "Qwen/Qwen3-Reranker-8B"}

JEV_INSTRUCTIONS = (
    "Which of the listed passages is most relevant to the question given in the "
    "state? A passage is relevant if it contains information that helps answer "
    "the question. Judge topical relevance to the question."
)
JEV_NOUL_INSTRUCTIONS = (
    "Is passage {label} in the state relevant to the question given in the state? "
    "A passage is relevant if it contains information that helps answer the "
    "question. Judge topical relevance to the question."
)

# fallback prices (USD/token) when usage.cost is absent
PRICE = {"jev": 0.042e-6, "voyage": 0.05e-6}


def result_path(system: str, k: int) -> Path:
    return RESULTS / f"{system}_k{k}.jsonl"


def load_done(system: str, k: int) -> dict:
    p = result_path(system, k)
    done = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if "error" not in r:  # errored queries get retried on rerun
                    done[r["qid"]] = r
    return done


async def run_cell(client, system, k, queries, texts, lock):
    path = result_path(system, k)
    done = load_done(system, k)
    todo = [q for q in queries if q["qid"] not in done]
    if not todo:
        print(f"[{system} k={k}] already complete ({len(done)})")
        return
    fout = open(path, "a", encoding="utf-8")
    t0 = time.perf_counter()
    finished = 0
    errors = 0

    async def job(q):
        nonlocal finished, errors
        qid, lang = q["qid"], q["lang"]
        pool = q["pool"][:k]
        # one shared shuffled presentation order for both systems (seeded)
        order = list(range(len(pool)))
        random.Random(f"{qid}|{k}").shuffle(order)
        dids = [pool[i] for i in order]
        ratio = D.TOK_PER_CHAR.get(lang, 0.45)
        cap0 = D.cap_chars(lang, len(dids))
        rec = {"qid": f"{lang}:{qid}", "lang": lang, "system": system, "K": k}
        for shrink in (1.0, 0.6, 0.35):
            cap = int(cap0 * shrink)
            docs = [texts[f"{lang}:{d}"][:cap] for d in dids]
            try:
                if system in JEV_MODELS:
                    labeled = {f"c{i:03d}": doc for i, doc in enumerate(docs)}
                    if "noul" in system:
                        probs, lat, usage = await client.jev_noul_batch(
                            JEV_MODELS[system], q["query"], labeled, JEV_NOUL_INSTRUCTIONS)
                    else:
                        probs, _choice, lat, usage = await client.jev_choice(
                            JEV_MODELS[system], q["query"], labeled, JEV_INSTRUCTIONS)
                    scores = [probs.get(f"c{i:03d}", 0.0) for i in range(len(dids))]
                elif system in DEEPINFRA_MODELS:
                    scores, lat, usage = await client.rerank_deepinfra(
                        DEEPINFRA_MODELS[system], q["query"], docs)
                else:
                    est = (len(q["query"]) + sum(len(x) for x in docs)) * ratio
                    scores, lat, usage = await client.rerank(
                        RERANK_MODELS[system], q["query"], docs, est,
                        pace=system.startswith("voyage"))
                # stable: score desc, ties -> earlier first-stage position
                rank_idx = sorted(range(len(dids)), key=lambda i: (-scores[i], order[i]))
                rec.update(
                    ranked=[dids[i] for i in rank_idx],
                    scores={dids[i]: round(scores[i], 6) for i in range(len(dids))},
                    latency_s=round(lat, 3),
                    cost_usd=usage.get("cost")
                             or (usage.get("input_tokens") or usage.get("total_tokens") or 0)
                             * PRICE.get(system, 0),
                    tokens=usage.get("input_tokens") or usage.get("total_tokens") or 0,
                    char_cap=cap,
                )
                break
            except FatalAPIError as e:
                if "max_tokens_exceeded" in str(e) and shrink != 0.35:
                    continue
                errors += 1
                rec.update(error=str(e)[:300], ranked=dids)
                break
        async with lock:
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()
            finished += 1
            if finished % 25 == 0 or finished == len(todo):
                el = time.perf_counter() - t0
                print(f"[{system} k={k}] {finished}/{len(todo)} "
                      f"({el:.0f}s, {finished/el:.1f} q/s, err={errors})")

    await asyncio.gather(*(job(q) for q in todo))
    fout.close()
    wall = time.perf_counter() - t0
    meta_p = RESULTS / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    meta[f"{system}_k{k}"] = {"wall_s": round(wall, 1), "n_new": len(todo),
                              "errors": errors, "ts": time.time()}
    meta_p.write_text(json.dumps(meta, indent=1))
    print(f"[{system} k={k}] done in {wall:.1f}s, errors={errors}")


async def amain(args):
    manifest, texts = D.load_sample()
    queries = manifest["queries"]
    if args.langs:
        keep = set(args.langs.split(","))
        queries = [q for q in queries if q["lang"] in keep]
    if args.max_queries:
        # round-robin across languages so smoke tests stay multilingual
        by_lang = {}
        for q in queries:
            by_lang.setdefault(q["lang"], []).append(q)
        picked, i = [], 0
        while len(picked) < args.max_queries and any(by_lang.values()):
            for lang in by_lang:
                v = by_lang[lang]
                if i < len(v) and len(picked) < args.max_queries:
                    picked.append(v[i])
            i += 1
        queries = picked
    RESULTS.mkdir(exist_ok=True)
    client = Client(concurrency=args.concurrency)
    lock = asyncio.Lock()
    try:
        for system in args.systems.split(","):
            for k in [int(x) for x in args.ks.split(",")]:
                await run_cell(client, system.strip(), k, queries, texts, lock)
    finally:
        await client.close()


def report():
    manifest, _texts = D.load_sample()
    qrels = {f"{q['lang']}:{q['qid']}": q["rels"] for q in manifest["queries"]}
    qlang = {f"{q['lang']}:{q['qid']}": q["lang"] for q in manifest["queries"]}

    # per-query metric vectors per (system, K) for paired tests
    per_query = {}  # (system, K) -> {qid: {metric: v}}
    rows = []
    for p in sorted(RESULTS.glob("*_k*.jsonl")):
        system, _, k = p.stem.rpartition("_k")
        if not k.isdigit():  # skip probe outputs such as *_k200_fit
            continue
        k = int(k)
        recs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        agg = {m: [] for m in M.METRICS}
        lat, cost, toks, err = [], 0.0, 0, 0
        per_lang = {}
        pq = {}
        for r in recs:
            if "error" in r:
                err += 1
                continue
            rels = [qrels[r["qid"]].get(d, 0) for d in r["ranked"]]
            sm = M.score_ranking(rels)
            pq[r["qid"]] = sm
            for m in M.METRICS:
                agg[m].append(sm[m])
            per_lang.setdefault(r["lang"], []).append(sm["ndcg@10"])
            lat.append(r["latency_s"])
            cost += r.get("cost_usd") or 0
            toks += r.get("tokens") or 0
        n = len(agg["map"])
        if not n:
            continue
        per_query[(system, k)] = pq
        lat_s = sorted(lat)
        rows.append({
            "system": system, "K": k, "n": n, "errors": err,
            **{m: sum(v) / n for m, v in agg.items()},
            "cost_usd": cost, "tokens": toks,
            "lat_mean": sum(lat) / n, "lat_p50": lat_s[n // 2],
            "lat_p95": lat_s[min(n - 1, int(n * 0.95))],
            "per_lang_ndcg10": {l: sum(v) / len(v) for l, v in sorted(per_lang.items())},
        })

    # baseline: first-stage order (top_ranked prefix)
    for k in (20, 50, 100):
        agg = {m: [] for m in M.METRICS}
        per_lang = {}
        for q in manifest["queries"]:
            pool = q["pool"][:k]
            rels = [q["rels"].get(d, 0) for d in pool]
            sm = M.score_ranking(rels)
            for m in M.METRICS:
                agg[m].append(sm[m])
            per_lang.setdefault(q["lang"], []).append(sm["ndcg@10"])
        n = len(agg["map"])
        rows.append({"system": "bm25(first-stage)", "K": k, "n": n, "errors": 0,
                     **{m: sum(v) / n for m, v in agg.items()},
                     "cost_usd": 0, "tokens": 0, "lat_mean": 0, "lat_p50": 0, "lat_p95": 0,
                     "per_lang_ndcg10": {l: sum(v) / len(v) for l, v in sorted(per_lang.items())}})

    (RESULTS / "summary.json").write_text(json.dumps(rows, indent=1))

    lines = ["# jev vs reranker — MIRACLReranking (multilingual, MTEB)\n"]
    lines.append(f"queries: {len(manifest['queries'])} "
                 f"({len(set(qlang.values()))} langs) | dataset: {manifest['dataset']}\n")
    hdr = "| system | K | n | ndcg@5 | ndcg@10 | map | mrr@10 | recall@10 | hit@1 | cost $ | $/1Kq | lat mean | p95 |"
    lines.append(hdr)
    lines.append("|" + "---|" * (hdr.count("|") - 1))
    for r in sorted(rows, key=lambda x: (x["K"], x["system"])):
        per1k = r["cost_usd"] / r["n"] * 1000 if r["n"] else 0
        lines.append(
            f"| {r['system']} | {r['K']} | {r['n']} | {r['ndcg@5']:.4f} | {r['ndcg@10']:.4f} "
            f"| {r['map']:.4f} | {r['mrr@10']:.4f} | {r['recall@10']:.4f} | {r['hit@1']:.4f} "
            f"| {r['cost_usd']:.4f} | {per1k:.3f} | {r['lat_mean']:.2f}s | {r['lat_p95']:.2f}s |")
    lines.append("\n## per-language ndcg@10 (K=100)\n")
    k100 = [r for r in rows if r["K"] == 100]
    langs = sorted({l for r in k100 for l in r["per_lang_ndcg10"]})
    lines.append("| lang | " + " | ".join(r["system"] for r in k100) + " |")
    lines.append("|" + "---|" * (len(k100) + 1))
    for l in langs:
        lines.append(f"| {l} | " + " | ".join(
            f"{r['per_lang_ndcg10'].get(l, float('nan')):.3f}" for r in k100) + " |")
    out = "\n".join(lines)

    # paired bootstrap: voyage - jev per query, per K
    try:
        import numpy as np
        sig = ["\n## significance: paired bootstrap Δ (10k resamples)\n",
               "| K | pair | metric | Δ mean | 95% CI | t |",
               "|---|---|---|---|---|---|"]
        meta_p = RESULTS / "meta.json"
        meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
        systems = sorted({s for (s, _k) in per_query})
        for k in (20, 50, 100):
            for i in range(len(systems)):
                for j in range(i + 1, len(systems)):
                    a, b = per_query.get((systems[i], k)), per_query.get((systems[j], k))
                    if not a or not b:
                        continue
                    qids = sorted(set(a) & set(b))
                    for m in ("ndcg@10",):
                        dv = np.array([b[q][m] - a[q][m] for q in qids])
                        rng = np.random.default_rng(0)
                        boots = rng.choice(dv, size=(10_000, len(dv)), replace=True).mean(axis=1)
                        lo, hi = np.percentile(boots, [2.5, 97.5])
                        t = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv)) + 1e-12)
                        sig.append(f"| {k} | {systems[j]} − {systems[i]} | {m} | "
                                   f"{dv.mean():+.4f} | [{lo:+.4f}, {hi:+.4f}] | {t:.2f} |")
        sig.append("\nwall-clock for 252 queries (64-way concurrent): "
                   + ", ".join(f"{cell}: {v['wall_s']}s"
                               for cell, v in sorted(meta.items())))
        out += "\n".join(sig) + "\n"
    except Exception as e:  # significance section is additive; never break report
        out += f"\n(significance skipped: {e})\n"

    (RESULTS / "REPORT.md").write_text(out)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--systems", default="jev,voyage")
    pr.add_argument("--ks", default="20,50,100")
    pr.add_argument("--concurrency", type=int, default=64)
    pr.add_argument("--max-queries", type=int, default=0)
    pr.add_argument("--langs", default="")
    pr.add_argument("--out", default="results")
    sub.add_parser("report").add_argument("--out", default="results")
    args = ap.parse_args()
    RESULTS = Path(args.out)  # module global read by run_cell/report
    if args.cmd == "run":
        asyncio.run(amain(args))
    else:
        report()
