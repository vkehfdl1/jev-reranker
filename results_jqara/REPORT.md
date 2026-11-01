# Phase 2: mteb/JQaRAReranking — decision models vs fast rerankers

queries: 1667 | candidates/query: 100 (untruncated, same seeded shuffle for every system) | positives/query: 9.7

Latency columns: service latency of the successful HTTP call (queueing excluded), measured while 64 requests were in flight (`load`) and one at a time (`seq`).

| system | n | err | ndcg@10 [95% CI] | ndcg@5 | map | mrr@10 | recall@10 | hit@1 | $/1Kq | lat load mean / p50 / p95 | lat seq mean / p50 / p95 | wall (n q) | q/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| jevnoul14 | 1667 | 0 | 0.8849 [0.8762, 0.8935] | 0.8939 | 0.8536 | 0.9538 | 0.7632 | 0.9298 | 1.141 | 1.25s / 0.55s / 5.01s | 0.49s / 0.48s / 0.64s | 33.3s (1667) | 50.1 |
| cohere | 1667 | 0 | 0.8191 [0.8093, 0.8289] | 0.8345 | 0.7749 | 0.9478 | 0.6924 | 0.9250 | 2.500 | 1.05s / 0.95s / 1.73s | 0.92s / 0.90s / 1.24s | 28.7s (1667) | 58.1 |
| lunanoul | 1667 | 0 | 0.8077 [0.7974, 0.8178] | 0.8240 | 0.7371 | 0.9096 | 0.6924 | 0.8530 | 3.585 | 1.27s / 1.20s / 1.87s | 1.11s / 1.08s / 1.43s | 34.2s (1667) | 48.7 |
| cohere35 | 1667 | 0 | 0.7014 [0.6900, 0.7124] | 0.7298 | 0.6324 | 0.9086 | 0.5853 | 0.8674 | 1.000 | 1.58s / 1.15s / 4.05s | 0.55s / 0.54s / 0.64s | 44.1s (1667) | 37.8 |
| jev14 | 1667 | 0 | 0.6992 [0.6891, 0.7094] | 0.7957 | 0.5912 | 0.9564 | 0.5473 | 0.9352 | 0.967 | 2.78s / 1.94s / 6.84s | 0.47s / 0.46s / 0.54s | 75.0s (1667) | 22.2 |
| voyagelite | 1667 | 0 | 0.6899 [0.6783, 0.7012] | 0.7221 | 0.6200 | 0.9045 | 0.5670 | 0.8632 | 0.387 | 1.90s / 0.86s / 6.06s | 0.59s / 0.58s / 0.68s | 152.3s (1667) | 10.9 |
| coherefast | 1667 | 0 | 0.6860 [0.6747, 0.6973] | 0.7114 | 0.6125 | 0.9031 | 0.5664 | 0.8608 | 2.000 | 1.09s / 0.76s / 3.09s | 0.72s / 0.69s / 0.97s | 29.9s (1667) | 55.8 |
| luna | 1667 | 5 | 0.5778 [0.5679, 0.5875] | 0.6607 | 0.4794 | 0.9547 | 0.4308 | 0.9394 | 1.802 | 0.93s / 0.71s / 1.88s | 0.61s / 0.57s / 0.85s | 744.9s (1667) | 2.2 |
| random-order | 1667 | 0 | 0.1138 [0.1074, 0.1202] | 0.1022 | 0.1374 | 0.2190 | 0.1023 | 0.0990 | – | – | – | – | – |

## HTTP outcomes per system (status code -> count, 429 = rate limit)

- jevnoul14: {'200': 1667} (cost field missing on 0 records)
- cohere: {'200': 1667, '503': 1} (cost field missing on 0 records)
- lunanoul: {'200': 1667} (cost field missing on 0 records)
- cohere35: {'200': 1667} (cost field missing on 0 records)
- jev14: {'200': 1667} (cost field missing on 0 records)
- voyagelite: {'200': 1667, '429': 2237} (cost field missing on 0 records)
- coherefast: {'200': 1667} (cost field missing on 0 records)
- luna: {'503': 1, '502': 100, '200': 1662} (cost field missing on 0 records)

## paired bootstrap on ndcg@10 (10k resamples): row − column

| pair | Δ mean | 95% CI | significant |
|---|---|---|---|
| jevnoul14 − cohere | +0.0658 | [+0.0591, +0.0727] | yes |
| jevnoul14 − lunanoul | +0.0772 | [+0.0702, +0.0841] | yes |
| jevnoul14 − cohere35 | +0.1835 | [+0.1744, +0.1926] | yes |
| jevnoul14 − jev14 | +0.1857 | [+0.1771, +0.1946] | yes |
| jevnoul14 − voyagelite | +0.1950 | [+0.1858, +0.2043] | yes |
| jevnoul14 − coherefast | +0.1989 | [+0.1895, +0.2085] | yes |
| jevnoul14 − luna | +0.3071 | [+0.2970, +0.3170] | yes |
| cohere − lunanoul | +0.0114 | [+0.0027, +0.0199] | yes |
| cohere − cohere35 | +0.1177 | [+0.1101, +0.1253] | yes |
| cohere − jev14 | +0.1199 | [+0.1102, +0.1297] | yes |
| cohere − voyagelite | +0.1292 | [+0.1213, +0.1372] | yes |
| cohere − coherefast | +0.1331 | [+0.1254, +0.1409] | yes |
| cohere − luna | +0.2413 | [+0.2302, +0.2522] | yes |
| lunanoul − cohere35 | +0.1063 | [+0.0968, +0.1161] | yes |
| lunanoul − jev14 | +0.1085 | [+0.0985, +0.1187] | yes |
| lunanoul − voyagelite | +0.1178 | [+0.1079, +0.1279] | yes |
| lunanoul − coherefast | +0.1217 | [+0.1115, +0.1320] | yes |
| lunanoul − luna | +0.2299 | [+0.2196, +0.2402] | yes |
| cohere35 − jev14 | +0.0022 | [-0.0084, +0.0128] | no |
| cohere35 − voyagelite | +0.0115 | [+0.0049, +0.0183] | yes |
| cohere35 − coherefast | +0.0154 | [+0.0086, +0.0223] | yes |
| cohere35 − luna | +0.1236 | [+0.1118, +0.1349] | yes |
| jev14 − voyagelite | +0.0093 | [-0.0014, +0.0201] | no |
| jev14 − coherefast | +0.0133 | [+0.0026, +0.0241] | yes |
| jev14 − luna | +0.1214 | [+0.1128, +0.1301] | yes |
| voyagelite − coherefast | +0.0039 | [-0.0030, +0.0108] | no |
| voyagelite − luna | +0.1121 | [+0.1003, +0.1236] | yes |
| coherefast − luna | +0.1081 | [+0.0963, +0.1196] | yes |
