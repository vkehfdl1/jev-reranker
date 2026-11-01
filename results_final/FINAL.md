# Final results: decision models vs Cohere rerankers on two datasets

Same 7 systems, same prompts, K=100, run through the latency-fixed client (latency = successful HTTP round-trip, no queueing). Voyage is excluded (heavy 429 rate limiting). `lat seq` = one request at a time (50 queries); `lat 64-way` = 64 requests in flight (all queries); `failed` queries are scored on the presented order.

## Summary across datasets

| system | MIRACL nDCG@10 | JQaRA nDCG@10 | mean | rank M / J | $/1Kq M / J | seq latency M / J (mean) |
|---|---|---|---|---|---|---|
| jev-1.14 pointwise (noul) | 0.7496 | 0.8849 | 0.8173 | 4 / 1 | 0.890 / 1.141 | 0.47s / 0.49s |
| cohere rerank-4-pro | 0.7931 | 0.8191 | 0.8061 | 2 / 2 | 2.500 / 2.500 | 0.89s / 0.92s |
| gpt-6-luna pointwise (noul) | 0.7159 | 0.8077 | 0.7618 | 6 / 3 | 2.885 / 3.585 | 1.14s / 1.11s |
| cohere rerank-v3.5 | 0.7949 | 0.7014 | 0.7482 | 1 / 4 | 1.000 / 1.000 | 0.56s / 0.55s |
| jev-1.14 listwise (choice) | 0.7479 | 0.6992 | 0.7235 | 5 / 5 | 0.715 / 0.967 | 0.46s / 0.47s |
| cohere rerank-4-fast | 0.7517 | 0.6860 | 0.7189 | 3 / 6 | 2.000 / 2.000 | 0.68s / 0.72s |
| gpt-6-luna listwise (choice) | 0.6804 | 0.5778 | 0.6291 | 7 / 7 | 1.102 / 1.802 | 0.58s / 0.61s |

mean = unweighted average of the two datasets' nDCG@10.

## Per-dataset detail

### MIRACLReranking (252 q, 18 langs)

| system | nDCG@10 [95% CI] | nDCG@5 | MAP | MRR@10 | Recall@10 | Hit@1 | $/1Kq | lat seq mean / p95 | lat 64-way mean / p95 | wall | q/s | failed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cohere rerank-v3.5 | 0.7949 [0.763, 0.825] | 0.7544 | 0.7269 | 0.8198 | 0.9078 | 0.7222 | 1.000 | 0.56s / 0.66s | 0.94s / 1.57s | 4.7s | 53.6 | 0 |
| cohere rerank-4-pro | 0.7931 [0.760, 0.825] | 0.7582 | 0.7367 | 0.8281 | 0.8870 | 0.7460 | 2.500 | 0.89s / 1.16s | 1.11s / 1.73s | 5.1s | 49.4 | 0 |
| cohere rerank-4-fast | 0.7517 [0.718, 0.784] | 0.7069 | 0.6821 | 0.7653 | 0.8857 | 0.6389 | 2.000 | 0.68s / 0.92s | 0.88s / 1.51s | 4.2s | 60.0 | 0 |
| jev-1.14 pointwise (noul) | 0.7496 [0.714, 0.784] | 0.7187 | 0.6905 | 0.7744 | 0.8537 | 0.6706 | 0.890 | 0.47s / 0.53s | 0.56s / 0.91s | 2.5s | 100.8 | 0 |
| jev-1.14 listwise (choice) | 0.7479 [0.713, 0.781] | 0.7042 | 0.6844 | 0.7811 | 0.8616 | 0.6746 | 0.715 | 0.46s / 0.56s | 0.54s / 0.82s | 2.3s | 109.6 | 0 |
| gpt-6-luna pointwise (noul) | 0.7159 [0.678, 0.752] | 0.6860 | 0.6521 | 0.7537 | 0.8238 | 0.6389 | 2.885 | 1.14s / 1.57s | 1.20s / 1.68s | 5.5s | 45.8 | 0 |
| gpt-6-luna listwise (choice) | 0.6804 [0.641, 0.719] | 0.6508 | 0.6196 | 0.7502 | 0.7639 | 0.6429 | 1.102 | 0.58s / 0.73s | 0.81s / 1.50s | 3.9s | 64.6 | 0 |
| *bm25 first-stage order* | 0.4427 | 0.3962 | 0.3920 | 0.4638 | 0.5780 | 0.3413 | – | – | – | – | – | – |

### JQaRAReranking (1,667 q, ja)

| system | nDCG@10 [95% CI] | nDCG@5 | MAP | MRR@10 | Recall@10 | Hit@1 | $/1Kq | lat seq mean / p95 | lat 64-way mean / p95 | wall | q/s | failed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jev-1.14 pointwise (noul) | 0.8849 [0.876, 0.894] | 0.8939 | 0.8536 | 0.9538 | 0.7632 | 0.9298 | 1.141 | 0.49s / 0.64s | 1.25s / 5.01s | 33.3s | 50.1 | 0 |
| cohere rerank-4-pro | 0.8191 [0.809, 0.829] | 0.8345 | 0.7749 | 0.9478 | 0.6924 | 0.9250 | 2.500 | 0.92s / 1.24s | 1.05s / 1.73s | 28.7s | 58.1 | 0 |
| gpt-6-luna pointwise (noul) | 0.8077 [0.797, 0.818] | 0.8240 | 0.7371 | 0.9096 | 0.6924 | 0.8530 | 3.585 | 1.11s / 1.43s | 1.27s / 1.87s | 34.2s | 48.7 | 0 |
| cohere rerank-v3.5 | 0.7014 [0.690, 0.712] | 0.7298 | 0.6324 | 0.9086 | 0.5853 | 0.8674 | 1.000 | 0.55s / 0.64s | 1.58s / 4.05s | 44.1s | 37.8 | 0 |
| jev-1.14 listwise (choice) | 0.6992 [0.689, 0.709] | 0.7957 | 0.5912 | 0.9564 | 0.5473 | 0.9352 | 0.967 | 0.47s / 0.54s | 2.78s / 6.84s | 75.0s | 22.2 | 0 |
| cohere rerank-4-fast | 0.6860 [0.675, 0.697] | 0.7114 | 0.6125 | 0.9031 | 0.5664 | 0.8608 | 2.000 | 0.72s / 0.97s | 1.09s / 3.09s | 29.9s | 55.8 | 0 |
| gpt-6-luna listwise (choice) | 0.5778 [0.568, 0.588] | 0.6607 | 0.4794 | 0.9547 | 0.4308 | 0.9394 | 1.802 | 0.61s / 0.85s | 0.93s / 1.88s | 744.9s | 2.2 | 5 |
| *random order (as presented)* | 0.1138 | 0.1022 | 0.1374 | 0.2190 | 0.1023 | 0.0990 | – | – | – | – | – | – |

## Paired bootstrap, nDCG@10 (10k resamples): MIRACLReranking (252 q, 18 langs)

| a − b | Δ | 95% CI | significant |
|---|---|---|---|
| jevnoul14 − jev14 | +0.0018 | [-0.0185, +0.0219] | no |
| jevnoul14 − lunanoul | +0.0337 | [+0.0072, +0.0606] | yes |
| jevnoul14 − luna | +0.0692 | [+0.0393, +0.0990] | yes |
| jevnoul14 − cohere | -0.0435 | [-0.0683, -0.0199] | yes |
| jevnoul14 − cohere35 | -0.0453 | [-0.0718, -0.0200] | yes |
| jevnoul14 − coherefast | -0.0021 | [-0.0304, +0.0266] | no |
| jev14 − lunanoul | +0.0319 | [+0.0042, +0.0605] | yes |
| jev14 − luna | +0.0674 | [+0.0421, +0.0924] | yes |
| jev14 − cohere | -0.0453 | [-0.0678, -0.0228] | yes |
| jev14 − cohere35 | -0.0471 | [-0.0727, -0.0213] | yes |
| jev14 − coherefast | -0.0039 | [-0.0315, +0.0240] | no |
| lunanoul − luna | +0.0355 | [+0.0054, +0.0662] | yes |
| lunanoul − cohere | -0.0772 | [-0.1075, -0.0472] | yes |
| lunanoul − cohere35 | -0.0790 | [-0.1104, -0.0483] | yes |
| lunanoul − coherefast | -0.0358 | [-0.0691, -0.0027] | yes |
| luna − cohere | -0.1127 | [-0.1419, -0.0838] | yes |
| luna − cohere35 | -0.1145 | [-0.1456, -0.0832] | yes |
| luna − coherefast | -0.0713 | [-0.1042, -0.0395] | yes |
| cohere − cohere35 | -0.0018 | [-0.0218, +0.0185] | no |
| cohere − coherefast | +0.0414 | [+0.0180, +0.0648] | yes |
| cohere35 − coherefast | +0.0432 | [+0.0212, +0.0656] | yes |

## Paired bootstrap, nDCG@10 (10k resamples): JQaRAReranking (1,667 q, ja)

| a − b | Δ | 95% CI | significant |
|---|---|---|---|
| jevnoul14 − jev14 | +0.1857 | [+0.1771, +0.1946] | yes |
| jevnoul14 − lunanoul | +0.0772 | [+0.0702, +0.0841] | yes |
| jevnoul14 − luna | +0.3071 | [+0.2970, +0.3170] | yes |
| jevnoul14 − cohere | +0.0658 | [+0.0591, +0.0727] | yes |
| jevnoul14 − cohere35 | +0.1835 | [+0.1744, +0.1926] | yes |
| jevnoul14 − coherefast | +0.1989 | [+0.1895, +0.2085] | yes |
| jev14 − lunanoul | -0.1085 | [-0.1187, -0.0985] | yes |
| jev14 − luna | +0.1214 | [+0.1128, +0.1301] | yes |
| jev14 − cohere | -0.1199 | [-0.1297, -0.1102] | yes |
| jev14 − cohere35 | -0.0022 | [-0.0128, +0.0084] | no |
| jev14 − coherefast | +0.0133 | [+0.0026, +0.0241] | yes |
| lunanoul − luna | +0.2299 | [+0.2196, +0.2402] | yes |
| lunanoul − cohere | -0.0114 | [-0.0199, -0.0027] | yes |
| lunanoul − cohere35 | +0.1063 | [+0.0968, +0.1161] | yes |
| lunanoul − coherefast | +0.1217 | [+0.1115, +0.1320] | yes |
| luna − cohere | -0.2413 | [-0.2522, -0.2302] | yes |
| luna − cohere35 | -0.1236 | [-0.1349, -0.1118] | yes |
| luna − coherefast | -0.1081 | [-0.1196, -0.0963] | yes |
| cohere − cohere35 | +0.1177 | [+0.1101, +0.1253] | yes |
| cohere − coherefast | +0.1331 | [+0.1254, +0.1409] | yes |
| cohere35 − coherefast | +0.0154 | [+0.0086, +0.0223] | yes |

## Notes

- Rank reversal for Jev pointwise: 4th on MIRACL (significantly below cohere 4-pro and v3.5, tied with cohere 4-fast and Jev listwise) but 1st on JQaRA (+0.066 vs cohere 4-pro).
- cohere rerank-4-pro is the only system in the top 2 on both datasets; v3.5 and 4-fast are 1st/3rd on MIRACL but 4th/6th on JQaRA.
- gpt-6-luna is significantly below Jev in the same mode on both datasets, at 1.5-3.2x the $/1Kq (pointwise 3.2x, listwise 1.5-1.9x).
- Pointwise vs listwise: Jev not significant on MIRACL (+0.002, 2.2 positives/query), +0.186 on JQaRA (9.7 positives/query); luna +0.036 / +0.230.
- Sequential latency: Jev is lowest at 0.46-0.49s (both modes, both datasets); cohere 0.55-0.92s; luna listwise 0.58-0.61s; luna pointwise 1.11-1.14s. Under 64 in flight Jev listwise on JQaRA degrades to 2.78s mean / 6.84s p95.
- MIRACL was re-run for this table with the latency-fixed client, so quality numbers differ slightly from the phase-1 REPORT (run-to-run variation, e.g. jev-1.14 pointwise 0.7496 vs 0.7552). MIRACL wall times (2-6s for 252 queries) are short and noisy; HTTP status counters were not recorded for that run (0 failed queries).
- JQaRA luna listwise wall time (745s) is retry backoff on 5 queries OpenAI refuses deterministically (502); it is not throughput. Those 5 queries use the fallback order.
- One run per system and dataset. Voyage models excluded: 429 rate limiting (`results_jqara/SUMMARY.md`, probe).
