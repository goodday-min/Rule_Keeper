"""메모리 저장소. 테스트와 Firebase 없이 화면을 먼저 확인할 때 쓴다 (STORAGE=memory)."""
from __future__ import annotations

import copy
import uuid
from typing import Iterable, Optional


class MemoryRepo:
    def __init__(self):
        self._db: dict[str, dict[str, dict]] = {}

    def _col(self, col: str) -> dict[str, dict]:
        return self._db.setdefault(col, {})

    def get(self, col, doc_id):
        d = self._col(col).get(doc_id)
        return copy.deepcopy(d) if d is not None else None

    def put(self, col, doc_id, doc):
        d = {**copy.deepcopy(doc), "id": doc_id}
        self._col(col)[doc_id] = d
        return copy.deepcopy(d)

    def add(self, col, doc):
        return self.put(col, uuid.uuid4().hex[:20], doc)

    def update(self, col, doc_id, fields):
        cur = self._col(col).get(doc_id)
        if cur is None:
            return None
        cur.update(copy.deepcopy(fields))
        return copy.deepcopy(cur)

    def delete(self, col, doc_id):
        return self._col(col).pop(doc_id, None) is not None

    def where(self, col, field=None, value=None):
        docs = self._col(col).values()
        if field is not None:
            docs = [d for d in docs if d.get(field) == value]
        return [copy.deepcopy(d) for d in docs]

    def put_many(self, col, docs: Iterable[tuple[str, dict]]):
        n = 0
        for doc_id, doc in docs:
            self.put(col, doc_id, doc)
            n += 1
        return n

    def delete_where(self, col, field, value):
        ids = [k for k, d in self._col(col).items() if d.get(field) == value]
        for k in ids:
            del self._col(col)[k]
        return len(ids)
