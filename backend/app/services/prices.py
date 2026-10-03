"""시세 동기화. 마지막 저장일 다음 날부터 빠진 날짜만 채운다.

provider(ticker, start_date) -> [{date, open, high, low, close}] 형태의 함수를 주입할 수 있다.
기본은 yfinance (요청 시에만 import).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable, Optional

from ..repo.base import PRICES, Repo
from .common import price_doc_id, price_rows

Provider = Callable[[str, str], list[dict]]


def yfinance_provider(ticker: str, start: str) -> list[dict]:
    import yfinance as yf

    df = yf.download(ticker, start=start, auto_adjust=False, progress=False, multi_level_index=False)
    out = []
    for idx, row in df.iterrows():
        out.append({"date": idx.date().isoformat(), "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4), "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4)})
    return out


def last_date(repo: Repo, ticker: str) -> Optional[str]:
    rows = price_rows(repo, ticker)
    return rows[-1]["date"] if rows else None


def sync(repo: Repo, tickers: list[str], default_start: str, provider: Optional[Provider] = None) -> dict:
    provider = provider or yfinance_provider
    result = {}
    for t in tickers:
        last = last_date(repo, t)
        start = (date.fromisoformat(last) + timedelta(days=1)).isoformat() if last else default_start
        if start > date.today().isoformat():
            result[t] = {"added": 0, "last_date": last}
            continue
        try:
            rows = [r for r in provider(t, start) if not last or r["date"] > last]
        except Exception as e:
            result[t] = {"added": 0, "last_date": last, "error": f"시세를 가져오지 못했습니다: {e}"}
            continue
        n = repo.put_many(PRICES, ((price_doc_id(t, r["date"]), {**r, "ticker": t}) for r in rows))
        result[t] = {"added": n, "last_date": rows[-1]["date"] if rows else last}
    return result
