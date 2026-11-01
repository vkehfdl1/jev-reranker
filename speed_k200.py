"""K=200 speed probe: jev vs OpenRouter rerankers on a synthetic 200-doc pool.

MIRACLReranking caps at 100 candidates/query, so the 200-pool is the real
top-100 plus one duplicate copy (same texts, fresh labels) — a latency/
throughput proxy, NOT a quality measurement.

Two configs per system:
  fit  — budget-fit caps: cap_chars(lang, 200); total tokens ~ K=100 level
  long — K=100 caps kept: 2x tokens (jev auto-shrinks on 32K overflow)

Writes results/{system}_k200_{cfg}.jsonl + results/speed_k200_meta.json.
"""
import asyncio
import json
import random
import time
from pathlib import Path

import data as D
from clients import Client, FatalAPIError
from run import JEV_MODELS, RERANK_MODELS, JEV_INSTRUCTIONS, PRICE

JEV_MODEL = JEV_MODELS["jev14"]  # the 2026-10-22 probe ran on the alias, which served 1.14

RESULTS = Path("results")
K = 200
CONC = 64


async def run_cell(client, system, cfg, queries, texts):
    path = RESULTS / f"{system}_k200_{cfg}.jsonl"
    fout = open(path, "w", encoding="utf-8")
    lock = asyncio.Lock()
    t0 = time.perf_counter()
    finished = errors = 0
    tok_sum = 0

    async def job(q):
        nonlocal finished, errors, tok_sum
        qid, lang = q["qid"], q["lang"]
        pool = q["pool"][:100]
        dids = pool + pool  # synthetic 200-pool
        order = list(range(len(dids)))
        random.Random(f"{qid}|k200{cfg}").shuffle(order)
        dids = [dids[i] for i in order]
        ratio = D.TOK_PER_CHAR.get(lang, 0.45)
        cap0 = D.cap_chars(lang, K if cfg == "fit" else 100)
        rec = {"qid": f"{lang}:{qid}", "lang": lang, "system": system,
               "K": K, "cfg": cfg}
        for shrink in (1.0, 0.6, 0.35):
            cap = int(cap0 * shrink)
            docs = [texts[f"{lang}:{d}"][:cap] for d in dids]
            try:
                if system == "jev":
                    options = {f"c{i:03d}": doc for i, doc in enumerate(docs)}
                    probs, _choice, lat, usage = await client.jev_choice(
                        JEV_MODEL, q["query"], options, JEV_INSTRUCTIONS)
                    scores = [probs.get(f"c{i:03d}", 0.0) for i in range(len(dids))]
                else:
                    est = (len(q["query"]) + sum(len(x) for x in docs)) * ratio
                    scores, lat, usage = await client.rerank(
                        RERANK_MODELS[system], q["query"], docs, est,
                        pace=system == "voyage")
                rank_idx = sorted(range(len(dids)), key=lambda i: (-scores[i], order[i]))
                tok = usage.get("input_tokens") or usage.get("total_tokens") or 0
                rec.update(
                    ranked=[dids[i] for i in rank_idx],
                    scores={dids[i]: round(scores[i], 6) for i in range(len(dids))},
                    latency_s=round(lat, 3),
                    cost_usd=usage.get("cost") or tok * PRICE.get(system, 0),
                    tokens=tok, char_cap=cap)
                async with lock:
                    tok_sum += tok
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
            if finished % 50 == 0 or finished == len(queries):
                el = time.perf_counter() - t0
                print(f"[{system} {cfg}] {finished}/{len(queries)} "
                      f"({el:.0f}s, err={errors})", flush=True)

    await asyncio.gather(*(job(q) for q in queries))
    fout.close()
    wall = time.perf_counter() - t0
    return {"system": system, "cfg": cfg, "wall_s": round(wall, 1),
            "n": len(queries), "errors": errors, "tok_sum": tok_sum}


async def amain():
    manifest, texts = D.load_sample()
    queries = manifest["queries"]
    client = Client(concurrency=CONC)
    metas = []
    try:
        for cfg in ("fit", "long"):
            for system in ("jev", "voyage", "cohere"):
                m = await run_cell(client, system, cfg, queries, texts)
                metas.append(m)
                print(json.dumps(m), flush=True)
    finally:
        await client.close()
    (RESULTS / "speed_k200_meta.json").write_text(json.dumps(metas, indent=1))


if __name__ == "__main__":
    asyncio.run(amain())