"""Data loading for the jev-vs-reranker benchmark.

Dataset: mteb/MIRACLReranking (MTEB multilingual reranking).
Per language configs: {lang}-queries / -corpus / -qrels / -top_ranked, split=dev.
top_ranked gives the first-stage (BM25) top-100 candidate order per query;
qrels label every candidate 0/1.

Artifacts written to data_cache/:
  sample.json  - sampled queries with their top-100 pools + relevance labels
  texts.json   - passage texts for every candidate in the sample ("lang:did" -> text)
"""
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from datasets import load_dataset

LANGS = ["ar", "bn", "de", "en", "es", "fa", "fi", "fr", "hi",
         "id", "ja", "ko", "ru", "sw", "te", "th", "yo", "zh"]

CACHE = Path("data_cache")
SAMPLE_PATH = CACHE / "sample.json"
TEXTS_PATH = CACHE / "texts.json"

# rough tokens-per-char upper bounds for budget fitting (conservative)
TOK_PER_CHAR = {"zh": 1.0, "ja": 1.0, "ko": 0.9, "th": 1.0,
                "hi": 0.9, "bn": 1.0, "te": 1.1,
                "ar": 0.6, "fa": 0.6, "yo": 0.6, "ru": 0.6}


def _load(kind: str, lang: str):
    return load_dataset("mteb/MIRACLReranking", f"{lang}-{kind}", split="dev")


def build_sample(per_lang: int = 14, seed: int = 42, min_cands: int = 100):
    """Sample queries per language, persist pools + qrels + texts."""
    manifest = {"seed": seed, "per_lang": per_lang, "dataset": "mteb/MIRACLReranking",
                "queries": []}
    texts = {}

    def load_lang(lang):
        # per-language RNG: deterministic regardless of thread scheduling
        rng = random.Random(f"{seed}:{lang}")
        queries = {r["_id"]: r["text"] for r in _load("queries", lang)}
        top = {r["query-id"]: list(r["corpus-ids"]) for r in _load("top_ranked", lang)}
        qrels = {}
        for r in _load("qrels", lang):
            qrels.setdefault(r["query-id"], {})[r["corpus-id"]] = int(r["score"])
        # eligible: full 100-candidate pool with >=1 positive inside
        eligible = [q for q in queries
                    if len(top.get(q, [])) >= min_cands
                    and any(qrels.get(q, {}).get(d, 0) > 0 for d in top[q][:min_cands])]
        picked = rng.sample(sorted(eligible), min(per_lang, len(eligible)))
        need = {d for q in picked for d in top[q][:min_cands]}
        corpus = {}
        for r in _load("corpus", lang):
            if r["_id"] in need:
                t = (r["title"].strip() + "\n" + r["text"]) if r["title"] else r["text"]
                corpus[r["_id"]] = t
        return lang, queries, top, qrels, picked, corpus, len(eligible)

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(load_lang, LANGS))

    for lang, queries, top, qrels, picked, corpus, n_elig in results:
        missing = [d for q in picked for d in top[q][:min_cands] if d not in corpus]
        assert not missing, f"{lang}: {len(missing)} candidate texts missing"
        for q in picked:
            pool = top[q][:min_cands]
            manifest["queries"].append({
                "qid": q, "lang": lang, "query": queries[q],
                "pool": pool,
                "rels": {d: qrels[q].get(d, 0) for d in pool},
            })
        for d, t in corpus.items():
            texts[f"{lang}:{d}"] = t
        print(f"{lang}: eligible={n_elig} picked={len(picked)}")

    CACHE.mkdir(exist_ok=True)
    SAMPLE_PATH.write_text(json.dumps(manifest, ensure_ascii=False))
    TEXTS_PATH.write_text(json.dumps(texts, ensure_ascii=False))
    npairs = sum(len(q["pool"]) for q in manifest["queries"])
    print(f"sampled {len(manifest['queries'])} queries, {npairs} pairs, "
          f"{len(texts)} texts -> {SAMPLE_PATH}, {TEXTS_PATH}")


def load_sample():
    manifest = json.loads(SAMPLE_PATH.read_text())
    texts = json.loads(TEXTS_PATH.read_text())
    return manifest, texts


def cap_chars(lang: str, k: int, budget_tokens: int = 24000) -> int:
    """Per-passage char cap so k passages fit ~budget_tokens (worst case)."""
    r = TOK_PER_CHAR.get(lang, 0.45)
    return max(200, min(1500, int(budget_tokens / k / r)))


def stats():
    manifest, texts = load_sample()
    import numpy as np
    by_lang = {}
    for q in manifest["queries"]:
        lens = [len(texts[f"{q['lang']}:{d}"]) for d in q["pool"]]
        by_lang.setdefault(q["lang"], []).extend(lens)
    print(f"{'lang':5} {'n':>6} {'p50':>6} {'p90':>6} {'p99':>6} {'max':>7} {'cap@100':>8}")
    for lang in LANGS:
        v = np.array(by_lang.get(lang, [0]))
        print(f"{lang:5} {len(v):>6} {np.percentile(v,50):>6.0f} {np.percentile(v,90):>6.0f} "
              f"{np.percentile(v,99):>6.0f} {v.max():>7} {cap_chars(lang,100):>8}")
    qpos = [sum(1 for s in q["rels"].values() if s > 0) for q in manifest["queries"]]
    print("positives in top-100 pool: mean", sum(qpos) / len(qpos),
          "min", min(qpos), "max", max(qpos))
    qpos20 = [sum(1 for d in q["pool"][:20] if q["rels"][d] > 0) for q in manifest["queries"]]
    qpos50 = [sum(1 for d in q["pool"][:50] if q["rels"][d] > 0) for q in manifest["queries"]]
    print("positives in top-20:", sum(qpos20) / len(qpos20),
          "| top-50:", sum(qpos50) / len(qpos50),
          "| queries with 0 pos in top20:", sum(1 for x in qpos20 if x == 0))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats()
    else:
        per = int(sys.argv[1]) if len(sys.argv) > 1 else 14
        build_sample(per_lang=per)
