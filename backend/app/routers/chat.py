"""과제 필수: AI 채팅 (요약 조회 → 시스템 프롬프트 삽입 → GPT 호출 → 대화 자동 저장)."""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..deps import get_repo, require_key
from ..schemas import ChatIn, ChatOut
from ..services import chat as chat_svc

router = APIRouter(prefix="/api", tags=["chat"])


@lru_cache
def get_openai_client():
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY가 설정되지 않았습니다")
    return chat_svc.make_openai_client(settings.openai_api_key, settings.openai_base_url)


@router.post("/chat", response_model=ChatOut, summary="AI 채팅", dependencies=[Depends(require_key)])
def chat(body: ChatIn, repo=Depends(get_repo)):
    """conversation_id가 없으면 새 대화를 만들고, 있으면 이어서 저장한다.
    strategy_id를 주면 그 전략의 상세와 오늘 주문표가 프롬프트에 들어간다."""
    try:
        client = get_openai_client()
        return chat_svc.chat(repo, client, settings.openai_model, settings.tickers, body.message,
                             body.conversation_id, body.strategy_id)
    except HTTPException:
        raise
    except Exception as e:
        if e.__class__.__module__.startswith("openai"):
            raise HTTPException(status_code=502, detail=f"GPT 응답 실패: {e.__class__.__name__}")
        raise
