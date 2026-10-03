"""초기 데이터 적재 (로컬에서 한 번 실행).

    cd backend
    python -m scripts.seed              # 시세만 (TQQQ, SOXL 일별 종가)
    python -m scripts.seed --demo       # 시세 + 시뮬레이션 전략 2개 백테스트 (data 수백 건)

.env의 STORAGE·FIREBASE 설정을 그대로 쓴다.
"""
from __future__ import annotations

import argparse

from app.config import settings
from app.repo import get_repo
from app.services import prices as price_svc
from app.services import strategies as svc

DEMO = [
    {"type": "infinite", "ticker": "TQQQ", "rule_version": "v4.0", "splits": 40, "principal": 20000,
     "is_simulation": True, "name": "[시뮬] TQQQ V4.0 40분할"},
    {"type": "vr", "ticker": "TQQQ", "vr_type": "installment", "start_v": 8000, "start_pool": 2000,
     "cycle_amount": 250, "g": 10, "is_simulation": True, "name": "[시뮬] TQQQ VR 적립식"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="시뮬레이션 전략을 만들고 백테스트한다")
    ap.add_argument("--start", default=settings.price_start, help="시세 시작일 (YYYY-MM-DD)")
    args = ap.parse_args()

    repo = get_repo()
    print("시세 동기화:", price_svc.sync(repo, settings.tickers, args.start))
    if args.demo:
        for body in DEMO:
            s = svc.create_strategy(repo, body)
            res = svc.backtest(repo, s["id"], args.start)
            print(f"{s['name']}: {res}")


if __name__ == "__main__":
    main()
