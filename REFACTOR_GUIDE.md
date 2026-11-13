# 단계별 LangChain / LangGraph 실습

원본: `ai-agent-orchestrator/legal-intake-fastapi-lab` main `4fc98d5`.
원본 전체를 보존하고 **`ohgi-review-server`만** 리팩토링합니다. Legal Intake 루트 서버와 리뷰 서버는 별도 앱입니다.

| 브랜치 | 누적 내용 | 읽을 문서 |
|---|---|---|
| branch1 | 1단계 LCEL + 2단계 구조화 답글 | [1단계](ohgi-review-server/docs/01_LCEL.md), [2단계](ohgi-review-server/docs/02_STRUCTURED_OUTPUT.md) |
| branch2 | 3단계 검토·재작성 + 4단계 SSE | 해당 브랜치의 03·04 문서 |
| branch3 | 5단계 체크포인터 수정 + 6단계 규정 RAG | 해당 브랜치의 05·06 문서 |

```powershell
git switch branch1
cd ohgi-review-server
uv sync --python 3.14
uv run uvicorn app.main:app --port 8011
```

브랜치 전환 전 서버를 끄고, 전환 후 같은 폴더에서 `uv sync`를 다시 실행하세요. `.env`는 커밋되지 않습니다. 기본 fake 모드로 먼저 API 흐름을 확인할 수 있습니다. 원본 README는 이력과 원본 앱 설명을 위해 보존했습니다. 변경된 리뷰 서버 사용법은 이 문서와 단계별 문서를 기준으로 보세요.
