# refactor-langchain - 단계별 리뷰 답글 서버

`legal-intake-fastapi-lab`의 원본 코드를 보존하고 `ohgi-review-server`를 LangChain·LangGraph로 발전시킨 학습 저장소입니다. **main은 원본 기준과 안내**, 실제 실습 코드는 아래 세 브랜치에서 확인합니다.

| 브랜치 | 누적 구현 | 설명 |
|---|---|---|
| [branch1](https://github.com/ai-agent-orchestrator/refactor-langchain/tree/branch1) | 1·2단계: LCEL 비동기 체인, 구조화 출력 | [1단계](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch1/ohgi-review-server/docs/01_LCEL.md), [2단계](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch1/ohgi-review-server/docs/02_STRUCTURED_OUTPUT.md) |
| [branch2](https://github.com/ai-agent-orchestrator/refactor-langchain/tree/branch2) | 3·4단계: 상한 있는 자체 검토·재작성, SSE | [3단계](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch2/ohgi-review-server/docs/03_REVIEW_GRAPH.md), [4단계](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch2/ohgi-review-server/docs/04_SSE.md) |
| [branch3](https://github.com/ai-agent-orchestrator/refactor-langchain/tree/branch3) | 5·6단계: 체크포인터 수정 API, 매장 규정 Chroma RAG | [5단계](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch3/ohgi-review-server/docs/05_MEMORY.md), [6단계](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch3/ohgi-review-server/docs/06_POLICY_RAG.md) |

```powershell
git switch branch3
cd ohgi-review-server
uv sync --python 3.14
uv run uvicorn app.main:app --port 8011
```

기본 fake 모드로 API 흐름을 확인할 수 있습니다. 브랜치 전환 전에 서버를 종료하고 전환 후 `uv sync`를 다시 실행하세요. 브랜치별 실제 사용법은 위 단계 문서를 기준으로 봅니다.

**학습자료:** [26쪽 다크모드 PDF](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch3/ohgi-review-server/output/pdf/LANGCHAIN_REFACTOR_STUDY_DARK.pdf) · [수업 → 코드 주석집](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch3/ohgi-review-server/docs/LECTURE_TO_CODE.md) · [Mermaid 원본](https://github.com/ai-agent-orchestrator/refactor-langchain/tree/branch3/ohgi-review-server/docs/study/diagrams) · [검증 결과](https://github.com/ai-agent-orchestrator/refactor-langchain/blob/branch3/ohgi-review-server/docs/VALIDATION.md).

개인 복습을 위한 AI 생성 참고 구현입니다. 수업 제출 규칙을 확인하고 본인이 작성·검증한 코드와 구분해 사용하세요. 원본 저장소의 다른 앱과 미커밋 작업은 변경하지 않았습니다.

---

## 원본 프로젝트 설명 (아래 내용 보존)

# Legal Intake FastAPI Lab

FastAPI 기반 상담 준비 안내와 법률 마케팅 도구를 만드는 공개 프로젝트입니다. 이 저장소의 **필수 개발 범위는 기존 접수·안내 Python action, 보안 action 9개, 법률 마케팅 강화**입니다. 앱 API는 기존 MVP를 포함해 **최대 11개**로 제한합니다.

LangChain·LangGraph·LangSmith·RAG·임베딩·벡터 검색·memvid는 이 저장소의 필수 범위가 아니며, **리서치 multi-agent 검색 도구 저장소에서 따로 완성**합니다. ([7. RAG·검색 기능 분리](#7-rag검색-기능-분리))

[한국어](README.md) | [English](README.en.md)

## 1. 개발 범위

| 구분 | 포함 | 제외 (리서치 저장소로 이동) |
|---|---|---|
| 접수·안내 | 접수 등록·조회, 저장된 사실 기반 비동기 안내 | 검색 근거 기반 안내 생성 |
| 보안 | 보안 action 9개 전체와 서비스의 용량·예산·정산 관리 | RAG 자료 검사·근거 판정 |
| 마케팅 | 게시글·후기, M01 요약, M02 답변 초안, `check_marketing_response` | 검색 결과를 활용한 마케팅 초안 |
| 검색·생성 | 기존 OpenAI 비동기 어댑터와 fake client | LangChain·LangGraph·LangSmith·E5·memvid·Llama |

**완료 기준은 "action이 구현·연결되고 시험을 통과했는가"입니다.** 계획 문서의 존재나 샘플 실행 성공을 완료로 보지 않습니다.

## 2. 현재 구현 상태

| 구분 | 상태 |
|---|---|
| 루트 MVP | 동기 접수 등록·조회 + 비동기 안내 3개 API 구현. 기존 테스트 23개 |
| 선별 기반 `4fcc698` | 결정 DTO·불변 문맥·용량 관리자·예산 장부·위험 저장소 |
| L01 NeMo 래퍼 / L02 문맥·세션 위험 | 보안 입력 action 기반 구현. 실제 NeMo 시험은 별도 환경으로 구분 ([구현 기록](docs/L01_L02_IMPLEMENTATION.md)) |
| 보안 action 9개 | 2026-11-09 `feat/marketing-actions`: 9개 구현·연결. 독립 마케팅 코어·얇은 어댑터 추가. [현황·시험·제한](docs/MARKETING_IMPLEMENTATION_2026-11-09.md) |
| 법률 마케팅 게시판·M01/M02 | 11개 API 전체 앱에 연결. 검토·마스킹한 초안만 반환하고 M02는 안전 초안만 저장. 자동 외부 게시 없음 |
| RAG·검색 코드 | 저장소에 남아 있으나 이 저장소의 범위 밖. 리서치 저장소로 이전 예정 |

접수는 정의한 전화·이메일·주민번호 패턴을 **저장 전에** 가립니다. 안내는 저장값을 재검사·마스킹한 뒤 공급자에 보내고, 전체 출력 검사·최종 마스킹·문맥 검증 뒤 반환합니다. 등록의 정책 차단은 HTTP 200 + `blocked=true`이며 저장하지 않습니다. 등록·안내 모두 선택적 `X-Session-ID`를 받으며 인증 정보로 쓰지 않습니다. 정상 응답과 기존 API 3개는 유지합니다.

보안·게시판 회귀는 **Python 3.14 local 214개, Python 3.12 실제 NeMo 포함 285개 통과**이며 RAG 시험과 분리했습니다. 판정 코어는 표준 라이브러리만 쓰며 파일 단독 실행 구조 시험을 통과했습니다. 기존 RAG 오류를 해결·재실행한 결과나 저장소 전체 통과가 아닙니다. 실제 NeMo rail과 fake 공급자 시험, 실제 유료 공급자 호출은 서로 다른 검증입니다. [마케팅 구현·시험 로그·마스킹 확대 측정](docs/MARKETING_IMPLEMENTATION_2026-11-09.md)을 참고하세요.

보존 브랜치 `wip/codex-legal-snapshot`은 복구용이며 `main`에 합치지 않습니다.

기존 접수 MVP 팩터리(`create_app`)의 API는 다음 3개입니다. 실제 실행 대상 `app.main:app`은 `create_full_app`으로 조립한 11개 API 앱입니다.

| 메서드·경로 | 방식 | 정상·오류 |
|---|---|---|
| POST `/api/intakes` | `def` | 등록 201, 입력 오류 422 |
| GET `/api/intakes/{intake_id}` | `def` | 조회 200, 없으면 404 |
| POST `/api/intakes/{intake_id}/guidance` | `async def` | 저장된 사실 기반 안내, LLM 실패 502 |

메모리 데이터는 재시작하면 초기화됩니다. fake/mock 성공과 실제 공급자 호출 성공은 별도로 확인합니다.

## 3. 보안 action 9개는 전체 필수

| action | 책임 |
|---|---|
| `validate_request_context` | 요청·snapshot·응답의 연결 확인 |
| `check_session_risk` | 누적 위험과 기존 세션 차단 확인 |
| `check_input_policy` | 법률 악용·jailbreak·injection·secret·privacy 검사 |
| `mask_personal_data` | 저장·외부 전송·반환 전 정의한 개인정보 치환 |
| `check_generation_admission` | 동시 실행·유한 대기열·대기 한도 |
| `check_request_budget` | 원자 예산 확인·예약 |
| `check_output_policy` | 생성 전체의 빈값·길이·정책 검사 |
| `check_marketing_response` | 보장·과장 표현의 사람 검토 표시 |
| `record_risk_event` | 확정 정책 차단의 중복 없는 위험 기록 |

서비스가 **용량 확보 → 예산 예약 → 호출 → 정산 → 슬롯 반환**을 관리합니다. timeout·취소·실패 정리와 실제 NeMo rail의 호출·결과 소비를 시험했습니다. 현재 9개 action은 접수·안내·마케팅 각 대상 경계에 연결됐으며 유료 공급자 실호출은 미검증입니다.

### 마케팅 강화: `check_marketing_response`

법률 마케팅 게시판의 **M01 요약과 M02 답변 초안은 전체 출력 검사 후 이 action을 반드시 통과**하고, 최종 마스킹·문맥 확인 뒤에만 반환합니다. 보장·과장 표현은 검토 필요로 표시하고 안전하게 정리한 초안만 제공하며 자동 게시하지 않습니다.

정상 문구·보장 표현·부정/인용 문맥·개인정보·검사기 실패 사례를 테스트합니다. 정상 부정문과 보장 표현이 한 문장에 섞인 우회 사례도 포함합니다. 샘플 실행 성공과 AI 보안 확장 완료는 따로 확인합니다.

내부 결정은 `ALLOW/BLOCK/TRANSFORM/REVIEW`, 사유는 `reasonCode/detailCode`입니다. 기존 `COST_LIMIT_BLOCKED`·`DYNAMIC_SESSION_BLOCKED`와 신규 제안을 구분합니다. 패턴 마스킹의 완전성이나 표현 검사의 법률적 적합성을 보장한다고 가정하지 않습니다.

## 4. 최종 앱 API는 최대 11개

아래 11개 operation을 `app.main:app`에서 제공합니다. 기존 MVP 팩터리 3개와 전체 앱 11개는 각각 별도 시험으로 고정합니다.

| 기능 | 메서드·경로 | 개수 |
|---|---|---|
| 기존 접수 | POST `/api/intakes`, GET `/api/intakes/{intake_id}`, POST `/api/intakes/{intake_id}/guidance` | 3 |
| 상태 | GET `/health` | 1 |
| 게시글 | POST·GET `/api/posts`, GET `/api/posts/{postId}` | 3 |
| 후기 | POST·GET `/api/posts/{postId}/reviews` | 2 |
| AI 마케팅 | POST `/api/posts/{postId}/ai-summary`, POST `/api/reviews/{reviewId}/reply-draft` | 2 |
| 합계 | 메서드와 경로의 조합 | **11** |

이전 상세 설계의 21개는 과거 후보 목록입니다. 게시글 수정·삭제·독립 Chat/SSE·단독 guardrail API·검색 API를 여기에 더하지 않습니다. 동기 비교는 별도 학습 앱에서 진행합니다.

## 5. 개발 순서와 최소 학습 요구사항

개발은 **보안 action 9개 완성 → 서비스 경계(용량·예산·정산) → 게시판·후기 → M01/M02 + 마케팅 검사 → 회귀·통합 시험** 순서입니다.

기초 리뷰·답글 예제는 다음 순서만 유지합니다.

1. **프로젝트:** 빈 폴더의 `uv init` → `uv add "fastapi[standard]"` → 패키지 폴더 → `pyproject.toml`의 `entrypoint = "app.main:app"` 설정.
2. **리뷰 API:** 엔티티 → 딕셔너리 저장소 → DTO → 예외·처리기 → 서비스 → 의존성 함수 → 라우터 → `main.py` 조립.
3. **답글 API:** `uv add pydantic-settings openai` → 설정 → LLM client → 답글 서비스 → 의존성 함수 → 비동기 핸들러 → lifespan. `core/config.py`와 `clients/llm_client.py`는 기존 예제 구조를 참고할 수 있습니다.

완성 기준은 `uv run fastapi dev`, `/docs`·Postman의 세 API 호출, 등록 201·잘못된 입력 422·없는 리뷰 404, 저장 리뷰 기반 답글과 실제 서버 로그의 `MainThread` 확인입니다. [독립 리뷰 예제](ohgi-review-server/README.md)는 루트 접수 API와 구분합니다.

심화는 **별점 1~2 사과·공감 / 3 공감·개선 / 4~5 감사**, 검사 완료 답글의 저장·조회, 별도 `def`+동기 client와 비동기 client의 비교입니다. 주력 M02는 비동기로 유지하며 어느 별점도 마케팅 검사를 생략하지 않습니다.

`.env`는 Git에 올리지 않습니다. 기초 학습에서는 구조를 직접 설명·작성하고 AI는 자료구조·문법·오류 이해에 보조적으로 사용합니다. 막히면 기존 `HOWTO-chap01.md`·`HOWTO-chap02.md`·`HOWTO-chap03.md`를 참고합니다.

## 6. 현재 MVP 실행

저장소 루트에서 실행합니다. 기존 프로젝트에서 `uv init`을 다시 하지 않습니다.

```powershell
uv sync --python 3.14
$env:FAKE_LLM = "true"
$env:GUARDRAIL_BACKEND = "local"
uv run fastapi dev
```

Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

```powershell
# local 범위의 회귀 시험. 실제 NeMo 시험은 별도 환경으로 구분합니다.
uv run pytest -q -m "not nemo"
```

실제 OpenAI 키·모델 접근은 별도 검증합니다. 보안 전용 환경과 전체 시험 방법은 [구현 기록](docs/L01_L02_IMPLEMENTATION.md)을 참고합니다.

## 7. RAG·검색 기능 분리

아래 기능은 **리서치 multi-agent 검색 도구 저장소로 모아서 따로 완성**합니다. 이 저장소에는 새로 추가하지 않습니다.

- LangChain · LangGraph · LangSmith
- RAG · 임베딩(E5) · 벡터 검색 · memvid
- Llama 생성 어댑터, 합성 안내문 기반 검색 평가

이전 대상 후보(경로는 이전 시점에 다시 확인):

| 구분 | 경로 |
|---|---|
| 앱 코드 | `app/rag/` |
| 실행 환경 | `rag-runtime/` |
| 스크립트 | `scripts/` 중 E5·memvid·검색 평가 관련 파일 |
| 자료·시험 | `fixtures/rag/`, `tests/rag/`, `tests/test_rag_b03_b05.py` |
| 문서 | `docs/RAG_*.md`, `docs/CLAUDE_RAG_DESIGN_REVIEW.md`, `docs/EMBEDDING_RETRIEVAL_STUDY.md`, `docs/evidence/` |

이전이 끝나기 전까지 위 파일은 저장소에 남아 있지만 **이 저장소의 완료 기준에 포함하지 않습니다.** 이전 후 리서치 저장소에서 필요하면 보안 action을 재사용 모듈로 연결합니다.

## 8. 저장소 발전 순서

| 순서 | 역할 |
|---|---|
| ① 현재 `legal-intake-fastapi-lab` | FastAPI 단독에서 접수·보안·마케팅 기능 검증 |
| ③ [`langchain-rag-research-agent`](https://github.com/ai-agent-orchestrator/langchain-rag-research-agent) (구 python-memvid-guardrail) | 검증한 보안 부품을 재사용 모듈로 분리 |
| ② `spring-fastapi-async-refactor` | Spring 인증·인가와 FastAPI AI 서비스 연결 |
| 리서치 multi-agent 저장소 | LangChain·LangGraph·RAG 검색 도구를 따로 완성 |
| 이후 | 검증한 기능을 기반으로 별도 비공개 상업화 개발 |

① → ③ → ② 순서를 유지합니다. 이번에는 인증·인가·자동 외부 게시·일반 웹 검색·운영 DB·Redis/Celery/Kafka를 추가하지 않습니다. 기존 Java 서버와 DB도 수정하지 않습니다.

## 참고 문서

- [전체 보안 이전 목표](docs/SECURITY_MIGRATION_PLAN.md) · [마케팅 게시판 계약](docs/LEGAL_MARKETING_BOARD.md)
- [로컬 L01/L02 범위와 검증 기록](docs/L01_L02_IMPLEMENTATION.md)
