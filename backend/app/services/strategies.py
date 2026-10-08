"""전략 상태 재생, 주문표, 체결 판정·확정, 백테스트, VR 갱신.

원칙: 사실(설정, 체결, 주문표, VR 스냅샷)만 저장하고 상태는 매번 재생해 계산한다.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict
from typing import Optional

from ..engine.backtest import Bar, run_infinite, run_vr
from ..engine.common import Day, Fill, OrderLine, judge
from ..engine.infinite import NORMAL, QUARTER_STOP, REVERSE, InfSettings, InfState, make_engine
from ..engine.vr import VREngine, VRSettings, VRState
from ..repo.base import DATA, ORDER_SHEETS, STRATEGIES, VR_SNAPSHOTS, Repo
from .common import Conflict, NotFound, get_strategy, next_trading_day, now_iso, price_rows

MODE_KO = {NORMAL: "일반", REVERSE: "리버스", QUARTER_STOP: "쿼터손절", "vr": "VR"}
PHASE_KO = {"start": "새 사이클", "first_half": "전반전", "second_half": "후반전"}


# ---------------------------------------------------------------------------
# 전략 CRUD


def strategy_name(s: dict) -> str:
    if s["type"] == "vr":
        return f"{s['ticker']} VR {({'installment': '적립식', 'lump_sum': '거치식', 'withdrawal': '인출식'})[s['vr_type']]}"
    return f"{s['ticker']} {s['rule_version'].upper()} {s.get('splits', 40)}분할"


def create_strategy(repo: Repo, body: dict) -> dict:
    body = dict(body)
    body.setdefault("status", "active")
    body.setdefault("is_simulation", False)
    body.setdefault("name", strategy_name(body))
    body["created_at"] = now_iso()
    _validate(body)
    doc = repo.add(STRATEGIES, body)
    doc["warnings"] = duplicate_warnings(repo, doc)
    return doc


def update_strategy(repo: Repo, sid: str, fields: dict) -> dict:
    s = get_strategy(repo, sid)
    merged = {**s, **fields}
    _validate(merged)
    doc = repo.update(STRATEGIES, sid, fields)
    doc["warnings"] = duplicate_warnings(repo, doc)
    return doc


def end_strategy(repo: Repo, sid: str) -> dict:
    get_strategy(repo, sid)
    return repo.update(STRATEGIES, sid, {"status": "ended", "ended_at": now_iso()})


def _validate(s: dict):
    if s["type"] == "infinite":
        InfSettings(s["ticker"], s["rule_version"], s["principal"], s.get("splits", 40))
    elif s["type"] == "vr":
        VRSettings(s["ticker"], s["vr_type"], s["start_v"], s["start_pool"])
    else:
        raise ValueError("type은 infinite 또는 vr")


def duplicate_warnings(repo: Repo, s: dict) -> list[str]:
    """같은 종목·같은 계좌의 실전 전략이 있으면 평단이 섞인다."""
    if s.get("is_simulation") or s.get("status") == "ended":
        return []
    others = [o for o in repo.where(STRATEGIES, "ticker", s["ticker"])
              if o["id"] != s["id"] and o.get("status") == "active" and not o.get("is_simulation")
              and (o.get("account_memo") or "") == (s.get("account_memo") or "")]
    if others:
        names = ", ".join(o.get("name", o["id"]) for o in others)
        return [f"같은 종목·계좌의 전략이 있습니다({names}). 평단이 섞이니 계좌를 분리하세요."]
    return []


def list_strategies(repo: Repo, include_ended: bool = False) -> list[dict]:
    out = []
    for s in sorted(repo.where(STRATEGIES), key=lambda x: x.get("created_at", "")):
        if s.get("status") == "ended" and not include_ended:
            continue
        try:
            st = status(repo, s["id"])
        except Exception as e:  # 상태 계산 실패가 목록 전체를 막지 않게
            st = {"error": str(e)}
        out.append({**s, "status_summary": st})
    return out


# ---------------------------------------------------------------------------
# 재생


def inf_settings(s: dict) -> InfSettings:
    return InfSettings(s["ticker"], s["rule_version"], float(s["principal"]), int(s.get("splits", 40)),
                       bool(s.get("compounding", False)), s.get("big_pct"), int(s.get("ladder_count", 8)))


def vr_settings(s: dict) -> VRSettings:
    return VRSettings(s["ticker"], s["vr_type"], float(s["start_v"]), float(s["start_pool"]),
                      float(s.get("g", 10)), float(s.get("band", 0.15)), float(s.get("cycle_amount", 0)))


def fills_of(repo: Repo, sid: str) -> list[dict]:
    return sorted(repo.where(DATA, "strategy_id", sid), key=lambda d: (d["date"], d.get("created_at", "")))


def _days(repo: Repo, s: dict) -> tuple[list[Day], Optional[dict]]:
    """체결이 없는 거래일도 포함한 날짜별 Day 목록 (리버스 별지점 = 직전 5거래일 종가 평균)."""
    fills = fills_of(repo, s["id"])
    by_date: dict[str, list[Fill]] = defaultdict(list)
    for f in fills:
        by_date[f["date"]].append(Fill(f["role"], f["side"], float(f["value"]), int(f["qty"])))
    start = s.get("start_date") or (fills[0]["date"] if fills else None)
    prices = {r["date"]: r for r in price_rows(repo, s["ticker"], start)}
    dates = sorted(set(prices) | set(by_date))
    days = []
    for d in dates:
        p = prices.get(d)
        close = float(p["close"]) if p else by_date[d][-1].price
        high = float(p.get("high", close)) if p else close
        days.append(Day(d, close, high, [], by_date.get(d, [])))
    # 주문표 기준 종가는 전략 시작일과 무관하게 그 종목의 최신 종가
    all_rows = price_rows(repo, s["ticker"])
    last_price = all_rows[-1] if all_rows else None
    return days, last_price


def replay_infinite(repo: Repo, s: dict) -> tuple[InfState, Optional[dict]]:
    eng = make_engine(inf_settings(s))
    st = eng.initial_state()
    days, last_price = _days(repo, s)
    for d in days:
        st = eng.apply_day(st, d)
    return st, last_price


def replay_vr(repo: Repo, s: dict) -> tuple[VRState, Optional[dict], int]:
    """VR 상태와 마지막 갱신 이후 지난 거래일 수."""
    vs = vr_settings(s)
    eng = VREngine(vs)
    st = eng.initial_state(int(s.get("initial_qty", 0)))
    snaps = {x["date"]: x for x in repo.where(VR_SNAPSHOTS, "strategy_id", s["id"])}
    days, last_price = _days(repo, s)
    dates = sorted(set(d.date for d in days) | set(snaps))
    day_map = {d.date: d for d in days}
    since = 0
    for d in dates:
        if d in snaps:
            sn = snaps[d]
            pool = st.pool + float(sn.get("cycle_amount", 0))
            st = VRState(v=float(sn["v"]), pool=pool, qty=st.qty, budget_left=max(0.0, pool) * vs.pool_limit,
                         snapshots=st.snapshots + [sn])
            since = 0
        if d in day_map:
            st = eng.apply_day(st, day_map[d])
            since += 1
    return st, last_price, since


# ---------------------------------------------------------------------------
# 상태


def status(repo: Repo, sid: str) -> dict:
    s = get_strategy(repo, sid)
    if s["type"] == "vr":
        return _vr_status(repo, s)
    st, lp = replay_infinite(repo, s)
    eng = make_engine(inf_settings(s))
    close = float(lp["close"]) if lp else None
    out = {
        "strategy_id": sid, "name": s.get("name"), "type": "infinite", "version": s["rule_version"],
        "ticker": s["ticker"], "splits": s["splits"], "mode": st.mode, "mode_ko": MODE_KO[st.mode],
        "t": round(st.t, 4), "qty": st.qty, "avg": round(st.avg, 4), "cash": round(st.cash, 2),
        "principal": round(st.principal, 2), "cycle_no": st.cycle_no, "cycle_start": st.cycle_start,
        "cycles": st.cycles, "profit_total": round(st.profit_total, 2),
        "last_date": lp["date"] if lp else None, "last_close": close,
    }
    if st.qty:
        out["star_pct"] = round(eng.star_pct(st.t), 4)
        out["star"] = eng.star_price(st)
        out["phase"] = "first_half" if st.t < s["splits"] / 2 else "second_half"
        out["phase_ko"] = PHASE_KO[out["phase"]]
        if close:
            out["pnl"] = round((close - st.avg) * st.qty, 2)
            out["pnl_pct"] = round((close / st.avg - 1) * 100, 2) if st.avg else None
    else:
        out["phase"], out["phase_ko"] = "start", PHASE_KO["start"]
    if s["rule_version"] == "v4.0":
        out["unit"] = round(st.cash / (s["splits"] - st.t), 2) if st.mode == NORMAL and st.t < s["splits"] else None
        if st.mode == REVERSE:
            out["reverse_star"] = eng.reverse_star(st)
            out["reverse_exit_price"] = round(st.avg * (1 - eng.reverse_exit_pct()), 2)
    else:
        out["unit"] = round(eng.unit, 2)
        if st.mode == QUARTER_STOP:
            out["quarter_stop"] = {"phase": st.qs_phase, "buys": st.qs_buys, "unit": round(st.qs_unit, 2)}
    return out


def _vr_status(repo: Repo, s: dict) -> dict:
    vs = vr_settings(s)
    st, lp, since = replay_vr(repo, s)
    close = float(lp["close"]) if lp else None
    e = st.qty * close if close else None
    lo, hi = st.band(vs.band)
    pos = None
    if e is not None:
        pos = "below" if e < lo else "above" if e > hi else "inside"
    return {
        "strategy_id": s["id"], "name": s.get("name"), "type": "vr", "ticker": s["ticker"], "mode": "vr",
        "mode_ko": "VR", "vr_type": vs.vr_type, "v": round(st.v, 2), "e": round(e, 2) if e is not None else None,
        "band_low": round(lo, 2), "band_high": round(hi, 2), "band_position": pos, "pool": round(st.pool, 2),
        "budget_left": round(st.budget_left, 2), "qty": st.qty, "g": vs.g,
        "days_since_rebalance": since, "rebalance_due": since >= vs.rebalance_days,
        "last_date": lp["date"] if lp else None, "last_close": close,
        "snapshots": st.snapshots[-5:],
    }


# ---------------------------------------------------------------------------
# 주문표


def _lines_to_docs(lines: list[OrderLine]) -> list[dict]:
    return [{**asdict(l), "line_id": i} for i, l in enumerate(lines)]


def build_next_sheet(repo: Repo, sid: str) -> dict:
    """마지막 종가 다음 거래일의 주문표. 확정된 주문표는 다시 만들지 않는다."""
    s = get_strategy(repo, sid)
    if s["type"] == "vr":
        vs = vr_settings(s)
        st, lp, since = replay_vr(repo, s)
        if not lp:
            raise Conflict("시세가 없습니다. 먼저 시세를 동기화하세요")
        sheet = VREngine(vs).next_orders(st)
        sheet["rebalance_due"] = since >= vs.rebalance_days
        if sheet["rebalance_due"]:
            sheet["notice"] = "V 갱신일입니다. V를 먼저 갱신하면 주문표가 새 밴드로 바뀝니다."
        lo, hi = sheet["band_low"], sheet["band_high"]
        e = st.qty * float(lp["close"])
        if lo <= e <= hi:
            sheet["notice"] = sheet.get("notice") or "평가금이 밴드 안에 있습니다. 밴드를 벗어나는 날에만 체결됩니다."
    else:
        st, lp = replay_infinite(repo, s)
        if not lp:
            raise Conflict("시세가 없습니다. 먼저 시세를 동기화하세요")
        sheet = make_engine(inf_settings(s)).next_orders(st, float(lp["close"]))
    date = next_trading_day(lp["date"])
    # 장중 시세로 잘못 만들어졌던 '앞선 날짜'의 미확정 주문표는 지운다 (시세 동기화가 장중 행을 지운 경우)
    for x in repo.where(ORDER_SHEETS, "strategy_id", sid):
        if x.get("status") == "pending" and x["date"] > date:
            repo.delete(ORDER_SHEETS, x["id"])
    sheet_id = f"{sid}_{date}"
    existing = repo.get(ORDER_SHEETS, sheet_id)
    if existing and existing.get("status") == "confirmed":
        return existing
    doc = {"strategy_id": sid, "date": date, "based_on": lp["date"], "status": "pending",
           "lines": _lines_to_docs(sheet.pop("lines")),
           "meta": {k: v for k, v in sheet.items()}, "created_at": now_iso()}
    unconfirmed = [x for x in repo.where(ORDER_SHEETS, "strategy_id", sid)
                   if x["status"] == "pending" and x["date"] <= lp["date"]]
    doc["provisional"] = bool(unconfirmed)       # 이전 체결이 확정되지 않았으면 임시 주문표
    same = ("based_on", "status", "lines", "meta", "provisional")
    if existing and all(existing.get(k) == doc[k] for k in same):
        return existing                          # 바뀐 것이 없으면 다시 쓰지 않는다 (Firestore 쓰기 절약)
    return repo.put(ORDER_SHEETS, sheet_id, doc)


def judge_sheet(repo: Repo, sid: str, date: str) -> dict:
    s = get_strategy(repo, sid)
    sheet = repo.get(ORDER_SHEETS, f"{sid}_{date}")
    if not sheet:
        raise NotFound("해당 날짜의 주문표가 없습니다")
    p = repo.get("prices", f"{s['ticker']}_{date}")
    if not p:
        return {**sheet, "judge_status": "no_price", "judged": []}
    lines = [OrderLine(l["side"], l["order_type"], l["role"], l["price"], l["qty"]) for l in sheet["lines"]]
    judged = []
    for l, src in zip(lines, sheet["lines"]):
        f = judge([l], float(p["close"]), float(p.get("high", p["close"])))
        judged.append({"line_id": src["line_id"], "filled": bool(f),
                       "price": f[0].price if f else None, "qty": f[0].qty if f else 0})
    return {**sheet, "judge_status": "ok", "close": p["close"], "high": p.get("high"), "judged": judged}


def confirm_sheet(repo: Repo, sid: str, date: str, overrides: Optional[list[dict]] = None) -> dict:
    """판정(고친 줄 반영)을 체결 기록으로 저장하고 주문표를 확정한다."""
    j = judge_sheet(repo, sid, date)
    if j.get("status") == "confirmed":
        raise Conflict("이미 확정된 주문표입니다")
    if j["judge_status"] != "ok" and not overrides:
        raise Conflict("그날 시세가 없어 자동 판정을 할 수 없습니다. 체결을 직접 입력하세요")
    result = {x["line_id"]: dict(x) for x in j["judged"]}
    for o in overrides or []:
        result.setdefault(o["line_id"], {"line_id": o["line_id"]}).update(o)
    lines = {l["line_id"]: l for l in j["lines"]}
    created = []
    for lid, r in sorted(result.items()):
        if not r.get("filled") or not r.get("qty"):
            continue
        l = lines[lid]
        created.append(repo.add(DATA, {
            "date": date, "value": float(r["price"]), "qty": int(r["qty"]), "memo": l.get("note") or "",
            "strategy_id": sid, "side": l["side"], "role": l["role"], "order_type": l["order_type"],
            "sheet_id": j["id"], "line_id": lid, "source": "auto", "created_at": now_iso()}))
    repo.update(ORDER_SHEETS, j["id"], {"status": "confirmed", "confirmed_at": now_iso()})
    return {"sheet_id": j["id"], "fills_created": len(created), "fills": created, "status": status(repo, sid)}


def orders_today(repo: Repo) -> list[dict]:
    """대시보드용: 전략별 확정 대기 주문표 + 오늘 주문표."""
    out = []
    for s in repo.where(STRATEGIES, "status", "active"):
        item = {"strategy_id": s["id"], "name": s.get("name"), "is_simulation": s.get("is_simulation", False)}
        try:
            pending = []
            for sh in sorted(repo.where(ORDER_SHEETS, "strategy_id", s["id"]), key=lambda x: x["date"]):
                if sh["status"] == "pending":
                    j = judge_sheet(repo, s["id"], sh["date"])
                    if j["judge_status"] == "ok":
                        pending.append(j)
            item["to_confirm"] = pending
            item["today"] = build_next_sheet(repo, s["id"])
            item["status"] = status(repo, s["id"])
        except Exception as e:
            item["error"] = str(e)
        out.append(item)
    order = {"reverse": 0, "quarter_stop": 0}
    return sorted(out, key=lambda x: (order.get(x.get("status", {}).get("mode"), 2)
                                      - (1 if x.get("status", {}).get("rebalance_due") else 0)))


# ---------------------------------------------------------------------------
# VR 갱신


def vr_rebalance(repo: Repo, sid: str, cycle_amount: Optional[float] = None, dry_run: bool = False) -> dict:
    s = get_strategy(repo, sid)
    if s["type"] != "vr":
        raise Conflict("VR 전략이 아닙니다")
    if cycle_amount is not None:
        s = {**s, "cycle_amount": cycle_amount}
    vs = vr_settings(s)
    st, lp, _ = replay_vr(repo, s)
    if not lp:
        raise Conflict("시세가 없습니다")
    st2 = VREngine(vs).rebalance(st, lp["date"], float(lp["close"]))
    snap = {**st2.snapshots[-1], "strategy_id": sid, "created_at": now_iso()}
    if dry_run:
        return {"preview": snap}
    repo.put(VR_SNAPSHOTS, f"{sid}_{lp['date']}", snap)
    return {"snapshot": snap, "status": status(repo, sid)}


# ---------------------------------------------------------------------------
# 백테스트 (시뮬레이션 전략)


def backtest(repo: Repo, sid: str, start_date: str) -> dict:
    s = get_strategy(repo, sid)
    if not s.get("is_simulation"):
        raise Conflict("시뮬레이션 전략에서만 백테스트를 실행할 수 있습니다")
    rows = price_rows(repo, s["ticker"])
    idx = next((i for i, r in enumerate(rows) if r["date"] >= start_date), None)
    if idx is None or len(rows) < 2:
        raise Conflict("시작일 이후 시세가 부족합니다")
    bars = [Bar(r["date"], float(r["close"]), float(r.get("high", r["close"]))) for r in rows[max(0, idx - 1):]]
    repo.delete_where(DATA, "strategy_id", sid)
    repo.delete_where(VR_SNAPSHOTS, "strategy_id", sid)
    repo.delete_where(ORDER_SHEETS, "strategy_id", sid)
    docs = []
    if s["type"] == "vr":
        init_qty = math.floor(float(s["start_v"]) / bars[0].close)
        repo.update(STRATEGIES, sid, {"start_date": bars[1].date, "initial_qty": init_qty})
        st, days = run_vr(vr_settings(s), bars[1:], init_qty)
        snaps = [(f"{sid}_{x['date']}", {**x, "strategy_id": sid, "created_at": now_iso()}) for x in st.snapshots]
        repo.put_many(VR_SNAPSHOTS, snaps)
        summary = {"snapshots": len(snaps), "final_qty": st.qty, "final_pool": round(st.pool, 2),
                   "final_v": round(st.v, 2)}
    else:
        repo.update(STRATEGIES, sid, {"start_date": bars[1].date})
        st, days = run_infinite(inf_settings(s), bars)
        summary = {"cycles": len(st.cycles), "profit_total": round(st.profit_total, 2), "mode": st.mode,
                   "t": round(st.t, 2)}
    n = 0
    for d in days:
        for f in d.fills:
            n += 1
            docs.append((f"{sid}_bt_{n:06d}", {
                "date": d.date, "value": f.price, "qty": f.qty, "memo": f"백테스트 {f.role}",
                "strategy_id": sid, "side": f.side, "role": f.role, "order_type": "",
                "source": "backtest", "created_at": now_iso()}))
    repo.put_many(DATA, docs)
    return {"fills_created": len(docs), "days": len(days), **summary}
