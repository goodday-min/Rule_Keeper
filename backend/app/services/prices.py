"""시세 동기화.

- 마지막 저장일 며칠 전부터 다시 받아, 새 날짜는 추가하고 바뀐 값은 고친다.
- 미국장이 아직 끝나지 않은 날의 시세(장중 가격)는 저장하지 않는다. yfinance는 장중에도 오늘 날짜
  행을 현재가로 돌려주는데, 이걸 종가로 저장하면 주문표와 체결 판정이 틀어지기 때문이다.
  예전에 장중 가격이 저장돼 있었다면 다음 동기화 때 지운다.

provider(ticker, start_date) -> [{date, open, high, low, close}] 형태의 함수를 주입할 수 있다.
기본은 yfinance (요청 시에만 import).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional

from ..repo.base import PRICES, Repo
from .common import price_doc_id, price_rows

Provider = Callable[[str, str], list[dict]]

REFRESH_DAYS = 7               # 마지막 저장일 기준 며칠 전부터 다시 받아 확인할지
FINAL_AFTER = time(17, 0)      # 뉴욕 시간 17시 이후면 그날 종가를 확정으로 본다 (정규장 마감 16시)


def _ny_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:  # 시간대 정보가 없는 환경: 서머타임 기준(UTC-4)으로 근사
        return datetime.now(timezone(timedelta(hours=-4)))


def last_final_date(now: Optional[datetime] = None) -> str:
    """종가가 확정된 마지막 날짜(뉴욕 기준). 그 이후 날짜의 시세는 장중 가격이라 저장하지 않는다."""
    now = now or _ny_now()
    d = now.date() if now.time() >= FINAL_AFTER else now.date() - timedelta(days=1)
    return d.isoformat()


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


def sync(repo: Repo, tickers: list[str], default_start: str, provider: Optional[Provider] = None,
         now: Optional[datetime] = None) -> dict:
    provider = provider or yfinance_provider
    final = last_final_date(now)
    result = {}
    for t in tickers:
        stored = price_rows(repo, t)
        last = stored[-1]["date"] if stored else None
        start = ((date.fromisoformat(last) - timedelta(days=REFRESH_DAYS)).isoformat() if last else default_start)
        # 확정되지 않은 날(장중)의 행은 지운다
        removed = [r for r in stored if r["date"] > final]
        for r in removed:
            repo.delete(PRICES, price_doc_id(t, r["date"]))
        if start > final:
            result[t] = {"added": 0, "updated": 0, "removed": len(removed), "last_date": last}
            continue
        try:
            fetched = [r for r in provider(t, start) if r["date"] <= final]
        except Exception as e:
            result[t] = {"added": 0, "last_date": last, "error": f"시세를 가져오지 못했습니다: {e}"}
            continue
        old = {r["date"]: r for r in stored if r["date"] >= start and r["date"] <= final}
        keys = ("open", "high", "low", "close")
        changed = [r for r in fetched
                   if r["date"] not in old or any(abs(float(old[r["date"]].get(k, 0)) - float(r[k])) > 1e-6 for k in keys)]
        if changed:
            repo.put_many(PRICES, ((price_doc_id(t, r["date"]), {**r, "ticker": t}) for r in changed))
        kept_last = max([r["date"] for r in stored if r["date"] <= final] + [r["date"] for r in fetched], default=None)
        result[t] = {"added": sum(1 for r in changed if r["date"] not in old),
                     "updated": sum(1 for r in changed if r["date"] in old),
                     "removed": len(removed), "last_date": kept_last}
    return result
