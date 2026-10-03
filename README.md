# Rule_Keeper · 분할매수 기록장

라오어 무한매수법(V2.2, V4.0)과 VR 5.0을 여러 전략으로 동시에 운용할 때,
매일 저녁 주문표를 계산하고 체결을 기록하며 AI에게 상태를 물어볼 수 있는 개인 비서입니다.
감정이 아니라 규칙대로 매매하도록 돕습니다.

> 투자 권유가 아닌 규칙 계산 보조 도구입니다. 무한매수법·VR 방법론의 원저작자는 라오어입니다.

## 진행 상황

- [x] 계산 엔진 (`backend/app/engine`) — 카페 원문 예시 표 재현 테스트
- [x] FastAPI + Firestore + 필수 API (data CRUD·summary, conversations, chat)
- [x] 전략·주문표·체결 확정·백테스트·VR 갱신 API, Function Calling 도구 5개
- [x] 프론트엔드 (바닐라 HTML/CSS/JS): 오늘 주문, 전략, 체결 기록, 요약·통계, AI 비서, 다크 모드, 그래프, CSV/JSON 내보내기
- [ ] 배포 (Render, Vercel)
- [ ] 보너스 마무리 (GPT Actions 연결)

## 기술 스택

FastAPI · Firebase Firestore · OpenAI API (Function Calling) · yfinance · 바닐라 JS · Render · Vercel

## 폴더 구조

```
backend/
  app/
    engine/      계산 엔진 (외부 의존성 없음): infinite.py, vr.py, common.py, backtest.py
    services/    상태 재생, 주문표, 체결 확정, 요약, 채팅, 대화
    routers/     FastAPI 엔드포인트
    repo/        저장소 (firestore.py, memory.py)
    schemas.py   요청 검증
    main.py      앱 진입점
  scripts/seed.py  시세·데모 데이터 적재
  tests/         엔진 30개 + 서비스 17개 테스트
frontend/
  index.html     화면 뼈대 (해시 라우터로 5개 화면 전환)
  config.js      백엔드 주소 (배포 후 Render 주소로 변경)
  css/style.css  스타일 (라이트/다크 테마)
  js/            api.js, chart.js(SVG 그래프), slip.js(주문 전표), views/(화면별 코드)
render.yaml      Render 배포 설정
```

## 로컬 실행

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env  → 값 채우기

python -m scripts.seed --demo   # 시세 + 시뮬레이션 전략 2개 (data 수백 건)
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

화면은 터미널을 하나 더 열어 `frontend` 폴더에서 정적 서버를 띄웁니다.

```bash
cd frontend
python -m http.server 5500      # http://127.0.0.1:5500
```

데이터를 바꾸는 요청(체결 확정, 전략 등록, 채팅)은 화면 왼쪽 아래 **연결 설정**에 `APP_API_KEY` 값을 넣어야 합니다. 키는 그 브라우저에만 저장되고 코드에는 들어가지 않습니다.

Firebase 없이 먼저 확인하려면 `.env`에서 `STORAGE=memory`로 두면 됩니다 (서버를 끄면 데이터가 사라집니다).

## 환경 변수 (최소 세트)

| 이름 | 용도 |
| --- | --- |
| `OPENAI_API_KEY` | GPT 호출 키 (교육장 가상 키) — `.env`와 Render 환경 변수에만 저장 |
| `OPENAI_BASE_URL` | OpenAI 호환 주소 (교육장: `https://copa.codyssey.kr/v1`, 비우면 OpenAI 기본) |
| `OPENAI_MODEL` | 모델 이름 (기본 gpt-5-mini) |
| `FIREBASE_CREDENTIALS` 또는 `FIREBASE_CREDENTIALS_PATH` | 서비스 계정 키 (JSON 문자열/base64 또는 파일 경로) |
| `APP_API_KEY` | 데이터를 바꾸는 요청에 필요한 `X-API-Key` 값 |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 (Vercel 주소) |
| `PUBLIC_API_URL` | GPT Actions 스키마의 서버 주소 |

## 주요 API

| 메서드 · 경로 | 설명 |
| --- | --- |
| `POST/GET /api/data`, `PUT/DELETE /api/data/{id}` | 체결 기록 CRUD (과제의 date·value·memo + 체결 정보) |
| `GET /api/data/summary` | 데이터 요약 (프롬프트 주입용 `text` 포함) |
| `POST/GET /api/conversations`, `GET/DELETE /api/conversations/{id}` | 대화 저장·목록·불러오기·삭제 |
| `POST /api/chat` | 요약 주입 → GPT(도구 호출) → 대화 자동 저장 |
| `GET /api/orders/today` | 전체 전략의 확정 대기 주문표 + 오늘 주문표 |
| `POST /api/strategies/{id}/orders/{date}/confirm` | 자동 판정 결과를 체결 기록으로 확정 |
| `POST /api/strategies/{id}/backtest` | 시뮬레이션 전략 백테스트 |
| `GET /api/actions/openapi.json` | GPT Actions용 스키마 (조회 API만) |

전체 목록은 `/docs`(Swagger UI)에서 확인할 수 있습니다.

## 화면

| 화면 | 내용 |
| --- | --- |
| 오늘 주문 | 전략별 다음 거래일 주문 전표(매수 빨강·매도 파랑), 전날 주문의 자동 체결 판정과 확정 |
| 전략 | 전략 목록·등록(실전/시뮬레이션)·설정 수정·종료, 상세(상태, 그래프, 사이클·V 갱신 이력, V 갱신) |
| 체결 기록 | data CRUD, 전략·기간·출처 필터, CSV/JSON 내려받기 |
| 요약·통계 | 종목별 시세 그래프(20일 이동평균), 기간·평균·최대·최소·추세·변동성·최대 낙폭, AI에게 들어가는 요약 원문 |
| AI 비서 | 대화 기록 · 채팅 · AI가 보는 요약 3단, 전략 선택, 사용한 도구 표시 |

## 테스트

```bash
cd backend
python -m unittest discover -s tests -t .
```

## 설계 원칙

- **사실은 저장하고 상태는 계산한다.** 설정·체결·주문표·VR 스냅샷만 저장하고 T·평단·별지점은 매번 체결 기록을 재생해 구한다. 체결을 고치면 그 뒤 상태가 저절로 다시 계산된다.
- **숫자는 백엔드가, 설명은 GPT가.** GPT에는 계산된 요약과 읽기 전용 도구만 주고 직접 계산하지 말라고 지시한다.
