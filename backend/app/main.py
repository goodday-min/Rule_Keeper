"""Rule_Keeper API.

실행: uvicorn app.main:app --reload   (backend 폴더에서)
문서: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import copy
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .routers import chat, conversations, data, prices, strategies
from .services.common import Conflict, NotFound


def demo_seed():
    """메모리 모드는 서버를 켤 때마다 비어 있으므로 시세와 시뮬레이션 전략 2개를 자동으로 채운다."""
    from scripts.seed import DEMO
    from .repo import get_repo
    from .services import prices as price_svc
    from .services import strategies as strat_svc

    repo = get_repo()
    print("[메모리 모드] 시세와 데모 전략을 준비하는 중입니다 (10초 안팎)...")
    print("[메모리 모드] 시세:", price_svc.sync(repo, settings.tickers, settings.price_start))
    for body in DEMO:
        s = strat_svc.create_strategy(repo, body)
        res = strat_svc.backtest(repo, s["id"], settings.price_start)
        print(f"[메모리 모드] {s['name']}: 가상 체결 {res['fills_created']}건")
    print("[메모리 모드] 준비 완료. 브라우저에서 http://127.0.0.1:8000/docs 를 여세요.")


@asynccontextmanager
async def lifespan(_app):
    if settings.storage == "memory" and os.getenv("DEMO_SEED", "1") == "1":
        try:
            demo_seed()
        except Exception as e:   # 시세를 못 받아도 서버는 켠다
            print("[메모리 모드] 데모 데이터 준비 실패:", e)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Rule_Keeper API",
    version="0.1.0",
    description="분할매수 기록장: 라오어 무한매수법(V2.2·V4.0)과 VR 5.0 운용 비서. "
                "데이터를 바꾸는 요청은 `X-API-Key` 헤더가 필요합니다. 투자 권유가 아닌 규칙 계산 보조 도구입니다.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (data.router, conversations.router, chat.router, strategies.router, prices.router):
    app.include_router(r)


@app.exception_handler(NotFound)
def _not_found(_: Request, e: NotFound):
    return JSONResponse(status_code=404, content={"detail": str(e)})


@app.exception_handler(Conflict)
def _conflict(_: Request, e: Conflict):
    return JSONResponse(status_code=409, content={"detail": str(e)})


@app.exception_handler(ValueError)
def _value_error(_: Request, e: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(e)})


@app.get("/health", tags=["system"], summary="서버 상태 (프론트 콜드스타트 확인용)")
def health():
    return {"status": "ok", "storage": settings.storage}


@app.get("/", include_in_schema=False)
def root():
    return {"name": "Rule_Keeper API", "docs": "/docs"}


# ---- GPT Actions용 OpenAPI (조회 API만) ---------------------------------------

ACTION_OPERATIONS = {
    ("/api/data/summary", "get"): "getSummary",
    ("/api/strategies", "get"): "listStrategies",
    ("/api/strategies/{strategy_id}/status", "get"): "getStrategyStatus",
    ("/api/orders/today", "get"): "getTodayOrders",
    ("/api/data", "get"): "listFills",
    ("/api/data/statistics", "get"): "getStatistics",
    ("/api/conversations", "get"): "listConversations",
}


@app.get("/api/actions/openapi.json", include_in_schema=False)
def actions_openapi():
    """커스텀 GPT의 Actions에 붙여 넣을 스키마. 조회 API만 담고 API 키 인증을 건다."""
    spec = copy.deepcopy(app.openapi())
    spec["openapi"] = "3.1.0"
    paths = {}
    for (path, method), op_id in ACTION_OPERATIONS.items():
        op = spec["paths"].get(path, {}).get(method)
        if op:
            op = {**op, "operationId": op_id, "security": [{"ApiKeyAuth": []}]}
            paths.setdefault(path, {})[method] = op
    spec["paths"] = paths
    spec.setdefault("components", {})["securitySchemes"] = {
        "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}
    spec["servers"] = [{"url": os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8000")}]
    return spec
