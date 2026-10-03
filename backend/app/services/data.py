"""체결 기록(data 컬렉션) CRUD와 내보내기. 과제의 (date, value, memo)에 체결 정보 필드를 더했다."""
from __future__ import annotations

import csv
import io
import json
from typing import Optional

from ..engine.common import BUY_ROLES, SELL_ROLES
from ..repo.base import DATA, Repo
from .common import NotFound, get_strategy, now_iso

EDITABLE = {"date", "value", "qty", "memo"}


def list_data(repo: Repo, strategy_id: Optional[str] = None, date_from: Optional[str] = None,
              date_to: Optional[str] = None, source: Optional[str] = None, limit: int = 500) -> list[dict]:
    docs = repo.where(DATA, "strategy_id", strategy_id) if strategy_id else repo.where(DATA)
    docs = [d for d in docs
            if (not date_from or d["date"] >= date_from) and (not date_to or d["date"] <= date_to)
            and (not source or d.get("source") == source)]
    docs.sort(key=lambda d: (d["date"], d.get("created_at", "")), reverse=True)
    return docs[:limit]


def create_data(repo: Repo, body: dict) -> dict:
    get_strategy(repo, body["strategy_id"])
    role, side = body["role"], body["side"]
    if (side == "buy" and role not in BUY_ROLES) or (side == "sell" and role not in SELL_ROLES):
        raise ValueError(f"역할 {role}은(는) {side}에 쓸 수 없습니다")
    doc = {**body, "source": body.get("source", "manual"), "created_at": now_iso()}
    doc.setdefault("memo", "")
    doc.setdefault("order_type", "")
    return repo.add(DATA, doc)


def update_data(repo: Repo, data_id: str, fields: dict) -> dict:
    fields = {k: v for k, v in fields.items() if k in EDITABLE and v is not None}
    doc = repo.update(DATA, data_id, {**fields, "updated_at": now_iso()})
    if not doc:
        raise NotFound("체결 기록을 찾을 수 없습니다")
    return doc


def delete_data(repo: Repo, data_id: str) -> dict:
    doc = repo.get(DATA, data_id)
    if not doc:
        raise NotFound("체결 기록을 찾을 수 없습니다")
    repo.delete(DATA, data_id)
    return doc


EXPORT_FIELDS = ["id", "date", "value", "qty", "memo", "strategy_id", "side", "role", "order_type", "source"]


def export_data(docs: list[dict], fmt: str) -> tuple[str, str]:
    if fmt == "json":
        return json.dumps(docs, ensure_ascii=False, indent=2), "application/json"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    w.writeheader()
    w.writerows(docs)
    return "﻿" + buf.getvalue(), "text/csv; charset=utf-8"     # 엑셀 한글 깨짐 방지 BOM
