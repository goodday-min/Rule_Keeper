"""백테스트: 주문표 생성 → 자동 체결 판정 → 상태 재생을 하루씩 반복한다.

시뮬레이션 전략의 가상 체결(source = backtest)을 만드는 데 쓰고,
엔진 전체가 오류 없이 돌아가는지 확인하는 용도로도 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass

from .common import Day, judge
from .infinite import InfSettings, make_engine
from .vr import VREngine, VRSettings


@dataclass
class Bar:
    date: str
    close: float
    high: float


def run_infinite(s: InfSettings, bars: list[Bar]):
    """bars[0]은 시작 전날(전일 종가용). 반환: (최종 상태, Day 목록)."""
    eng = make_engine(s)
    st = eng.initial_state()
    days: list[Day] = []
    for prev, bar in zip(bars, bars[1:]):
        sheet = eng.next_orders(st, prev.close)
        fills = judge(sheet["lines"], bar.close, bar.high)
        day = Day(bar.date, bar.close, bar.high, sheet["lines"], fills)
        st = eng.apply_day(st, day)
        days.append(day)
    return st, days


def run_vr(s: VRSettings, bars: list[Bar], initial_qty: int):
    eng = VREngine(s)
    st = eng.initial_state(initial_qty)
    days: list[Day] = []
    for bar in bars:
        if eng.is_rebalance_day(st):
            st = eng.rebalance(st, bar.date, bar.close)
        sheet = eng.next_orders(st)
        fills = judge(sheet["lines"], bar.close, bar.high)
        day = Day(bar.date, bar.close, bar.high, sheet["lines"], fills)
        st = eng.apply_day(st, day)
        days.append(day)
    return st, days
