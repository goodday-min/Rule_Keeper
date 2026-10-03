"""환경 변수 설정. 키는 코드에 넣지 않고 .env 또는 배포 환경 변수로 관리한다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # python-dotenv가 있으면 .env를 읽는다 (없어도 동작)
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # pragma: no cover
    pass


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass
class Settings:
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    # OpenAI 호환 프록시 주소 (예: 교육장 https://copa.codyssey.kr/v1). 비우면 OpenAI 기본 주소
    openai_base_url: str = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", ""))
    # 서비스 계정 키 JSON 문자열 또는 base64. 비우면 FIREBASE_CREDENTIALS_PATH 파일을 쓴다
    firebase_credentials: str = field(default_factory=lambda: os.getenv("FIREBASE_CREDENTIALS", ""))
    firebase_credentials_path: str = field(default_factory=lambda: os.getenv("FIREBASE_CREDENTIALS_PATH", ""))
    app_api_key: str = field(default_factory=lambda: os.getenv("APP_API_KEY", ""))
    allowed_origins: list[str] = field(default_factory=lambda: _list("ALLOWED_ORIGINS", "*"))
    # memory: Firebase 없이 메모리 저장소로 실행 (로컬 확인·테스트용)
    storage: str = field(default_factory=lambda: os.getenv("STORAGE", "firestore"))
    tickers: list[str] = field(default_factory=lambda: _list("TICKERS", "TQQQ,SOXL"))
    price_start: str = field(default_factory=lambda: os.getenv("PRICE_START", "2024-01-01"))


settings = Settings()
