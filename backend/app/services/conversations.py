"""대화 기록 (conversations 컬렉션).

목록 조회는 messages를 빼고 돌려주고, 불러오기는 GET /api/conversations/{id}로 전체를 준다 (요구사항 A안).
"""
from __future__ import annotations

from typing import Optional

from ..repo.base import CONVERSATIONS, Repo
from .common import NotFound, now_iso


def title_from(text: str) -> str:
    t = " ".join(text.split())
    return t[:30] + ("…" if len(t) > 30 else "")


def create(repo: Repo, messages: list[dict], title: Optional[str] = None,
           strategy_id: Optional[str] = None) -> dict:
    first_user = next((m["content"] for m in messages if m.get("role") == "user"), "새 대화")
    now = now_iso()
    msgs = [{**m, "created_at": m.get("created_at") or now} for m in messages]
    return repo.add(CONVERSATIONS, {"title": title or title_from(first_user), "strategy_id": strategy_id,
                                    "messages": msgs, "created_at": now, "updated_at": now})


def list_all(repo: Repo) -> list[dict]:
    out = []
    for c in repo.where(CONVERSATIONS):
        out.append({"id": c["id"], "title": c.get("title"), "strategy_id": c.get("strategy_id"),
                    "message_count": len(c.get("messages", [])), "created_at": c.get("created_at"),
                    "updated_at": c.get("updated_at")})
    return sorted(out, key=lambda c: c.get("updated_at") or "", reverse=True)


def get(repo: Repo, cid: str) -> dict:
    c = repo.get(CONVERSATIONS, (cid or "").strip())
    if not c:
        raise NotFound("대화를 찾을 수 없습니다")
    return c


def append(repo: Repo, cid: str, new_messages: list[dict], strategy_id: Optional[str] = None) -> dict:
    c = get(repo, cid)
    cid = c["id"]
    now = now_iso()
    msgs = c.get("messages", []) + [{**m, "created_at": m.get("created_at") or now} for m in new_messages]
    fields = {"messages": msgs, "updated_at": now}
    if strategy_id is not None:
        fields["strategy_id"] = strategy_id
    return repo.update(CONVERSATIONS, cid, fields)


def delete(repo: Repo, cid: str) -> bool:
    if not repo.delete(CONVERSATIONS, (cid or "").strip()):
        raise NotFound("대화를 찾을 수 없습니다")
    return True
