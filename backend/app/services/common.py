from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..repo.base import PRICES, STRATEGIES, Repo


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def next_trading_day(d: str) -> str:
    """다음 평일. 미국 휴장일은 반영하지 않는다 (휴장일 주문표는 다음 날 다시 만든다)."""
    x = date.fromisoformat(d) + timedelta(days=1)
    while x.weekday() >= 5:
        x += timedelta(days=1)
    return x.isoformat()


def get_strategy(repo: Repo, sid: str) -> dict:
    s = repo.get(STRATEGIES, sid)
    if not s:
        raise NotFound(f"전략을 찾을 수 없습니다: {sid}")
    return s


def price_rows(repo: Repo, ticker: str, start: str | None = None) -> list[dict]:
    rows = [r for r in repo.where(PRICES, "ticker", ticker) if not start or r["date"] >= start]
    return sorted(rows, key=lambda r: r["date"])


def price_doc_id(ticker: str, d: str) -> str:
    return f"{ticker}_{d}"
