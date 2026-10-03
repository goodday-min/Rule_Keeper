"""전략·주문표·VR·백테스트."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_repo, require_key
from ..repo.base import VR_SNAPSHOTS
from ..schemas import BacktestIn, ConfirmIn, RebalanceIn, StrategyIn, StrategyUpdate
from ..services import strategies as svc

router = APIRouter(prefix="/api", tags=["strategies (전략·주문표)"])


@router.get("/strategies", summary="전략 목록 + 한 줄 상태")
def list_strategies(include_ended: bool = False, repo=Depends(get_repo)):
    return svc.list_strategies(repo, include_ended)


@router.post("/strategies", status_code=201, summary="전략 등록", dependencies=[Depends(require_key)])
def create_strategy(body: StrategyIn, repo=Depends(get_repo)):
    """같은 종목·같은 계좌의 실전 전략이 있으면 응답의 warnings에 경고를 담는다."""
    return svc.create_strategy(repo, body.to_doc())


@router.put("/strategies/{strategy_id}", summary="전략 설정 수정", dependencies=[Depends(require_key)])
def update_strategy(strategy_id: str, body: StrategyUpdate, repo=Depends(get_repo)):
    return svc.update_strategy(repo, strategy_id, body.model_dump(exclude_none=True))


@router.delete("/strategies/{strategy_id}", summary="전략 종료 (기록은 보존)", dependencies=[Depends(require_key)])
def end_strategy(strategy_id: str, repo=Depends(get_repo)):
    return svc.end_strategy(repo, strategy_id)


@router.get("/strategies/{strategy_id}/status", summary="전략 현재 상태")
def status(strategy_id: str, repo=Depends(get_repo)):
    return svc.status(repo, strategy_id)


@router.get("/orders/today", summary="전체 전략의 확정 대기 주문표 + 오늘 주문표")
def orders_today(repo=Depends(get_repo)):
    return svc.orders_today(repo)


@router.get("/strategies/{strategy_id}/orders/next", summary="다음 거래일 주문표")
def next_orders(strategy_id: str, repo=Depends(get_repo)):
    return svc.build_next_sheet(repo, strategy_id)


@router.get("/strategies/{strategy_id}/orders/{date}", summary="특정 날 주문표 + 자동 체결 판정")
def judge(strategy_id: str, date: str, repo=Depends(get_repo)):
    return svc.judge_sheet(repo, strategy_id, date)


@router.post("/strategies/{strategy_id}/orders/{date}/confirm", summary="체결 확정 → data에 기록",
             dependencies=[Depends(require_key)])
def confirm(strategy_id: str, date: str, body: ConfirmIn, repo=Depends(get_repo)):
    return svc.confirm_sheet(repo, strategy_id, date, [o.model_dump() for o in body.overrides])


@router.get("/strategies/{strategy_id}/cycles", summary="무한매수법 사이클 이력")
def cycles(strategy_id: str, repo=Depends(get_repo)):
    st = svc.status(repo, strategy_id)
    return st.get("cycles", [])


@router.get("/strategies/{strategy_id}/vr-snapshots", summary="VR 갱신 이력")
def vr_snapshots(strategy_id: str, repo=Depends(get_repo)):
    return sorted(repo.where(VR_SNAPSHOTS, "strategy_id", strategy_id), key=lambda x: x["date"])


@router.post("/strategies/{strategy_id}/vr/rebalance", summary="VR V 갱신 (dry_run=true면 미리보기)",
             dependencies=[Depends(require_key)])
def vr_rebalance(strategy_id: str, body: RebalanceIn, repo=Depends(get_repo)):
    return svc.vr_rebalance(repo, strategy_id, body.cycle_amount, body.dry_run)


@router.post("/strategies/{strategy_id}/backtest", summary="시뮬레이션 전략 백테스트 → 가상 체결 생성",
             dependencies=[Depends(require_key)])
def backtest(strategy_id: str, body: BacktestIn, repo=Depends(get_repo)):
    return svc.backtest(repo, strategy_id, body.start_date)
