"""Firestore 저장소.

서비스 계정 키는 환경 변수로만 받는다.
- FIREBASE_CREDENTIALS: 키 JSON 문자열 그대로 또는 base64 인코딩
- FIREBASE_CREDENTIALS_PATH: 키 파일 경로 (로컬 개발용)
"""
from __future__ import annotations

import base64
import copy
import json
import time
import uuid
from typing import Iterable, Optional

from ..config import settings
from .base import CONVERSATIONS, DATA, ORDER_SHEETS, PRICES, STRATEGIES, VR_SNAPSHOTS

# 상태는 매번 체결을 재생해 계산하므로 목록 조회(where)가 많다. Firestore 무료 한도(읽기 하루 5만 건)를
# 지키려고 컬렉션 전체를 한 번 읽어 서버 메모리에 보관하고, 조회·필터는 메모리에서 처리한다.
# 이 서버를 거치는 쓰기는 Firestore와 캐시를 함께 고치므로(write-through) 쓰기 뒤에 다시 읽지 않는다.
# Firebase 콘솔에서 직접 고친 내용은 CACHE_TTL초 안에 반영된다.
CACHED_COLLECTIONS = {PRICES, STRATEGIES, DATA, ORDER_SHEETS, VR_SNAPSHOTS, CONVERSATIONS}
CACHE_TTL = 6 * 3600


def _load_credentials():
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return
    raw = settings.firebase_credentials.strip()
    if raw:
        if not raw.startswith("{"):
            raw = base64.b64decode(raw).decode("utf-8")
        cred = credentials.Certificate(json.loads(raw))
    elif settings.firebase_credentials_path:
        cred = credentials.Certificate(settings.firebase_credentials_path)
    else:
        raise RuntimeError("FIREBASE_CREDENTIALS 또는 FIREBASE_CREDENTIALS_PATH 환경 변수가 필요합니다")
    firebase_admin.initialize_app(cred)


class FirestoreRepo:
    def __init__(self, db=None):
        if db is None:
            _load_credentials()
            from firebase_admin import firestore
            db = firestore.client()
        self.db = db
        self._cache: dict[str, tuple[float, dict[str, dict]]] = {}   # 컬렉션 -> (읽은 시각, {id: 문서})
        self.reads = 0                                                # 시험·점검용 읽기 횟수

    # --- 캐시 -------------------------------------------------------------
    def _docs(self, col) -> Optional[dict[str, dict]]:
        """캐시 대상 컬렉션이면 전체 문서 {id: doc}를 돌려준다 (없거나 오래되면 한 번 전체 읽기)."""
        if col not in CACHED_COLLECTIONS:
            return None
        hit = self._cache.get(col)
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return hit[1]
        docs = {}
        for snap in self.db.collection(col).stream():
            self.reads += 1
            docs[snap.id] = self._with_id(snap)
        self._cache[col] = (time.monotonic(), docs)
        return docs

    def _cached(self, col) -> Optional[dict[str, dict]]:
        """이미 캐시에 있으면 그 dict (쓰기 반영용). 없으면 None (다음 조회 때 읽으면 됨)."""
        hit = self._cache.get(col)
        return hit[1] if hit and time.monotonic() - hit[0] < CACHE_TTL else None

    def invalidate(self, col=None):
        if col is None:
            self._cache.clear()
        else:
            self._cache.pop(col, None)

    def _with_id(self, snap) -> dict:
        d = snap.to_dict() or {}
        d["id"] = snap.id
        return d

    # --- 읽기 -------------------------------------------------------------
    def get(self, col, doc_id) -> Optional[dict]:
        docs = self._docs(col)
        if docs is not None:
            d = docs.get(doc_id)
            return copy.deepcopy(d) if d else None
        snap = self.db.collection(col).document(doc_id).get()
        self.reads += 1
        return self._with_id(snap) if snap.exists else None

    def where(self, col, field=None, value=None):
        docs = self._docs(col)
        if docs is None:
            from google.cloud.firestore_v1.base_query import FieldFilter
            q = self.db.collection(col)
            if field is not None:
                q = q.where(filter=FieldFilter(field, "==", value))
            out = [self._with_id(s) for s in q.stream()]
            self.reads += len(out)
            return out
        out = [d for _, d in sorted(docs.items()) if field is None or d.get(field) == value]
        return copy.deepcopy(out)

    # --- 쓰기 (Firestore + 캐시 함께) ---------------------------------------
    def put(self, col, doc_id, doc):
        body = {k: v for k, v in doc.items() if k != "id"}
        self.db.collection(col).document(doc_id).set(body)
        cached = self._cached(col)
        if cached is not None:
            cached[doc_id] = copy.deepcopy({**body, "id": doc_id})
        return {**body, "id": doc_id}

    def add(self, col, doc):
        return self.put(col, uuid.uuid4().hex[:20], doc)

    def update(self, col, doc_id, fields):
        cur = self.get(col, doc_id)
        if cur is None:
            return None
        body = {k: v for k, v in fields.items() if k != "id"}
        self.db.collection(col).document(doc_id).update(body)
        cur.update(body)
        cached = self._cached(col)
        if cached is not None:
            cached[doc_id] = copy.deepcopy(cur)
        return cur

    def delete(self, col, doc_id):
        if self.get(col, doc_id) is None:
            return False
        self.db.collection(col).document(doc_id).delete()
        cached = self._cached(col)
        if cached is not None:
            cached.pop(doc_id, None)
        return True

    def put_many(self, col, docs: Iterable[tuple[str, dict]]):
        cached = self._cached(col)
        n, batch = 0, self.db.batch()
        for doc_id, doc in docs:
            body = {k: v for k, v in doc.items() if k != "id"}
            batch.set(self.db.collection(col).document(doc_id), body)
            if cached is not None:
                cached[doc_id] = copy.deepcopy({**body, "id": doc_id})
            n += 1
            if n % 400 == 0:           # Firestore 배치 한도 500
                batch.commit()
                batch = self.db.batch()
        batch.commit()
        return n

    def delete_where(self, col, field, value):
        docs = self.where(col, field, value)
        cached = self._cached(col)
        batch, n = self.db.batch(), 0
        for d in docs:
            batch.delete(self.db.collection(col).document(d["id"]))
            if cached is not None:
                cached.pop(d["id"], None)
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()
        return n
