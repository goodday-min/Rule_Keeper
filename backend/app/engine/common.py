"""공통 모델과 계산 도우미.

엔진은 Firestore·FastAPI와 무관한 순수 함수 모음이다.
- 사실(설정, 주문표, 체결)을 입력받아 상태를 재생하고
- 상태와 시세로 다음 주문표를 만든다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING
from typing import Optional

CENT = Decimal("0.01")

# ---- 주문 역할(role) ----------------------------------------------------
# 무한매수법
BIG = "big"                    # 큰수 매수 (새 사이클 첫 매수 / 증권사 제한 대응 병합)
STAR_BUY = "star_buy"          # 별지점 LOC 매수
AVG_BUY = "avg_buy"            # 평단 LOC 매수
LADDER = "ladder"              # 사다리 LOC 매수 (1주씩)
QUARTER_SELL = "quarter_sell"  # 1/4 별지점 LOC 매도
LIMIT_SELL = "limit_sell"      # 3/4 지정가 매도
QS_MOC = "quarter_stop_moc"    # V2.2 쿼터손절 1/4 MOC 매도
QS_BUY = "quarter_stop_buy"    # V2.2 쿼터손절 -10%(-12%) LOC 매수
QS_SELL = "quarter_stop_sell"  # V2.2 쿼터손절 1/4 -10%(-12%) LOC 매도
REV_MOC = "reverse_moc"        # V4.0 리버스 첫날 MOC 매도
REV_SELL = "reverse_sell"      # V4.0 리버스 별지점 LOC 매도
REV_BUY = "reverse_buy"        # V4.0 리버스 쿼터매수
# VR
VR_BUY = "vr_buy"
VR_SELL = "vr_sell"

BUY_ROLES = {BIG, STAR_BUY, AVG_BUY, LADDER, QS_BUY, REV_BUY, VR_BUY}
SELL_ROLES = {QUARTER_SELL, LIMIT_SELL, QS_MOC, QS_SELL, REV_MOC, REV_SELL, VR_SELL}

# ---- 금액 반올림 --------------------------------------------------------


def _d(x: float) -> Decimal:
    return Decimal(str(x))


def round_cents(x: float) -> float:
    """센트 단위 반올림 (별지점, 평단, 지정가)."""
    return float(_d(x).quantize(CENT, rounding=ROUND_HALF_UP))


def floor_cents(x: float) -> float:
    """센트 단위 내림 (사다리 가격: 그 가격에 사도 1회 매수금을 넘지 않게)."""
    return float(_d(x).quantize(CENT, rounding=ROUND_FLOOR))


def ceil_cents(x: float) -> float:
    return float(_d(x).quantize(CENT, rounding=ROUND_CEILING))


def ceil_to(x: float, places: int) -> float:
    q = Decimal(1).scaleb(-places)
    return float(_d(x).quantize(q, rounding=ROUND_CEILING))


def round_half_up_int(x: float) -> int:
    return int(_d(x).quantize(Decimal(1), rounding=ROUND_HALF_UP))


# ---- 모델 ---------------------------------------------------------------


@dataclass
class OrderLine:
    side: str            # "buy" | "sell"
    order_type: str      # "LOC" | "MOC" | "LIMIT"
    role: str
    price: Optional[float]  # MOC는 None
    qty: int
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Fill:
    """실제 체결 1건. 가격·수량은 증권사 체결 내역 그대로."""
    role: str
    side: str
    price: float
    qty: int


@dataclass
class Day:
    """하루치 사실: 그날 건 주문표와 실제 체결."""
    date: str
    close: float
    high: Optional[float] = None
    sheet: list[OrderLine] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)


# ---- 사다리 / 큰수 ------------------------------------------------------


def ladder(budget: float, shares_above: int, below_price: float, count: int) -> list[OrderLine]:
    """사다리 LOC 1주 주문.

    가격 = 1회 매수금 ÷ (위 주문 누적 수량 + k). 종가가 그 가격 이하이면
    위 주문과 합쳐 (N + k)주를 사도 1회 매수금을 넘지 않는다.
    위 주문 가격보다 낮은 가격만 건다.
    """
    lines: list[OrderLine] = []
    k = 1
    while len(lines) < count and k < 1000:
        p = floor_cents(budget / (shares_above + k))
        k += 1
        if p <= 0:
            break
        if p >= below_price:
            continue
        lines.append(OrderLine("buy", "LOC", LADDER, p, 1))
    return lines


def apply_big_number(lines: list[OrderLine], prev_close: float, big_pct: float,
                     broker_limit: float = 0.20) -> list[OrderLine]:
    """증권사 가격 제한(약 ±20%) 대응.

    가장 높은 매수 가격이 전일 종가 × (1 + broker_limit)를 넘으면,
    전일 종가 × (1 + big_pct) 이상인 매수 줄을 그 가격 한 줄로 합친다.
    아래쪽 사다리는 그대로 둔다. 매도는 너무 멀면 거부될 수 있다는 표시만 단다.
    """
    buys = [l for l in lines if l.side == "buy" and l.order_type == "LOC"]
    others = [l for l in lines if not (l.side == "buy" and l.order_type == "LOC")]
    for l in others:
        if l.side == "sell" and l.price is not None and l.price > prev_close * (1 + broker_limit):
            l.note = (l.note + " 증권사가 거부하면 걸지 않아도 됨").strip()
    if not buys or max(l.price for l in buys) <= prev_close * (1 + broker_limit):
        return lines
    cap = round_cents(prev_close * (1 + big_pct))
    merged_qty = sum(l.qty for l in buys if l.price >= cap)
    rest = [l for l in buys if l.price < cap]
    out = []
    if merged_qty:
        out.append(OrderLine("buy", "LOC", BIG, cap, merged_qty, "큰수: 위 주문 합산"))
    out.extend(rest)
    return out + others


# ---- 자동 체결 판정 -----------------------------------------------------


def judge(lines: list[OrderLine], close: float, high: Optional[float] = None) -> list[Fill]:
    """주문표와 그날 종가·고가로 체결을 판정한다.

    LOC 매수: 종가 ≤ 지정가 → 종가 체결 / LOC 매도: 종가 ≥ 지정가 → 종가 체결
    MOC: 종가 체결 / 지정가 매도: 고가 ≥ 지정가 → 지정가 체결
    """
    fills: list[Fill] = []
    for l in lines:
        if l.qty <= 0:
            continue
        if l.order_type == "MOC":
            fills.append(Fill(l.role, l.side, close, l.qty))
        elif l.order_type == "LOC":
            if l.side == "buy" and close <= l.price:
                fills.append(Fill(l.role, l.side, close, l.qty))
            elif l.side == "sell" and close >= l.price:
                fills.append(Fill(l.role, l.side, close, l.qty))
        elif l.order_type == "LIMIT" and l.side == "sell":
            h = high if high is not None else close
            if h >= l.price:
                fills.append(Fill(l.role, l.side, l.price, l.qty))
    # 매도 수량이 보유를 넘지 않게 하는 처리는 엔진(apply_day)에서 한다.
    return fills
