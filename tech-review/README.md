# CS410 Technology Review — 패키지

- 과제: CS410 Fall 2026 Technology Review (4학점 필수, 통과/실패, **개인 과제**, 마감 2026-11-09 14:59 KST)
- 주제: **Decision-model reranking vs cross-encoder rerankers — 두 데이터셋(MIRACL 252q, JQaRA 1,667q)에서 품질·비용·지연 실측 비교와 메커니즘 설명**
- 근거 데이터: 이 레포의 `results_final/FINAL.md` (최종 표), `results_final/ANALYSIS.md` (추가 분석), 상세 설정은 `results_jqara/SUMMARY.md`

## 파일

| 파일 | 용도 |
|------|------|
| `overview.md` | TextData topic community Overview 제출용 영문 본문 (100단어+, `#pin`) |
| `slides/slides.html`, `slides/slides.pdf` | 발표 슬라이드 15장 (영문, 흰 배경 논문 스타일). HTML은 ←/→ 키로 넘김. 재생성: `python tech-review/slides/make_figures.py && python tech-review/slides/build_slides.py && tech-review/slides/make_pdf.sh` (그림은 `slides/figs/`, 가격·지연 대비 성능 분석은 `results_final/PARETO.md`) |
| `slide-outline.md` | 발표 계획: 7파트 구조, 파트별 시간 배분, 리소스 풀 20개 (슬라이드 파일과 번호가 일치하지 않음) |
| `technical-notes.md` | 심층 기술 내용: cross-encoder, LLM prompting 3방식, decision model(만드는 방식·reranker로 쓰는 법), 실험 설계, 결과, 한계, 실무 가이드. 모든 주장에 근거 등급 표기 |

## 공식 제출 절차 (Coursera 과제 페이지, 2026-11-01 확인)

1. [ ] TextData 계정 생성 + Chrome Extension 설치 (https://textdata.org/about) — 이미 있으면 생략
2. [ ] 주제 선택 (승인 불필요, 텍스트 검색·분석 관련이면 됨)
3. [ ] TextData에서 기존 Tech Review 검색 → 겹치면 그 리뷰 링크 + 내 리뷰가 더하는 점 설명
   (이번 학기 `Tech Review: LLM Rerankers as a Second Stage over BM25` https://textdata.org/submissions/6ae0097ca8567d79c2f76fb9 — `overview.md`에 반영됨)
4. [ ] **public** community 생성 (CS410 Fall 2026 community *안이 아님*): Communities → Create → 이름 입력 → CREATE → 연필 아이콘 → public → SAVE
5. [ ] community에 `Overview of [주제]` submission (100단어+, 정의·배경·유용성) + `#pin`
   (Campuswire #301에 `#pin`이 실제로 고정되지 않는다는 보고가 있음 — 해결 여부는 확인 못 함)
6. [ ] 웹 리소스 **10개 이상** 저장 + 각각 짧은 설명 (Chrome Extension이 가장 쉬움) — 후보: `slide-outline.md` 리소스 풀
7. [ ] 발표 녹화 (공식 가이드라인 약 8~12분; 슬라이드 + 음성 + 내 분석 + 리소스 인용) → 영상 업로드
   (영상 호스팅 방법은 공식 안내에 구체적 지정 없음 — "course submission instructions에 따라 제출")
8. [ ] **CS410 Fall 2026 community**에 submission: Tech Review community URL + 영상 URL + `#techreview` + `#fa2026`
   (community: https://textdata.org/community/6a8e5f4ca8567d79c2f60b30)
9. [ ] Coursera 과제 페이지에서 명예 규율 동의 후 제출 (본인이 직접)

AI 사용 규정(과제 지침): AI가 쓴 리뷰를 내 것처럼 제출하면 안 됨. 발표에는 내 탐구·평가·의견이 있어야 하며, 질문을 받을 수 있음.

## 상태

- [x] 실험 완료, 최종 표·분석 기록 (`results_final/`)
- [x] overview 영문 초안, 슬라이드 아웃라인, 심층 기술 노트 작성
- [ ] 슬라이드 제작, 녹화, TextData·Coursera 제출 (모두 미완료)
