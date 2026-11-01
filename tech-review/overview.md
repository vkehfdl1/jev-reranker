# Overview Submission Draft

> TextData submission: title `Overview of Decision-Model Reranking vs Cross-Encoder Rerankers: Quality, Cost and Latency on Two Datasets`
> Body must be ≥ 100 words and contain `#pin`. The draft below is the English text to post (~390 words).
> Every number is from `results_final/FINAL.md` (K=100, one run per system and dataset).

---

## Overview of Decision-Model Reranking vs Cross-Encoder Rerankers: Quality, Cost and Latency on Two Datasets

**What it is.** Reranking is the second stage of a retrieval pipeline: a cheap first stage (BM25 or dense embeddings) returns about 100 candidates and a slower model reorders them. Dedicated rerankers such as Cohere Rerank and Qwen3-Reranker score each (query, passage) pair, in the tradition of the BERT cross-encoder. A *decision model* such as TypeSafe's Jev or OpenAI's gpt-6-luna-decisions is different: it does not generate text but returns a typed answer with probabilities (Choice: a distribution over options; Noul: the probability of "yes"). Asking "which passage is most relevant?" (listwise) or "is passage *i* relevant?" (batched pointwise) and sorting by probability turns it into a reranker.

**Background.** Neural reranking started with BERT cross-encoders (Nogueira & Cho, 2019) and sequence-to-sequence rankers such as monoT5, and moved to LLM prompting: pointwise, pairwise (PRP), listwise (RankGPT) and setwise. Decision models are a 2026 addition; OpenRouter lists 22 of them from 13 makers behind one Decisions API.

**Why it is useful.** Anyone building search or RAG must choose a second stage under three constraints: ranking quality, cost per query and latency. This review measures all three. I compared seven systems (Jev 1.14 and gpt-6-luna in both modes, Cohere rerank-4-pro, 4-fast and v3.5) with the same 100 shuffled candidates per query on MIRACLReranking (252 queries, 18 languages) and JQaRAReranking (1,667 Japanese queries), using billed cost, sequential and under-load latency, and paired bootstrap tests.

**What I found.** There is no single winner. On MIRACL, Cohere 4-pro beats Jev pointwise (nDCG@10 0.793 vs 0.750). On JQaRA the order reverses (Jev 0.885 vs Cohere 0.819). Jev costs $0.89 to $1.14 per 1,000 queries against $2.50 for Cohere 4-pro, and answers in about 0.47 s sequentially. Listwise mode gives excellent top-1 accuracy but returns non-zero probabilities for only about six candidates, so it cannot order the rest. gpt-6-luna was significantly worse than Jev in the same mode on both datasets and cost 1.5 to 3.2 times more. Simple rank fusion of two systems did not help.

**How this review differs.** The related review "LLM Rerankers as a Second Stage over BM25" (https://textdata.org/submissions/6ae0097ca8567d79c2f76fb9) surveys LLM-based reranking. This one adds an original, reproducible benchmark that compares decision models with cross-encoder rerankers on cost and latency as well as quality, explains how each family works, and states what the evidence does and does not show.

`#pin`

---

## 작성 노트 (제출용 아님)

- 공식 지시문 요건: define / background / why useful 포함, 100단어 이상, `#pin`. 겹치는 기존 리뷰가 있으면 링크하고 차별점 설명 — 위 마지막 문단이 그 요건이다 (삭제 금지).
- 숫자 출처: `results_final/FINAL.md`. 문장별 대응
  - Cohere 4-pro 0.793 vs Jev pointwise 0.750 (MIRACL), 0.885 vs 0.819 (JQaRA)
  - $0.89–1.14 (Jev pointwise, MIRACL/JQaRA) vs $2.50 (Cohere 4-pro)
  - 순차 지연 0.47s (Jev pointwise)
  - "about six candidates": Jev listwise support 평균 6.5 / 6.0 (`ANALYSIS.md` A)
  - luna 1.5~3.2배 비용: listwise 1.5~1.9배, pointwise 3.2배 (`FINAL.md` 비용 열)
  - rank fusion: `ANALYSIS.md` C (JQaRA에서는 유의하게 나쁨, MIRACL에서는 차이 없음)
- "22 models from 13 makers": OpenRouter Jev guide (2026-10-16 기준, 벤더 문서) — 제출 시 날짜가 바뀌었으면 "more than twenty"로 완화.
- 이전 초안에서 삭제한 주장: "decision model이 mid-tier reranker와 동급이고 가격 절반", "lowest wall-clock", "pre-filter 15%/85%", "hybrid가 sweet spot". 모두 새 데이터로 지지되지 않거나 측정 아티팩트였다.
