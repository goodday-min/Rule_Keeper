"""FirestoreRepo 캐시 시험: 가짜 Firestore 클라이언트로 읽기 횟수와 쓰기 반영을 확인한다."""
import unittest

from app.repo.base import DATA, ORDER_SHEETS
from app.repo.firestore import FirestoreRepo


class _Snap:
    def __init__(self, doc_id, data):
        self.id, self._data = doc_id, data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _Doc:
    def __init__(self, store, col, doc_id):
        self.store, self.col, self.id = store, col, doc_id

    def get(self):
        self.store.reads += 1
        return _Snap(self.id, self.store.data.setdefault(self.col, {}).get(self.id))

    def set(self, body):
        self.store.data.setdefault(self.col, {})[self.id] = dict(body)

    def update(self, body):
        self.store.data[self.col][self.id].update(body)

    def delete(self):
        self.store.data.get(self.col, {}).pop(self.id, None)


class _Col:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def document(self, doc_id):
        return _Doc(self.store, self.name, doc_id)

    def stream(self):
        docs = self.store.data.get(self.name, {})
        self.store.reads += len(docs)
        return [_Snap(k, v) for k, v in sorted(docs.items())]


class _Batch:
    def __init__(self):
        self.ops = []

    def set(self, ref, body):
        self.ops.append(lambda: ref.set(body))

    def delete(self, ref):
        self.ops.append(ref.delete)

    def commit(self):
        for op in self.ops:
            op()
        self.ops = []


class FakeDB:
    def __init__(self):
        self.data, self.reads = {}, 0

    def collection(self, name):
        return _Col(self, name)

    def batch(self):
        return _Batch()


class FirestoreCacheTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        for i in range(50):
            self.db.data.setdefault(DATA, {})[f"d{i:02d}"] = {"strategy_id": "a" if i % 2 else "b", "qty": i}
        self.repo = FirestoreRepo(db=self.db)

    def test_collection_read_once(self):
        self.repo.where(DATA, "strategy_id", "a")
        self.repo.where(DATA, "strategy_id", "b")
        self.repo.where(DATA)
        self.repo.get(DATA, "d03")
        self.assertEqual(self.db.reads, 50)          # 전체 한 번만 읽음
        self.assertEqual(len(self.repo.where(DATA, "strategy_id", "a")), 25)

    def test_writes_update_cache_without_rereading(self):
        self.repo.where(DATA)
        new = self.repo.add(DATA, {"strategy_id": "a", "qty": 99})
        self.repo.update(DATA, "d01", {"qty": 1000})
        self.repo.delete(DATA, "d02")
        self.repo.put_many(DATA, [("x1", {"strategy_id": "c"})])
        self.repo.delete_where(DATA, "strategy_id", "b")
        reads_after_writes = self.db.reads
        a = self.repo.where(DATA, "strategy_id", "a")
        self.assertEqual(self.db.reads, reads_after_writes)          # 쓰기 뒤 다시 읽지 않음
        self.assertIn(new["id"], [d["id"] for d in a])
        self.assertEqual(self.repo.get(DATA, "d01")["qty"], 1000)
        self.assertIsNone(self.repo.get(DATA, "d02"))
        self.assertEqual(self.repo.where(DATA, "strategy_id", "b"), [])
        # 캐시와 실제 저장 내용이 같은지: 캐시를 비우고 다시 읽어 비교
        cached = self.repo.where(DATA)
        self.repo.invalidate()
        self.assertEqual(self.repo.where(DATA), cached)

    def test_returned_docs_are_copies(self):
        d = self.repo.get(DATA, "d01")
        d["qty"] = -1
        self.assertEqual(self.repo.get(DATA, "d01")["qty"], 1)

    def test_missing_doc(self):
        self.assertIsNone(self.repo.update(ORDER_SHEETS, "nope", {"x": 1}))
        self.assertFalse(self.repo.delete(ORDER_SHEETS, "nope"))


if __name__ == "__main__":
    unittest.main()
