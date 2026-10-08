"""Rule_Keeper MCP 서버 (보너스 1: 멀티채널 연동).

Claude 데스크톱 앱 같은 MCP 클라이언트가 Rule_Keeper 백엔드(Render)의 조회 API를 '도구'로 호출하게 해 준다.
웹 화면의 AI 비서(/api/chat의 Function Calling)와 같은 데이터·같은 계산 결과를 다른 채널에서 쓰는 것이 목적이다.

- 모두 조회 전용이다. 데이터를 바꾸는 API(체결 확정, 전략 등록 등)는 노출하지 않는다.
- 통신: 표준 입출력(stdio). 클라이언트가 이 파일을 직접 실행한다.
- 백엔드 주소는 환경 변수 RULE_KEEPER_API (기본: Render 배포 주소).

실행 확인:  python server.py   (아무것도 출력하지 않고 대기하면 정상, Ctrl+C로 종료)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

API = os.getenv("RULE_KEEPER_API", "https://rule-keeper.onrender.com").rstrip("/")
TIMEOUT = 90  # Render 무료 서버가 잠들어 있으면 첫 요청이 30~60초 걸린다

mcp = FastMCP("rule-keeper")


def _get(path: str, **params: Any) -> Any:
    query = {k: v for k, v in params.items() if v not in (None, "")}
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "rule-keeper-mcp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail")
        except Exception:
            detail = e.reason
        return {"error": f"API 오류 {e.code}: {detail}", "url": url}
    except Exception as e:  # 네트워크 오류도 도구 결과로 돌려줘서 AI가 사용자에게 설명하게 한다
        return {"error": f"서버에 연결하지 못했습니다: {e}", "url": url}


def _brief_lines(lines: list[dict]) -> list[dict]:
    return [{k: l.get(k) for k in ("side", "role", "order_type", "price", "qty", "note") if l.get(k) not in (None, "")}
            for l in lines or []]


@mcp.tool()
def get_portfolio_summary() -> dict:
    """모든 전략의 한 줄 상태와 종목별 시세 요약(기간, 개수, 평균, 최대, 최소, 30일 추세).
    전체 현황이나 여러 전략 비교 질문에 먼저 사용한다. 각 전략의 id는 strategies[].strategy_id에 있다."""
    s = _get("/api/data/summary")
    if "error" in s:
        return s
    return {"text": s.get("text"), "strategies": s.get("strategies"), "prices": s.get("prices")}


@mcp.tool()
def get_strategy_status(strategy_id: str) -> dict:
    """전략 하나의 현재 상태. 무한매수법: T, 평단, 별%, 별지점, 잔금, 모드(일반/리버스/쿼터손절), 최근 사이클.
    VR: V, 평가금, 밴드, Pool, 이번 사이클 남은 매수 한도, V 갱신일 여부. strategy_id는 get_portfolio_summary에서 얻는다."""
    st = _get(f"/api/strategies/{urllib.parse.quote(strategy_id)}/status")
    if isinstance(st, dict):
        st.pop("snapshots", None)
        if isinstance(st.get("cycles"), list):
            st["cycles"] = st["cycles"][-5:]
    return st


@mcp.tool()
def get_today_orders(strategy_id: Optional[str] = None) -> Any:
    """다음 거래일에 넣을 주문표(가격·수량·LOC/지정가)와 체결 확인 대기 여부.
    strategy_id를 주면 그 전략만, 비우면 모든 운용 중 전략. '오늘 뭐 걸어야 해?' 같은 질문에 사용한다."""
    if strategy_id:
        sh = _get(f"/api/strategies/{urllib.parse.quote(strategy_id)}/orders/next")
        if "error" in sh:
            return sh
        return {"date": sh.get("date"), "based_on": sh.get("based_on"), "provisional": sh.get("provisional"),
                "meta": sh.get("meta"), "lines": _brief_lines(sh.get("lines"))}
    items = _get("/api/orders/today")
    if isinstance(items, dict) and "error" in items:
        return items
    out = []
    for x in items:
        t = x.get("today") or {}
        out.append({"strategy_id": x.get("strategy_id"), "name": x.get("name"),
                    "is_simulation": x.get("is_simulation"), "error": x.get("error"),
                    "date": t.get("date"), "based_on": t.get("based_on"), "provisional": t.get("provisional"),
                    "lines": _brief_lines(t.get("lines")),
                    "to_confirm_dates": [j.get("date") for j in x.get("to_confirm") or []]})
    return out


@mcp.tool()
def get_fill_history(strategy_id: Optional[str] = None, date_from: Optional[str] = None,
                     date_to: Optional[str] = None, limit: int = 20) -> Any:
    """체결 기록(최신순). 날짜는 YYYY-MM-DD. limit은 1~100."""
    docs = _get("/api/data", strategy_id=strategy_id, date_from=date_from, date_to=date_to,
                limit=max(1, min(int(limit), 100)))
    if isinstance(docs, dict):
        return docs
    keys = ("date", "side", "role", "value", "qty", "memo", "source", "strategy_id")
    return [{k: d.get(k) for k in keys} for d in docs]


@mcp.tool()
def get_statistics() -> dict:
    """추가 지표: 종목별 연 변동성과 최대 낙폭, 전략별 실현 수익·평가손익(VR은 V·평가금·Pool)."""
    return _get("/api/data/statistics")


if __name__ == "__main__":
    mcp.run()  # 기본 stdio
