from functools import lru_cache

from ..config import settings
from .base import Repo


@lru_cache
def get_repo() -> Repo:
    if settings.storage == "memory":
        from .memory import MemoryRepo
        return MemoryRepo()
    from .firestore import FirestoreRepo
    return FirestoreRepo()
