"""저장소 인터페이스.

Firestore 복합 색인이 필요 없도록 '필드 하나 같음' 조건으로만 조회하고,
날짜 범위·정렬은 파이썬에서 한다. (데이터가 수천 건 규모라 충분하다)
"""
from __future__ import annotations

from typing import Iterable, Optional, Protocol

# 컬렉션 이름
STRATEGIES = "strategies"
DATA = "data"                    # 체결 기록 (과제 필수 컬렉션)
ORDER_SHEETS = "order_sheets"
VR_SNAPSHOTS = "vr_snapshots"
PRICES = "prices"
CONVERSATIONS = "conversations"  # 과제 필수 컬렉션


class Repo(Protocol):
    def get(self, col: str, doc_id: str) -> Optional[dict]: ...
    def put(self, col: str, doc_id: str, doc: dict) -> dict: ...
    def add(self, col: str, doc: dict) -> dict: ...
    def update(self, col: str, doc_id: str, fields: dict) -> Optional[dict]: ...
    def delete(self, col: str, doc_id: str) -> bool: ...
    def where(self, col: str, field: Optional[str] = None, value=None) -> list[dict]: ...
    def put_many(self, col: str, docs: Iterable[tuple[str, dict]]) -> int: ...
    def delete_where(self, col: str, field: str, value) -> int: ...
