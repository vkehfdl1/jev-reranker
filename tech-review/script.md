# Video script — "Can a Decision Model Rerank?" (1,490 words: ≈11:00 at 135 wpm, ≈9:55 at 150 wpm)

**How to use.** Read it as written; it is meant to sound like a prepared talk, not a casual chat. Do not read the slides: the slides carry the numbers, you carry the reasoning. `[→ N]` means "advance to slide N". The word counts assume about 130–145 words per minute; if your own pace is faster or slower, scale the times.

---

## Slide 1 — Title  (~0:18)

Hello, my name is Dongkyu Kim, and this is my Technology Review for CS410. The title is "Can a Decision Model Rerank?" I compare decision models, such as Jev, with dedicated rerankers on three axes: ranking quality, cost, and latency.

`[→ 2]`

## Slide 2 — Question and thesis  (~0:54)

Search systems typically rank in two stages, and the second stage is usually a dedicated reranker. My question is whether a different kind of model, a decision model, can do that job. A decision model returns a typed answer with probabilities instead of generated text, and Jev from TypeSafe is an example. To answer the question, I tested seven systems on two benchmarks, measuring ranking quality, cost, and latency. The result was more interesting than I expected: the same Jev model loses to Cohere's best reranker on one dataset, 0.750 against 0.793, and wins on the other, 0.885 against 0.819. So the answer is neither a simple yes nor a simple no. In the next ten minutes I will explain why, and what I would actually recommend.

`[→ 3]`

## Slide 3 — Two-stage retrieval  (~0:45)

First, some background. Searching a large corpus is usually done in two stages. The first stage, such as BM25 or dense embeddings, is cheap, and it narrows millions of passages down to about a hundred candidates. The second stage, the reranker, reads the query together with each candidate and puts the candidates in a better order. Two consequences follow. The cost of the reranker grows with the number of candidates, and the final quality can never be better than what the first stage retrieved. This is why the choice of the second stage matters so much for both cost and quality.

`[→ 4]`

## Slide 4 — Bi-encoder versus cross-encoder  (~1:04)

The key difference is between a bi-encoder and a cross-encoder. A bi-encoder, which the first stage uses, encodes the query and each document separately and compares the two vectors. Because a document vector does not depend on the query, it can be computed in advance, and that makes the first stage fast. A cross-encoder puts the query and one passage into the same input, so every query token can attend to every passage token. The relevance judgment is much more precise, but nothing can be precomputed: every pair needs its own forward pass. That is why cross-encoders are used only on the top candidates. Qwen3-Reranker is a good example: it is a language model that reads the probability of the word "yes", and this idea will return shortly. Cohere Rerank is used as the same kind of pointwise scorer, although its internals are not public.

`[→ 5]`

## Slide 5 — LLMs as rerankers  (~0:31)

Language models can also be prompted to rank. In the pointwise style, the model sees one passage at a time and scores it, so every passage is judged independently. In the listwise style, the model sees the whole list and decides among all passages at once. Other variants exist, but these two matter today, because they are exactly the two ways in which a decision model can be used.

`[→ 6]`

## Slide 6 — What a decision model is  (~1:22)

Now, what is a decision model? I use Jev from TypeSafe as the example. Its input is a state, the content to evaluate, plus typed questions. Its output is not text but a typed answer with probabilities: for a Choice question, a probability for every option, and for a Noul question, the probability of "yes". It costs only 0.042 dollars per million input tokens, and output tokens are free.

How is it built? The vendor says it is trained with reinforcement learning for calibrated decisions, so that a probability of 0.8 is right about eighty percent of the time. The architecture and the backbone are not disclosed, so the rest is my own speculation. I believe a decision model is a pretrained language model with a post-training step, whose answer probabilities are read out directly instead of sampling text. Two observations support this: the gpt-6-luna decision model reports zero output tokens, and its price and context length equal those of the regular gpt-6-luna model. If this is right, the backbone matters a great deal, because the quality of the decisions is inherited from it.

`[→ 7]`

## Slide 7 — Using it as a reranker  (~1:00)

To use such a model as a reranker, I tried two modes. In the listwise mode, the query goes into the state, and the hundred passages become the options of one single Choice question. The model returns a probability for every option, and I sort by it. In the pointwise mode, the query and all the passages go into the state, and I ask one hundred Noul questions, such as "Is passage seven relevant?" The probability of "yes" is the score. The figure shows a real query. In listwise mode, only a few passages receive any probability at all, while in pointwise mode every passage receives a graded score. One caveat: because all the passages share one state, this is not strictly pointwise, and I did not compare it with sending one request per passage.

`[→ 8]`

## Slide 8 — Experimental setting  (~0:44)

The setting is simple. I compared seven systems: Jev and gpt-6-luna, each in both modes, and three Cohere rerankers. Every system received the same hundred candidates per query, in the same shuffled order, with one fixed prompt and no tuning. The two datasets differ: MIRACL has 252 queries in 18 languages with about two relevant passages per query, and JQaRA has 1,667 Japanese queries with about ten. The main metric is nDCG at ten, with paired bootstrap tests; cost and latency come directly from the API. Voyage and a few other rerankers were excluded because of rate limits.

`[→ 9]`

## Slide 9 — Ranking quality  (~0:44)

Here is the ranking quality. Each marker is a mean, and each bar is a ninety-five percent interval. On MIRACL, on the left, the Cohere rerankers are at the top, and Jev pointwise is fourth, significantly below Cohere 4-pro. On JQaRA, on the right, the order changes: Jev pointwise is first, by a clear margin, 0.066 above Cohere 4-pro. Cohere 4-pro is the only system that stays in the top two on both datasets, and the gpt-6-luna models are below Jev in the same mode on both. So, in terms of quality alone, there is no stable winner.

`[→ 10]`

## Slide 10 — Price-performance and latency  (~0:58)

Now the practical view: quality against price, and against latency. The circles mark the Pareto-optimal systems, and Jev, in both modes, is on the frontier in all four panels. On JQaRA, Jev pointwise is better than Cohere 4-pro, cheaper by about 1.4 dollars per thousand queries, and faster by 0.4 seconds, so 4-pro is worse on every axis. On MIRACL, Jev gives up 0.044 of nDCG but saves 1.6 dollars per thousand queries, about 37 cents for each 0.01 given up.

The gpt-6-luna decision model is different. In pointwise mode it costs more than Cohere 4-pro and is not better; in listwise mode it is cheaper but the weakest. It is beaten in all four panels. One caution: under sixty-four concurrent requests, Jev's listwise latency increased, so load should be tested.

`[→ 11]`

## Slide 11 — Why pointwise separates better  (~0:48)

Why does pointwise behave so differently from listwise? The chart shows the average score of the k-th ranked candidate. In listwise mode the total probability is one, and it collapses onto about six of the hundred candidates; the other ninety-four tie at zero, so the model cannot order them. This is excellent for finding the top passage, but it gives no ranking below it. In pointwise mode every candidate receives a graded score, so the ordering is much richer. The effect is large on JQaRA, 0.885 against 0.699, and negligible on MIRACL. One warning: the pointwise probability is a ranking score, not the probability that a passage is relevant.

`[→ 12]`

## Slide 12 — Why did the ranking flip?  (~0:26)

Why did the ranking flip? I cannot say for certain, because the two datasets differ in the number of relevant passages, passage truncation, labelling rule, and language, all at once. My hypotheses are that shallow listwise output hurts more when many passages are relevant, and that quiz-style questions may favour a model with world knowledge. Both are untested.

`[→ 13]`

## Slide 13 — Limitations  (~0:28)

There are several limitations. Each system was run once per dataset, with one fixed prompt per mode and no tuning. Most requests were very long, and the vendor says that very long requests run in a slower and less accurate mode, so Jev may be underestimated. Finally, simply fusing two rankings did not help, so this data does not support a hybrid pipeline.

`[→ 14]`

## Slide 14 — Conclusion  (~0:47)

So, what did I learn? First, rankings do not transfer between datasets. Second, a decision model is a score-and-select API, not a drop-in cross-encoder: listwise gives a strong top result, and pointwise gives a real ranking. Third, the price structure matters: Jev sits on the cost frontier, while Cohere 4-pro and gpt-6-luna do not.

My practical conclusion is this. If you already use Jev, or you do not want to operate one more model in your system, Jev is a good choice for reranking. But before you decide, test it on fifty to two hundred of your own queries, with cost and latency in the table.

`[→ 15]`

## Slide 15 — Resources  (~0:14)

The resources I found most useful are listed here, from the original BERT reranking paper to the TypeSafe documentation. All code and raw results are in my repository. Thank you for listening.

---

## Checklist before recording

- Say the numbers that are on the slides only once; do not read tables.
- Where the script says "speculation" (slide 6), say it clearly: it is the part where you give your own opinion.
- Pace checkpoints (135 wpm): slide 6 should end near 4:50, slide 9 near 7:20, the whole talk near 11:00. If you reach slide 10 after about 8:00, shorten slides 12 and 13.
- If you run long, cut in this order: the last sentence of slide 4 (Cohere), the caveat in slide 7, the last sentence of slide 10, slide 12.
