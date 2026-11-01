# Phase 2 — JQaRA: decision models vs fast rerankers

Run 2026-11-01 (OpenRouter, `jqara_run.py`). Full tables incl. all pairwise bootstrap tests:
`REPORT.md` (generated), raw per-query records: `*.jsonl`, run metadata: `meta.json`,
`meta_seq.json`. Reranker selection probe: `probe/`.

## Problem

Phase 1 (MIRACLReranking, 252 queries, `results/REPORT.md`) found dedicated rerankers ahead of
Jev, and a cost/latency picture clouded by harness artifacts. Phase 2 repeats the comparison
on a ~2K-query dataset with (a) richer relevance labels, (b) no truncation, (c) gpt-6-luna
decision added, (d) only rerankers that can be called quickly, and (e) cost and per-query
latency measured as first-class outputs.

## Setting

| | |
|---|---|
| Dataset | `mteb/JQaRAReranking` test: **1,667 queries**, 100 candidates each, binary qrels, 9.7 positives/query (Japanese quiz-style QA over Wikipedia passages) |
| Why this one | MTEB reranking sets near 2K queries: VoyageMMarcoReranking (2,048 q, 26 cands, 1.06 pos/q), AlloprofReranking (2,316 q, 10.8 cands, 1.3 pos/q), JQaRA (1,667 q, 100 cands, 9.7 pos/q). JQaRA keeps K=100 like phase 1 and has ~4x more positives per query, so nDCG@10 is far less noisy |
| Input | all 100 passages per query, **untruncated** (≤427 chars each, ≈23K tokens/query on average; worst case 35K chars accepted by Jev 1.14 and luna) |
| Order | same seeded shuffle for every system (`shuffled_order`); ties → presented position. The HF ids (`apositive_*`) and given order leak labels and are never sent |
| Decision models (`/api/alpha/decisions`) | `jev14` = typesafe/jev-1.14 listwise `choice`; `jevnoul14` = jev-1.14 batched pointwise `noul`; `luna` = openai/gpt-6-luna-decisions `choice`; `lunanoul` = same model, batched `noul`. Prompts identical to phase 1 |
| Rerankers | cohere rerank-4-pro (`cohere`), rerank-4-fast (`coherefast`), rerank-v3.5 (`cohere35`), voyage rerank-2.5-lite (`voyagelite`) via OpenRouter `/api/v1/rerank` |
| Load | 64 concurrent requests, 1,667 queries per system. Separate sequential pass (concurrency 1, 50 evenly strided queries) for unloaded latency |
| Latency definition | service latency of the final successful HTTP round-trip. Excludes harness queueing and retry backoff (`clients.Client._post`) |
| Cost | `usage.cost` returned by OpenRouter, summed over successful calls (0 records missing it) |
| Stats | paired bootstrap, 10k resamples, over queries; per-system 95% CI on ndcg@10 |
| Failed queries | scored on the presented (random) order — the no-op fallback — so every system covers all 1,667 queries |

### Reranker selection (probe, `probe/`, first 600 queries, unpaced, 64 concurrent)

Requirement: fast and no rate limiting.

| model | probe wall (600 q) | 429s in probe | decision |
|---|---|---|---|
| cohere rerank-4-pro / 4-fast / v3.5 | 11.4 / 9.2 / 8.1s | 0 | selected |
| voyage rerank-2.5-lite | 23.5s | 0 | selected, but **hit 2,237 429s in the full 1,667-query run** (rate limit appears at sustained volume) |
| voyage rerank-2.5 / 3 / 3-lite | 94 / 195 / 65s | 1105 / 2150 / 875 | excluded (rate-limited) |
| qwen3-reranker-8b via OpenRouter (100 q) | 89s | 393 × 503 | excluded |
| qwen3-reranker-8b via DeepInfra (100 q) | 188s | 449 × 429 | excluded |
| nvidia nemotron (free) | not probed | – | excluded: free tier throttled to ~0.9 q/s in phase 1 |

Only the three Cohere models were clean at scale; voyage-lite is kept as the 4th reranker with
its rate limiting reported, because no other reranker on OpenRouter qualified.

## Results (1,667 queries, K=100)

| system | ndcg@10 [95% CI] | hit@1 | mrr@10 | recall@10 | $/1Kq | latency, 64 in flight (mean / p95) | latency, sequential (mean / p95) | wall, 1,667 q | HTTP errors |
|---|---|---|---|---|---|---|---|---|---|
| **jev-1.14 pointwise** (`jevnoul14`) | **0.8849** [0.876, 0.894] | 0.930 | 0.954 | 0.763 | 1.141 | 1.25s / 5.01s | 0.49s / 0.64s | 33s | none |
| cohere rerank-4-pro | 0.8191 [0.809, 0.829] | 0.925 | 0.948 | 0.692 | 2.500 | 1.05s / 1.73s | 0.92s / 1.24s | 29s | 1 × 503 |
| gpt-6-luna pointwise (`lunanoul`) | 0.8077 [0.797, 0.818] | 0.853 | 0.910 | 0.692 | 3.585 | 1.27s / 1.87s | 1.11s / 1.43s | 34s | none |
| cohere rerank-v3.5 | 0.7014 [0.690, 0.712] | 0.867 | 0.909 | 0.585 | 1.000 | 1.58s / 4.05s | 0.55s / 0.64s | 44s | none |
| jev-1.14 listwise (`jev14`) | 0.6992 [0.689, 0.709] | **0.935** | **0.956** | 0.547 | 0.967 | 2.78s / 6.84s | 0.47s / 0.54s | 75s | none |
| voyage rerank-2.5-lite | 0.6899 [0.678, 0.701] | 0.863 | 0.905 | 0.567 | **0.387** | 1.90s / 6.06s | 0.59s / 0.68s | 152s | 2,237 × 429 |
| cohere rerank-4-fast | 0.6860 [0.675, 0.697] | 0.861 | 0.903 | 0.566 | 2.000 | 1.09s / 3.09s | 0.72s / 0.97s | 30s | none |
| gpt-6-luna listwise (`luna`) | 0.5778 [0.568, 0.588] | **0.939** | 0.955 | 0.431 | 1.802 | 0.93s / 1.88s | 0.61s / 0.85s | 745s* | 5 queries refused |
| random order | 0.1138 | 0.099 | 0.219 | 0.102 | – | – | – | – | – |

\* luna listwise wall time is dominated by retry backoff on 5 queries on which OpenAI returns
`502 "OpenAI refused to answer question rank"` deterministically (10 tries each, twice); it is
not a throughput figure. Those 5 queries are scored with the fallback order. The 5 are
test_query123/144/482/1017/1179 (harmless quiz questions). `luna` $/1Kq is over the 1,662
successful calls.

Significance (paired bootstrap, ndcg@10; all pairs in `REPORT.md`):
- jev-1.14 pointwise beats every other system significantly: +0.066 vs cohere-4-pro
  [+0.059, +0.073], +0.077 vs gpt-6-luna pointwise [+0.070, +0.084].
- cohere-4-pro > luna pointwise (+0.011 [+0.003, +0.020]), small but significant.
- Not distinguishable: cohere v3.5 vs jev listwise (+0.002), jev listwise vs voyage-lite
  (+0.009), voyage-lite vs cohere-4-fast (+0.004).
- Pointwise vs listwise within the same model: jev +0.186, luna +0.230 ndcg@10, both
  significant. Listwise is best on hit@1/mrr@10 (top-1 pick) but its probability mass
  covers few candidates, so ranks beyond the first handful are essentially presented order.

## Observations

- Reversal vs phase 1: on MIRACL (2.2 positives/query, truncated passages) dedicated
  rerankers beat Jev pointwise significantly; on JQaRA Jev pointwise is first. Same Jev
  model, same prompt. Dataset/label density and truncation differ; one run per dataset
  cannot tell which factor matters.
- Pareto on (ndcg@10, $/1Kq): voyage-lite (cheapest, 0.690) and jev pointwise (best, 0.885
  at $1.14). cohere-4-pro costs 2.2x as much for −0.066 ndcg@10. All other points are
  dominated.
- gpt-6-luna costs 3.1x jev pointwise per query ($0.10/M vs $0.042/M input, plus ~32% more
  tokens counted) for −0.077 ndcg@10 pointwise.
- Latency: sequentially every system is 0.47–1.11s. With 64 requests in flight jev listwise
  degrades most (0.47 → 2.78s mean, p95 6.84s), cohere-4-pro least (0.92 → 1.05s). Throughput
  at 64-way: 22–58 q/s except voyage-lite (11 q/s, 429 backoff) and luna listwise.
- Rate limits: only voyage hit 429 at this volume; the 600-query probe missed it for
  voyage-lite (0 × 429) but the 1,667-query run did not — probe-sized runs under-report it.

## Caveats

- One dataset, one language (Japanese), one run per system; no repeated trials, so
  run-to-run latency variance is not measured.
- JQaRA contamination is not ruled out for any model (training data unknown; not checked).
  I did not verify from the dataset code how JQaRA positives were labelled; treat qrels
  as given.
- Phase-1 latency numbers (`results/`) were measured with the old client, which included
  semaphore wait in `latency_s`; they are not comparable to the numbers here. Phase-1 quality
  numbers are unaffected.
- Failed queries (luna listwise, 5) count as the fallback order in ndcg; excluding them
  would raise luna's mean slightly.
- Voyage 2.5/3 (non-lite) and qwen3 were not benchmarked at full scale because they failed
  the no-rate-limit criterion; probe numbers on 600/100 queries are in `probe/REPORT.md`
  (voyage-3 0.766, voyage-2.5 0.750, qwen3 0.790 on 100 q) and are not comparable to the
  full-run rows.
