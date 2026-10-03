"""AI 채팅: 요약 주입 → GPT(Function Calling) → 대화 자동 저장.

숫자는 백엔드가 계산한 값만 쓰게 한다. GPT는 설명과 대화만 맡는다.
도구는 모두 읽기 전용이며 GPT Actions에도 같은 기능을 조회 API로 노출한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..repo.base import Repo
from . import conversations as conv_svc
from . import data as data_svc
from . import strategies as strat_svc
from . import summary as sum_svc
from .common import price_rows

MAX_TOOL_ROUNDS = 3
HISTORY_LIMIT = 12
KST = timezone(timedelta(hours=9))

RULES_BRIEF = """[규칙 요약 - 설명할 때 근거로 사용]
- 무한매수법 공통: 별지점 = 평단 × (1 + 별%). 매수점은 별지점 − 0.01, 매도점은 별지점. 매수는 모두 LOC이고 아래에 1주씩 사다리 LOC를 둔다.
- V4.0: 1회 매수금 = 잔금 ÷ (분할수 − T). T는 1회 매수 +1, 절반 +0.5, 쿼터매도 ×0.75. 별%는 TQQQ 20분할 15−1.5T, 40분할 15−0.75T, SOXL 20분할 20−2T, 40분할 20−T.
  전반전(T < 분할/2)은 절반 별지점·절반 평단 LOC, 후반전은 전액 별지점 LOC. 매도는 1/4 별지점 LOC + 3/4 지정가(TQQQ +15%, SOXL +20%).
  T > 분할−1이면 리버스모드: 별지점 = 직전 5거래일 종가 평균, 첫날 MOC로 1/20(20분할 1/10) 매도, 이후 별지점 위 매도와 잔금÷4 쿼터매수, 종가가 평단 대비 TQQQ −15%·SOXL −20% 위로 오면 일반모드 복귀(T 승계).
- V2.2: 40분할, 1회 매수금 고정, T = 매수누적액 ÷ 1회 매수금. 별% TQQQ 10 − T/2, SOXL 12 − 0.6T. 매도 1/4 별지점 LOC + 3/4 지정가(TQQQ +10%, SOXL +12%).
  39 < T(1회분을 더 살 수 없음)이면 쿼터손절: 1/4 MOC 매도 후 (잔금+수익금)÷10으로 10회 −10%(SOXL −12%) LOC 매수, 중간에 −10% LOC 매도가 체결되면 후반전 복귀.
- VR 5.0: 2주마다 다음 V = V + Pool/G + 적립금(인출식은 − 인출금). 밴드 V×0.85~1.15를 벗어나면 매수·매도. 사이클당 Pool 사용 한도 적립식 75%, 거치식 50%, 인출식 25%. 평단은 쓰지 않는다.
- 큰수 매수: 증권사가 현재가와 약 20% 넘게 떨어진 주문을 거부하므로, 너무 높은 매수 주문은 전일 종가 +10% 근처 한 줄로 합친다."""

SYSTEM_TEMPLATE = """당신은 Rule_Keeper(분할매수 기록장)의 AI 비서입니다. 사용자는 라오어 무한매수법(V2.2, V4.0)과 VR 5.0으로 여러 전략을 운용합니다.

지켜야 할 것
1. 숫자(T, 평단, 별지점, 주문 가격·수량, V, 밴드, 통계)는 아래 [요약]이나 도구 결과에 있는 값만 그대로 인용한다. 직접 계산·추정하지 않는다. 값이 없으면 도구를 호출하고, 그래도 없으면 모른다고 말한다.
2. "왜"를 물으면 [규칙 요약]의 조항을 근거로 설명한다.
3. 매수·매도 권유, 수익 예측, 규칙을 어기라는 조언을 하지 않는다. 이 앱은 사용자가 정한 규칙의 계산 보조 도구이며 투자 권유가 아니다.
4. 한국어로 짧고 명확하게 답한다. 주문은 "매수 별지점 LOC 78.11 × 3주"처럼 쓴다.
   도구 결과의 영어 필드 이름은 그대로 쓰지 말고 우리말로 바꾼다 (budget_left → 이번 사이클 남은 매수 한도,
   pool → Pool, e → 평가금, v → V, cash → 잔금, avg → 평단, star → 별지점, qty → 보유 수량, unit → 1회 매수금).
5. [시뮬레이션] 전략은 실제 돈이 아닌 백테스트 결과임을 구분해서 말한다.
6. 당신은 대화로 답하는 것만 할 수 있다. 파일 생성·주문 실행·알림 같은 기능을 제안하지 않는다. 내보내기나 체결 입력은 앱 화면(데이터 관리, 대시보드)을 안내한다.

오늘(한국 시간): {today}

{rules}

[요약]
{summary}"""

TOOLS: list[dict] = [
    {"type": "function", "function": {
        "name": "get_portfolio_summary",
        "description": "모든 전략의 한 줄 상태와 종목별 시세 요약. 전체 현황·여러 전략 비교 질문에 사용.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_strategy_status",
        "description": "전략 하나의 현재 상태 (무한매수: T, 평단, 별%, 별지점, 잔금, 모드 / VR: V, 밴드, Pool).",
        "parameters": {"type": "object", "properties": {
            "strategy_id": {"type": "string", "description": "요약의 id=값"}},
            "required": ["strategy_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_today_orders",
        "description": "다음 거래일 주문표. strategy_id를 비우면 모든 전략.",
        "parameters": {"type": "object", "properties": {
            "strategy_id": {"type": "string"}}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_fill_history",
        "description": "체결 기록 조회 (최신순).",
        "parameters": {"type": "object", "properties": {
            "strategy_id": {"type": "string"},
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_price_stats",
        "description": "종목의 최근 N거래일 시세 통계 (기간, 개수, 평균, 최대, 최소, 추세, 변동성, 최대 낙폭).",
        "parameters": {"type": "object", "properties": {
            "ticker": {"type": "string", "enum": ["TQQQ", "SOXL"]},
            "days": {"type": "integer", "minimum": 5, "maximum": 2000}},
            "required": ["ticker"], "additionalProperties": False}}},
]


def run_tool(repo: Repo, tickers: list[str], name: str, args: dict) -> Any:
    if name == "get_portfolio_summary":
        s = sum_svc.build_summary(repo, tickers)
        return {"prices": s["prices"], "strategies": s["strategies"]}
    if name == "get_strategy_status":
        st = strat_svc.status(repo, args["strategy_id"])
        st.pop("snapshots", None)
        st["cycles"] = st.get("cycles", [])[-5:]
        return st
    if name == "get_today_orders":
        if args.get("strategy_id"):
            return sum_svc._sheet_brief(strat_svc.build_next_sheet(repo, args["strategy_id"]))
        return [{"strategy_id": x["strategy_id"], "name": x["name"],
                 **({"today": sum_svc._sheet_brief(x["today"])} if "today" in x else {"error": x.get("error")})}
                for x in strat_svc.orders_today(repo)]
    if name == "get_fill_history":
        docs = data_svc.list_data(repo, args.get("strategy_id"), args.get("date_from"), args.get("date_to"),
                                  limit=int(args.get("limit", 20)))
        return [{k: d.get(k) for k in ("date", "side", "role", "value", "qty", "memo", "source", "strategy_id")}
                for d in docs]
    if name == "get_price_stats":
        rows = price_rows(repo, args["ticker"])
        rows = rows[-int(args.get("days", 30)):]
        return {"ticker": args["ticker"], **sum_svc.price_stats(rows, trend_days=min(30, max(1, len(rows) - 1))),
                **sum_svc.extra_stats(rows)}
    raise ValueError(f"알 수 없는 도구: {name}")


def _tool_call_dict(tc) -> dict:
    return {"id": tc.id, "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


def build_messages(repo: Repo, tickers: list[str], history: list[dict], message: str,
                   strategy_id: Optional[str]) -> tuple[list[dict], dict]:
    summary = sum_svc.build_summary(repo, tickers, strategy_id)
    system = SYSTEM_TEMPLATE.format(today=datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                                    rules=RULES_BRIEF, summary=summary["text"])
    msgs = [{"role": "system", "content": system}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_LIMIT:]
             if m.get("role") in ("user", "assistant") and m.get("content")]
    msgs.append({"role": "user", "content": message})
    return msgs, summary


def chat(repo: Repo, client, model: str, tickers: list[str], message: str,
         conversation_id: Optional[str] = None, strategy_id: Optional[str] = None) -> dict:
    history = conv_svc.get(repo, conversation_id).get("messages", []) if conversation_id else []
    messages, summary = build_messages(repo, tickers, history, message, strategy_id)
    tools_used: list[dict] = []
    reply = None
    for round_no in range(MAX_TOOL_ROUNDS + 1):
        kwargs = {"model": model, "messages": messages, "tools": TOOLS}
        if round_no == MAX_TOOL_ROUNDS:        # 도구는 최대 3회, 마지막에는 답변만 받는다
            kwargs["tool_choice"] = "none"
        resp = client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        calls = getattr(msg, "tool_calls", None) or []
        if not calls:
            reply = msg.content or ""
            break
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [_tool_call_dict(tc) for tc in calls]})
        for tc in calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                result = run_tool(repo, tickers, tc.function.name, args)
                ok = True
            except Exception as e:  # 도구 오류는 GPT에게 알려서 답변에 반영
                args, result, ok = {}, {"error": str(e)}, False
            tools_used.append({"name": tc.function.name, "args": args, "ok": ok})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False, default=str)[:12000]})
    if reply is None:
        reply = "답변을 만들지 못했습니다. 다시 시도해 주세요."

    new_msgs = [{"role": "user", "content": message},
                {"role": "assistant", "content": reply, "tools_used": tools_used}]
    if conversation_id:
        conv = conv_svc.append(repo, conversation_id, new_msgs, strategy_id)
    else:
        conv = conv_svc.create(repo, new_msgs, strategy_id=strategy_id)
    return {"reply": reply, "conversation_id": conv["id"], "tools_used": tools_used,
            "summary_used": summary["text"]}


def make_openai_client(api_key: str, base_url: str = ""):
    """OpenAI 또는 OpenAI 호환 프록시(교육장 가상 키 등) 클라이언트."""
    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=base_url or None)
