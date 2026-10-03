"""데이터 요약 (GET /api/data/summary, 프롬프트 주입용)과 추가 지표 (GET /api/data/statistics)."""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Optional

from ..repo.base import STRATEGIES, Repo
from . import strategies as svc
from .common import price_rows


def price_stats(rows: list[dict], trend_days: int = 30) -> dict:
    if not rows:
        return {"count": 0}
    closes = [float(r["close"]) for r in rows]
    out = {"period_start": rows[0]["date"], "period_end": rows[-1]["date"], "count": len(rows),
           "mean": round(mean(closes), 2), "max": round(max(closes), 2), "min": round(min(closes), 2),
           "last": closes[-1]}
    if len(closes) > trend_days:
        base = closes[-trend_days - 1]
        chg = (closes[-1] / base - 1) * 100
        out["change_30d_pct"] = round(chg, 2)
        out["trend_30d"] = "상승" if chg > 3 else "하락" if chg < -3 else "유지"
    return out


def extra_stats(rows: list[dict]) -> dict:
    closes = [float(r["close"]) for r in rows]
    if len(closes) < 3:
        return {}
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    peak, mdd = closes[0], 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = min(mdd, c / peak - 1)
    return {"volatility_annual_pct": round(pstdev(rets) * math.sqrt(252) * 100, 1),
            "max_drawdown_pct": round(mdd * 100, 1)}


def strategy_line(st: dict) -> str:
    if st.get("error"):
        return f"{st.get('name', '?')}: 상태 계산 오류"
    if st["type"] == "vr":
        pos = {"below": "밴드 하단 아래(매수 구간)", "above": "밴드 상단 위(매도 구간)", "inside": "밴드 안"}.get(
            st.get("band_position"), "평가금 미상")
        due = ", V 갱신일" if st.get("rebalance_due") else ""
        return (f"{st['name']}: V {st['v']:,.0f}, 평가금 {st['e'] or 0:,.0f}, 밴드 {st['band_low']:,.0f}~"
                f"{st['band_high']:,.0f} ({pos}), Pool {st['pool']:,.0f}{due}")
    if not st["qty"]:
        return f"{st['name']}: 보유 없음, 새 사이클 대기 ({st['cycle_no']}사이클)"
    mode = st["mode_ko"] if st["mode"] != "normal" else st["phase_ko"]
    pnl = f", 평가손익 {st['pnl_pct']:+.1f}%" if st.get("pnl_pct") is not None else ""
    return (f"{st['name']}: {mode}, T {st['t']:.2f}/{st['splits']}, 평단 {st['avg']:.2f}, "
            f"별지점 {st.get('star')}, 보유 {st['qty']}주, 잔금 {st['cash']:,.0f}{pnl}")


def build_summary(repo: Repo, tickers: list[str], strategy_id: Optional[str] = None) -> dict:
    prices = {t: price_stats(price_rows(repo, t)) for t in tickers}
    strategies = []
    for s in repo.where(STRATEGIES, "status", "active"):
        try:
            st = svc.status(repo, s["id"])
        except Exception as e:
            st = {"name": s.get("name"), "error": str(e)}
        strategies.append({"strategy_id": s["id"], "name": s.get("name"), "is_simulation": s.get("is_simulation"),
                           "line": strategy_line(st), "mode": st.get("mode"), "rebalance_due": st.get("rebalance_due")})
    out = {"prices": prices, "strategies": strategies,
           "counts": {"infinite": sum(1 for s in repo.where(STRATEGIES, "status", "active") if s["type"] == "infinite"),
                      "vr": sum(1 for s in repo.where(STRATEGIES, "status", "active") if s["type"] == "vr")}}
    if strategy_id:
        out["selected"] = {"status": svc.status(repo, strategy_id),
                           "today": _sheet_brief(svc.build_next_sheet(repo, strategy_id))}
    out["text"] = summary_text(out)
    return out


def _sheet_brief(sheet: dict) -> dict:
    return {"date": sheet["date"], "provisional": sheet.get("provisional", False), "meta": sheet.get("meta", {}),
            "lines": [{k: l[k] for k in ("side", "order_type", "role", "price", "qty", "note")} for l in sheet["lines"]]}


ROLE_KO = {"big": "큰수 LOC", "star_buy": "별지점 LOC", "avg_buy": "평단 LOC", "ladder": "사다리 LOC",
           "quarter_sell": "쿼터 LOC", "limit_sell": "지정가", "quarter_stop_moc": "쿼터손절 MOC",
           "quarter_stop_buy": "쿼터손절 LOC", "quarter_stop_sell": "쿼터손절 LOC", "reverse_moc": "리버스 MOC",
           "reverse_sell": "리버스 LOC", "reverse_buy": "쿼터매수 LOC", "vr_buy": "VR LOC", "vr_sell": "VR LOC"}


def summary_text(s: dict) -> str:
    """시스템 프롬프트에 넣을 압축 요약."""
    lines = ["[시세 요약]"]
    for t, p in s["prices"].items():
        if not p.get("count"):
            lines.append(f"- {t}: 데이터 없음")
            continue
        trend = f", 최근 30거래일 {p['trend_30d']}({p['change_30d_pct']:+.1f}%)" if "trend_30d" in p else ""
        lines.append(f"- {t}: {p['period_start']}~{p['period_end']} {p['count']}개, 평균 {p['mean']}, "
                     f"최대 {p['max']}, 최소 {p['min']}, 최근 종가 {p['last']}{trend}")
    lines.append(f"[전략 {s['counts']['infinite']}+{s['counts']['vr']}개 (무한매수+VR)]")
    for x in s["strategies"]:
        sim = " [시뮬레이션]" if x.get("is_simulation") else ""
        lines.append(f"- (id={x['strategy_id']}) {x['line']}{sim}")
    sel = s.get("selected")
    if sel:
        lines.append(f"[선택 전략 상세: {sel['status'].get('name')}]")
        lines.append(", ".join(f"{k}={v}" for k, v in sel["status"].items()
                               if k not in ("cycles", "snapshots", "strategy_id") and v is not None))
        t = sel["today"]
        flag = " (어젯밤 체결 확정 전이라 임시)" if t["provisional"] else ""
        lines.append(f"[오늘 주문표 {t['date']}{flag}]")
        for l in t["lines"]:
            price = "시장가(MOC)" if l["price"] is None else f"{l['price']:.2f}"
            side = "매수" if l["side"] == "buy" else "매도"
            lines.append(f"- {side} {ROLE_KO.get(l['role'], l['role'])} {price} × {l['qty']}주 {l.get('note') or ''}".rstrip())
    return "\n".join(lines)


def statistics(repo: Repo, tickers: list[str]) -> dict:
    out = {"prices": {}, "strategies": []}
    for t in tickers:
        rows = price_rows(repo, t)
        out["prices"][t] = {**price_stats(rows), **extra_stats(rows)}
    for s in repo.where(STRATEGIES, "status", "active"):
        try:
            st = svc.status(repo, s["id"])
        except Exception:
            continue
        item = {"strategy_id": s["id"], "name": s.get("name")}
        if st["type"] == "infinite":
            item["realized_profit"] = st["profit_total"]
            item["cycles_done"] = len(st["cycles"])
            item["unrealized"] = st.get("pnl")
        else:
            item["e"], item["v"], item["pool"] = st["e"], st["v"], st["pool"]
        out["strategies"].append(item)
    return out
