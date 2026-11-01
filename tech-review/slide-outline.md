# Tech Review 비디오 — 슬라이드 아웃라인 (v2, 새 실험 기준)

- 공식 가이드라인(Coursera 과제 페이지): **약 8~12분**, 목소리 설명 + 본인 분석/의견 + 사용한 리소스 표시. 발표 구조 7파트: Introduction → Background → How it works → Examples/applications → Comparison·strengths·limitations → Your thoughts → Resources.
- 최종 슬라이드는 `slides/slides.html` / `slides/slides.pdf` (15장, 데모 스니펫 슬라이드 없음, 영문). 이 문서는 발표 계획용이며 S 번호는 슬라이드 파일 번호와 일치하지 않는다. 파트별 배분 합계 **≈ 11:00**. 깊은 설명은 `technical-notes.md`에 있고 슬라이드에는 핵심만 올린다.
- 채점 포인트 = "내가 직접 조사하고 평가한 것". 발표 전체가 직접 측정한 데이터 위에 서 있다 (`results_final/FINAL.md`).
- 이 문서의 모든 숫자 출처: `results_final/FINAL.md`, `results_final/ANALYSIS.md`. 근거 등급 표기는 `technical-notes.md` 범례 참고.

## Thesis (한 문장, 1·15번 슬라이드에서 반복)

> "Decision model이 reranker를 대체하는가?"는 잘못된 질문이다. 같은 Jev가 MIRACL에서는 Cohere에 지고 JQaRA에서는 이긴다 — 순위는 데이터와 호출 방식에 달려 있으니 **내 데이터로 비용·지연·품질을 직접 재 보라**.

---

## Part 1 — Introduction (0:45, S1–S2)

**S1. Title**
- "Can a Decision Model Rerank? Decision Models vs Cross-Encoder Rerankers on Two Datasets"
- 이름/NetID, CS410 Fall 2026 Tech Review, "Original benchmark: 7 systems × 2 datasets (252 + 1,667 queries)"

**S2. Why this topic**
- 실무 질문: second stage를 고를 때 "전용 reranker 대신 LLM decision API를 쓰면 안 되나?" → 내가 찾아본 범위에서는 decision model과 전용 reranker를 같은 조건에서 비용·지연·품질까지 함께 재 본 자료를 못 찾아 직접 만들었다 (없다고 단정하지 않는다).
- 이번 학기 기존 리뷰(LLM Rerankers as a Second Stage over BM25)는 LLM reranking 방법 조사; 이 리뷰는 **측정 + 메커니즘 설명**이라는 점에서 보완 관계.
- 한 문장 결론 예고: thesis.

## Part 2 — Background (2:00, S3–S5)

**S3. Two-stage retrieval (강의 연결)**
- BM25/dense가 코퍼스 전체에서 후보 100개 → reranker가 100개만 쿼리와 함께 읽고 재정렬.
- 비용 식: reranker 호출은 후보 수 K에 비례. 1단계 recall이 상한. (BM25 nDCG@10 = 0.443 on MIRACL)
- 근거: ColBERT(cross-encoder 비용 설명), BEIR(re-ranking이 zero-shot 평균 최고지만 비용 큼).

**S4. Cross-encoder reranker 한 장 요약**
- 쿼리+문서를 한 시퀀스로 넣어 전 토큰이 attention → 점수 1개 (Nogueira & Cho 2019, BERT, MS MARCO 1위).
- 변형: monoT5(true/false 토큰 logit을 relevance 확률로), **Qwen3-Reranker**(LLM의 yes/no logit → P(yes), 모델 카드 코드로 확인), Cohere Rerank(API: relevance_score, search-unit 과금; 내부 구조 비공개).
- 성질: pointwise, 입력 순서 무관, 문서 표현 사전 계산 불가 → 2단계 전용.

**S5. LLM prompting 3분류 (표 하나)**
- Pointwise(독립·병렬·약한 비교) / Pairwise(PRP, 정확하지만 호출 수 부담 — 선형 변형도 제안됨) / Listwise(RankGPT, 전체 비교·컨텍스트/순서 편향) / (+Setwise = 중간).
- "decision model은 이 중 listwise(Choice)와 pointwise(Noul)를 한 API로 제공" → 다음 파트로 연결.

## Part 3 — How it works (3:15, S6–S9)

**S6. Decision model (System One)이란** — 입출력 계약
- state + typed questions → typed answer + probabilities. 텍스트 생성 없음. Primitive: Choice / Noul / Score / Box.
- 출력 토큰 무료, 입력 $0.042/M (Jev). 한 요청의 질문들은 state를 한 번 읽고 병렬 평가 (벤더 문서).
- 만드는 법(벤더 주장): **RLCD** — RLHF(선호), RLVR(검증 가능한 보상)과 달리 *calibrated decisions*를 목표로 확률을 반환하도록 사후학습. 파라미터/백본/데이터는 비공개 — 모른다고 말한다.
- 다른 decision model도 같은 API: OpenAI gpt-6-luna-decisions 등 22개(13개 제조사, 2026-10-16 기준). 우리는 `model` 문자열만 바꿔 교체.
- 내 해석(추론): Qwen3-Reranker의 yes/no logit read-out과 같은 계열의 인터페이스 — luna 응답의 `output_tokens = 0`이 이와 일관됨(API 관측).

**S7. Listwise = Choice 1개**
- 후보 100개를 `criteria`(c000…c099)로 넣고 "가장 relevant한 passage?" → 확률분포 → 정렬.
- 측정: 확률 합 1.0, **0보다 큰 후보 Jev ≈ 6개 / luna ≈ 20개** → 그 아래는 동점(랜덤 순서).
- 그래서: top-1은 최고(JQaRA hit@1 luna 0.939, Jev 0.935) 하지만 순위 깊이가 얕음.

**S8. Batched pointwise = Noul 100개**
- state에 질문+후보 100개, 질문 100개 "Is passage cXXX relevant?" → P(yes) → 정렬.
- 측정: 후보 전부 점수를 받지만 0.01 단위 양자화 → 동점 63%(Jev), luna는 yes가 드물어 support ≈15~22.
- **주의(정직하게)**: TypeSafe 공식 cookbook은 후보마다 별도 요청이라 "서로 안 본다". 내 방식은 한 state에 100개를 싣는 shared-context 배치 → 순수 pointwise가 아님. 비용: 입력 토큰 +18%(Jev) / +99%(luna).

**S9. 비용 모델 한 장**
- 토큰 과금: 비용 = 입력 토큰 × 단가 (Jev 0.042, luna 0.10 $/M). 검색 단위 과금: Cohere 4-pro $0.0025 / 쿼리(≤100 문서).
- 손익분기 입력 토큰: Jev 59.5K, luna 25K. 우리 쿼리는 11~36K 토큰 → Jev는 항상 4-pro보다 쌈; luna pointwise는 더 비쌈. 문서가 길수록 정액 과금이 유리.

## Part 4 — Analysis of the scores (≈0:45, S11)

**S11. 점수 분포는 어떻게 생겼나 (내 분석)**
- 표: support 크기, 동점 비율, 점수 합 (`ANALYSIS.md` A).
- 포인트 1: listwise는 질량 1을 소수 후보에 몰아 줌 → top-1에 강하고 tail 정보 없음.
- 포인트 2: pointwise P(yes)의 합이 22~24인데 정답은 쿼리당 2.2/9.7개 → **P(yes)는 정답 확률이 아니라 순위 점수**로만 읽어야 한다 (프롬프트의 relevance 정의가 라벨보다 넓기 때문, 보정이 틀렸다는 결론은 아님).

## Part 5 — Comparison, strengths, limitations (2:30, S12–S14)

**S12. 결과 표 (두 데이터셋) — 핵심 슬라이드**
- nDCG@10: Jev pointwise MIRACL 0.750 / JQaRA **0.885**, Cohere 4-pro 0.793 / 0.819, Cohere v3.5 **0.795** / 0.701, luna pointwise 0.716 / 0.808, Jev listwise 0.748 / 0.699, Cohere 4-fast 0.752 / 0.686, luna listwise 0.680 / 0.578.
- **순위 뒤집힘** 강조: Jev pointwise 4위 → 1위. Cohere 4-pro만 양쪽 모두 상위 2위.
- 설정 한 줄: 후보 100개 동일 셔플, 252 / 1,667 쿼리, paired bootstrap 10k.

**S13. 비용 · 지연**
- $/1Kq: Jev 0.72–1.14, Cohere 1.0–2.5, luna 1.1–3.6. 순차 지연: Jev 0.46–0.49s (최저), Cohere 0.55–0.92s, luna 0.58–1.14s.
- 64동시: Jev listwise만 2.8s로 증가 (원인 미확인).
- 메시지: Jev의 장점은 **싸고 순차 지연이 짧음**; 전용 reranker의 장점은 단순하고 안정적인 실패 모드.

**S14. Limitations + 왜 뒤집혔나 (정직하게)**
- 측정 사실: pointwise − listwise 효과가 MIRACL 유의하지 않음 / JQaRA +0.186. 원인 후보: 정답 밀도(2.2 vs 9.7), 입력 절단(MIRACL은 218–533자로 잘림), 일본어 퀴즈형 라벨("답 문자열 포함" 규칙) — **두 데이터셋에서 동시에 변해서 분리하지 못했다**.
- 한계: 시스템당 1회 실행, 프롬프트 튜닝 없음, 요청의 92~97%가 32,000 byte 초과(벤더 말로는 느리고 덜 정확한 long-context 모드 → Jev에 불리했을 수 있음, 미검증), luna listwise는 5쿼리 거부(OpenAI refusal), Voyage/Qwen3 호스팅은 rate limit으로 제외.
- 부정적 결과도 공개: RRF fusion은 JQaRA에서 단일 최고보다 유의하게 나쁨 → "hybrid가 답"이라는 이전 가설 폐기.

## Part 6 — Your thoughts (0:45, S15)

**S15. 내 평가 (채점 포인트)**
- decision model = "싸고 빠른 점수기 + 강한 top-1 selector". 그러나 인터페이스 수준 실패 모드(동점·얕은 support·거부)가 있어 *그대로* reranker로 쓰기엔 설계가 필요하다.
- 선택 가이드: ① 비용 계산(손익분기) ② 정답이 1~2개/top-1 중요 → listwise, 정답이 많고 전체 순위 중요 → pointwise 또는 전용 reranker ③ 50~200개 쿼리로 A/B.
- 배운 점: (1) 벤치마크 순위는 이전되지 않는다 (2) 지연 측정에 harness 아티팩트(큐 대기)가 섞이기 쉽다 — 내 1차 실험의 지연 수치가 실제로 오염돼 있었고 고쳤다 (3) 벤더 문서의 주장(보정, 언어 지원)은 그대로 믿지 않고 데이터로 점검.
- 다음에 볼 것: Score primitive, per-pair noul과의 비교, setwise를 Choice로 구현, Cohere Rerank 5.

## Part 7 — Resources (0:45, S16)

**S16. 추천 리소스 Top 6** (아래 풀에서 6개, 각 한 줄 이유)
1. Passage Re-ranking with BERT — cross-encoder reranking의 출발점
2. Pretrained Transformers for Text Ranking: BERT and Beyond — 전체 지도
3. RankGPT — listwise LLM reranking
4. PRP / Setwise — pairwise·setwise trade-off
5. TypeSafe System One docs + OpenRouter Jev guide — decision model 1차 자료
6. 이 레포 (코드·원본 결과) — 재현 가능한 practical example

---


## 리소스 풀 (TextData에 10개 이상 저장, 각 항목 한 문단 설명 필수 — 아래 한 줄을 확장)

모든 URL은 이번 작업 중 직접 열어 abstract/페이지 내용을 확인했다.

1. **Passage Re-ranking with BERT** (Nogueira & Cho, 2019) — https://arxiv.org/abs/1901.04085 — BERT를 쿼리-passage 쌍 reranker로 처음 체계화해 MS MARCO 1위를 기록, cross-encoder reranking의 기준점.
2. **Pretrained Transformers for Text Ranking: BERT and Beyond** (Lin, Nogueira, Yates) — https://arxiv.org/abs/2010.06467 — reranking과 dense retrieval을 아우르는 서베이, effectiveness–efficiency trade-off를 다룸.
3. **Document Ranking with a Pretrained Sequence-to-Sequence Model (monoT5)** — https://arxiv.org/abs/2003.06713 — T5가 생성하는 "true/false"의 logit을 relevance 확률로 쓰는 방식, LLM yes/no 점수화의 직계 조상.
4. **Is ChatGPT Good at Search? (RankGPT)** — https://arxiv.org/abs/2304.09542 — instruction된 LLM의 listwise reranking과 permutation distillation.
5. **Large Language Models are Effective Text Rankers with Pairwise Ranking Prompting (PRP)** — https://arxiv.org/abs/2306.17563 — pointwise/listwise prompt의 한계를 분석하고 pairwise로 해결.
6. **A Setwise Approach for Effective and Highly Efficient Zero-shot Ranking with LLMs** — https://arxiv.org/abs/2310.09497 — pointwise/pairwise/listwise를 같은 틀에서 비교하고 중간 지점(setwise) 제안.
7. **RankZephyr** — https://arxiv.org/abs/2312.02724 — 오픈소스 listwise reranker, 초기 순서·문서 수 변화에 대한 강건성 논의.
8. **ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT** — https://arxiv.org/abs/2004.12832 — cross-encoder의 비용 문제와 late interaction이라는 대안.
9. **BEIR** — https://arxiv.org/abs/2104.08663 — zero-shot 검색 평가 프레임워크, BM25·re-ranking·dense 비교의 표준 레퍼런스.
10. **Making a MIRACL: Multilingual Information Retrieval Across a Continuum of Languages** — https://arxiv.org/abs/2210.09984 — 18개 언어, native speaker 판정 데이터셋 (우리 벤치마크 1).
11. **JQaRA dataset card** (hotchpotch) — https://huggingface.co/datasets/hotchpotch/JQaRA — 일본어 QA 검색 데이터셋, 라벨 구성 방식(답 문자열 일치 + LLM 검증)이 상세히 적혀 있음 (우리 벤치마크 2, MTEB 버전: https://huggingface.co/datasets/mteb/JQaRAReranking).
12. **Qwen3-Reranker-8B model card** — https://huggingface.co/Qwen/Qwen3-Reranker-8B — LLM yes/no logit reranker의 공개 구현 코드와 instruction 사용법 (논문: https://arxiv.org/abs/2506.05176).
13. **Cohere Rerank overview** — https://docs.cohere.com/docs/rerank-overview — rerank API 입력/출력과 search-unit 과금 구조.
14. **TypeSafe docs: System One** — https://docs.typesafe.ai/concepts/system-one — decision model 개념, primitive(Choice/Score/Noul)의 정의.
15. **TypeSafe docs: AI primer (RLHF vs RLVR vs RLCD)** — https://docs.typesafe.ai/introduction/machine-learning-primer — decision model을 calibrated probability로 학습한다는 벤더의 설명 (주장으로 읽을 것).
16. **TypeSafe docs: Noul primitive** — https://docs.typesafe.ai/primitives/noul — P(yes) 해석, threshold 설정, 질문 설계 지침; **Choice**: https://docs.typesafe.ai/primitives/choice.
17. **TypeSafe cookbook: Re-ranking** — https://docs.typesafe.ai/cookbooks/rerank_typesafe — decision model로 reranking하는 공식 예제 (후보마다 Noul, CLERC 데이터); 우리 batched 방식과 비교 포인트.
18. **OpenRouter: Jev documentation** — https://openrouter.ai/docs/guides/community/jev — Decisions API, 다른 decision model 목록, 가격, 컨텍스트 주의사항.
19. **OpenRouter blog: What Is Jev?** — https://openrouter.ai/blog/insights/what-is-jev/ — Choice/Score/Noul/Box의 실제 요청·응답 예시와 확률 읽는 법.
20. **이 레포: jev-reranker** — 로컬 레포 (`jqara_run.py`, `run.py`, `results_final/`) — 재현 가능한 코드, 원본 쿼리별 결과, 분석 스크립트. 제출 시 공개 URL(GitHub 등)이 있으면 그것으로 대체.

선정 팁: TextData에는 1~19에서 질이 좋은 12~14개만 저장하고, 각 항목에 "무엇이 유용한지 + 내 실험에서 어떻게 썼는지"를 한 문단으로 쓴다.

---

## 녹화 전 준비물 체크리스트

- [ ] `results_final/FINAL.md`에서 S12, S13 표를 슬라이드용으로 축약 (7행 × 4열 정도)
- [ ] `slides/slides.pdf`를 열어 15장 모두 확인, 필요하면 `slides/build_slides.py`를 고쳐 `python tech-review/slides/build_slides.py && tech-review/slides/make_pdf.sh`로 재생성
- [ ] 모든 슬라이드 하단에 출처 표기 (논문 번호, 벤더 문서 URL, `results_final/…` 파일명)
- [ ] 한 번 소리 내어 리허설해서 11분을 넘지 않는지 확인
- [ ] 발표 중 AI 사용 규정: 내용은 내 실험과 내 분석으로 설명할 것 (과제 지침: 일반 정보만 반복하면 불충분)
