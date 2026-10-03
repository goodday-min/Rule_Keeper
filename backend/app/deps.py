from __future__ import annotations

import hmac
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import settings
from .repo import get_repo  # noqa: F401  (라우터에서 Depends(get_repo)로 사용)


# Swagger 오른쪽 위 Authorize 버튼에 한 번 넣으면 모든 요청에 X-API-Key 헤더가 붙는다
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="데이터를 바꾸는 요청에 필요한 키")


def require_key(x_api_key: Optional[str] = Security(api_key_header)):
    """APP_API_KEY가 설정돼 있으면 X-API-Key 헤더가 같아야 한다 (비어 있으면 로컬 개발로 보고 통과)."""
    if not settings.app_api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="API 키가 맞지 않습니다")
