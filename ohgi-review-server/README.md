# ohgi-review-server

> **현재 LangChain·LangGraph 실습 안내:** 저장소의 [루트 README](../README.md)에서 branch1·2·3 및 각 단계 문서를 확인하세요. 아래 본문은 리팩토링 전 서버 설명을 보존한 것이며, 변경된 실행 방법·기능·검증 결과는 단계별 문서에 있습니다.

> **개인 복습용 AI 생성 참고본**으로 구분합니다. 강사는 구조를 직접 세우고 AI는 문법·자료구조·오류 이해에 제한해 활용하라고 안내했습니다. 제출용 코드는 수업 규칙에 맞춰 직접 구성할 때 비교 자료로 사용하고, 이 참고본을 직접 작성한 제출물로 표시하지 않습니다.

사용자가 제공한 수업 명세에 맞춘 최소 리뷰 서버입니다. **동기 등록·조회 2개 + 비동기 LLM 답글 1개**를 구현합니다. 별도의 Legal Intake 21개 API·NeMo action 9개는 이 과제 서버에 넣지 않습니다.

## API와 예시

| API | 구현 | 결과 |
|---|---|---|
| POST `/api/reviews` | def | 정상 201, 필드·별점 오류 422 |
| GET `/api/reviews/{review_id}` | def | 정상 200, 사용자 정의 예외·처리기로 404 |
| POST `/api/reviews/{review_id}/reply` | async def | 저장 리뷰 조회 → 프롬프트 → await LLM → 답글 200, 외부 호출 실패 502 |

리뷰 등록 JSON:

```json
{"customerName":"연습손님","rating":5,"content":"설명이 친절했습니다."}
```

서버가 `reviewId`를 발급합니다. 별점은 정수 1~5, 이름은 1~50자, 본문은 1~2000자입니다. 응답은 camelCase입니다. 이름·본문 길이는 제공 명세에 구체적인 수치가 없어 학습용으로 정한 값입니다.

리뷰 생성 후 POST `/api/reviews/1/reply`를 본문 없이 실행합니다. 기본 fake 모드에서는 model이 fake-llm이며 가짜 초안을 반환합니다. 답글은 자동 게시하거나 저장하지 않습니다. 딕셔너리 리뷰는 재시작하면 사라집니다.

## 실행

현재 PC에 이미 준비된 가상환경을 재사용할 수 있습니다.

```powershell
cd C:\myLectureWs\legal-intake-fastapi-lab\ohgi-review-server
C:\myLectureWs\fastapi-openai-practice\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

Swagger: http://127.0.0.1:8011/docs

독립 가상환경을 만들 때는 이 폴더에서 다음을 실행합니다.

```powershell
uv sync --python 3.14
uv run fastapi dev --port 8011
```

## 가짜/실제 OpenAI 구분

현재 `.env`는 FAKE_LLM=true이고 실제 키는 없습니다. `.env.example`을 참고해 로컬 `.env`를 편집하고 다음을 설정하면 실제 client를 선택합니다.

```dotenv
FAKE_LLM=false
OPENAI_API_KEY=본인_키
OPENAI_MODEL=본인_프로젝트에서_사용할_모델
```

키를 채팅이나 Git에 넣지 않습니다. real 모드에 키가 없으면 서버 시작에 실패합니다. 모델 접근 권한과 실제 유료 호출은 아직 검증하지 않았습니다. fake 답글 성공을 실제 연결 성공으로 표시하지 않습니다. 환경 변수는 .env보다 우선할 수 있고 변경 후 재시작해야 합니다.

## 코드 읽기 순서

### 강사가 안내한 직접 작성 순서

1. 빈 실습 폴더에서 uv init → fastapi[standard] 추가 → 패키지 폴더와 빈 __init__.py → entrypoint 설정.
2. 엔티티 → 딕셔너리 저장소 → DTO → 사용자 정의 예외·처리기 → 리뷰 서비스 → 의존성 함수 → 라우터 → main 조립.
3. pydantic-settings·openai 추가 → 설정 → LLM client → 답글 서비스 → 의존성 함수 → 비동기 핸들러 → lifespan.

config.py와 llm_client.py는 chap02를 참고할 수 있습니다. 학습 시 위 순서로 직접 작성한 뒤 아래 파일 읽기 순서와 비교합니다. 기존 참고본 폴더에서 uv init을 다시 실행하지 않습니다.

### 참고본을 읽는 순서

1. schemas/review.py: 요청·응답과 1~5 별점 제약.
2. routers/review_router.py: def 두 개·async def 한 개.
3. dependencies.py: 공유 저장소·client를 서비스에 주입.
4. review_service.py → review_repository.py: 동기 저장·조회.
5. reply_service.py: 불변 리뷰를 조회해 프롬프트를 만들고 await.
6. clients/llm_client.py: 가짜 대기와 실제 AsyncOpenAI 호출.
7. core/exceptions.py: 사용자 정의 404·502 처리.
8. main.py: lifespan에서 자원 생성·종료, 라우터와 처리기 등록.

서비스·저장소 등 실제 파일은 모두 app 아래의 제시된 패키지에 있습니다. 각 app 패키지에 빈 `__init__.py`를 만들었습니다. 이름·별점·리뷰 데이터는 JSON으로 구분해 프롬프트에 전달하며 임의 지시로 실행하지 않습니다. 이 짧은 과제가 개인정보 마스킹·NeMo·운영 인증을 갖췄다는 의미는 아닙니다. 합성 리뷰로 로컬 실험합니다.

## 검증

추가 테스트 설치 없이 실행하는 방법:

```powershell
C:\myLectureWs\fastapi-openai-practice\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

독립 uv 환경에서는 `uv run pytest -v`도 사용할 수 있습니다. 정상 등록·조회, rating 6 등 검증 오류, 없는 리뷰·답글 404, 저장된 내용으로 await 호출, LLM 실패 502, 동기/비동기 구분, 재시작 초기화, 동시 ID 발급을 확인합니다. SDK 오류 테스트도 mock으로 실행하며 실제 OpenAI 네트워크는 호출하지 않습니다.

OpenAI 비동기 호출 방식: [공식 Python 문서](https://developers.openai.com/api/reference/python). 학원 chap01·02의 구조를 참고하고 이번에 제공된 리뷰 명세로 작성했습니다. 게시판 샘플 전체 소스가 주어진 것으로 표시하지 않습니다.

## 완성 기준과 스레드 확인

실제 Uvicorn 서버·fake 모드의 로컬 HTTP 확인을 마쳤습니다. /docs 200, 등록 201, 조회·답글 200, rating 6의 422, 없는 ID 404와 아래 스레드 이름을 확인했습니다. 확인용 서버는 종료했습니다. 실패 client의 502는 별도 자동 테스트에서 확인했습니다.

일반 Uvicorn 실행에서 터미널에는 다음처럼 출력됩니다. 이름·리뷰 본문·키는 로그에 쓰지 않습니다.

```text
[register] thread=AnyIO worker thread
[find] thread=AnyIO worker thread reviewId=1
[reply] thread=MainThread reviewId=1
```

TestClient는 자체 테스트 스레드에서 ASGI 앱을 실행할 수 있으므로 거기서도 MainThread라고 가정하지 않습니다. 실제 Uvicorn 서버와 TestClient 검증을 구분합니다.

Postman에서는 아래 순서로 직접 확인합니다. 수동 Postman 검증은 아직 하지 않았습니다.

1. POST http://127.0.0.1:8011/api/reviews, Body → raw → JSON에 위 등록 본문 입력: 201과 reviewId.
2. rating을 6으로 변경해 같은 요청: 422.
3. GET http://127.0.0.1:8011/api/reviews/1: 200. ID를 999로 변경: 사용자 정의 404.
4. POST http://127.0.0.1:8011/api/reviews/1/reply, 본문 없음: 저장 리뷰 기반 답글과 터미널 MainThread.

이 폴더에서 아래 명령으로 임시 로컬 서버를 켜 실제 HTTP와 스레드 이름을 자동 확인할 수 있습니다. fake 모드를 강제하고 확인 후 자기 서버를 종료합니다.

```powershell
C:\myLectureWs\fastapi-openai-practice\.venv\Scripts\python.exe scripts\verify_local.py
```

이 검증은 기존 환경의 Uvicorn 직접 실행입니다. 독립 uv 환경의 `uv run fastapi dev`는 위 설치 순서대로 환경을 만든 후 확인합니다. 실제 유료 OpenAI와 수동 Postman 확인을 대신하지 않습니다.

## 선택 심화 — 아직 구현하지 않음

- 별점 2 이하이면 사과로 시작하는 등 말투 변경.
- 생성한 답글을 리뷰에 저장하고 조회 응답에 포함.
- def + 동기 LLM 메서드의 비교용 답글 API를 추가해 Postman 두 탭으로 비교.

필수 3개 API 검증 후 필요할 때만 진행합니다. 현재 답글을 저장하거나 동기 AI endpoint를 추가하지 않았습니다.

## 커밋 전 .env 확인

이 폴더 자체의 .gitignore와 상위 저장소 .gitignore에 모두 .env를 제외했습니다. 현재 .env는 가짜 모드 설정만 포함합니다. 나중에 별도 Git 저장소로 초기화한 뒤에는 `git check-ignore .env`와 `git status --short`로 확인하고, 이미 추적한 .env는 ignore만 추가해도 추적이 해제되지 않는다는 점을 확인합니다. 이번에 커밋·업로드는 하지 않았습니다.
