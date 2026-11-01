# jev vs reranker benchmark

Is [Jev](https://openrouter.ai/typesafe/jev-1.13) (TypeSafe System One decision model)
competitive with a dedicated reranker ([voyageai/rerank-2.5](https://openrouter.ai/voyageai/rerank-2.5))
on a standard multilingual reranking benchmark? Both called via OpenRouter.

## Setup

- **Dataset**: `mteb/MIRACLReranking` (MTEB multilingual reranking; 18 languages,
  100 candidates/query with binary qrels, first-stage BM25 order included).
  Stratified sample: 14 queries/lang × 18 langs = **252 queries, 25,200 query–passage
  pairs** at K=100 (seed 42, `data_cache/sample.json`).
- **Protocol**: per query, candidate pool = BM25 top-K (K ∈ {20, 50, 100}); both systems
  see the same seeded shuffle of the pool; each reorders it. Metrics: ndcg@5/10, MAP,
  MRR@10, recall@10, hit@1 vs qrels. Baseline = original BM25 order.
- **Jev listwise** (`jev`, `jev14`): one `choice` decision per query — `state={"question": ...}`,
  criteria = `{c000..: passage}`; rank by per-choice probability (ties → original BM25 position).
  Probabilities sum to 1 across candidates.
- **Jev batched pointwise** (`jevnoul`, `jevnoul14`): one request per query, passages in
  `state`, one independent `noul` (yes/no) question per passage; rank by P(yes). Each score
  is independent (0–1), same price as listwise (passages sent once, output tokens free).
- Jev versions are pinned (`typesafe/jev-1.13`, `typesafe/jev-1.14`); the
  `~typesafe/jev-latest` alias moved to 1.14 on 2026-10-14.
- **Rerankers**: pointwise `/api/v1/rerank`, rank by `relevance_score`. All 10 rerank models
  on OpenRouter (voyage 2.5/2.5-lite/3/3-lite, cohere 4-pro/4-fast/v3.5, qwen3-reranker-8b,
  two free nvidia nemotron rerankers).
- Passages truncated per language/K to fit jev's 32K context (see `data.cap_chars`;
  same text for both systems). Voyage requests are token-paced at ~5M tokens/min.
  The limit is upstream at Voyage, not OpenRouter: on 2026-10-22, unpaced 64-way bursts
  ran a full K=100 cell (4.25M tokens) in 4.6-11s, and the third back-to-back cell got
  429 "project's TPM rate limit of 12,000,000 tokens per minute for rerank-2.5-lite".
  Cohere rerankers (per-call billing) showed no 429s at 252 concurrent requests.

## Reproduce

```bash
uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python datasets httpx numpy rank_bm25 tenacity
export OPENROUTER_API_KEY=...
.venv/bin/python data.py 14          # download + sample -> data_cache/
.venv/bin/python data.py stats       # length/positive stats
.venv/bin/python run.py run --concurrency 64        # full run (~2-3 min, <$1)
.venv/bin/python run.py run --max-queries 6         # smoke
.venv/bin/python run.py report       # -> results/REPORT.md + summary.json
```

## Latest results (252 queries, 0 errors, K=100)

| system | ndcg@10 | recall@10 | hit@1 | $/1Kq | lat mean | 252q wall |
|---|---|---|---|---|---|---|
| bm25 | 0.4427 | – | 0.3413 | – | – | – |
| nvidia nemotron-3.5-rerank-8b (free) | 0.8121 | 0.9252 | 0.7381 | $0 | 136s | 282s |
| qwen3-reranker-8b | 0.8061 | 0.9070 | 0.7619 | $4.886 | 80s | 294s |
| qwen3-reranker-8b via DeepInfra direct | 0.8010 | 0.9038 | 0.7500 | $1.216 | 106s | 180s |
| voyage rerank-2.5 | 0.7989 | 0.9064 | 0.7302 | $0.844 | 0.95s | 77.2s |
| voyage rerank-3 | 0.7971 | 0.9049 | 0.7421 | $0.844 | 0.61s | 55.5s |
| cohere rerank-v3.5 | 0.7949 | 0.9078 | 0.7222 | $1.000 | 2.10s | 5.3s |
| cohere rerank-4-pro | 0.7929 | 0.8870 | 0.7460 | $2.500 | 2.32s | 4.1s |
| nvidia llama-nemotron-rerank-vl-1b (free) | 0.7852 | 0.8867 | 0.7262 | $0 | 44s | 290s |
| voyage rerank-2.5-lite | 0.7794 | 0.8887 | 0.7103 | $0.338 | 0.60s | 55.4s |
| voyage rerank-3-lite | 0.7647 | 0.8801 | 0.6825 | $0.338 | 0.61s | 56.5s |
| jev 1.14 batched pointwise | 0.7552 | 0.8562 | 0.6944 | $0.890 | 1.49s | 2.6s |
| cohere rerank-4-fast | 0.7539 | 0.8857 | 0.6508 | $2.000 | 2.61s | 5.2s |
| jev 1.13 batched pointwise | 0.7485 | 0.8488 | 0.6944 | $0.890 | 1.60s | 2.6s |
| jev 1.14 listwise | 0.7463 | 0.8566 | 0.6786 | $0.715 | 1.45s | 2.5s |
| jev 1.13 listwise | 0.7337 | 0.8503 | 0.6627 | $0.715 | 0.96s | 1.7s |

Paired bootstrap (ndcg@10): batched pointwise vs listwise is not significant for either Jev
version (+0.015 on 1.13, +0.009 on 1.14; CIs cross 0). Every reranker except cohere
rerank-4-fast beats jev 1.13 batched pointwise significantly (voyage rerank-2.5 +0.050).
Batched pointwise turns Jev into a pre-filter: P(yes) ≥ 0.5 keeps 15.1 docs/query with
85% of qrels positives, vs 0.81 docs/query and 27% for listwise.
Pricing: voyage/qwen bill per token, cohere per search unit (rerank-4-pro $0.0025,
4-fast $0.002, v3.5 $0.001 per ≤100 docs), nvidia free tiers are rate-limited (~0.9 q/s).
The same Qwen3-Reranker-8B costs $4.886/1Kq via OpenRouter (Fireworks, $0.20/M) and
$1.216/1Kq on DeepInfra direct ($0.05/M, `diqwen3`, needs `DEEPINFRA_API_KEY`);
quality difference is not significant (−0.005, CI crosses 0).
Jev listwise rows from 1.13 were run 2026-10-02, DeepInfra on 2026-10-23, everything else
2026-10-22.

**Full report with charts (radar + per-axis bars + per-language): `results/report.html`**
(regenerate: `.venv/bin/python report_html.py`). Markdown tables: `results/REPORT.md`.

## Phase 2: JQaRA (1,667 queries) — jev vs gpt-6-luna decisions vs fast rerankers

Second dataset (`mteb/JQaRAReranking`, 100 untruncated candidates/query, 9.7 positives/query)
with cost and per-query latency as first-class outputs; only rerankers that can be called
quickly without rate limiting. Setup, reranker-selection probe, results and caveats:
**`results_jqara/SUMMARY.md`** (full tables + pairwise bootstrap: `results_jqara/REPORT.md`).

| system | ndcg@10 | hit@1 | $/1Kq | latency seq / 64-way |
|---|---|---|---|---|
| jev-1.14 pointwise | 0.8849 | 0.930 | 1.141 | 0.49s / 1.25s |
| cohere rerank-4-pro | 0.8191 | 0.925 | 2.500 | 0.92s / 1.05s |
| gpt-6-luna pointwise | 0.8077 | 0.853 | 3.585 | 1.11s / 1.27s |
| cohere rerank-v3.5 | 0.7014 | 0.867 | 1.000 | 0.55s / 1.58s |
| jev-1.14 listwise | 0.6992 | 0.935 | 0.967 | 0.47s / 2.78s |
| voyage rerank-2.5-lite | 0.6899 | 0.863 | 0.387 | 0.59s / 1.90s (2,237 × 429) |
| cohere rerank-4-fast | 0.6860 | 0.861 | 2.000 | 0.72s / 1.09s |
| gpt-6-luna listwise | 0.5778 | 0.939 | 1.802 | 0.61s / 0.93s (5 queries refused) |

```bash
.venv/bin/python jqara_data.py                                  # -> data_cache_jqara/
.venv/bin/python jqara_run.py run --systems jev14,jevnoul14,luna,lunanoul,cohere,coherefast,cohere35,voyagelite --concurrency 64
.venv/bin/python jqara_run.py latency --systems <same> --max-queries 50   # sequential latency
.venv/bin/python jqara_run.py report                            # -> results_jqara/REPORT.md
```

Latency in phase 2 times only the successful HTTP round-trip; the phase-1 numbers above
included harness queueing (`clients.Client._post` was fixed after phase 1), so latencies
are not comparable across phases.

## Final table (MIRACL + JQaRA, 7 systems, voyage excluded)

`results_final/FINAL.md` (generated by `final_table.py`): same systems and prompts on both
datasets, latency-fixed client. MIRACL was re-run into `results_miracl_v2/` for this
(`run.py run --out results_miracl_v2 --ks 100`).

| system | MIRACL nDCG@10 | JQaRA nDCG@10 | mean | $/1Kq M / J | seq latency M / J |
|---|---|---|---|---|---|
| jev-1.14 pointwise | 0.7496 | 0.8849 | 0.8173 | 0.890 / 1.141 | 0.47s / 0.49s |
| cohere rerank-4-pro | 0.7931 | 0.8191 | 0.8061 | 2.500 / 2.500 | 0.89s / 0.92s |
| gpt-6-luna pointwise | 0.7159 | 0.8077 | 0.7618 | 2.885 / 3.585 | 1.14s / 1.11s |
| cohere rerank-v3.5 | 0.7949 | 0.7014 | 0.7482 | 1.000 / 1.000 | 0.56s / 0.55s |
| jev-1.14 listwise | 0.7479 | 0.6992 | 0.7235 | 0.715 / 0.967 | 0.46s / 0.47s |
| cohere rerank-4-fast | 0.7517 | 0.6860 | 0.7189 | 2.000 / 2.000 | 0.68s / 0.72s |
| gpt-6-luna listwise | 0.6804 | 0.5778 | 0.6291 | 1.102 / 1.802 | 0.58s / 0.61s |

## Files

- `data.py` — dataset download, sampling, length stats, token-budget caps
- `clients.py` — async OpenRouter clients (retry/backoff, voyage TPM token bucket,
  Jev choice + batched noul) plus DeepInfra native rerank
- `metrics.py` — ndcg/map/mrr/recall
- `run.py` — runner (resumable JSONL cells) + report (paired bootstrap significance)
- `report_html.py` — 3-axis HTML report generator (inline SVG, self-contained)
- `results/` — raw per-query rankings + REPORT.md + report.html
- `jqara_data.py`, `jqara_run.py` — phase-2 dataset loader and runner/report
- `results_jqara/` — phase-2 raw rankings, `SUMMARY.md`, `REPORT.md`, `probe/` (reranker selection)
