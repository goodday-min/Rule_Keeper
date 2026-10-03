"""과제 필수: 대화 기록 저장·목록·불러오기·삭제.

목록(GET /api/conversations)은 messages를 빼고 message_count만 준다.
불러오기는 GET /api/conversations/{id}로 전체 messages를 받는다 (요구사항 A안).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_repo, require_key
from ..schemas import ConversationIn
from ..services import conversations as conv_svc

router = APIRouter(prefix="/api/conversations", tags=["conversations (대화 기록)"])


@router.post("", status_code=201, summary="대화 저장", dependencies=[Depends(require_key)])
def create(body: ConversationIn, repo=Depends(get_repo)):
    return conv_svc.create(repo, [m.model_dump() for m in body.messages], body.title, body.strategy_id)


@router.get("", summary="대화 목록 (messages 제외)")
def list_all(repo=Depends(get_repo)):
    return conv_svc.list_all(repo)


@router.get("/{conversation_id}", summary="대화 불러오기 (전체 messages)")
def get(conversation_id: str, repo=Depends(get_repo)):
    return conv_svc.get(repo, conversation_id)


@router.delete("/{conversation_id}", summary="대화 삭제", dependencies=[Depends(require_key)])
def delete(conversation_id: str, repo=Depends(get_repo)):
    conv_svc.delete(repo, conversation_id)
    return {"deleted": conversation_id}
