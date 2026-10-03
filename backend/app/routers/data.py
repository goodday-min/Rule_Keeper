"""과제 필수: 체결 기록 CRUD 4개 + summary. 보너스: statistics, export."""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Response

from ..config import settings
from ..deps import get_repo, require_key
from ..schemas import DataIn, DataUpdate
from ..services import data as data_svc
from ..services import summary as sum_svc

router = APIRouter(prefix="/api/data", tags=["data (체결 기록)"])


@router.get("", summary="체결 기록 목록")
def list_data(strategy_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
              source: Optional[Literal["auto", "manual", "backtest"]] = None,
              limit: int = Query(500, ge=1, le=5000), repo=Depends(get_repo)):
    return data_svc.list_data(repo, strategy_id, date_from, date_to, source, limit)


@router.post("", status_code=201, summary="체결 기록 추가", dependencies=[Depends(require_key)])
def create_data(body: DataIn, repo=Depends(get_repo)):
    return data_svc.create_data(repo, body.model_dump())


@router.get("/summary", summary="데이터 요약 (프롬프트 주입용)")
def summary(strategy_id: Optional[str] = None, repo=Depends(get_repo)):
    """종목별 기간·개수·평균·최대·최소·최근 추세 + 전략별 한 줄 상태.
    strategy_id를 주면 그 전략의 상세와 오늘 주문표를 포함한다. `text`가 시스템 프롬프트에 들어가는 문자열이다."""
    return sum_svc.build_summary(repo, settings.tickers, strategy_id)


@router.get("/statistics", summary="추가 지표 (변동성, 최대 낙폭, 전략별 누적 수익)")
def statistics(repo=Depends(get_repo)):
    return sum_svc.statistics(repo, settings.tickers)


@router.get("/export", summary="체결 기록 내보내기 (CSV 또는 JSON)")
def export(format: Literal["csv", "json"] = "csv", strategy_id: Optional[str] = None,
           date_from: Optional[str] = None, date_to: Optional[str] = None, repo=Depends(get_repo)):
    docs = data_svc.list_data(repo, strategy_id, date_from, date_to, limit=100000)
    body, ctype = data_svc.export_data(docs, format)
    return Response(content=body, media_type=ctype,
                    headers={"Content-Disposition": f'attachment; filename="rule_keeper_data.{format}"'})


@router.put("/{data_id}", summary="체결 기록 수정", dependencies=[Depends(require_key)])
def update_data(data_id: str, body: DataUpdate, repo=Depends(get_repo)):
    return data_svc.update_data(repo, data_id, body.model_dump(exclude_none=True))


@router.delete("/{data_id}", summary="체결 기록 삭제", dependencies=[Depends(require_key)])
def delete_data(data_id: str, repo=Depends(get_repo)):
    return {"deleted": data_svc.delete_data(repo, data_id)["id"]}
