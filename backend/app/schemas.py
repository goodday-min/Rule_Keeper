"""요청 검증용 Pydantic 모델."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

DATE = r"^\d{4}-\d{2}-\d{2}$"


# ---- 체결 기록 (data) --------------------------------------------------------

class DataIn(BaseModel):
    """과제의 (date, value, memo)에 체결 정보를 더한 형태. value = 체결 단가."""
    model_config = {"json_schema_extra": {"examples": [{
        "date": "2026-10-01", "value": 76.40, "memo": "별 LOC 체결", "strategy_id": "<GET /api/strategies의 id>",
        "side": "buy", "qty": 3, "role": "star_buy", "order_type": "LOC"}]}}
    date: str = Field(pattern=DATE, examples=["2026-10-01"])
    value: float = Field(gt=0, description="체결 단가(달러)", examples=[76.40])
    memo: str = Field("", max_length=200)
    strategy_id: str
    side: Literal["buy", "sell"]
    qty: int = Field(ge=1, description="체결 수량(주)")
    role: str = Field(description="주문 역할: big, star_buy, avg_buy, ladder, quarter_sell, limit_sell, "
                                   "quarter_stop_moc, quarter_stop_buy, quarter_stop_sell, reverse_moc, "
                                   "reverse_sell, reverse_buy, vr_buy, vr_sell")
    order_type: Literal["LOC", "MOC", "LIMIT", ""] = ""


class DataUpdate(BaseModel):
    """수정은 날짜·단가·수량·메모만. 전략·역할을 바꾸려면 삭제 후 다시 추가한다."""
    date: Optional[str] = Field(None, pattern=DATE)
    value: Optional[float] = Field(None, gt=0)
    qty: Optional[int] = Field(None, ge=1)
    memo: Optional[str] = Field(None, max_length=200)


# ---- 전략 ------------------------------------------------------------------

class StrategyIn(BaseModel):
    type: Literal["infinite", "vr"]
    ticker: Literal["TQQQ", "SOXL"]
    name: Optional[str] = None
    account_memo: str = Field("", max_length=50, description="같은 종목 전략은 계좌를 분리해야 한다")
    is_simulation: bool = False
    start_date: Optional[str] = Field(None, pattern=DATE)
    # 무한매수법
    rule_version: Optional[Literal["v2.2", "v4.0"]] = None
    splits: int = 40
    principal: Optional[float] = Field(None, gt=0)
    compounding: bool = False
    big_pct: Optional[float] = Field(None, ge=0.05, le=0.20)
    ladder_count: int = Field(8, ge=0, le=20)
    # VR
    vr_type: Optional[Literal["installment", "lump_sum", "withdrawal"]] = None
    start_v: Optional[float] = Field(None, gt=0)
    start_pool: Optional[float] = Field(None, ge=0)
    g: float = Field(10, gt=0)
    band: float = Field(0.15, gt=0, lt=0.5)
    cycle_amount: float = Field(0, ge=0)
    initial_qty: int = Field(0, ge=0)

    @model_validator(mode="after")
    def check_required(self):
        if self.type == "infinite":
            if not self.rule_version or not self.principal:
                raise ValueError("무한매수법은 rule_version과 principal이 필요합니다")
            if self.rule_version == "v4.0" and self.splits not in (20, 40):
                raise ValueError("V4.0은 20분할 또는 40분할만 지원합니다")
            if self.rule_version == "v2.2" and self.splits != 40:
                raise ValueError("V2.2는 40분할을 사용합니다")
        else:
            if not self.vr_type or self.start_v is None or self.start_pool is None:
                raise ValueError("VR은 vr_type, start_v, start_pool이 필요합니다")
        return self

    def to_doc(self) -> dict:
        d = self.model_dump(exclude_none=True)
        keep = ({"rule_version", "splits", "principal", "compounding", "big_pct", "ladder_count"}
                if self.type == "infinite" else
                {"vr_type", "start_v", "start_pool", "g", "band", "cycle_amount", "initial_qty"})
        common = {"type", "ticker", "name", "account_memo", "is_simulation", "start_date"}
        return {k: v for k, v in d.items() if k in keep | common}


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    account_memo: Optional[str] = Field(None, max_length=50)
    compounding: Optional[bool] = None
    big_pct: Optional[float] = Field(None, ge=0.05, le=0.20)
    ladder_count: Optional[int] = Field(None, ge=0, le=20)
    g: Optional[float] = Field(None, gt=0)
    band: Optional[float] = Field(None, gt=0, lt=0.5)
    cycle_amount: Optional[float] = Field(None, ge=0)


class LineOverride(BaseModel):
    line_id: int
    filled: bool
    price: Optional[float] = Field(None, gt=0)
    qty: Optional[int] = Field(None, ge=0)


class ConfirmIn(BaseModel):
    overrides: list[LineOverride] = []


class RebalanceIn(BaseModel):
    cycle_amount: Optional[float] = Field(None, ge=0, description="이번 사이클 적립금 또는 인출금")
    dry_run: bool = False


class BacktestIn(BaseModel):
    start_date: str = Field(pattern=DATE)


# ---- 대화 / 채팅 -------------------------------------------------------------

class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ConversationIn(BaseModel):
    title: Optional[str] = Field(None, max_length=60)
    strategy_id: Optional[str] = None
    messages: list[MessageIn] = Field(min_length=1)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 때만. 비우면 새 대화")
    strategy_id: Optional[str] = Field(None, description="특정 전략을 선택할 때만. 비우면 전체")

    model_config = {"json_schema_extra": {"examples": [{"message": "오늘 뭐 걸어야 해?"}]}}


class ToolUse(BaseModel):
    name: str
    args: dict
    ok: bool


class ChatOut(BaseModel):
    reply: str
    conversation_id: str
    tools_used: list[ToolUse]
