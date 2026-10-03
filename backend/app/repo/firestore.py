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
# 지키려고 조회 결과를 서버 메모리에 캐시한다. 이 서버를 거치는 쓰기는 그 컬렉션 캐시를 바로 비우고,
# Firebase 콘솔에서 직접 고친 내용은 CACHE_TTL초 안에 반영된다.
CACHED_COLLECTIONS = {PRICES, STRATEGIES, DATA, ORDER_SHEETS, VR_SNAPSHOTS, CONVERSATIONS}
CACHE_TTL = 600


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
    def __init__(self):
        _load_credentials()
        from firebase_admin import firestore
        self.db = firestore.client()
        self._cache: dict[tuple, tuple[float, list[dict]]] = {}

    def _invalidate(self, col):
        if col in CACHED_COLLECTIONS:
            self._cache = {k: v for k, v in self._cache.items() if k[0] != col}

    def _with_id(self, snap) -> dict:
        d = snap.to_dict() or {}
        d["id"] = snap.id
        return d

    def get(self, col, doc_id) -> Optional[dict]:
        snap = self.db.collection(col).document(doc_id).get()
        return self._with_id(snap) if snap.exists else None

    def put(self, col, doc_id, doc):
        self._invalidate(col)
        body = {k: v for k, v in doc.items() if k != "id"}
        self.db.collection(col).document(doc_id).set(body)
        return {**body, "id": doc_id}

    def add(self, col, doc):
        return self.put(col, uuid.uuid4().hex[:20], doc)

    def update(self, col, doc_id, fields):
        self._invalidate(col)
        ref = self.db.collection(col).document(doc_id)
        if not ref.get().exists:
            return None
        ref.update({k: v for k, v in fields.items() if k != "id"})
        return self.get(col, doc_id)

    def delete(self, col, doc_id):
        self._invalidate(col)
        ref = self.db.collection(col).document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True

    def where(self, col, field=None, value=None):
        from google.cloud.firestore_v1.base_query import FieldFilter

        key = (col, field, value)
        hit = self._cache.get(key) if col in CACHED_COLLECTIONS else None
        if hit and time.monotonic() - hit[0] < CACHE_TTL:
            return copy.deepcopy(hit[1])
        q = self.db.collection(col)
        if field is not None:
            q = q.where(filter=FieldFilter(field, "==", value))
        docs = [self._with_id(s) for s in q.stream()]
        if col in CACHED_COLLECTIONS:
            self._cache[key] = (time.monotonic(), copy.deepcopy(docs))
        return docs

    def put_many(self, col, docs: Iterable[tuple[str, dict]]):
        self._invalidate(col)
        n, batch = 0, self.db.batch()
        for doc_id, doc in docs:
            batch.set(self.db.collection(col).document(doc_id), {k: v for k, v in doc.items() if k != "id"})
            n += 1
            if n % 400 == 0:           # Firestore 배치 한도 500
                batch.commit()
                batch = self.db.batch()
        batch.commit()
        return n

    def delete_where(self, col, field, value):
        self._invalidate(col)
        docs = self.where(col, field, value)
        batch, n = self.db.batch(), 0
        for d in docs:
            batch.delete(self.db.collection(col).document(d["id"]))
            n += 1
            if n % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()
        self._invalidate(col)          # 위의 where가 캐시를 다시 채웠으므로 한 번 더 비운다
        return n
