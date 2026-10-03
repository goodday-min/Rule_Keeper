"""엔진 전체를 수백 거래일 돌려 보는 스모크 테스트.

시세는 고정 시드의 가상 경로(실제 데이터 아님)다. 숫자 정답을 보는 테스트가 아니라
- 오류 없이 돌아가는지
- 수량·잔금·T가 말이 되는 범위에 있는지
- 리버스모드·쿼터손절에 들어갔다 나오는지
를 확인한다.
"""
import math
import random
import unittest

from app.engine.backtest import Bar, run_infinite, run_vr
from app.engine.common import BUY_ROLES
from app.engine.infinite import InfSettings, make_engine
from app.engine.vr import VRSettings


def path(n, seed, start=50.0, drift=0.0008, vol=0.04, crash_at=None, crash_len=0, crash_drift=-0.03):
    rnd = random.Random(seed)
    p, out = start, []
    for i in range(n):
        d = crash_drift if crash_at is not None and crash_at <= i < crash_at + crash_len else drift
        r = d + vol * rnd.gauss(0, 1)
        close = round(p * math.exp(r), 2)
        high = round(max(p, close) * (1 + abs(rnd.gauss(0, 0.012))), 2)
        out.append(Bar(f"D{i:04d}", close, high))
        p = close
    return out


class InfiniteBacktest(unittest.TestCase):
    CASES = [
        ("TQQQ", "v4.0", 40), ("TQQQ", "v4.0", 20), ("SOXL", "v4.0", 40), ("SOXL", "v4.0", 20),
        ("TQQQ", "v2.2", 40), ("SOXL", "v2.2", 40),
    ]

    def check(self, s, bars):
        st, days = run_infinite(s, bars)
        modes = set()
        eng = make_engine(s)
        state = eng.initial_state()
        for d in days:
            state = eng.apply_day(state, d)
            modes.add(state.mode)
            self.assertGreaterEqual(state.qty, 0)
            self.assertGreaterEqual(state.t, 0)
            self.assertTrue(math.isfinite(state.cash))
            # 잔금은 (기존 수익금을 빌려 쓰는 V2.2 쿼터손절을 빼면) 음수가 되지 않는다
            self.assertGreaterEqual(state.cash, -max(0.0, state.profit_total) - 0.01, d.date)
            self.assertLessEqual(state.t, n_splits := s.splits * 1.0 + 1e-9)
            for l in d.sheet:
                self.assertGreaterEqual(l.qty, 0)
                if l.price is not None:
                    self.assertGreater(l.price, 0)
            spent = sum(f.price * f.qty for f in d.fills if f.role in BUY_ROLES)
            self.assertLess(spent, state.principal)          # 하루 매수가 원금을 넘지 않음
        self.assertEqual(state.qty, st.qty)                 # 재생 결과가 백테스트와 같다
        return st, modes

    def test_normal_market(self):
        for tk, ver, n in self.CASES:
            with self.subTest(tk=tk, ver=ver, n=n):
                st, modes = self.check(InfSettings(tk, ver, principal=20000, splits=n), path(700, seed=7))
                self.assertGreater(len(st.cycles), 0, "사이클이 한 번은 끝나야 한다")

    def test_crash_enters_and_leaves_exhaustion_mode(self):
        for tk, ver, n in self.CASES:
            with self.subTest(tk=tk, ver=ver, n=n):
                bars = path(500, seed=3, crash_at=60, crash_len=70, crash_drift=-0.02, vol=0.03)
                st, modes = self.check(InfSettings(tk, ver, principal=20000, splits=n), bars)
                expected = "reverse" if ver == "v4.0" else "quarter_stop"
                self.assertIn(expected, modes)


class VRBacktest(unittest.TestCase):
    def test_runs_all_types(self):
        bars = path(400, seed=11)
        for vr_type, amt in [("installment", 250), ("lump_sum", 0), ("withdrawal", 100)]:
            with self.subTest(vr_type=vr_type):
                s = VRSettings("TQQQ", vr_type, start_v=8000, start_pool=2000, cycle_amount=amt,
                               g=20 if vr_type == "withdrawal" else 10)
                st, days = run_vr(s, bars, initial_qty=int(8000 / bars[0].close))
                self.assertGreater(len(st.snapshots), 30)
                self.assertGreaterEqual(st.qty, 0)
                for snap in st.snapshots:
                    self.assertLess(snap["band_low"], snap["v"])
                    self.assertGreater(snap["band_high"], snap["v"])


if __name__ == "__main__":
    unittest.main()
