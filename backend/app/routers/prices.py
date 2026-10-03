from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends

from ..config import settings
from ..deps import get_repo, require_key
from ..services import prices as price_svc
from ..services.common import price_rows

router = APIRouter(prefix="/api/prices", tags=["prices (시세)"])


@router.post("/sync", summary="빠진 날짜의 일별 시세를 채운다 (yfinance)", dependencies=[Depends(require_key)])
def sync(repo=Depends(get_repo)):
    return price_svc.sync(repo, settings.tickers, settings.price_start)


@router.get("", summary="종목별 일별 시세")
def list_prices(ticker: Literal["TQQQ", "SOXL"] = "TQQQ", date_from: Optional[str] = None,
                date_to: Optional[str] = None, repo=Depends(get_repo)):
    rows = price_rows(repo, ticker, date_from)
    return [r for r in rows if not date_to or r["date"] <= date_to]
