"""무한매수법 계산 엔진 (V2.2, V4.0).

사용 흐름
    eng = make_engine(settings)
    state = eng.initial_state()
    for day in days:                       # 저장된 사실을 순서대로 재생
        state = eng.apply_day(state, day)
    sheet = eng.next_orders(state, prev_close)   # 다음 거래일 주문표

규칙 출처: 라오어 카페 원문 (V2.2 2022.12~2023.7, V4.0 2026.3).
원문에 없는 세부(수량 반올림, 사다리 개수)는 설정값으로 둔다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Optional

from .common import (
    AVG_BUY, BIG, LADDER, LIMIT_SELL, QS_BUY, QS_MOC, QS_SELL, QUARTER_SELL,
    REV_BUY, REV_MOC, REV_SELL, STAR_BUY, Day, Fill, OrderLine,
    apply_big_number, ceil_to, ladder, round_cents, round_half_up_int,
)

NORMAL, REVERSE, QUARTER_STOP = "normal", "reverse", "quarter_stop"


@dataclass
class InfSettings:
    ticker: str                 # "TQQQ" | "SOXL"
    version: str                # "v2.2" | "v4.0"
    principal: float
    splits: int = 40            # V2.2: 40 권장(a분할 일반식 지원), V4.0: 20 | 40
    compounding: bool = False   # V4.0 재시작 원금에 수익 포함 여부
    big_pct: Optional[float] = None  # 큰수 비율. None이면 버전 기본값
    ladder_count: int = 8
    broker_limit: float = 0.20

    def __post_init__(self):
        self.ticker = self.ticker.upper()
        if self.ticker not in ("TQQQ", "SOXL"):
            raise ValueError("공식 종목은 TQQQ, SOXL만 지원합니다")
        if self.version == "v4.0" and self.splits not in (20, 40):
            raise ValueError("V4.0 별% 공식은 20분할·40분할만 공개되어 있습니다")


@dataclass
class InfState:
    principal: float            # 이번 사이클 원금
    cash: float                 # 잔금
    qty: int = 0
    avg: float = 0.0
    t: float = 0.0
    mode: str = NORMAL
    cycle_no: int = 1
    cycle_start: Optional[str] = None
    profit_total: float = 0.0   # 끝난 사이클 누적 수익
    closes: list[float] = field(default_factory=list)  # 최근 종가 (리버스 별지점용)
    rev_day: int = 0            # 리버스 경과일. 0이면 다음 주문표가 첫날 MOC
    qs_phase: str = "moc"       # V2.2 쿼터손절: "moc" | "buying"
    qs_buys: int = 0
    qs_unit: float = 0.0
    qs_round: int = 0
    cycles: list[dict] = field(default_factory=list)
    last_date: Optional[str] = None

    @property
    def cost(self) -> float:
        return self.avg * self.qty


# ---------------------------------------------------------------------------


class _Base:
    def __init__(self, s: InfSettings):
        self.s = s

    # 버전별로 채운다
    def star_pct(self, t: float) -> float: ...
    def target_pct(self) -> float: ...
    def default_big_pct(self) -> float: ...

    @property
    def big_pct(self) -> float:
        return self.s.big_pct if self.s.big_pct is not None else self.default_big_pct()

    def initial_state(self) -> InfState:
        return InfState(principal=self.s.principal, cash=self.s.principal)

    def star_price(self, st: InfState) -> float:
        return round_cents(st.avg * (1 + self.star_pct(st.t) / 100))

    # ---- 주문표 ----------------------------------------------------------

    def _first_buy(self, unit: float, prev_close: float) -> list[OrderLine]:
        price = round_cents(prev_close * (1 + self.big_pct))
        q = math.floor(unit / price)
        lines = [OrderLine("buy", "LOC", BIG, price, q, "새 사이클 첫 매수 (큰수)")]
        return lines + ladder(unit, q, price, self.s.ladder_count)

    def _normal_buys(self, st: InfState, unit: float) -> list[OrderLine]:
        star = self.star_price(st)
        buyp = round_cents(star - 0.01)
        if st.t < self.s.splits / 2:          # 전반전
            q1 = math.floor((unit / 2) / buyp)
            avgp = round_cents(st.avg)
            q2 = max(0, round_half_up_int((unit - q1 * buyp) / avgp))
            lines = [OrderLine("buy", "LOC", STAR_BUY, buyp, q1),
                     OrderLine("buy", "LOC", AVG_BUY, avgp, q2)]
            return lines + ladder(unit, q1 + q2, min(buyp, avgp), self.s.ladder_count)
        q = math.floor(unit / buyp)            # 후반전
        return [OrderLine("buy", "LOC", STAR_BUY, buyp, q)] + ladder(unit, q, buyp, self.s.ladder_count)

    def _normal_sells(self, st: InfState) -> list[OrderLine]:
        if st.qty <= 0:
            return []
        qq = st.qty // 4
        lines = []
        if qq:
            lines.append(OrderLine("sell", "LOC", QUARTER_SELL, self.star_price(st), qq))
        lines.append(OrderLine("sell", "LIMIT", LIMIT_SELL,
                               round_cents(st.avg * (1 + self.target_pct())), st.qty - qq))
        return lines

    # ---- 재생 공통 -------------------------------------------------------

    @staticmethod
    def _split_fills(st: InfState, fills: list[Fill]):
        sells = [f for f in fills if f.side == "sell"]
        buys = [f for f in fills if f.side == "buy"]
        return sells, buys

    def _apply_trades(self, st: InfState, fills: list[Fill]) -> tuple[InfState, set, set]:
        """매도 먼저(장중 지정가 → 종가), 매수 나중. 평단·잔금·수량 갱신."""
        sells, buys = self._split_fills(st, fills)
        qty, avg, cash = st.qty, st.avg, st.cash
        sold_roles, bought_roles = set(), set()
        for f in sells:
            q = min(f.qty, qty)
            if q <= 0:
                continue
            qty -= q
            cash += f.price * q
            sold_roles.add(f.role)
        if qty == 0:
            avg = 0.0
        for f in buys:
            if f.qty <= 0:
                continue
            avg = (avg * qty + f.price * f.qty) / (qty + f.qty)
            qty += f.qty
            cash -= f.price * f.qty
            bought_roles.add(f.role)
        return replace(st, qty=qty, avg=avg, cash=cash), sold_roles, bought_roles

    def _close_cycle(self, st: InfState, date: str) -> InfState:
        profit = st.cash - st.principal
        rec = {"cycle_no": st.cycle_no, "start": st.cycle_start, "end": date,
               "principal": st.principal, "profit": round(profit, 2)}
        if self.s.version == "v4.0" and self.s.compounding:
            new_principal, total = st.cash, st.profit_total + profit
        else:
            new_principal, total = st.principal, st.profit_total + profit
        return replace(st, principal=new_principal, cash=new_principal, qty=0, avg=0.0, t=0.0,
                       mode=NORMAL, cycle_no=st.cycle_no + 1, cycle_start=None,
                       profit_total=total, rev_day=0, qs_phase="moc", qs_buys=0, qs_round=0,
                       cycles=st.cycles + [rec])

    def _remember_close(self, st: InfState, day: Day) -> InfState:
        return replace(st, closes=(st.closes + [day.close])[-5:], last_date=day.date)


# ---------------------------------------------------------------------------


class V40(_Base):
    def star_pct(self, t: float) -> float:
        n = self.s.splits
        if self.s.ticker == "TQQQ":
            return 15 - (30 / n) * t      # 20분할 15-1.5T, 40분할 15-0.75T
        return 20 - (40 / n) * t          # 20분할 20-2T, 40분할 20-T

    def target_pct(self) -> float:
        return 0.15 if self.s.ticker == "TQQQ" else 0.20

    def reverse_exit_pct(self) -> float:
        return 0.15 if self.s.ticker == "TQQQ" else 0.20

    def default_big_pct(self) -> float:
        return 0.10

    @property
    def rev_ratio(self) -> float:      # 20분할 1/10, 40분할 1/20
        return 2 / self.s.splits

    def unit(self, st: InfState) -> float:
        return st.cash / (self.s.splits - st.t)

    def reverse_star(self, st: InfState) -> float:
        c = st.closes[-5:]
        return round_cents(sum(c) / len(c)) if c else 0.0

    def next_orders(self, st: InfState, prev_close: float) -> dict:
        if st.mode == REVERSE:
            return {"mode": REVERSE, "unit": round(st.cash / 4, 2), "lines": self._reverse_orders(st, prev_close)}
        if st.qty == 0:
            unit = st.cash / self.s.splits
            lines = self._first_buy(unit, prev_close)
            return {"mode": NORMAL, "phase": "start", "unit": round(unit, 2), "lines": lines}
        unit = self.unit(st)
        lines = self._normal_buys(st, unit) + self._normal_sells(st)
        lines = apply_big_number(lines, prev_close, self.big_pct, self.s.broker_limit)
        phase = "first_half" if st.t < self.s.splits / 2 else "second_half"
        return {"mode": NORMAL, "phase": phase, "unit": round(unit, 2),
                "star_pct": round(self.star_pct(st.t), 4), "star": self.star_price(st), "lines": lines}

    def _reverse_orders(self, st: InfState, prev_close: float) -> list[OrderLine]:
        sell_q = max(1, math.floor(st.qty * self.rev_ratio)) if st.qty else 0
        if st.rev_day == 0:                       # 첫날: 무조건 매도, 매수 없음
            return [OrderLine("sell", "MOC", REV_MOC, None, sell_q, "리버스 첫날 무조건 매도")]
        star = self.reverse_star(st)
        lines = [OrderLine("sell", "LOC", REV_SELL, star, sell_q)]
        budget = st.cash / 4
        buyp = round_cents(star - 0.01)
        q = math.floor(budget / buyp) if buyp > 0 else 0
        if q > 0:
            lines.append(OrderLine("buy", "LOC", REV_BUY, buyp, q, "쿼터매수 (잔금/4)"))
            lines += ladder(budget, q, buyp, self.s.ladder_count)
        return apply_big_number(lines, prev_close, self.big_pct, self.s.broker_limit)

    def apply_day(self, st: InfState, day: Day) -> InfState:
        had_position = st.qty > 0
        if not had_position and st.cycle_start is None and any(f.side == "buy" for f in day.fills):
            st = replace(st, cycle_start=day.date)
        mode_before, t = st.mode, st.t
        second_half = mode_before == NORMAL and st.t >= self.s.splits / 2
        st, sold, bought = self._apply_trades(st, day.fills)

        if mode_before == REVERSE:
            if sold:
                t *= (1 - self.rev_ratio)
            if bought:
                t += (self.s.splits - t) * 0.25
            st = replace(st, t=t, rev_day=st.rev_day + 1)
            if st.qty == 0:
                return self._remember_close(self._close_cycle(st, day.date), day)
            if day.close > st.avg * (1 - self.reverse_exit_pct()):
                st = replace(st, mode=NORMAL, rev_day=0)          # 다음 날부터 일반모드, T 승계
            elif math.floor((st.cash / 4) / day.close) < 1:
                st = replace(st, rev_day=0)                        # 리버스 중 소진 → 다시 MOC부터
            return self._remember_close(st, day)

        # 일반모드 T
        inc = self._buy_increment(bought, had_position, second_half)
        if LIMIT_SELL in sold and QUARTER_SELL in sold:
            t = 0.0 if st.qty == 0 else t * 0.25 * 0.75 + inc
        elif LIMIT_SELL in sold:
            t = t * 0.25 + inc                 # 지정가 매도 후 LOC 매수: ×0.25 + 1 또는 + 0.5
        elif QUARTER_SELL in sold:
            t = t * 0.75 + inc
        else:
            t = t + inc
        st = replace(st, t=t)

        if had_position and st.qty == 0:
            return self._remember_close(self._close_cycle(st, day.date), day)
        if st.t > self.s.splits - 1:
            st = replace(st, mode=REVERSE, rev_day=0)
        return self._remember_close(st, day)

    @staticmethod
    def _buy_increment(bought: set, had_position: bool, second_half: bool) -> float:
        """1회분 전체 체결 +1, 절반 체결 +0.5 (사다리는 주 주문이 체결된 뒤에만 체결된다)."""
        if not bought:
            return 0.0
        if BIG in bought or not had_position or second_half:
            return 1.0
        star, avg = STAR_BUY in bought, AVG_BUY in bought
        if star and avg:
            return 1.0
        if star or avg:
            return 0.5
        return 1.0


# ---------------------------------------------------------------------------


class V22(_Base):
    def star_pct(self, t: float) -> float:
        a = self.s.splits
        if self.s.ticker == "TQQQ":
            return 10 - (t / 2) * (40 / a)
        return 12 - (t * 0.6) * (40 / a)

    def target_pct(self) -> float:
        return 0.10 if self.s.ticker == "TQQQ" else 0.12

    def qs_pct(self) -> float:
        return 0.10 if self.s.ticker == "TQQQ" else 0.12

    def default_big_pct(self) -> float:
        return 0.10 if self.s.ticker == "TQQQ" else 0.12

    @property
    def unit(self) -> float:
        return self.s.principal / self.s.splits

    def calc_t(self, avg: float, qty: int) -> float:
        """T = 매수누적액 ÷ 1회 매수금, 소수 셋째 자리에서 올림 (2024.9.5 개정)."""
        return ceil_to(avg * qty / self.unit, 2) if qty else 0.0

    def next_orders(self, st: InfState, prev_close: float) -> dict:
        unit = self.unit
        if st.qty == 0:
            return {"mode": NORMAL, "phase": "start", "unit": round(unit, 2),
                    "lines": self._first_buy(unit, prev_close)}
        if st.mode == QUARTER_STOP:
            return {"mode": QUARTER_STOP, "unit": round(st.qs_unit or unit, 2),
                    "lines": self._qs_orders(st, prev_close)}
        unit = min(unit, max(0.0, st.cash))                   # 가진 돈 이상은 사지 않는다
        lines = (self._normal_buys(st, unit) if unit > 0 else []) + self._normal_sells(st)
        lines = [l for l in lines if l.qty > 0]
        lines = apply_big_number(lines, prev_close, self.big_pct, self.s.broker_limit)
        phase = "first_half" if st.t < self.s.splits / 2 else "second_half"
        return {"mode": NORMAL, "phase": phase, "unit": round(unit, 2),
                "star_pct": round(self.star_pct(st.t), 4), "star": self.star_price(st), "lines": lines}

    def _qs_orders(self, st: InfState, prev_close: float) -> list[OrderLine]:
        limit = OrderLine("sell", "LIMIT", LIMIT_SELL, round_cents(st.avg * (1 + self.target_pct())),
                          st.qty - st.qty // 4)
        if st.qs_phase == "moc":
            return [OrderLine("sell", "MOC", QS_MOC, None, st.qty // 4, "쿼터손절 1/4 무조건 매도"), limit]
        p = round_cents(st.avg * (1 - self.qs_pct()))
        budget = min(st.qs_unit, self._spendable(st))
        q = math.floor(budget / p) if p > 0 else 0
        if q == 0:
            # 1주도 살 돈이 없으면 1/4 MOC 매도로 현금을 만든다
            return [OrderLine("sell", "MOC", QS_MOC, None, st.qty // 4, "쿼터손절: 매수 자금 부족, 1/4 매도"), limit]
        lines = []
        if q:
            lines.append(OrderLine("buy", "LOC", QS_BUY, p, q, f"쿼터손절 {st.qs_buys + 1}/10회"))
            lines += ladder(budget, q, p, self.s.ladder_count)
        lines += [OrderLine("sell", "LOC", QS_SELL, p, st.qty // 4), limit]
        return apply_big_number(lines, prev_close, self.big_pct, self.s.broker_limit)

    def apply_day(self, st: InfState, day: Day) -> InfState:
        had_position = st.qty > 0
        if not had_position and st.cycle_start is None and any(f.side == "buy" for f in day.fills):
            st = replace(st, cycle_start=day.date)
        mode_before = st.mode
        avg_before = st.avg
        st, sold, bought = self._apply_trades(st, day.fills)
        st = replace(st, t=self.calc_t(st.avg, st.qty))

        if had_position and st.qty == 0:
            return self._remember_close(self._close_cycle(st, day.date), day)

        if mode_before == QUARTER_STOP:
            if QS_SELL in sold:
                st = replace(st, mode=NORMAL, qs_phase="moc", qs_buys=0, qs_round=0)   # 후반전 복귀
            elif QS_MOC in sold:
                moc = next(f for f in day.fills if f.role == QS_MOC)
                if st.qs_round > 0 and moc.price > avg_before * (1 - self.qs_pct()):
                    st = replace(st, mode=NORMAL, qs_phase="moc", qs_buys=0, qs_round=0)
                else:
                    # 1회 매수금 = (남은 자금 + 기존 수익금) ÷ 10, 기존 1회 매수금보다 크게 하지 않음
                    qs_unit = min(self.unit, self._spendable(st) / 10)
                    st = replace(st, qs_phase="buying", qs_unit=qs_unit, qs_buys=0)
            elif st.qs_phase == "buying" and (QS_BUY in bought or BIG in bought):   # 큰수로 합쳐진 경우 포함
                n = st.qs_buys + 1
                st = replace(st, qs_buys=n) if n < 10 else replace(
                    st, qs_buys=0, qs_phase="moc", qs_round=st.qs_round + 1)
            return self._remember_close(st, day)

        # 쿼터손절 진입: 1회치 매수를 온전히 더 할 수 없는 상태 (T > 39 또는 잔금 < 1회 매수금)
        if st.t > self.s.splits - 1 or st.cash < self.unit - 1e-9:
            st = replace(st, mode=QUARTER_STOP, qs_phase="moc", qs_buys=0, qs_round=0)
        return self._remember_close(st, day)

    @staticmethod
    def _spendable(st: InfState) -> float:
        """쿼터손절에서 쓸 수 있는 돈: 잔금 + 기존 수익금(손실이면 0으로 본다)."""
        return max(0.0, st.cash + max(0.0, st.profit_total))


# ---------------------------------------------------------------------------


def make_engine(s: InfSettings):
    if s.version == "v4.0":
        return V40(s)
    if s.version == "v2.2":
        return V22(s)
    raise ValueError(f"지원하지 않는 버전: {s.version}")


def replay(s: InfSettings, days: list[Day]) -> InfState:
    eng = make_engine(s)
    st = eng.initial_state()
    for d in days:
        st = eng.apply_day(st, d)
    return st
