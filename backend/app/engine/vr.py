"""VR 5.0 (밸류 리밸런싱) 계산 엔진.

- V 갱신 (2주마다): 다음 V = 현재 V + Pool ÷ G + 적립금 (인출식은 − 인출금)
- 밴드: V × (1 − band) ~ V × (1 + band). 평가금이 밴드 아래면 매수, 위면 매도.
- 사이클당 Pool 사용 한도: 적립식 75%, 거치식 50%, 인출식 25%.
- 평단은 쓰지 않는다.

매수표·매도표: 보유 수량 q에서 k주를 더 샀을 때 평가금이 밴드 하단에 닿는 가격
    매수 k번째 = 하단 ÷ (q + k),  매도 k번째 = 상단 ÷ (q − k)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Optional

from .common import VR_BUY, VR_SELL, Day, OrderLine, ceil_cents, floor_cents

POOL_LIMIT = {"installment": 0.75, "lump_sum": 0.50, "withdrawal": 0.25}
VR_TYPES_KO = {"installment": "적립식", "lump_sum": "거치식", "withdrawal": "인출식"}


@dataclass
class VRSettings:
    ticker: str
    vr_type: str                 # "installment" | "lump_sum" | "withdrawal"
    start_v: float               # 시작 V (보통 처음 매수한 평가금)
    start_pool: float            # 시작 Pool (현금)
    g: float = 10.0
    band: float = 0.15
    cycle_amount: float = 0.0    # 사이클마다 적립금(적립식) 또는 인출금(인출식). 양수로 입력
    rebalance_days: int = 10     # 2주 = 약 10거래일
    max_lines: int = 10

    def __post_init__(self):
        if self.vr_type not in POOL_LIMIT:
            raise ValueError(f"VR 유형은 {list(POOL_LIMIT)} 중 하나")

    @property
    def pool_limit(self) -> float:
        return POOL_LIMIT[self.vr_type]

    @property
    def signed_amount(self) -> float:
        if self.vr_type == "installment":
            return self.cycle_amount
        if self.vr_type == "withdrawal":
            return -self.cycle_amount
        return 0.0


@dataclass
class VRState:
    v: float
    pool: float
    qty: int = 0
    budget_left: float = 0.0          # 이번 사이클에 남은 매수 한도
    days_since: int = 0
    snapshots: list[dict] = field(default_factory=list)
    last_date: Optional[str] = None

    def band(self, band: float) -> tuple[float, float]:
        return self.v * (1 - band), self.v * (1 + band)


class VREngine:
    def __init__(self, s: VRSettings):
        self.s = s

    def initial_state(self, initial_qty: int = 0) -> VRState:
        return VRState(v=self.s.start_v, pool=self.s.start_pool, qty=initial_qty,
                       budget_left=self.s.start_pool * self.s.pool_limit)

    def new_v(self, v: float, pool: float) -> float:
        """다음 V = 현재 V + Pool/G + 적립금(−인출금). Pool은 적립·인출 전 값."""
        return v + pool / self.s.g + self.s.signed_amount

    def rebalance(self, st: VRState, date: str, close: float) -> VRState:
        """V 갱신일 처리: 새 V, Pool(적립·인출 반영), 이번 사이클 매수 한도, 스냅샷."""
        v2 = self.new_v(st.v, st.pool)
        pool2 = st.pool + self.s.signed_amount
        lo, hi = v2 * (1 - self.s.band), v2 * (1 + self.s.band)
        snap = {"date": date, "v": round(v2, 2), "e": round(st.qty * close, 2), "pool": round(pool2, 2),
                "band_low": round(lo, 2), "band_high": round(hi, 2),
                "cycle_amount": self.s.signed_amount,
                "pool_limit": round(max(0.0, pool2) * self.s.pool_limit, 2)}
        return replace(st, v=v2, pool=pool2, budget_left=max(0.0, pool2) * self.s.pool_limit,
                       days_since=0, snapshots=st.snapshots + [snap])

    def next_orders(self, st: VRState) -> dict:
        lo, hi = st.band(self.s.band)
        lines: list[OrderLine] = []
        spent = 0.0
        for k in range(1, self.s.max_lines + 1):
            p = floor_cents(lo / (st.qty + k))
            if spent + p > st.budget_left:
                break
            spent += p
            lines.append(OrderLine("buy", "LOC", VR_BUY, p, 1))
        for k in range(1, min(self.s.max_lines, max(0, st.qty - 1)) + 1):
            p = ceil_cents(hi / (st.qty - k))
            lines.append(OrderLine("sell", "LOC", VR_SELL, p, 1))
        return {"mode": "vr", "v": round(st.v, 2), "band_low": round(lo, 2), "band_high": round(hi, 2),
                "pool": round(st.pool, 2), "budget_left": round(st.budget_left, 2), "lines": lines}

    def apply_day(self, st: VRState, day: Day) -> VRState:
        qty, pool, budget = st.qty, st.pool, st.budget_left
        for f in day.fills:
            if f.side == "buy":
                qty += f.qty
                pool -= f.price * f.qty
                budget -= f.price * f.qty
            else:
                q = min(f.qty, qty)
                qty -= q
                pool += f.price * q
        st = replace(st, qty=qty, pool=pool, budget_left=max(0.0, budget),
                     days_since=st.days_since + 1, last_date=day.date)
        return st

    def is_rebalance_day(self, st: VRState) -> bool:
        return st.days_since >= self.s.rebalance_days
