"""Phase-2 dataset: mteb/JQaRAReranking (Japanese quiz-style QA, test split).

1,667 queries x exactly 100 candidates, binary qrels (mean 9.7 positives/query).
Passages are <= 427 chars, so they are sent untruncated to every system.

Caveat: the HF candidate ids are `apositive_*` / `negative_*` and top_ranked lists the
positives first. Ids and the given order are never sent to a model; every system sees
the same seeded shuffle (jqara_run.shuffled_order).

Artifacts (data_cache_jqara/):
  manifest.json - {"dataset", "queries": [{qid, query, pool, rels}]}
  texts.json    - candidate id -> passage text
"""
import json
from pathlib import Path

from datasets import load_dataset

NAME = "mteb/JQaRAReranking"
CACHE = Path("data_cache_jqara")
MANIFEST_PATH = CACHE / "manifest.json"
TEXTS_PATH = CACHE / "texts.json"


def build():
    queries = {r["id"]: r["text"] for r in load_dataset(NAME, "queries", split="test")}
    top = {r["query-id"]: list(r["corpus-ids"])
           for r in load_dataset(NAME, "top_ranked", split="test")}
    rels: dict[str, dict[str, int]] = {}
    for r in load_dataset(NAME, "qrels", split="test"):
        rels.setdefault(r["query-id"], {})[r["corpus-id"]] = int(r["score"])
    corpus = {r["id"]: ((r["title"].strip() + "\n" + r["text"]) if r["title"] else r["text"])
              for r in load_dataset(NAME, "corpus", split="test")}

    manifest = {"dataset": NAME, "queries": []}
    texts = {}
    for qid in sorted(queries, key=lambda x: int(x.removeprefix("test_query"))):
        pool = top[qid]
        assert len(pool) == 100 and all(d in corpus for d in pool), qid
        manifest["queries"].append({
            "qid": qid, "query": queries[qid], "pool": pool,
            "rels": {d: rels.get(qid, {}).get(d, 0) for d in pool}})
        texts.update({d: corpus[d] for d in pool})
    CACHE.mkdir(exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False))
    TEXTS_PATH.write_text(json.dumps(texts, ensure_ascii=False))
    npos = sum(sum(v > 0 for v in q["rels"].values()) for q in manifest["queries"])
    print(f"{len(manifest['queries'])} queries, {len(texts)} passages, {npos} positives "
          f"-> {CACHE}/")


def load():
    return json.loads(MANIFEST_PATH.read_text()), json.loads(TEXTS_PATH.read_text())


if __name__ == "__main__":
    build()
