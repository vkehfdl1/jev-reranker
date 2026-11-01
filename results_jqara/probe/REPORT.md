# Phase 2: mteb/JQaRAReranking — decision models vs fast rerankers

queries: 1667 | candidates/query: 100 (untruncated, same seeded shuffle for every system) | positives/query: 9.7

Latency columns: service latency of the successful HTTP call (queueing excluded), measured while 64 requests were in flight (`load`) and one at a time (`seq`).

| system | n | err | ndcg@10 [95% CI] | ndcg@5 | map | mrr@10 | recall@10 | hit@1 | $/1Kq | lat load mean / p50 / p95 | lat seq mean / p50 / p95 | wall (n q) | q/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cohere | 600 | 0 | 0.8132 | 0.8331 | 0.7695 | 0.9429 | 0.6630 | 0.9183 | 2.500 | 1.09s / 0.98s / 1.70s | – | 11.4s (600) | 52.6 |
| diqwen3 | 100 | 0 | 0.7920 | 0.8182 | 0.7545 | 0.9340 | 0.6377 | 0.9100 | 1.323 | 14.99s / 18.20s / 22.68s | – | 187.6s (100) | 0.5 |
| qwen3 | 100 | 0 | 0.7900 | 0.8133 | 0.7507 | 0.9295 | 0.6400 | 0.9000 | 5.312 | 2.69s / 2.72s / 4.14s | – | 89.1s (100) | 1.1 |
| voyage3 | 600 | 0 | 0.7659 | 0.8004 | 0.7083 | 0.9381 | 0.6114 | 0.9117 | 0.948 | 0.66s / 0.63s / 0.92s | – | 194.7s (600) | 3.1 |
| voyage | 600 | 0 | 0.7497 | 0.7801 | 0.6903 | 0.9297 | 0.5991 | 0.9000 | 0.948 | 0.72s / 0.64s / 1.35s | – | 94.2s (600) | 6.4 |
| voyage3lite | 600 | 0 | 0.7180 | 0.7558 | 0.6511 | 0.9196 | 0.5672 | 0.8833 | 0.379 | 1.64s / 0.98s / 4.65s | – | 65.0s (600) | 9.2 |
| cohere35 | 600 | 0 | 0.6944 | 0.7345 | 0.6283 | 0.9040 | 0.5555 | 0.8583 | 1.000 | 0.77s / 0.61s / 1.67s | – | 8.1s (600) | 74.1 |
| voyagelite | 600 | 0 | 0.6885 | 0.7319 | 0.6190 | 0.9088 | 0.5405 | 0.8700 | 0.379 | 2.36s / 1.62s / 6.02s | – | 23.5s (600) | 25.5 |
| coherefast | 600 | 0 | 0.6829 | 0.7169 | 0.6089 | 0.9017 | 0.5411 | 0.8600 | 2.000 | 0.84s / 0.73s / 1.69s | – | 9.2s (600) | 65.2 |
| random-order | 1667 | 0 | 0.1138 [0.1074, 0.1202] | 0.1022 | 0.1374 | 0.2190 | 0.1023 | 0.0990 | – | – | – | – | – |

## HTTP outcomes per system (status code -> count, 429 = rate limit)

- cohere: {'200': 600} (cost field missing on 0 records)
- diqwen3: {'200': 100, '429': 449} (cost field missing on 0 records)
- qwen3: {'503': 393, '200': 100} (cost field missing on 0 records)
- voyage3: {'200': 600, '429': 2150} (cost field missing on 0 records)
- voyage: {'200': 600, '429': 1105} (cost field missing on 0 records)
- voyage3lite: {'200': 600, '429': 875} (cost field missing on 0 records)
- cohere35: {'200': 600} (cost field missing on 0 records)
- voyagelite: {'200': 600} (cost field missing on 0 records)
- coherefast: {'200': 600} (cost field missing on 0 records)

## paired bootstrap on ndcg@10 (10k resamples): row − column

| pair | Δ mean | 95% CI | significant |
|---|---|---|---|
