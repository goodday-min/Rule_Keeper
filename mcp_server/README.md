# Rule_Keeper MCP 서버 (보너스 1)

Claude 데스크톱 앱이 Rule_Keeper 백엔드(Render)의 **조회 API를 도구로 호출**하게 해 주는 작은 서버입니다.
웹 화면의 AI 비서와 같은 데이터, 같은 계산 결과를 다른 채널(Claude 앱)에서 씁니다.

| 도구 | 호출하는 API | 용도 |
|---|---|---|
| `get_portfolio_summary` | `GET /api/data/summary` | 전체 전략·시세 요약 |
| `get_strategy_status` | `GET /api/strategies/{id}/status` | T, 평단, 별지점 / V, 밴드, Pool |
| `get_today_orders` | `GET /api/orders/today`, `/api/strategies/{id}/orders/next` | 다음 거래일 주문표 |
| `get_fill_history` | `GET /api/data` | 체결 기록 |
| `get_statistics` | `GET /api/data/statistics` | 변동성, 최대 낙폭, 손익 |

- 모두 **조회 전용**입니다. 데이터를 바꾸는 API는 노출하지 않으므로 API 키가 필요 없습니다.
- 백엔드 주소는 환경 변수 `RULE_KEEPER_API`로 바꿀 수 있습니다(기본 `https://rule-keeper.onrender.com`).

## 설치

```powershell
cd C:\Users\user\codyssey\M1_2_RuleKeeper\Rule_Keeper\backend
.venv\Scripts\activate
python -m pip install "mcp<2"   # mcp 2.x는 FastMCP 이름이 바뀌어서 1.x로 고정
python ..\mcp_server\server.py   # 아무것도 출력하지 않고 기다리면 정상 (Ctrl+C로 종료)
```

## 설정 파일 없이 검증 (test_client.py)

`test_client.py`가 MCP 클라이언트 역할을 합니다. 서버를 실행하고 → 도구 목록을 받고 → 도구를 호출해 결과를 출력합니다.

```powershell
python ..\mcp_server\test_client.py                         # 도구 목록 + get_today_orders
python ..\mcp_server\test_client.py get_portfolio_summary
python ..\mcp_server\test_client.py get_strategy_status "{\"strategy_id\": \"전략id\"}"
```

## Claude 데스크톱 앱에 등록 (선택)

설정 → 개발자 → 설정 편집 → `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "rule-keeper": {
      "command": "C:\\Users\\user\\codyssey\\M1_2_RuleKeeper\\Rule_Keeper\\backend\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\user\\codyssey\\M1_2_RuleKeeper\\Rule_Keeper\\mcp_server\\server.py"]
    }
  }
}
```

앱을 완전히 종료(트레이 아이콘까지)한 뒤 다시 열고, 새 대화에서 "Rule_Keeper에서 오늘 걸 주문 알려줘"라고 물어봅니다.
