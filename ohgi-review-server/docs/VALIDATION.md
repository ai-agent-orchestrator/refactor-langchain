# 구현 및 검증 기록

검증일: 2026-11-13 (Asia/Seoul). 원본 기준: legal-intake-fastapi-lab main `4fc98d5`. 대상: refactor-langchain의 `ohgi-review-server`.

## 단계별 완료 범위

| 브랜치 | 포함 단계 | 단계 종료 시 테스트 |
|---|---|---|
| branch1 | LCEL, 구조화 출력 | 21 passed + 7 subtests passed |
| branch2 | 위 단계 + 검토·재작성, SSE | 27 passed + 7 subtests passed |
| branch3 | 위 단계 + 체크포인터 수정, 규정 RAG | 38 passed + 7 subtests passed |

branch3에서는 `uv run pytest -q`와 같은 환경의 `.venv/Scripts/python.exe -m pytest -q --basetemp=.runs/pytest-final`로 확인했습니다. 최종 실패·오류·skip은 없습니다. 하위 라이브러리의 Python asyncio deprecation 경고 14개는 남아 있으며 기능 실패와 구분합니다.

## 확인한 동작

- 기존 리뷰 등록 201·조회 200·검증 422·없는 리뷰 404.
- 실제 ChatOpenAI/SDK 경로의 잘못된 키 401·모델 없음 404·제한 429·서버 오류 500을 HTTP 전송 대역으로 재현하고, 일반 답글 API의 기존 502로 변환.
- 시작 시 한 번의 모델·체인 생성, 요청 간 재사용, 종료 시 연결 정리.
- 구조화 스키마, camelCase 응답, 1·2·5점 및 환불 키워드의 fake 결과 구분.
- 검토가 계속 실패해도 최대 두 번만 재작성하고 종료. 피드백과 직전 초안 전달.
- SSE의 draft 토큰만 전달, 검토 내부 출력 제외, 최종 done, 스트림 오류 이벤트와 취소 전파.
- 체크포인트 원본·직전 답글 복원, 리뷰별 기억 격리, 초안 없는 수정 409, 공백 422, 재시작 초기화.
- 실제 Chroma에 규정 문서를 적재·검색하고 출처·절·chunk ID·규정 버전 보존.
- 실제 디스크 Chroma를 다시 열 때 문서 재임베딩 없이 기존 인덱스 재사용. OpenAI 임베딩 전송은 HTTP 대역.
- 네이티브 비동기 임베딩 호출과 로컬 Chroma 검색의 작업 스레드 분리.
- 검색 실패 시 일반 502, 시작된 SSE는 error 이벤트.
- 근거 부재 시 생성 호출을 생략하고 확인 안내, 대표적인 보상 확약은 재작성 후 미통과면 확인 안내로 대체.

## 실제 로컬 서버 확인

`scripts/verify_local.py`는 임시 포트의 실제 Uvicorn을 켜고 검사한 뒤 자기 서버를 종료합니다. fake 모드, 실제 Chroma, 네트워크 HTTP 클라이언트를 사용했습니다.

```text
PASS: live localhost /docs 200; create 201; get/reply 200; rating 6 -> 422; missing -> 404
PASS: sync handlers -> AnyIO worker thread; async reply -> MainThread
PASS: model created once; draft/review on MainThread; incremental SSE tokens before done
PASS: real Chroma retrieval and source metadata; checkpointed one-sentence revision
```

## 실제 모델 확인 절차 — 별도 실행 필요

1. `.env.example`을 `.env`로 복사하고 본인 키와 구조화 출력을 지원하는 모델을 설정합니다. `FAKE_LLM=false`, `RAG_ENABLED=true`를 설정하고 서버를 재시작합니다. 문서 임베딩부터 외부 API 호출이 발생할 수 있습니다.
2. `/docs`에서 1점 환불·이물질 리뷰와 5점 칭찬 리뷰를 각각 등록합니다. 응답의 본문·tone·needsFollowup·sources를 비교합니다.
3. 환불 리뷰에 쿠폰·전액 환불 약속이 생기지 않고 담당자 확인 절차로 안내되는지, 출처가 실제 규정과 맞는지 확인합니다.
4. 생성 후 `{"instruction":"한 문장으로 줄여 줘"}`만 수정 API에 보내 맥락을 유지하는지 확인합니다.
5. `curl.exe -N -X POST http://127.0.0.1:8011/api/reviews/1/reply/stream`으로 실제 모델의 순차 전달을 확인합니다. 토큰은 검토 전 임시 초안입니다.
6. 의도적인 오류 실험은 `RAG_ENABLED=false`로 시작 시 문서 임베딩을 분리한 뒤 잘못된 키 또는 모델로 답글을 요청해 502를 확인할 수 있습니다. RAG가 켜져 있으면 잘못된 임베딩 키는 서버 시작 실패가 될 수 있습니다.

실제 유료 모델 품질·검색 성능, 완전한 환각/인젝션 차단, 운영 다중 프로세스·권한·보존기간·부하 시험은 수행하지 않았습니다. fake 결과와 HTTP 대역을 실제 의미 품질로 표시하지 않습니다.

## 학습자료

- 수업 원본 최신 확인: `09_langchain` 커밋 `fa6525000cdfe2428b75e14236c2880dbc54b195`.
- `docs/LECTURE_TO_CODE.md`: 05·06·07·10·11·12·13과 우리 파일·함수 대응.
- `docs/study/diagrams`: 수정 가능한 Mermaid 원본 21개.
- `output/pdf/LANGCHAIN_REFACTOR_STUDY_DARK.pdf`: 26쪽, 한글 폰트 내장, 렌더된 흐름도와 클릭 가능한 수업 출처 포함.
- `scripts/study_content.py` → `render_study_diagrams.cjs` → `build_study_pdf.py` 순서로 자료 재생성. PDF 제작에는 앱 번들 ReportLab·Pillow·Poppler, Mermaid 렌더에는 로컬 Playwright·Chrome을 사용했습니다.
