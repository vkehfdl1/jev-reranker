# Technical notes — deep review content (backing material for the video)

범례 — 모든 주장에 근거 등급을 붙였다 (프로젝트 규칙: 문서/문장은 증거가 아니라 단서이고, 코드·데이터가 기준).

- **[측정]** 이 레포의 코드/원본 결과로 직접 재계산한 값 (`results_final/FINAL.md`, `results_final/ANALYSIS.md`, `results_jqara/`, `results_miracl_v2/`)
- **[API 관측]** 2026-11-01에 실제 호출해서 본 응답
- **[논문 abstract]** arXiv abstract에서 확인 (본문은 읽지 않음)
- **[벤더 문서]** TypeSafe / OpenRouter / Cohere / Qwen 공식 문서에 적힌 주장. 독립 검증 안 됨
- **[추론]** 위 근거에서 내가 끌어낸 해석. 검증 안 됨

---

## 0. 한 장 요약 (thesis)

> 리랭커를 고를 때 "decision model이 cross-encoder를 대체하는가"는 잘못된 질문이다.
> 같은 Jev 1.14가 MIRACL에서는 Cohere 4-pro에 유의하게 지고(0.750 vs 0.793), JQaRA에서는 유의하게 이긴다(0.885 vs 0.819).
> 순위는 데이터셋(라벨 성격 · 후보당 정답 밀도 · 입력 절단 · 언어)과 호출 방식(listwise/pointwise)에 따라 뒤집힌다.
> 측정 사실: 호출 방식의 효과가 데이터셋마다 다르다 (pointwise − listwise: MIRACL 유의하지 않음, JQaRA +0.186). 원인은 가설이며(정답 밀도, 입력 절단, 언어, 라벨 방식이 두 데이터셋에서 동시에 다르다) 분리하지 못했다 (§7.3).
> 그래서 결론은 "모델 하나를 고른다"가 아니라 "내 데이터로 두 호출 방식을 직접 재 본다"이고,
> 비용·지연 구조(토큰 과금 vs 검색단위 과금)가 그 결정을 좌우한다.

---

## 1. Two-stage retrieval과 reranking이 필요한 이유

- 1단계(first stage): BM25 같은 lexical 검색이나 dense embedding이 전체 코퍼스에서 후보 K개(여기서는 100)를 싸게 뽑는다.
  쿼리·문서를 독립적으로 표현하므로 문서 표현을 미리 계산해 둘 수 있다.
- 2단계(reranker): 후보 K개만 쿼리와 **함께** 읽고 점수를 다시 매긴다. 비싸지만 K개에만 쓴다.
- 비용 구조: 쿼리당 reranker 호출 비용이 K에 비례하고(문서 K개를 읽어야 하므로), 정확도는 1단계 recall이 상한이다.
  ColBERT 논문은 이 긴장을 정면으로 다룬다 — 쿼리·문서 쌍마다 큰 네트워크를 통과시키는 것이 비용의 원인이고, late interaction으로 문서 표현을 미리 계산해 2자릿수 빠르게 만든다 **[논문 abstract: arXiv 2004.12832]**.
- BEIR는 re-ranking과 late-interaction 모델이 zero-shot 평균 성능이 가장 좋지만 계산 비용이 크다고 보고한다 **[논문 abstract: arXiv 2104.08663]**.

우리 실험의 1단계 후보: MIRACL은 BM25 top-100 (BM25 nDCG@10 = 0.443 **[측정]**), JQaRA는 데이터셋 카드에 따르면 5개 embedding 모델 결과를 RRF로 합친 top-100 **[벤더 문서: JQaRA 카드]**.

---

## 2. Cross-encoder 기반 reranker — 어떻게 만들고 어떻게 쓰나

### 2.1 구조
- **Cross-encoder**: 쿼리와 문서를 하나의 시퀀스로 이어 붙여 transformer에 넣고, 모든 토큰이 서로 attention한다. 마지막 표현(예: [CLS])에서 relevance 점수 하나를 낸다.
  Nogueira & Cho(2019)가 BERT를 이 방식으로 passage re-ranking에 써서 MS MARCO 1위, MRR@10 상대 27% 개선을 보고했다 **[논문 abstract: arXiv 1901.04085]**. 입력 이어붙이기와 분류 헤드 세부 구조는 본문에 있고, 나는 abstract만 확인했다.
- 대조: **bi-encoder**는 쿼리·문서를 따로 인코딩해 벡터 내적으로 점수를 낸다 (문서 임베딩 사전 계산 가능, 상호작용 약함). **ColBERT**는 둘을 독립 인코딩한 뒤 token 수준 late interaction으로 중간 지점을 잡는다 **[논문 abstract: 2004.12832]**.
- **비용**: cross-encoder는 (쿼리, 문서) 쌍마다 forward pass 1번. 후보 K개면 쿼리당 K번 (또는 K개 배치). 문서 표현을 미리 계산할 수 없다 — 그래서 2단계에서만 쓴다.

### 2.2 학습 신호
- pointwise(문서 하나가 relevant인가 분류) / pairwise / listwise loss 계열이 있다 (일반 지식, 본문 미재확인).
- **seq2seq 방식 (monoT5)**: T5가 "true"/"false" 같은 target word를 생성하도록 학습하고, 그 **logit을 relevance 확률로 해석**해 정렬한다. 데이터가 적은 환경에서 encoder-only 모델보다 낫다고 보고 **[논문 abstract: arXiv 2003.06713]**.
- **LLM 기반 reranker (Qwen3-Reranker)**: decoder LLM에 chat template로 `<Instruct> / <Query> / <Document>`를 넣고, 시스템 프롬프트가 "답은 yes 또는 no만"이라고 제한한다. 마지막 위치에서 `yes`/`no` 두 토큰의 logit만 꺼내 `log_softmax` 후 **P(yes)** 를 점수로 쓴다 — 모델 카드의 공개 코드에서 확인 **[벤더 문서: Qwen/Qwen3-Reranker-8B model card, 코드 직접 읽음]**. 컨텍스트 32K, instruction을 바꿀 수 있고 instruction을 쓰면 1~5% 개선(카드 주장). 논문: arXiv 2506.05176 **[논문 abstract]**.
- **Cohere Rerank**: API는 `query` + `documents`를 받아 문서마다 `relevance_score`를 돌려주고, 과금 단위는 `search_units`다. 100개 이상 언어 지원을 표방한다 **[벤더 문서: docs.cohere.com Rerank overview]**. 내가 읽은 문서에는 내부 아키텍처·학습법 설명이 없다 → 블랙박스 pointwise scorer로 취급한다.

### 2.3 실무 관점의 성질
- 점수는 문서마다 독립적인 값 (pointwise). 입력 순서에 둔감하다 (후보를 한 번에 하나씩/배치로 본다).
- 출력은 숫자 스코어 → 정렬 → 끝. 파싱 실패, 거부(refusal), 형식 오류가 없다. 우리 JQaRA 실행에서 Cohere 3종 × 1,667쿼리는 HTTP 503 1건(재시도로 성공) 외에 실패가 없었다 **[측정: `results_jqara/meta.json`]**.
- 과금: Cohere는 **검색 단위**. 우리 실행에서 100개 후보 쿼리 1건 = $0.0025 (4-pro), $0.002 (4-fast), $0.001 (v3.5) → $/1Kq 2.500 / 2.000 / 1.000. 후보 200개 probe에서는 쿼리당 $0.005 = 2 search unit **[측정: `results/cohere_k200_*.jsonl`, `results_jqara/REPORT.md`]**. 문서 길이와 무관하게 후보 수(100개 단위)로만 과금된다.

---

## 3. LLM을 reranker로 쓰는 세 가지 prompting 방식

| 방식 | 모델이 보는 것 | 출력 | 장점 | 단점 | 대표 |
|---|---|---|---|---|---|
| **Pointwise** | (쿼리, 문서 1개) | yes/no 확률 또는 점수 | 문서 간 독립, 병렬, 입력 순서 무관 | 문서 간 상대 비교 불가, 점수 보정 필요 | monoT5, Qwen3-Reranker |
| **Pairwise** | (쿼리, 문서 A, 문서 B) | 더 나은 쪽 | 상대 비교가 정확 | 호출 수 O(N²) 또는 정렬 알고리즘 필요 | PRP |
| **Listwise** | (쿼리, 문서 N개 전체) | 순열 또는 선택 | 한 번에 전체 비교 | 컨텍스트 한계, 순서 편향, 형식 파싱 | RankGPT, RankZephyr |

- RankGPT: 적절히 지시된 LLM이 지도학습 SOTA와 겨루거나 능가, ChatGPT의 순위 능력을 작은 모델로 distill(permutation distillation) **[논문 abstract: arXiv 2304.09542]**.
- PRP: off-the-shelf LLM은 pointwise·listwise 형식을 잘 이해하지 못한다고 주장하고 pairwise로 부담을 줄인다. 선형 복잡도 변형도 제안 **[논문 abstract: arXiv 2306.17563]**.
- Setwise: pointwise는 효율이 높지만 효과가 낮고, pairwise는 효과가 높지만 오버헤드가 크다 — 추론 횟수와 prompt 토큰을 줄이는 중간 해법 **[논문 abstract: arXiv 2310.09497]**.
- RankZephyr: 오픈소스 listwise reranker, 초기 문서 순서와 문서 수 변화에 강건하다고 보고 **[논문 abstract: arXiv 2312.02724]**. → listwise는 입력 순서에 민감하다는 것이 문제로 알려져 있고, 우리도 모든 시스템에 같은 seed 셔플을 줘서 공통 조건을 만들었다.

핵심: 세 방식은 **정확도·호출 수·토큰 소비의 trade-off**이고, decision model은 이 중 listwise(Choice)와 pointwise(Noul)를 API 한 번에 담아 준다.

---

## 4. Decision model (System One)은 무엇이고 어떻게 만들어지나

### 4.1 정의 — 입출력 계약
- **[벤더 문서]** Jev는 TypeSafe의 "System One" 모델. `state`(평가할 내용)와 typed `questions`를 받아 **텍스트가 아니라 typed answer + probabilities**를 돌려준다. 설명·코드·답장은 생성하지 않는다.
- Primitive 4종: **Choice**(옵션 중 하나; 옵션별 확률과 confidence), **Noul**(yes/no, P(yes) 하나), **Score**(순서 척도; 확률가중 위치), **Box**(이미지 bbox, 1.14).
- 질문 id는 모델에 전달되지 않고, 의미는 전부 `instructions`/`criteria` 설명에 담긴다. Choice 옵션은 최대 255개, 요청 안의 질문들은 `state`를 한 번 읽고 **병렬로** 평가된다 (벤더 문서).
- 가격: 입력 토큰 $0.042/M, **출력 토큰 무료**. OpenRouter 컨텍스트 262K; TypeSafe 자체 API는 기본 64K(요청) / 32K(질문) (벤더 문서). 수백 개 질문을 한 요청에 묶어도 상태는 한 번만 입력으로 계산된다는 점이 pointwise 배치의 경제성을 만든다.
- 다른 decision model도 같은 Decisions API를 쓴다. 2026-10-16 기준 OpenRouter에 13개 제조사 22개 모델 (OpenAI `gpt-6-luna-decisions`, Microsoft, Perplexity, Cloudflare, Inception, Liquid, Upstage 등) **[벤더 문서: OpenRouter Jev guide]**. 확률 분포는 모델마다 달라서 임계값을 모델별로 다시 잡아야 한다는 경고가 있다.

### 4.2 학습 방식 (벤더 주장)
- **[벤더 문서: TypeSafe AI primer]** 사후학습(post-training)을 세 갈래로 구분한다.
  - RLHF: 사람이 선호하는 응답을 내도록 학습 → 챗봇. 선호 최적화가 sycophancy, mode dropping을 유발한다고 주장.
  - RLVR: 검증 가능한 보상으로 reasoning 모델 → 느리고 비쌈.
  - **RLCD (Reinforcement Learning for Calibrated Decisions)**: 텍스트를 생성하지 않고 **결정과 보정된(calibrated) 확률**을 반환하도록 학습. 0.8이라고 한 사건이 대략 80% 맞는 것을 목표로 한다. 보정은 개별 답이 아니라 **예측 묶음**에 대한 통계적 성질이라고 명시.
- 공개 문서에서 파라미터 수, 백본, 학습 데이터, 손실 함수는 찾지 못했다. 고객 데이터로 fine-tuning하지 않으며 모든 계정이 같은 weight를 쓴다고 한다 (벤더 문서: Models). **내가 모르는 부분을 채우지 않는다.**
- 언어: "영어가 주 학습 언어이고 CJK 등은 같은 수준이 아니다" (벤더 문서: Models, Language support). → 일본어 JQaRA에서 1위가 나온 것은 이 문서 서술과 긴장 관계라서 흥미로운 관측이다 [추론: 이유는 확인 못 함].

### 4.3 왜 reranker로 쓸 수 있나 — 개념적 다리 [추론]
- Qwen3-Reranker는 LLM의 `yes`/`no` 다음-토큰 logit을 꺼내 P(yes)를 점수로 쓴다 (§2.2). Noul은 "yes/no 확률 하나를 typed 응답으로 노출"한 인터페이스이고, Choice는 "옵션 라벨 위의 softmax"를 노출한 인터페이스로 볼 수 있다.
- 관측: `openai/gpt-6-luna-decisions`의 응답 `usage.output_tokens`는 0이다 (우리 probe 호출 **[API 관측]**). 즉 샘플링으로 텍스트를 생성하지 않고 한 번의 forward에서 확률을 읽어 오는 형태와 일관된다. Jev는 `output_tokens`를 보고하지만(50~1,904) 과금은 0이다 **[API 관측]**. 내부 메커니즘은 모른다 — 이 해석은 추론이다.
- 같은 계약(확률 반환)이 있으므로, 모델을 바꿔도 요청 형식이 같다. 우리 코드에서 `model` 문자열만 바꿔 Jev ↔ gpt-6-luna를 교체했다 **[측정: `jqara_run.py` DECISION_MODELS]**.

### 4.4 Confidence와 Noul 해석 (벤더 문서에 수식이 있다)
- Choice confidence = (p_max − 1/n) / (1 − 1/n). 균등분포 0, 확실하면 1. Noul에는 별도 confidence가 없고 p 자체가 답.
- 보정 주장은 벤더의 학습 목표다. 우리 데이터로 간단히 점검: Jev 1.14 pointwise가 쿼리당 100개 후보에 준 **P(yes)의 합은 MIRACL 24.1, JQaRA 22.0**, 반면 qrel 정답은 쿼리당 2.2 / 9.7개다 **[측정: `results_final/ANALYSIS.md` A]**.
  프롬프트의 relevance 정의("질문에 답하는 데 도움이 되면 relevant")가 qrel보다 넓기 때문에 "보정이 틀렸다"고 결론 내릴 수는 없다 — 단지 **P(yes)를 정답 확률로 읽으면 안 되고 순위 점수로만 읽어야 한다**는 뜻이다.

---

## 5. 우리가 decision model을 reranker로 쓴 방법 (코드 기준)

모든 시스템: 쿼리당 후보 100개, 같은 seed 셔플, 점수 내림차순 정렬, 동점은 제시 순서 (`jqara_run.score_query`, `run.run_cell`). 프롬프트는 두 모드 각각 한 개로 고정 (튜닝 안 함).

### 5.1 Listwise — Choice 1개
```json
POST /api/alpha/decisions
{ "model": "typesafe/jev-1.14",
  "state": {"question": "<query>"},
  "questions": {"rank": {"type": "choice",
      "instructions": "Which of the listed passages is most relevant to the question given in the state? ...",
      "criteria": {"c000": "<passage 0>", "c001": "<passage 1>", ... "c099": "<passage 99>"}}} }
```
응답: `answers.rank.probabilities` = 100개 라벨 위의 분포. 이 분포로 정렬한다.
- **[측정]** 확률 합 = 1.0 (두 모델 모두), **0보다 큰 후보는 Jev ≈ 6개, gpt-6-luna ≈ 20~23개**. 나머지는 점수 0 → 정렬에서 전부 동점 → 제시 순서(랜덤)로 채워진다. 동점 비율 0.94~0.95.
- 결과: "가장 좋은 1개"는 잘 고르지만(hit@1: JQaRA에서 Jev 0.935, luna 0.939 = 전 시스템 1·2위) 그 아래 순서는 정보가 없다. 쿼리당 정답이 9.7개인 JQaRA에서 Jev listwise는 정답의 53%만 support(점수>0)에 넣었다 → nDCG@10 0.699. 정답이 2.2개인 MIRACL에서는 지원 recall 0.83, nDCG@10 0.748로 pointwise와 구분 안 된다.
- 효과적 ranking depth ≈ support 크기라는 것이 listwise의 구조적 한계 [측정에 근거한 해석].

### 5.2 Batched pointwise — Noul 100개를 한 요청에
```json
{ "model": "typesafe/jev-1.14",
  "state": {"question": "<query>", "passages": {"c000": "<p0>", ... "c099": "<p99>"}},
  "questions": {"c000": {"type": "noul", "instructions": "Is passage c000 in the state relevant to the question given in the state? ..."},
                ... "c099": {...}} }
```
응답: 라벨마다 P(yes). 이 값으로 정렬.
- **[측정]** 후보 100개 모두 점수 > 0 (Jev). 점수는 0.01 단위로 양자화되어 쿼리당 distinct 값 ≈ 37 → **동점 63%**. luna는 yes가 드물게 높아 support ≈ 15~22, 동점 85~89%.
- **TypeSafe 공식 re-ranking cookbook과 다른 점** **[벤더 문서]**: cookbook은 (쿼리, 후보) 쌍마다 별도 요청을 보내 "어떤 요청도 다른 후보를 보지 않는다". 우리는 비용을 위해 `state`에 100개 후보를 모두 싣고 각 질문이 한 후보를 가리키게 했다 → 모델이 **다른 후보를 볼 수 있어서 순수 pointwise가 아니다** (shared-context pointwise). 쌍별 요청 방식과의 비교는 실험하지 않았다.
- **토큰/비용** **[측정]**: listwise 대비 입력 토큰이 Jev +18%(JQaRA 23.0K→27.2K), luna +99%(18.0K→35.9K). 질문 100개가 각각 instruction을 가지기 때문이고 토크나이저가 달라서 증가율도 다르다. luna pointwise가 listwise의 2배 가까이 비싼 이유.

### 5.3 쓰지 않은 것
- **Score** primitive(순서 척도, 0~n 확률가중 점수)는 쓰지 않았다. 한 후보에 대한 graded relevance를 얻는 가장 자연스러운 primitive인데 비교하지 않았다 → future work.
- Pairwise/setwise: Choice를 후보 부분집합(예: 5개)에 반복 적용하면 setwise·토너먼트로 구현 가능하지만 [추론] 실행하지 않았다.
- Hybrid(두 시스템 결합): 실행했다 — §7.4.

---

## 6. 실험 설계 (재현 가능한 부분만)

| 항목 | MIRACLReranking | JQaRAReranking |
|---|---|---|
| 쿼리 | 18개 언어 × 14 = **252** (seed 42, 후보 풀에 정답이 있는 쿼리만 표본) | test 전체 **1,667** |
| 후보/쿼리 | BM25 top-100 | 100 (embedding 5종 RRF) |
| 정답/쿼리 | 2.2 | 9.7 |
| 라벨 | MIRACL 원 라벨 (native speaker 판정, arXiv 2210.09984) | **답 문자열이 제목/본문에 정확히 포함되면 positive** + 일부 LLM 검증 후 라벨 삭제 (JQaRA 카드, 벤더 문서) |
| 입력 | passage를 언어별로 **218~533자로 절단** (`data.cap_chars`; Jev 컨텍스트 때문, 재실행에서 추가 축소 폴백은 발동 안 함) | **절단 없음** (passage 길이 약 400자 이하; 표본 측정 최대 427자) |
| 비교 시스템 | jev-1.14 pointwise·listwise, gpt-6-luna-decisions pointwise·listwise, Cohere 4-pro·4-fast·v3.5 | 동일 |
| 제외 | Voyage 2.5/3/lite 계열, Qwen3 호스팅, NVIDIA 무료 (rate limit 429·503, 느림; probe 근거 `results_jqara/SUMMARY.md`) | |

- 지표: nDCG@10(주), nDCG@5, MAP, MRR@10, Recall@10, Hit@1. nDCG = DCG / IDCG, DCG = Σ rel_i / log2(i+1) (구현: `metrics.py`).
- 통계: 쿼리 단위 **paired bootstrap 10,000회** (95% CI).
- 비용: OpenRouter 응답의 `usage.cost` 합산 (누락 0건). 지연: 성공한 HTTP 왕복 시간만 (`clients.Client._post`, 큐 대기 제외) — 순차(1건씩, 50쿼리)와 64동시 두 가지.
- 실패 쿼리(gpt-6-luna listwise 5건: OpenAI가 `refused to answer`로 결정적으로 거부)는 제시 순서(랜덤)로 채점.
- 그림 하나로 정리: 모든 수치의 근거 표는 `results_final/FINAL.md`.

---

## 7. 결과와 해석

### 7.1 nDCG@10 (K=100)
| system | MIRACL | JQaRA | 평균 |
|---|---|---|---|
| jev-1.14 pointwise | 0.7496 | **0.8849** | **0.8173** |
| cohere rerank-4-pro | 0.7931 | 0.8191 | 0.8061 |
| gpt-6-luna pointwise | 0.7159 | 0.8077 | 0.7618 |
| cohere rerank-v3.5 | **0.7949** | 0.7014 | 0.7482 |
| jev-1.14 listwise | 0.7479 | 0.6992 | 0.7235 |
| cohere rerank-4-fast | 0.7517 | 0.6860 | 0.7189 |
| gpt-6-luna listwise | 0.6804 | 0.5778 | 0.6291 |

(1단계 기준선: MIRACL BM25 0.443, JQaRA 무작위 0.114.)

### 7.2 비용·지연 **[측정]**
| system | $/1Kq (M / J) | 순차 지연 평균 (M / J) | 64동시 평균 / p95 (J) |
|---|---|---|---|
| jev pointwise | 0.890 / 1.141 | 0.47s / 0.49s | 1.25s / 5.01s |
| jev listwise | 0.715 / 0.967 | 0.46s / 0.47s | 2.78s / 6.84s |
| luna pointwise | 2.885 / 3.585 | 1.14s / 1.11s | 1.27s / 1.87s |
| luna listwise | 1.102 / 1.802 | 0.58s / 0.61s | 0.93s / 1.88s |
| cohere 4-pro | 2.500 / 2.500 | 0.89s / 0.92s | 1.05s / 1.73s |
| cohere v3.5 | 1.000 / 1.000 | 0.56s / 0.55s | 1.58s / 4.05s |
| cohere 4-fast | 2.000 / 2.000 | 0.68s / 0.72s | 1.09s / 3.09s |

**비용 모델** (식으로 외워 둘 것):
- 토큰 과금 모델: 쿼리당 비용 = 입력 토큰 × 단가. Jev $0.042/M, gpt-6-luna-decisions $0.10/M.
- Cohere: 쿼리당 $0.0025 (4-pro) 고정 (후보 ≤100).
- **손익분기 입력 토큰** (vs Cohere 4-pro $0.0025): Jev = 0.0025 / 0.042e-6 ≈ **59.5K 토큰**, gpt-6-luna-decisions = 0.0025 / 0.1e-6 = **25K 토큰**. 우리 쿼리는 후보 100개가 약 11~36K 토큰 → Jev는 두 모드 모두 Cohere 4-pro(와 4-fast $0.002)보다 싸고 Cohere v3.5($0.001)와는 비슷하다 (Jev pointwise $0.89–1.14 vs $1.00). gpt-6-luna는 listwise(11~18K)만 4-pro보다 싸고 pointwise(29~36K)는 더 비싸다. 후보 문서가 길어지면 길이 무관 정액인 Cohere가 상대적으로 유리해진다.
- 지연과 입력 길이: Jev listwise는 평균 입력 17K 토큰(MIRACL)과 23K 토큰(JQaRA)에서 순차 지연이 0.46s / 0.47s로 거의 같았다 — 길이를 체계적으로 바꾼 실험은 아니고 두 점뿐이다. 동시 호출 64개에서 listwise Jev만 2.78s로 늘었다 (서버 큐/배치 영향 추정, 원인은 확인 못 함).

### 7.3 왜 순위가 뒤집혔나 — 가설 (검증된 것과 아닌 것)
측정 사실 **[측정]**:
1. 정답 밀도와 listwise support: MIRACL 쿼리당 정답 2.2개, JQaRA 9.7개. listwise Jev의 support(점수>0 후보)는 평균 6개이고 JQaRA에서 정답의 53%만 담는다. pointwise는 100개 전부 점수를 준다. pointwise − listwise 차이는 MIRACL +0.002 (n.s.), JQaRA +0.186 (유의). **원인이 정답 밀도라는 해석은 가설**이다 — 밀도와 데이터셋이 같이 바뀌어서 분리되지 않았다.
2. 입력 절단: MIRACL은 passage를 218–533자로 잘랐고 JQaRA는 안 잘랐다. 두 조건이 동시에 바뀌므로 어느 쪽이 효과인지 분리하지 못했다.

검증 안 된 가설 **[추론]**:
3. JQaRA 라벨은 "답 문자열 포함" 규칙으로 만들어졌고 문제는 퀴즈형 상식 질문이다. 세계 지식이 있는 decision model은 passage가 답을 담는지 판단하기 쉬울 수 있다. 오염(contamination) 가능성도 배제하지 못한다.
4. Cohere rerank-4-fast와 v3.5가 JQaRA에서 크게 무너진 (각 0.686, 0.701) 반면 4-pro는 0.819 — 같은 제조사 안에서도 모델 크기/등급 효과가 데이터셋에 따라 다르다.

### 7.4 Hybrid (rank fusion) — 부정적 결과 **[측정: `ANALYSIS.md` C]**
- RRF(k=60)로 두 시스템 순위를 합쳤다. JQaRA에서 모든 쌍이 더 좋은 단일 시스템보다 **유의하게 나빴다** (jevnoul14+cohere −0.015 [−0.019, −0.010]). MIRACL에서는 0과 구분 안 됨 (jevnoul14+cohere35 +0.009 [−0.010, +0.028]).
- 사후(post-hoc) 분석이고 후보 필터링형 hybrid(Jev로 거르고 Cohere로 재정렬)는 하지 않았다. 이전 초안의 "하이브리드가 sweet spot" 주장은 **데이터로 지지되지 않으므로 삭제**한다.

### 7.5 Qrels 불완전성 **[측정, 1차 실험]**
- MIRACL에서 Jev 1.13 listwise 점수 ≥ 0.5이면서 qrel이 non-relevant인 53쌍 중 47쌍을 독립 judge(Haiku 5.5, 전체 문서·엄격 프롬프트)가 relevant로 판정했다. MIRACL은 쿼리당 라벨이 적어 false negative가 많을 수 있다. 이 judge는 Jev 점수 구간에만 적용했으므로 시스템 간 비교는 아니다.

---

## 8. Threats to validity / limitations (영상에서 정직하게 말할 것)

1. 데이터셋 2개, 시스템당 1회 실행. 지연의 run-to-run 분산 미측정. MIRACL 재실행에서 같은 모델 점수가 −0.006~+0.002 변했다 (jev pointwise 0.7552 → 0.7496, jev listwise 0.7463 → 0.7479, cohere 4-fast 0.7539 → 0.7517).
2. **Jev 요청이 long-context 모드로 실행됐을 가능성**: 실제로 전송한 passage 텍스트는 MIRACL 평균 47.7 KB (92% 쿼리가 32,000 byte 초과), JQaRA 평균 59.8 KB (97%)다 (UTF-8) **[측정: `ANALYSIS.md` B]**. OpenRouter의 Jev 안내는 이 크기 이상의 요청이 TypeSafe의 "느리고 덜 정확한" long-context 모드로 실행된다고 한다 **[벤더 문서, 미검증]**. 사실이라면 Jev 점수는 보수적인(낮은) 추정일 수 있다 **[추론]**.
3. 프롬프트 1종, 튜닝 없음. 임계값/instruction 최적화 없이 비교했다.
4. 후보당 요청(per-pair)형 pointwise는 비교하지 않았다 — 우리 "pointwise"는 shared-context 배치다.
5. Cohere는 OpenRouter 카탈로그에서 rerank-4/v3.5를 썼다. Cohere 문서는 Rerank 5도 소개하지만 우리 카탈로그 목록에는 없었다.
6. JQaRA 라벨 방식과 퀴즈 질문 특성 때문에 결과가 일반 검색 품질로 외삽되지 않을 수 있다 (한 언어, 한 도메인).
7. 두 데이터셋에서 지연·비용은 모두 OpenRouter 경유 값이다 (벤더 직접 호출과 다를 수 있음).
8. 제외 시스템(Voyage 등)의 품질은 최종 표에 없다. 1차 실험(MIRACL, 15개 시스템)은 `results/REPORT.md`에 남아 있다.

---

## 9. 실무 가이드 (My own assessment — 채점 포인트)

의사결정 순서:
1. **후보 수 K와 문서 길이**를 본다 → 토큰 과금(Jev/luna)과 검색단위 과금(Cohere)의 손익분기(§7.2)로 비용을 계산한다.
2. **라벨/목표가 "정답 문서 존재"인가, "순위 전체의 품질"인가**를 정한다. 정답이 쿼리당 1~2개이고 top-1이 중요하면 listwise(`Choice`)가 싸고 빠르다. 정답이 많고 nDCG@10 전체가 중요하면 pointwise(`Noul` 배치) 또는 전용 reranker.
3. **지연 요구가 순차(1쿼리)냐 처리량(동시)이냐** — Jev는 순차 0.47s로 가장 빠르지만 listwise는 동시 부하에서 느려졌다.
4. 내 데이터에서 **50~200개 쿼리로 먼저 A/B** 한다. 이번 결과가 보여 주듯 한 데이터셋의 순위는 다른 데이터셋에 이전되지 않는다.
5. Decision model은 확률 점수를 **순위용 점수로만** 쓴다. 정답 확률로 해석하지 않는다 (§4.4). 동점이 많으므로 tie-break를 설계한다 (우리는 제시 순서).

내 의견: decision model은 "더 싸고 빠른 selector 겸 점수기"로 매력적이지만, 동점과 얕은 support(listwise), 거부(refusal) 같은 **인터페이스 수준의 실패 모드**를 가진다. 전용 reranker의 장점은 정확도가 아니라 **실패 모드가 단순하다는 것**(숫자 하나) 쪽에 가깝다.

---

## 10. 코드·데이터 포인터
- 1차(MIRACL 252q, 15 시스템): `run.py`, `results/`, `README.md`
- 2차(JQaRA 1,667q + reranker 선별 probe): `jqara_data.py`, `jqara_run.py`, `results_jqara/SUMMARY.md`
- 최종 표(MIRACL 재실행 + JQaRA): `final_table.py`, `results_miracl_v2/`, `results_final/FINAL.md`
- 추가 분석(score shape, 요청 크기, rank fusion): `analysis_extra.py`, `results_final/ANALYSIS.md`
- API 호출 구현: `clients.py` (`jev_choice`, `jev_noul_batch`, `rerank`)
