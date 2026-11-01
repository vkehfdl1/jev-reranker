"""LLM-as-a-judge relevance labels for calibrating jev thresholds.

Judges a stratified union of query-passage pairs from the K=100 pool with an
independent judge model (2026+ release, via OpenRouter), then the analysis
computes P(relevant | jev score >= t) against judge verdicts.

Two modes:
  default — K=100 truncated chunks, topical-relevance prompt (v1; too lenient)
  --full  — full document text + strict answer-bearing prompt (v2; primary)

Strata (deduped union):
  A  all pairs with jev score >= 0.01            (exact precision for t>=0.01)
  B  all qrels-positive pairs                    (recall + judge validation)
  C  all pairs with 0 < score < 0.01             (boundary band)
  D  1,500 random pairs with score == 0          (negative base rate)

Same truncated texts as the K=100 run (cap_chars(lang, 100)) so labels align
with the jev scores being calibrated.

Writes results/judge_relevance.jsonl (resumable) + results/judge_meta.json.
"""
import asyncio
import json
import random
import sys
import time
from pathlib import Path

import data as D
from clients import Client, FatalAPIError

RESULTS = Path("results")
JUDGE_MODEL = "anthropic/claude-haiku-5.5"
K = 100
CONC = 32

PROMPT = """Question: {q}

Passage: {doc}

Does the passage contain the specific information the question asks for? Relevant means it actually helps answer the question — merely sharing the topic is not enough. Reply with exactly `true` or `false`."""


def build_tasks():
    jev = {}
    for line in (RESULTS / "jev_k100.jsonl").read_text().splitlines():
        r = json.loads(line)
        if "error" not in r:
            jev[r["qid"]] = r
    manifest = json.loads(Path("data_cache/sample.json").read_text())
    qlang = {f"{q['lang']}:{q['qid']}": q for q in manifest["queries"]}
    texts = json.loads(Path("data_cache/texts.json").read_text())

    tasks = {}
    for fq, rec in jev.items():
        q = qlang[fq]
        for d, s in rec["scores"].items():
            pos = q["rels"].get(d, 0) > 0
            if s >= 0.01 or pos:
                tasks[(fq, d)] = (s, pos, "A/B")
    for fq, rec in jev.items():
        q = qlang[fq]
        for d, s in rec["scores"].items():
            if 0 < s < 0.01:
                tasks.setdefault((fq, d), (s, q["rels"].get(d, 0) > 0, "C"))
    zeros = [(fq, d) for fq, rec in jev.items()
             for d, s in rec["scores"].items() if s == 0]
    random.Random(42).shuffle(zeros)
    for fq, d in zeros[:1500]:
        q = qlang[fq]
        tasks.setdefault((fq, d), (0.0, q["rels"].get(d, 0) > 0, "D"))
    # attach lang + doc text
    out = []
    for (fq, d), (s, pos, strat) in tasks.items():
        q = qlang[fq]
        cap = D.cap_chars(q["lang"], K)
        out.append({"qid": fq, "doc": d, "lang": q["lang"], "query": q["query"],
                    "text": texts[f"{q['lang']}:{d}"][:cap], "s": s,
                    "qrel": pos, "stratum": strat})
    return out


FULL_TEXTS = json.loads(Path("data_cache/texts.json").read_text())


async def amain(limit, full=False):
    tasks = build_tasks()
    if full:  # judge the whole document, not the K=100 truncated chunk
        for t in tasks:
            t["text"] = FULL_TEXTS[t["qid"].split(":")[0] + ":" + t["doc"]]
    if limit:
        tasks = tasks[:limit]
    out_p = RESULTS / ("judge_relevance_full.jsonl" if full else "judge_relevance.jsonl")
    done = set()
    if out_p.exists():
        for line in out_p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("judge") is not None:
                    done.add((r["qid"], r["doc"]))
    todo = [t for t in tasks if (t["qid"], t["doc"]) not in done]
    print(f"tasks={len(tasks)} done={len(done)} todo={len(todo)}", flush=True)
    fout = open(out_p, "a", encoding="utf-8")
    lock = asyncio.Lock()
    t0 = time.perf_counter()
    finished = errors = parse_fails = 0

    client = Client(concurrency=CONC)
    try:
        async def job(t):
            nonlocal finished, errors, parse_fails
            prompt = PROMPT.format(q=t["query"], doc=t["text"])
            judge, raw = None, ""
            try:
                j = await client._post("/api/v1/chat/completions", {
                    "model": JUDGE_MODEL, "temperature": 0, "max_tokens": 8,
                    "reasoning": {"enabled": False},
                    "messages": [{"role": "user", "content": prompt}]})
                raw = (j["choices"][0]["message"]["content"] or "").strip().lower()
                if raw.startswith("true"):
                    judge = True
                elif raw.startswith("false"):
                    judge = False
            except FatalAPIError as e:
                errors += 1
                raw = f"FATAL: {e}"
            if judge is None:
                parse_fails += 1
            rec = {k: t[k] for k in ("qid", "doc", "lang", "s", "qrel", "stratum")}
            rec.update(judge=judge, raw=raw[:120])
            async with lock:
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fout.flush()
                finished += 1
                if finished % 250 == 0 or finished == len(todo):
                    el = time.perf_counter() - t0
                    print(f"judge {finished}/{len(todo)} ({el:.0f}s, "
                          f"err={errors}, unparsed={parse_fails})", flush=True)

        await asyncio.gather(*(job(t) for t in todo))
    finally:
        await client.close()
        fout.close()
    wall = time.perf_counter() - t0
    meta = {"model": JUDGE_MODEL, "n": len(todo), "errors": errors,
            "parse_fails": parse_fails, "wall_s": round(wall, 1), "full": full}
    (RESULTS / "judge_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta), flush=True)


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    asyncio.run(amain(limit, full="--full" in sys.argv))