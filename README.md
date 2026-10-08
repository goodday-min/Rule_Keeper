# Rule_Keeper · 분할매수 기록장

라오어 무한매수법(V2.2, V4.0)과 VR(Value Rebalancing) 5.0을 여러 전략으로 동시에 운용할 때 쓰는 개인 비서입니다.  
매일 저녁 전략마다 주문표를 계산하고, 다음 날 체결을 기록하며, AI에게 현재 상태와 규칙의 근거를 물어볼 수 있습니다.
감정이 아니라 규칙대로 매매하도록 돕는 것이 목표입니다.

> 투자 권유가 아닌 규칙 계산 보조 도구입니다. 무한매수법·VR 방법론의 원저작자는 라오어입니다.

| 구분 | 주소 |
| --- | --- |
| 웹 화면 (Vercel) | https://rulekeeper-frontend.vercel.app |
| 백엔드 API (Render) | https://rule-keeper.onrender.com |
| Swagger UI | https://rule-keeper.onrender.com/docs |
| GPT Actions 스키마 | https://rule-keeper.onrender.com/api/actions/openapi.json |

Render 무료 요금제라 15분 동안 접속이 없으면 서버가 잠듭니다. 첫 접속은 30~60초 걸릴 수 있으며, 화면에 "서버를 깨우는 중" 안내가 나옵니다.

![오늘 주문 화면](docs/images/01_today_orders.png)

---

## 1. 서비스 소개 (무엇을 해결하나요)

일반 ChatGPT는 나의 주식 주문에 대한 전략 상태를 모릅니다. "오늘 뭐 주문 넣아야 해?"라고 물어도 일반론만 돌아옵니다.
주식 매수 매도의 한 방법 중 하나인 무한매수법과 VR(밸류 리밸런싱)을 여러 전략으로 동시에 돌리면 전략마다 T, 평단, 별지점, V가 달라서 매일 저녁 각각 손으로 계산하기 번거롭고 실수하기 쉽습니다.

Rule_Keeper는
- 매일의 시세(시계열 데이터)와 내 체결 기록을 Firestore에 저장하고,
- 규칙대로(전략대로) 상태와 다음 주문표를 서버가 계산하며,
- 그 요약을 GPT의 시스템 프롬프트에 넣어 **"내 상황을 아는 AI 비서"**로 답하게 합니다.

## 2. 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| 백엔드 | Python 3.11, FastAPI, Uvicorn, Pydantic, python-dotenv |
| 데이터베이스 | Firebase Firestore (firebase-admin) |
| AI | OpenAI API 호환 엔드포인트 (`gpt-5-mini`, Function Calling) |
| 시세 수집 | yfinance |
| 프론트엔드 | 바닐라 HTML / CSS / JavaScript (프레임워크·빌드 도구 없음, 그래프는 SVG 직접 작성) |
| 배포 | Render (백엔드), Vercel (프론트엔드), GitHub |
| 테스트 | unittest (엔진 30개 + 서비스 17개) |

## 3. 화면과 기능

| 화면 | 내용 |
| --- | --- |
| **오늘 주문** | 전략별 다음 거래일 주문을 전표 형태로 보여 줍니다(매수 빨강, 매도 파랑). 전날 주문은 그날 종가·고가로 자동 판정하고, 확인 후 **체결 확정**으로 기록합니다. |
| **전략** | 무한매수법·VR 전략을 종목·계좌별로 여러 개 등록합니다(실전/시뮬레이션). 상세 화면에서 상태, 그래프, 사이클·V 갱신 이력, VR V 갱신을 다룹니다. |
| **체결 기록** | 체결 기록(data) 조회·추가·수정·삭제, 필터, CSV/JSON 내려받기 |
| **요약·통계** | 종목별 시세 그래프와 통계(기간, 개수, 평균, 최대, 최소, 추세, 변동성, 최대 낙폭), AI에게 들어가는 요약 원문 |
| **AI 비서** | 대화 기록 · 채팅 · AI가 보는 요약 3단 구성. 전략을 골라 질문하면 그 전략 기준으로 답하고, 사용한 도구를 답 아래에 표시합니다. |

| 전략 상세 | 요약·통계 |
| --- | --- |
| ![전략 상세](docs/images/03_strategy_detail.png) | ![요약·통계](docs/images/04_summary_stats.png) |

| 다크 모드 | 체결 기록과 내보내기 |
| --- | --- |
| ![다크 모드](docs/images/02_dark_mode.png) | ![체결 기록](docs/images/05_fills_export.png) |

### 지원 규칙

> 무한매수법과 VR을 그림과 실제 화면 숫자로 쉽게 풀어 쓴 설명은 [docs/STRATEGY_GUIDE.md](docs/STRATEGY_GUIDE.md)에 있습니다.

- **무한매수법 V4.0:** 20/40분할, 별% = TQQQ 15−30T/n, SOXL 20−40T/n, 1/4 별지점 LOC + 3/4 지정가 매도, 리버스모드
- **무한매수법 V2.2:** 40분할, 1회 매수금 고정, 쿼터손절
- **VR 5.0:** 적립식·거치식·인출식, 2주마다 V' = V + Pool/G ± 적립·인출금, 밴드 ±15%, Pool 사용 한도 75/50/25%
- 공통: 사다리 LOC, 큰수 매수(증권사 가격 제한 대응), 수량 반올림 규칙, 자동 체결 판정(LOC는 종가, 지정가는 고가 기준)

---

## 4. 과제 요구사항 대응

### 필수

| 요구사항 | 구현 |
| --- | --- |
| 시계열 데이터 100개 이상 | TQQQ·SOXL 일별 시세 각 691개(2024-01-02 ~ 2026-10-02, yfinance) + 시뮬레이션 체결 기록 2,000건 이상 |
| data CRUD | `GET/POST /api/data`, `PUT/DELETE /api/data/{id}`. 과제의 `date·value·memo`에 체결 정보(전략, 매수/매도, 수량, 역할)를 더했습니다. `value` = 체결 단가 |
| 데이터 요약 | `GET /api/data/summary` → 종목별 기간·개수·평균·최대·최소·최근 30거래일 추세 + 전략별 한 줄 상태. `text` 필드가 시스템 프롬프트에 그대로 들어갑니다. |
| 대화 저장·목록·불러오기·삭제 | `POST/GET /api/conversations`, `GET/DELETE /api/conversations/{id}`. 목록은 messages 없이 개수만, 불러오기는 전체 messages |
| AI 채팅 | `POST /api/chat`: `/api/data/summary`와 같은 함수(`build_summary`)로 요약 생성 → 시스템 프롬프트에 주입 → GPT 호출(도구 사용) → 대화 자동 저장 |
| 채팅 화면 | 메시지 입력, 대화 표시, 답을 기다리는 동안 "숫자를 조회하며 답을 쓰는 중" 로딩 표시 |
| 데이터 요약 화면 | 요약·통계 화면과 AI 비서 오른쪽 칸에 기간·개수·평균·최대·최소·추세 표시 |
| CORS · Swagger | `CORSMiddleware`로 허용 주소만 받음(`ALLOWED_ORIGINS`), `/docs`에서 Swagger UI 확인 |
| 키 관리 | OpenAI 키, Firebase 서비스 계정 키, API 키는 환경 변수·Secret File로만 관리 (코드·Git에 없음) |
| 콜드스타트 대응 | 화면이 열릴 때 `/health`를 먼저 호출하고, 2.5초 넘게 걸리면 "서버를 깨우는 중" 안내 표시 |
| 저장소 | Firebase Firestore |
| 프론트엔드 | 바닐라 HTML/CSS/JS (프레임워크 없음) |
| 배포 | 백엔드 Render, 프론트엔드 Vercel. Vercel 환경 변수 `API_BASE_URL`로 API 서버 주소를 설정 |

### 보너스 1: AI 도구 호출(Function Calling) + 멀티채널 연동

- **Function Calling:** 조회 전용 도구 5개를 스키마로 정의해 `/api/chat`에 연결했습니다. → [6. AI 호출 흐름](#6-ai-호출-흐름)
- **멀티채널 (GPT Actions):** 같은 기능을 조회 API로 공개하고, ChatGPT의 내 GPT에 Actions로 연결합니다. → [7. GPT Actions 연동](#7-gpt-actions-연동)

### 보너스 2: 인사이트·UX 고도화

| 요구사항 | 구현 | 위치 |
| --- | --- | --- |
| 추가 지표 1개 이상 | `GET /api/data/statistics`: **연 변동성**(일별 수익률 표준편차 × √252), **최대 낙폭**(고점 대비 최대 하락률), 전략별 실현 수익·평가손익 | 요약·통계 화면 |
| 그래프 | 종가 + 20일 이동평균(종목·기간 선택), 무한매수 전략의 종가 + 평단·별지점선 + 체결 점, VR 전략의 평가금 + V + 밴드. 외부 라이브러리 없이 SVG로 그렸습니다. | 요약·통계, 전략 상세 |
| 내보내기 | `GET /api/data/export?format=csv\|json`. 화면의 필터(전략·기간)가 그대로 적용되고, CSV는 엑셀 한글 깨짐 방지(BOM)를 넣었습니다. | 체결 기록 화면 |
| 다크 모드 | 테마 버튼으로 전환, 브라우저에 기억, 처음에는 OS 설정을 따름 | 왼쪽 아래 |
| 선택 UI | 종목·기간 선택, 체결 기록 필터, AI 비서의 대상 전략 선택 | 각 화면 |

---

## 5. 제출 스크린샷

| 데이터 요약이 보이는 채팅 (질문 + 답변) | 데이터 관리 (CRUD 동작) | 대화 기록 (불러오기 동작) |
| --- | --- | --- |
| ![채팅과 데이터 요약](docs/images/07_chat_with_summary.png) | ![데이터 관리](docs/images/08_data_crud.png) | ![대화 불러오기](docs/images/09_conversation_load.png) |
| 오른쪽 "AI가 보는 요약"에 기간·개수·평균·최대·최소·추세가 보이고, 가운데에 질문과 답변이 있습니다. | 체결 기록의 **수정** 창입니다. 추가·수정·삭제 결과가 목록에 바로 반영됩니다. | 왼쪽 대화 기록에서 이전 대화를 고르면 그 대화의 메시지가 다시 표시됩니다. |

이미지를 누르면 크게 볼 수 있습니다.

## 6. AI 호출 흐름

### 원칙: 숫자는 서버가, 설명은 GPT가

GPT는 Firestore에 직접 접근할 수 없고, T·평단·별지점 같은 숫자를 스스로 계산하면 틀릴 수 있습니다. 그래서

1. 서버가 Firestore를 읽고 계산하는 **함수**를 만들어 두고,
2. GPT에게는 그 함수들의 **이름과 설명(스키마)**만 알려 주며,
3. GPT가 필요하다고 판단하면 "이 함수를 이 값으로 실행해 줘"라고 **요청**하고, 실제 실행은 서버가 합니다.
4. 시스템 프롬프트로 "숫자는 요약이나 도구 결과에 있는 값만 인용하고 직접 계산하지 말 것"을 지시합니다.

### 도구 5개 (모두 조회 전용)

| 도구 | 돌려주는 것 | GPT가 호출하는 근거 (스키마 설명 기준) |
| --- | --- | --- |
| `get_portfolio_summary` | 모든 전략의 한 줄 상태 + 종목별 시세 요약 | 전체 현황, 여러 전략 비교 질문 |
| `get_strategy_status` | 전략 하나의 T, 평단, 별%, 별지점, 잔금, 모드 / VR의 V, 밴드, Pool | 특정 전략의 상세 숫자가 요약에 없을 때 (요약의 `id=` 값을 인자로 사용) |
| `get_today_orders` | 다음 거래일 주문표 (전략 지정 또는 전체) | "오늘 뭐 걸어?"처럼 주문을 묻는 질문. 주문표는 기본 요약에 없으므로 대부분 호출 |
| `get_fill_history` | 체결 기록 (기간·전략 필터, 최신순) | 과거 매매 내역을 묻는 질문 |
| `get_price_stats` | 최근 N거래일 평균·최대·최소·추세·변동성·최대 낙폭 | 요약의 30일 범위를 벗어난 기간을 묻는 질문 |

### 처리 순서 (`POST /api/chat`)

```mermaid
sequenceDiagram
    participant U as 사용자 (웹 화면)
    participant S as 서버 (FastAPI, Render)
    participant G as GPT
    participant F as Firestore

    U->>S: 질문 (+ 대화 id, 선택 전략 id)
    S->>F: 시세·전략 읽기
    S->>S: 요약 생성 (summary.text)
    S->>G: 시스템 프롬프트(규칙 + 요약) + 이전 대화 + 질문 + 도구 스키마 5개
    alt 요약만으로 답할 수 있음
        G-->>S: 답변
    else 추가 숫자가 필요함
        G-->>S: 도구 실행 요청 (예: get_today_orders)
        S->>F: 읽기
        S->>S: 함수 실행 (주문표 계산)
        S->>G: 실행 결과(JSON)
        G-->>S: 결과를 인용한 답변
    end
    S->>F: 질문·답변·사용한 도구를 대화에 저장
    S-->>U: 답변 + 사용한 도구 목록
```

- 도구 호출은 한 질문에 최대 3회까지 허용하고, 마지막에는 도구 없이 답하도록 강제합니다.
- 사용한 도구는 대화 기록의 `tools_used`에 저장되고, 화면에서는 답 아래 회색 표시로 보입니다.

### 실제 예시

| 질문 | 기본 요약에 있는가 | GPT의 판단 | 사용한 도구 |
| --- | --- | --- | --- |
| 최근 30일 TQQQ 추세 어때? | 있음 (30거래일 추세) | 요약 값을 인용해 바로 답함 | 없음 |
| 오늘 뭐 걸어야 해? | 없음 (주문표) | 주문표 도구가 필요하다고 판단 | `get_today_orders` |
| 지금 소진에 가까운 전략 있어? | 일부 (T·잔금 한 줄) | 전체 현황 → 전략별 상세 확인 | `get_portfolio_summary`, `get_strategy_status` × 2 |

아래는 "오늘 뭐 걸어야 해?"에 대한 답입니다. 답 아래의 **[주문표 조회]**가 `get_today_orders`를 호출한 기록이며, 오른쪽 "AI가 보는 요약"에는 주문표가 없다는 것을 확인할 수 있습니다.

![AI 비서의 도구 호출](docs/images/06_ai_chat_tool_call.png)

---

## 7. GPT Actions 연동

웹 화면 외에 ChatGPT(내 GPT)에서도 같은 데이터를 조회할 수 있게 연결합니다.

```mermaid
flowchart LR
    W[웹 화면<br/>Vercel] -->|POST /api/chat| S[FastAPI 서버<br/>Render]
    S <-->|Function Calling| G[GPT]
    C[ChatGPT<br/>내 GPT] -->|GPT Actions<br/>GET 조회 API| S
    S --> F[(Firestore)]
```

- **스키마:** `GET /api/actions/openapi.json`이 OpenAPI 3.1 스키마를 만들어 줍니다. 데이터를 바꾸는 API는 빼고 **조회 API 7개**만 담았습니다.

  | operationId | API |
  | --- | --- |
  | `getSummary` | `GET /api/data/summary` |
  | `listStrategies` | `GET /api/strategies` |
  | `getStrategyStatus` | `GET /api/strategies/{strategy_id}/status` |
  | `getTodayOrders` | `GET /api/orders/today` |
  | `listFills` | `GET /api/data` |
  | `getStatistics` | `GET /api/data/statistics` |
  | `listConversations` | `GET /api/conversations` |

- **인증:** API Key 방식, 헤더 이름 `X-API-Key`
- **서버 주소:** 환경 변수 `PUBLIC_API_URL`(= Render 주소)이 스키마의 `servers`에 들어갑니다.
- **검증 결과:** _연동 후 질문 예시, 호출된 API, 웹 화면과 숫자 비교 결과를 추가합니다._

---

## 8. 구조

```mermaid
flowchart TB
    subgraph FE[frontend · Vercel]
        UI[index.html + js/views<br/>해시 라우터 5개 화면]
    end
    subgraph BE[backend · Render]
        R[routers<br/>FastAPI 엔드포인트] --> SV[services<br/>상태 재생·주문표·요약·채팅]
        SV --> EN[engine<br/>V2.2·V4.0·VR 계산, 외부 의존성 없음]
        SV --> RP[repo<br/>Firestore / 메모리]
    end
    UI -->|fetch + X-API-Key| R
    RP --> FS[(Firestore)]
    SV --> GPT["GPT<br/>(Function Calling)"]
    SV --> YF["yfinance<br/>(시세)"]
```

### 설계 원칙

- **사실은 저장하고 상태는 계산한다.** 설정, 체결, 주문표, VR 스냅샷만 저장하고 T·평단·별지점은 매번 체결 기록을 처음부터 재생해 구합니다. 체결 하나를 고치면 그 뒤 상태가 저절로 다시 계산됩니다.
- **숫자는 백엔드가, 설명은 GPT가.** GPT에는 계산된 요약과 읽기 전용 도구만 줍니다.
- **Firestore 무료 한도 지키기.** 조회 결과를 서버 메모리에 캐시하고, 이 서버를 거치는 쓰기가 생기면 해당 컬렉션 캐시를 비웁니다.

### Firestore 컬렉션

| 컬렉션 | 내용 |
| --- | --- |
| `strategies` | 전략 설정 (종류, 종목, 버전, 원금·분할 / V·Pool·G, 계좌 메모, 시뮬레이션 여부) |
| `data` | 체결 기록 (date, value, memo + strategy_id, side, qty, role, order_type, source) |
| `order_sheets` | 날짜별 주문표 스냅샷과 확정 여부 |
| `vr_snapshots` | VR 2주 갱신 기록 (V, 평가금, Pool, 밴드) |
| `prices` | 종목별 일별 시세 (시계열 데이터) |
| `conversations` | AI 대화 (title, strategy_id, messages[role, content, tools_used]) |

### 폴더

```
backend/
  app/
    engine/      계산 엔진: infinite.py(V2.2·V4.0), vr.py, common.py, backtest.py
    services/    상태 재생, 주문표, 체결 확정, 요약·통계, 채팅, 대화
    routers/     FastAPI 엔드포인트
    repo/        저장소 (firestore.py, memory.py)
    schemas.py   요청 검증
    main.py      앱 진입점, GPT Actions 스키마
  scripts/seed.py  시세·데모 데이터 적재
  tests/         엔진 30개 + 서비스 17개 테스트
frontend/
  index.html     화면 뼈대
  config.js      백엔드 주소 (로컬이면 127.0.0.1:8000, 배포면 Render)
  css/style.css  라이트/다크 테마
  js/            api.js, chart.js(SVG 그래프), slip.js(주문 전표), views/(화면별 코드)
docs/images/     README 화면 캡처
render.yaml      Render 배포 설정
```

---

## 9. 주요 API

| 메서드 · 경로 | 설명 | 키 필요 |
| --- | --- | --- |
| `GET /api/data` · `POST /api/data` | 체결 기록 목록 · 추가 | 추가만 |
| `PUT /api/data/{id}` · `DELETE /api/data/{id}` | 체결 기록 수정 · 삭제 | ✅ |
| `GET /api/data/summary` | 데이터 요약 (프롬프트 주입용 `text` 포함) | |
| `GET /api/data/statistics` | 추가 지표 (변동성, 최대 낙폭, 전략 성과) | |
| `GET /api/data/export?format=csv\|json` | 체결 기록 내보내기 | |
| `POST /api/conversations` · `GET /api/conversations` | 대화 저장 · 목록 | 저장만 |
| `GET /api/conversations/{id}` · `DELETE /api/conversations/{id}` | 대화 불러오기 · 삭제 | 삭제만 |
| `POST /api/chat` | AI 채팅 (요약 주입 → GPT·도구 → 자동 저장) | ✅ |
| `GET/POST /api/strategies`, `PUT/DELETE /api/strategies/{id}` | 전략 목록·등록·수정·종료 | 변경만 |
| `GET /api/strategies/{id}/status` | 전략 현재 상태 | |
| `GET /api/orders/today` | 전체 전략의 체결 확인 대기 + 다음 거래일 주문표 | |
| `POST /api/strategies/{id}/orders/{date}/confirm` | 자동 판정 결과(수정 포함)를 체결 기록으로 확정 | ✅ |
| `POST /api/strategies/{id}/vr/rebalance` | VR V 갱신 (`dry_run`이면 미리보기) | ✅ |
| `POST /api/strategies/{id}/backtest` | 시뮬레이션 전략 백테스트 | ✅ |
| `POST /api/prices/sync` · `GET /api/prices` | 빠진 날짜 시세 채우기 · 시세 조회 | 채우기만 |
| `GET /api/actions/openapi.json` | GPT Actions용 스키마 | |

데이터를 바꾸는 요청은 `X-API-Key` 헤더가 필요합니다. 전체 목록은 `/docs`(Swagger UI)에서 볼 수 있습니다.

---

## 10. 실행과 배포

### 로컬 실행

```bash
cd backend
python -m venv .venv            # Python 3.10 이상
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env  → 값 채우기

python -m scripts.seed --demo   # 시세 + 시뮬레이션 전략 2개 (한 번만 실행)
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

화면은 다른 터미널에서 띄웁니다.

```bash
cd frontend
python -m http.server 5500      # http://127.0.0.1:5500
```

데이터를 바꾸는 요청(체결 확정, 전략 등록, 채팅)은 화면 왼쪽 아래 **연결 설정**에 `APP_API_KEY` 값을 넣어야 합니다. 키는 그 브라우저에만 저장되고 코드에는 들어가지 않습니다.

Firebase 없이 확인하려면 `.env`에서 `STORAGE=memory`로 두면 됩니다. 서버를 켤 때 데모 데이터가 자동으로 채워지고, 끄면 사라집니다.

### 환경 변수

| 이름 | 용도 |
| --- | --- |
| `OPENAI_API_KEY` | GPT 호출 키 (교육장 가상 키). `.env`와 Render 환경 변수에만 저장 |
| `OPENAI_BASE_URL` | OpenAI 호환 주소 (교육장: `https://copa.codyssey.kr/v1`) |
| `OPENAI_MODEL` | 모델 이름 (기본 `gpt-5-mini`) |
| `FIREBASE_CREDENTIALS_PATH` 또는 `FIREBASE_CREDENTIALS` | 서비스 계정 키 파일 경로, 또는 키 JSON 문자열/base64 |
| `STORAGE` | `firestore` 또는 `memory` |
| `APP_API_KEY` | 데이터를 바꾸는 요청에 필요한 `X-API-Key` 값 (직접 정한 비밀번호) |
| `ALLOWED_ORIGINS` | CORS 허용 주소 (쉼표 구분, 끝에 `/` 없이) |
| `PUBLIC_API_URL` | GPT Actions 스키마에 들어갈 서버 주소 |

프론트엔드(Vercel) 환경 변수

| 이름 | 용도 |
| --- | --- |
| `API_BASE_URL` | 백엔드 API 주소 (예: `https://rule-keeper.onrender.com`). 빌드 때 `build-config.js`가 이 값으로 `config.js`를 만듭니다. 없으면 저장소의 `config.js`(로컬 → `127.0.0.1:8000`, 배포 → Render)를 그대로 씁니다. |

### 배포

- **Render (백엔드):** Web Service, Root Directory `backend`, Build `pip install -r requirements.txt`, Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, `PYTHON_VERSION=3.11.9`. Firebase 키 파일은 Secret File(`/etc/secrets/serviceAccountKey.json`)로 넣고 `FIREBASE_CREDENTIALS_PATH`로 가리킵니다.
- **Vercel (프론트엔드):** Root Directory `frontend`, Framework Preset `Other`. `frontend/vercel.json`이 빌드 명령(`node build-config.js`)과 출력 폴더(`.`)를 지정하고, 환경 변수 `API_BASE_URL`에 Render 주소를 넣습니다.
- **보안:** `.env`와 서비스 계정 키는 `.gitignore`로 저장소에서 제외했습니다. API 키는 코드·README·캡처에 넣지 않습니다.

### 테스트

```bash
cd backend
python -m unittest discover -s tests -t .
```

엔진 테스트는 라오어 카페 원문의 예시 표(T, 별%, 주문 가격·수량)를 그대로 재현하는지 확인합니다.

---

## 11. 설계 설명

### 11.1 용어 정리

이 문서와 코드에 나오는 개발 용어를 먼저 짧게 정리합니다.

| 용어 | 뜻 | 이 프로젝트에서 |
| --- | --- | --- |
| **API** | 프로그램끼리 데이터를 주고받는 약속된 창구 | 화면(프론트)이 서버에 "체결 기록 줘", "채팅 보내 줘"를 요청하는 통로 |
| **엔드포인트** | API 하나의 주소 + 방식 | `GET /api/data/summary`, `POST /api/chat` 등 |
| **HTTP 메서드** | 요청의 종류. GET(조회), POST(추가), PUT(수정), DELETE(삭제) | CRUD 4개가 각각 하나씩 대응 |
| **JSON** | `{"date": "2026-10-02", "value": 81.01}`처럼 이름과 값을 묶은 텍스트 형식 | 서버와 화면, 서버와 GPT가 주고받는 데이터 형식 |
| **CRUD** | Create(추가)·Read(조회)·Update(수정)·Delete(삭제) | 체결 기록 API 4개 |
| **FastAPI** | 파이썬으로 웹 API 서버를 만드는 라이브러리 | 주소와 함수 연결, 요청 검사, JSON 변환, Swagger 자동 생성 |
| **Uvicorn** | FastAPI 앱을 실제로 실행해 요청을 받게 하는 서버 프로그램 | `uvicorn app.main:app` |
| **Swagger UI / OpenAPI** | OpenAPI는 API 목록·입력·출력을 적는 표준 형식, Swagger UI는 그걸 웹 화면으로 보여 주고 직접 실행해 보게 하는 도구 | `/docs` 화면, GPT Actions 스키마 |
| **Pydantic** | 데이터의 모양(필드, 타입, 범위)을 클래스로 정의하고 자동 검사하는 라이브러리 | `schemas.py`의 `DataIn`, `StrategyIn`, `ChatIn` |
| **422 오류** | "요청 형식이 규칙에 맞지 않음" 응답 코드 | 날짜 형식이 틀리거나 수량이 0이면 저장 전에 거절 |
| **Firestore** | 구글 Firebase의 클라우드 NoSQL 데이터베이스. 표 대신 **컬렉션**(문서 묶음)과 **문서**(JSON 같은 한 건)로 저장 | `data`, `conversations` 등 6개 컬렉션 |
| **서비스 계정 키** | 서버가 Firestore에 접근할 때 쓰는 관리자용 열쇠 파일(JSON) | `.env`·Render Secret File에만 보관 |
| **환경 변수 / .env** | 코드 밖에서 프로그램에 넘겨주는 설정 값. `.env`는 로컬에서 그 값을 적어 두는 파일 | 키, 주소, 저장소 종류(`STORAGE`) |
| **CORS** | 브라우저가 "다른 주소의 서버"에 요청할 때 그 서버가 허락했는지 확인하는 보안 규칙 | Vercel 화면 → Render 서버 요청을 `ALLOWED_ORIGINS`로 허락 |
| **API 키 (`X-API-Key`)** | 요청 헤더에 담아 보내는 비밀 값. 서버가 같은 값인지 확인 | 데이터를 바꾸는 요청에만 요구 |
| **시스템 프롬프트** | GPT에게 대화 맨 앞에 주는 지시문(역할, 규칙, 참고 자료) | 규칙 요약 + 데이터 요약 |
| **컨텍스트 주입** | 시스템 프롬프트에 내 데이터를 넣어 GPT가 그 데이터를 바탕으로 답하게 하는 방식 | 매 질문마다 최신 요약을 `[요약]` 자리에 넣음 |
| **Function Calling** | GPT가 답 대신 "이 함수를 이 값으로 실행해 줘"라고 요청하고, 서버가 실행 결과를 돌려주는 방식 | 조회 도구 5개 |
| **콜드스타트** | 무료 서버가 잠들어 있다가 첫 요청에 깨어나느라 느려지는 현상 | 화면에 "서버를 깨우는 중" 안내 |

### 11.2 시계열 데이터 → 요약 → 서비스 활용

```mermaid
flowchart LR
    Y[yfinance<br/>일별 시세] -->|빠진 날짜만| P[(prices<br/>컬렉션)]
    D[(data<br/>체결 기록)] --> SM
    P --> SM[summary.py<br/>요약 계산]
    SM -->|기간·개수·평균·최대·최소·추세<br/>+ 전략 한 줄 상태| T["summary.text"]
    T --> A["GET /api/data/summary"]
    T --> B[요약·통계 화면<br/>AI 비서 오른쪽 칸]
    T --> C[AI 시스템 프롬프트]
```

1. `services/prices.py`가 yfinance에서 TQQQ·SOXL 일별 시세를 받아 `prices` 컬렉션에 저장합니다. 이미 있는 날짜는 건너뛰고 빠진 날짜만 채웁니다. 화면에 접속할 때와 **시세 갱신** 버튼을 누를 때 실행됩니다.
2. `services/summary.py`가 종목별 기간, 개수, 평균, 최대, 최소, 최근 30거래일 변화율과 추세(+3% 초과 상승, −3% 미만 하락, 그 사이 유지)를 계산하고, 전략별 현재 상태를 한 줄씩 덧붙여 `text`로 만듭니다.
3. 같은 요약이 API, 화면, AI 프롬프트 세 곳에서 그대로 쓰이므로 사람이 보는 숫자와 AI가 보는 숫자가 항상 같습니다.

### 11.3 라우터 / 서비스 / 엔진 / 저장소 분리 기준

```mermaid
flowchart TB
    REQ([HTTP 요청]) --> RT
    subgraph BE["백엔드"]
        RT["routers/<br/>주소 정의 · API 키 확인 · Pydantic 검사"]
        SV["services/<br/>업무 흐름 조합 · GPT 호출"]
        EN["engine/<br/>매매 규칙 계산 (순수 파이썬)"]
        RP["repo/<br/>저장소 읽기·쓰기"]
        RT --> SV
        SV --> EN
        SV --> RP
    end
    RP --> FS[(Firestore)]
    RP -.->|"STORAGE=memory"| MEM[(메모리)]
```

| 층 | 폴더 | 기준 | 이렇게 나눈 이유 |
| --- | --- | --- | --- |
| 라우터 | `routers/` | HTTP만 다룸: 주소 정의, API 키 확인, 요청 검사 후 서비스 호출 | 주소나 인증 방식이 바뀌어도 계산 코드는 그대로 |
| 서비스 | `services/` | 업무 흐름: 저장소에서 읽고 엔진으로 계산해 결과를 조합, GPT 호출 | 화면·AI·Actions가 같은 함수를 공유 |
| 엔진 | `engine/` | 매매 규칙 계산만. DB·웹을 모름 | 카페 원문 예시 표로 단독 테스트 가능 |
| 저장소 | `repo/` | 읽기·쓰기만. Firestore와 메모리 구현이 같은 함수 이름(`get`, `where`, `put`, `update`, `delete`) | `STORAGE` 값 하나로 저장소 교체, Firebase 없이 개발 가능 |

**요청 하나가 층을 지나는 예** (`GET /api/strategies/{id}/status`)

```mermaid
sequenceDiagram
    participant B as 브라우저
    participant R as routers/strategies.py
    participant S as services/strategies.py
    participant P as repo/firestore.py
    participant E as engine/infinite.py
    B->>R: GET /api/strategies/321c.../status
    R->>S: status(repo, "321c...")
    S->>P: 전략 설정, 체결 기록, 시세 읽기
    P-->>S: 문서 목록
    S->>E: 설정 + 날짜별 종가·체결
    E-->>S: T, 평단, 별지점, 잔금 ...
    S-->>R: 결과 묶음 (dict)
    R-->>B: JSON 응답
```

### 11.4 Pydantic 요청 검증

`schemas.py`에 요청 모양을 클래스로 정의하면, FastAPI가 요청이 들어올 때 자동으로 검사합니다.

```python
class DataIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")   # YYYY-MM-DD 형식만
    value: float = Field(gt=0)                           # 체결 단가 > 0
    qty: int = Field(ge=1)                               # 수량 1주 이상
    side: Literal["buy", "sell"]                         # 매수/매도만
    ...
```

```mermaid
flowchart LR
    Q["POST /api/data<br/>{date, value, qty, ...}"] --> V{Pydantic 검사}
    V -->|통과| SV[services/data.py] --> FS[(Firestore 저장)]
    V -->|"실패<br/>(예: qty=0, date=10/02)"| E[422 오류 응답<br/>어느 칸이 왜 틀렸는지]
```

- `StrategyIn`은 "V4.0은 20·40분할만", "VR은 시작 V와 Pool 필수" 같은 규칙도 검사합니다.
- **이유:** 이 앱은 체결 기록을 처음부터 다시 따라가며 상태를 계산하므로, 잘못된 기록이 한 건만 들어가도 그 뒤의 T·평단이 모두 틀어집니다. 검사를 저장 **전**에 해서 틀린 데이터가 Firestore에 들어가지 않게 막습니다.

#### 왜 프론트엔드(JS)가 아니라 백엔드에서 검사하나

프론트엔드도 검사를 합니다. 체결 입력 창의 `required`, `min="1"`, 체결 확정 때 "체결가와 수량을 모두 입력하세요" 안내가 그것입니다. 하지만 **프론트엔드 검사만으로는 막을 수 없는 경로**가 있어서 최종 검사는 백엔드가 맡습니다.

```mermaid
flowchart LR
    W["웹 화면<br/>(JS 검사 있음)"] --> API
    SW["Swagger UI /docs"] --> API
    GA["ChatGPT<br/>(GPT Actions)"] --> API
    CL["curl · 스크립트 등<br/>직접 호출"] --> API
    DT["개발자 도구로<br/>JS를 고친 브라우저"] --> API
    API{"백엔드<br/>Pydantic 검사"} -->|통과| DB[(Firestore)]
    API -->|실패| X[422 거절]
```

| | 프론트엔드 검사 (JS) | 백엔드 검사 (Pydantic) |
| --- | --- | --- |
| 목적 | 사용자 편의: 서버에 보내기 전에 바로 알려 줌 | 데이터 보호: 어디서 오든 마지막 관문 |
| 적용 범위 | 우리 웹 화면에서 보낸 요청만 | API로 들어오는 **모든** 요청 |
| 우회 가능 여부 | 가능 (개발자 도구로 JS 수정, Swagger·curl로 직접 호출) | 불가능 (서버 안에서 실행) |
| 이 프로젝트 예 | `min="1"`, 빈 칸 안내 | `DataIn`, `StrategyIn`, `ChatIn` |

실제로 개발 중 Swagger UI에서 형식이 깨진 JSON을 `/api/chat`에 보냈을 때, 웹 화면을 거치지 않았는데도 백엔드가 422로 거절했습니다. 또 같은 API를 GPT Actions(ChatGPT)도 호출하므로, 검사를 JS에만 두면 웹 화면 외의 경로는 무방비가 됩니다. 그래서 **프론트엔드 검사는 편의, 백엔드 검사는 보안·정확성**으로 역할을 나눴습니다.

### 11.5 Firestore 저장 구조와 CRUD

```mermaid
erDiagram
    strategies ||--o{ data : "체결 기록"
    strategies ||--o{ order_sheets : "날짜별 주문표"
    strategies ||--o{ vr_snapshots : "VR 갱신 기록"
    strategies }o--o{ prices : "같은 종목 시세 사용"
    strategies |o--o{ conversations : "대화 대상 (선택)"
    data {
        string date
        float value
        string memo
        string strategy_id
        string side
        int qty
        string role
    }
    conversations {
        string title
        string strategy_id
        array messages
    }
```

| 화면 동작 | API | 서비스 함수 | repo 함수 | Firestore |
| --- | --- | --- | --- | --- |
| 체결 직접 입력 | `POST /api/data` | `create_data` | `add` | `data`에 문서 추가 |
| 목록 보기·필터 | `GET /api/data` | `list_data` | `where` | `data` 조회 |
| 수정 | `PUT /api/data/{id}` | `update_data` | `update` | 날짜·단가·수량·메모만 변경 |
| 삭제 | `DELETE /api/data/{id}` | `delete_data` | `delete` | 문서 삭제 |

수정은 날짜·단가·수량·메모만 허용하고, 전략이나 역할을 바꾸려면 삭제 후 다시 추가하게 해서 기록의 일관성을 지킵니다. 무료 한도(읽기 하루 5만 건)를 지키려고 `repo/firestore.py`가 조회 결과를 서버 메모리에 캐시하고, 쓰기가 생기면 해당 컬렉션 캐시를 비웁니다.

### 11.6 컨텍스트 주입

GPT는 우리 Firestore를 모르므로, 질문이 올 때마다 서버가 최신 요약을 만들어 시스템 프롬프트에 끼워 넣습니다.

```mermaid
flowchart TB
    subgraph SP[GPT에게 보내는 메시지]
        direction TB
        S1["시스템 프롬프트<br/>① 역할: Rule_Keeper AI 비서<br/>② 지킬 것: 숫자는 요약·도구 결과만 인용, 투자 권유 금지 ...<br/>③ 오늘 날짜<br/>④ 규칙 요약: 별지점, V4.0, V2.2, VR 공식<br/>⑤ [요약] ← summary.text 를 여기에 주입"]
        S2["이전 대화 (최근 12개)"]
        S3["이번 질문"]
        S4["도구 스키마 5개"]
    end
    FS[(Firestore)] --> SUM[build_summary] --> S1
    SP --> G[GPT] --> ANS[요약 숫자를 인용한 답변]
```

- **효과:** 일반 ChatGPT는 "오늘 내 T가 몇이야?"에 답할 수 없지만, 이 서비스는 요약 안의 `T 4.31/40, 평단 72.86 ...`을 그대로 인용해 답합니다.
- **환각 방지:** "직접 계산·추정하지 말고 값이 없으면 도구를 호출하라"고 지시해, 요약에 없는 숫자는 Function Calling으로 서버에서 받아 옵니다.
- **전략 선택:** AI 비서에서 대상 전략을 고르면 그 전략의 상세 상태와 오늘 주문표까지 요약에 넣습니다.

### 11.7 CORS · 환경 변수 · 키 관리

**CORS가 필요한 이유**

```mermaid
sequenceDiagram
    participant B as 브라우저<br/>(rulekeeper-frontend.vercel.app)
    participant S as API 서버<br/>(rule-keeper.onrender.com)
    B->>S: 사전 확인: 이 주소에서 요청해도 돼?
    alt ALLOWED_ORIGINS에 Vercel 주소가 있음
        S-->>B: 허락 (Access-Control-Allow-Origin)
        B->>S: 실제 요청 (GET /api/orders/today)
        S-->>B: 데이터
    else 목록에 없음 (다른 사이트)
        S-->>B: 허락 표시 없음
        Note over B: 브라우저가 응답을 막음<br/>"blocked by CORS policy"
    end
```

화면(vercel.app)과 서버(onrender.com)의 주소가 다르기 때문에, 서버가 허락한 주소의 화면만 데이터를 읽을 수 있습니다. `ALLOWED_ORIGINS`에는 Vercel 주소와 로컬 개발 주소만 넣었습니다.

**비밀 값은 어디에 있나**

```mermaid
flowchart LR
    subgraph GIT[GitHub 저장소 · 공개]
        C[코드, README<br/>.env.example 예시만]
    end
    subgraph LOCAL[내 PC]
        E[".env<br/>serviceAccountKey.json"]
    end
    subgraph RENDER[Render 서버]
        RE["환경 변수<br/>Secret File"]
    end
    subgraph BROWSER[각자의 브라우저]
        K["연결 설정의 API 키<br/>(localStorage)"]
    end
    E -.->|".gitignore로 제외"| NG["GitHub에 올라가지 않음"]
```

| 값 | 보관 위치 | 노출되면 생기는 일 |
| --- | --- | --- |
| OpenAI 키 | `.env`, Render 환경 변수 | 남이 GPT를 호출해 비용·사용량을 씀 |
| Firebase 서비스 계정 키 | `serviceAccountKey.json`(로컬), Render Secret File | 남이 DB를 마음대로 읽고 고침 |
| `APP_API_KEY` | `.env`, Render 환경 변수, 각자 브라우저 | 남이 체결 기록을 추가·삭제함 |
| API 서버 주소 | Vercel 환경 변수 `API_BASE_URL` | 공개 정보 (비밀 아님) |

- **환경 변수를 쓰는 이유:** 로컬과 배포 환경에서 주소·키가 다르므로, 코드를 고치지 않고 실행 환경마다 값만 바꿔 끼웁니다. 또 코드에 키를 적지 않으니 GitHub에 올려도 안전합니다.
- **API 키를 한 번 더 두는 이유:** CORS는 **브라우저**만 지키는 규칙이라, 프로그램으로 직접 요청하면 막지 못합니다. 그래서 데이터를 바꾸는 요청은 `X-API-Key`가 맞아야만 처리합니다.
