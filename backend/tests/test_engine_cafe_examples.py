"""카페 원문 예시 표를 그대로 재현하는지 확인하는 테스트.

실행: python -m unittest discover -s tests   (pytest로도 실행 가능)
"""
import unittest

from app.engine.common import (
    AVG_BUY, BIG, LADDER, LIMIT_SELL, QUARTER_SELL, REV_BUY, REV_MOC, REV_SELL, STAR_BUY,
    Day, Fill, OrderLine, apply_big_number, judge,
)
from app.engine.infinite import (
    NORMAL, QUARTER_STOP, REVERSE, InfSettings, InfState, V22, V40, make_engine,
)
from app.engine.vr import VREngine, VRSettings


def lines_of(sheet, role):
    return [l for l in sheet["lines"] if l.role == role]


def prices(lines):
    return [l.price for l in lines]


class V40Orders(unittest.TestCase):
    def test_first_buy_big_number_and_ladder(self):
        # V4.0 일반모드 원문 표: 1회 617.89$, 전일 종가 45.93 → 큰수 51.44에 12주
        s = InfSettings("TQQQ", "v4.0", principal=617.89 * 40, splits=40, big_pct=0.12)
        eng = make_engine(s)
        sheet = eng.next_orders(eng.initial_state(), prev_close=45.93)
        big = lines_of(sheet, BIG)[0]
        self.assertEqual((big.price, big.qty), (51.44, 12))
        self.assertEqual(prices(lines_of(sheet, LADDER))[:7],
                         [47.53, 44.13, 41.19, 38.61, 36.34, 34.32, 32.52])

    def test_first_half_buys_sells(self):
        # 원문 전반전 표: 1회 539.23$, 평단 69.75, 별지점 78.12
        st = InfState(principal=24000, cash=539.23 * 36, qty=29, avg=69.75, t=4.0)
        eng = V40(InfSettings("TQQQ", "v4.0", principal=24000, splits=40))
        sheet = eng.next_orders(st, prev_close=76.40)
        self.assertAlmostEqual(sheet["unit"], 539.23, places=2)
        self.assertEqual(sheet["star"], 78.12)
        star, avg = lines_of(sheet, STAR_BUY)[0], lines_of(sheet, AVG_BUY)[0]
        self.assertEqual((star.price, star.qty), (78.11, 3))
        self.assertEqual((avg.price, avg.qty), (69.75, 4))
        self.assertEqual(prices(lines_of(sheet, LADDER))[:7],
                         [67.40, 59.91, 53.92, 49.02, 44.93, 41.47, 38.51])
        q, lim = lines_of(sheet, QUARTER_SELL)[0], lines_of(sheet, LIMIT_SELL)[0]
        self.assertEqual((q.price, q.qty), (78.12, 7))
        self.assertEqual((lim.price, lim.qty), (80.21, 22))

    def test_second_half_buys(self):
        # 원문 후반전 표: 1회 568.50$, 별지점 59.55 → 59.54에 9주
        st = InfState(principal=24000, cash=568.50 * 16, qty=141, avg=61.39, t=24.0)
        eng = V40(InfSettings("TQQQ", "v4.0", principal=24000, splits=40))
        sheet = eng.next_orders(st, prev_close=60.0)
        self.assertEqual(sheet["star"], 59.55)
        star = lines_of(sheet, STAR_BUY)[0]
        self.assertEqual((star.price, star.qty), (59.54, 9))
        self.assertEqual(prices(lines_of(sheet, LADDER)),
                         [56.85, 51.68, 47.37, 43.73, 40.60, 37.90, 35.53, 33.44])
        self.assertEqual(lines_of(sheet, QUARTER_SELL)[0].qty, 35)       # 141의 1/4
        self.assertEqual(lines_of(sheet, LIMIT_SELL)[0].qty, 106)

    def test_star_pct_soxl_20(self):
        # 원문: 20분할 SOXL, 평단 38.30, T=8.6 → 별% 2.8%, 별지점 39.37
        eng = V40(InfSettings("SOXL", "v4.0", principal=20000, splits=20))
        self.assertAlmostEqual(eng.star_pct(8.6), 2.8)
        self.assertEqual(eng.star_price(InfState(20000, 0, qty=110, avg=38.30, t=8.6)), 39.37)

    def test_unit_recalculated_daily(self):
        # 원문: 2만$ 40분할, 첫날 478$ 매수 → 잔금 19522, T=1 → 2일차 500.56$
        eng = V40(InfSettings("TQQQ", "v4.0", principal=20000, splits=40))
        self.assertAlmostEqual(eng.unit(InfState(20000, 19522, qty=10, avg=47.8, t=1)), 500.56, places=2)


class V40TValues(unittest.TestCase):
    def setUp(self):
        self.eng = V40(InfSettings("TQQQ", "v4.0", principal=20000, splits=40))
        self.st = InfState(principal=20000, cash=16500, qty=50, avg=70.0, t=7.0)

    def day(self, *fills, close=70.0):
        return Day("2026-10-01", close, close, [], list(fills))

    def test_full_buy_plus_one(self):
        st = self.eng.apply_day(self.st, self.day(Fill(STAR_BUY, "buy", 69, 3), Fill(AVG_BUY, "buy", 69, 4)))
        self.assertAlmostEqual(st.t, 8.0)

    def test_half_buy_plus_half(self):
        st = self.eng.apply_day(self.st, self.day(Fill(STAR_BUY, "buy", 72, 3), close=72))
        self.assertAlmostEqual(st.t, 7.5)

    def test_quarter_sell_times_075(self):
        # 원문: T=7에서 쿼터매도 → 5.25
        st = self.eng.apply_day(self.st, self.day(Fill(QUARTER_SELL, "sell", 80, 12), close=80))
        self.assertAlmostEqual(st.t, 5.25)

    def test_limit_sell_then_loc_buy_not_cycle_end(self):
        # 원문: 지정가매도 후 LOC 매수 → ×0.25 + 1, 사이클 종료 아님
        st = InfState(principal=20000, cash=15000, qty=40, avg=70.0, t=10.0)
        d = self.day(Fill(LIMIT_SELL, "sell", 80.5, 30), Fill(STAR_BUY, "buy", 66, 3),
                     Fill(AVG_BUY, "buy", 66, 4), close=66)
        st2 = self.eng.apply_day(st, d)
        self.assertAlmostEqual(st2.t, 3.5)
        self.assertEqual(st2.qty, 17)
        self.assertEqual(st2.cycle_no, 1)

    def test_full_exit_closes_cycle(self):
        st = InfState(principal=20000, cash=17200, qty=40, avg=70.0, t=6.0, cycle_start="2026-09-01")
        d = self.day(Fill(LIMIT_SELL, "sell", 80.5, 30), Fill(QUARTER_SELL, "sell", 81, 10), close=81)
        st2 = self.eng.apply_day(st, d)
        self.assertEqual((st2.qty, st2.t, st2.cycle_no), (0, 0.0, 2))
        self.assertAlmostEqual(st2.cycles[0]["profit"], 17200 + 2415 + 810 - 20000, places=2)


class V40Reverse(unittest.TestCase):
    def setUp(self):
        self.s = InfSettings("SOXL", "v4.0", principal=20000, splits=40)
        self.eng = V40(self.s)

    def test_enter_reverse_when_t_over_39(self):
        st = InfState(principal=20000, cash=480, qty=500, avg=40.0, t=38.6)
        d = Day("d", 30.0, 30.0, [], [Fill(STAR_BUY, "buy", 30, 16)])
        st2 = self.eng.apply_day(st, d)
        self.assertEqual(st2.mode, REVERSE)
        self.assertEqual(st2.rev_day, 0)

    def test_first_day_moc_twentieth(self):
        st = InfState(principal=20000, cash=400, qty=200, avg=40, t=39.5, mode=REVERSE)
        sheet = self.eng.next_orders(st, prev_close=30)
        self.assertEqual(len(sheet["lines"]), 1)
        moc = sheet["lines"][0]
        self.assertEqual((moc.role, moc.order_type, moc.qty), (REV_MOC, "MOC", 10))

    def test_sell_qty_sequence(self):
        # 원문: 200 → 10, 190 → 9, 181 → 9, 172 → 8
        for qty, expect in [(190, 9), (181, 9), (172, 8)]:
            st = InfState(principal=20000, cash=700, qty=qty, avg=40, t=37, mode=REVERSE,
                          rev_day=1, closes=[31, 31, 31, 31, 31])
            self.assertEqual(lines_of(self.eng.next_orders(st, 31), REV_SELL)[0].qty, expect)

    def test_reverse_t_formula(self):
        # 원문: T=39.5 → 첫날 MOC 매도 → 37.525 → 둘째날 쿼터매수 → 38.14375
        st = InfState(principal=20000, cash=400, qty=200, avg=40, t=39.5, mode=REVERSE)
        st = self.eng.apply_day(st, Day("d1", 30, 30, [], [Fill(REV_MOC, "sell", 30, 10)]))
        self.assertAlmostEqual(st.t, 37.525)
        self.assertAlmostEqual(st.cash, 700)                         # 400 + 300
        st = self.eng.apply_day(st, Day("d2", 29, 29, [], [Fill(REV_BUY, "buy", 29, 6)]))
        self.assertAlmostEqual(st.t, 38.14375)

    def test_quarter_buy_budget_and_ladder(self):
        # 원문 리버스 매수표: 544.47$, 별지점 48.62 → 48.61에 11주, 사다리 45.37 41.88 38.89 36.29
        st = InfState(principal=20000, cash=544.47 * 4, qty=300, avg=60, t=37, mode=REVERSE,
                      rev_day=1, closes=[48.62] * 5)
        sheet = self.eng.next_orders(st, 48.0)
        buy = lines_of(sheet, REV_BUY)[0]
        self.assertEqual((buy.price, buy.qty), (48.61, 11))
        self.assertEqual(prices(lines_of(sheet, LADDER))[:4], [45.37, 41.88, 38.89, 36.29])
        self.assertEqual(lines_of(sheet, REV_SELL)[0].price, 48.62)

    def test_exit_reverse(self):
        # 원문: 평단 40, SOXL 종가가 32를 넘으면 일반모드
        st = InfState(principal=20000, cash=700, qty=180, avg=40, t=37, mode=REVERSE, rev_day=2)
        st2 = self.eng.apply_day(st, Day("d", 32.01, 32.5, [], []))
        self.assertEqual(st2.mode, NORMAL)
        self.assertAlmostEqual(st2.t, 37)                            # T 승계
        st3 = self.eng.apply_day(st, Day("d", 31.99, 32.5, [], []))
        self.assertEqual(st3.mode, REVERSE)


class V22Rules(unittest.TestCase):
    def test_t_value(self):
        # 원문: 1회 1000불, 누적 980 → 0.98, 1940 → 1.94, 2880 → 2.88 (셋째 자리 올림)
        eng = V22(InfSettings("TQQQ", "v2.2", principal=40000))
        self.assertEqual(eng.calc_t(98.0, 10), 0.98)
        self.assertEqual(eng.calc_t(97.0, 20), 1.94)
        self.assertEqual(eng.calc_t(96.0, 30), 2.88)
        self.assertEqual(eng.calc_t(1941.0, 1), 1.95)

    def test_star_pct(self):
        tq = V22(InfSettings("TQQQ", "v2.2", principal=40000))
        for t, pct in [(6, 7), (13, 3.5), (12, 4), (21, -0.5), (38, -9), (35, -7.5)]:
            self.assertAlmostEqual(tq.star_pct(t), pct)
        sx = V22(InfSettings("SOXL", "v2.2", principal=40000))
        for t, pct in [(10, 6), (15, 3), (5, 9), (25, -3), (30, -6), (35, -9)]:
            self.assertAlmostEqual(sx.star_pct(t), pct)

    def test_star_pct_a_splits(self):
        # 원문: a=35, T=20 → TQQQ −1.43%, SOXL −1.71%
        self.assertAlmostEqual(V22(InfSettings("TQQQ", "v2.2", 35000, splits=35)).star_pct(20), -1.43, places=2)
        self.assertAlmostEqual(V22(InfSettings("SOXL", "v2.2", 35000, splits=35)).star_pct(20), -1.71, places=2)

    def test_orders_example(self):
        # 원문 '다음 매수매도 계획': 평단 38.365, 별지점 39.32 → 매수 39.31×12, 38.37×14, 사다리 37.03…
        #                         매도 1/4 39.32×95, 10% 지정가 42.20×288 (보유 383)
        eng = V22(InfSettings("TQQQ", "v2.2", principal=40000))
        st = InfState(principal=40000, cash=25000, qty=383, avg=38.365, t=15.0)
        sheet = eng.next_orders(st, prev_close=38.0)
        self.assertEqual(sheet["star"], 39.32)
        star, avg = lines_of(sheet, STAR_BUY)[0], lines_of(sheet, AVG_BUY)[0]
        self.assertEqual((star.price, star.qty), (39.31, 12))
        self.assertEqual((avg.price, avg.qty), (38.37, 14))
        self.assertEqual(prices(lines_of(sheet, LADDER))[:4], [37.03, 35.71, 34.48, 33.33])
        q, lim = lines_of(sheet, QUARTER_SELL)[0], lines_of(sheet, LIMIT_SELL)[0]
        self.assertEqual((q.price, q.qty), (39.32, 95))
        self.assertEqual((lim.price, lim.qty), (42.20, 288))

    def test_big_number_merge(self):
        # 원문 '큰수 매수': 평단 39.71, 별 41.34×12, 평단 39.71×13 상태에서 종가가 30까지 급락
        eng = V22(InfSettings("TQQQ", "v2.2", principal=40000))
        st = InfState(principal=40000, cash=25000, qty=300, avg=39.71, t=11.74)
        normal = eng.next_orders(st, prev_close=40.0)
        self.assertEqual([(l.price, l.qty) for l in normal["lines"][:2]], [(41.34, 12), (39.71, 13)])
        self.assertEqual(prices(lines_of(normal, LADDER)),
                         [38.46, 37.03, 35.71, 34.48, 33.33, 32.25, 31.25, 30.30])
        crash = eng.next_orders(st, prev_close=30.0)
        big = lines_of(crash, BIG)[0]
        self.assertEqual((big.price, big.qty), (33.00, 30))       # 위 주문 12+13+사다리 5 합산
        self.assertEqual(prices(lines_of(crash, LADDER)), [32.25, 31.25, 30.30])

    def test_new_cycle_soxl_plus_12(self):
        eng = V22(InfSettings("SOXL", "v2.2", principal=40000))
        big = lines_of(eng.next_orders(eng.initial_state(), prev_close=25.0), BIG)[0]
        self.assertEqual(big.price, 28.0)

    def test_quarter_stop_flow(self):
        eng = V22(InfSettings("TQQQ", "v2.2", principal=40000))
        st = InfState(principal=40000, cash=600, qty=1300, avg=30.0, t=39.0)
        st = eng.apply_day(st, Day("d0", 25, 25, [], [Fill(STAR_BUY, "buy", 25, 20)]))
        self.assertEqual(st.mode, QUARTER_STOP)
        sheet = eng.next_orders(st, 25)
        self.assertEqual(sheet["lines"][0].order_type, "MOC")
        self.assertEqual(sheet["lines"][0].qty, st.qty // 4)
        st = eng.apply_day(st, Day("d1", 25, 25, [], [Fill("quarter_stop_moc", "sell", 25, st.qty // 4)]))
        self.assertEqual(st.qs_phase, "buying")
        self.assertLessEqual(st.qs_unit, 1000)
        sheet = eng.next_orders(st, 25)
        buy = [l for l in sheet["lines"] if l.role == "quarter_stop_buy"][0]
        self.assertEqual(buy.price, round(st.avg * 0.9, 2))


class Judge(unittest.TestCase):
    def test_loc_moc_limit(self):
        lines = [OrderLine("buy", "LOC", STAR_BUY, 78.11, 3), OrderLine("buy", "LOC", AVG_BUY, 69.75, 4),
                 OrderLine("sell", "LIMIT", LIMIT_SELL, 80.21, 22), OrderLine("sell", "MOC", REV_MOC, None, 5)]
        fills = judge(lines, close=76.40, high=80.30)
        got = {(f.role, f.price, f.qty) for f in fills}
        self.assertEqual(got, {(STAR_BUY, 76.40, 3), (LIMIT_SELL, 80.21, 22), (REV_MOC, 76.40, 5)})


class VR(unittest.TestCase):
    def test_new_v(self):
        # quantstack 예시: V 9000, Pool 1000, G 10, 적립 250 → 9350
        eng = VREngine(VRSettings("TQQQ", "installment", start_v=9000, start_pool=1000, cycle_amount=250))
        self.assertAlmostEqual(eng.new_v(9000, 1000), 9350)

    def test_withdrawal_and_pool_limit(self):
        s = VRSettings("TQQQ", "withdrawal", start_v=9000, start_pool=1000, g=20, cycle_amount=100)
        eng = VREngine(s)
        st = eng.rebalance(eng.initial_state(100), "d", 80.0)
        self.assertAlmostEqual(st.v, 9000 + 50 - 100)
        self.assertAlmostEqual(st.pool, 900)
        self.assertAlmostEqual(st.budget_left, 900 * 0.25)

    def test_order_table(self):
        eng = VREngine(VRSettings("TQQQ", "lump_sum", start_v=10000, start_pool=5000))
        st = eng.initial_state(100)
        sheet = eng.next_orders(st)
        buys = [l.price for l in sheet["lines"] if l.side == "buy"]
        sells = [l.price for l in sheet["lines"] if l.side == "sell"]
        self.assertEqual(buys[:2], [84.15, 83.33])          # 8500/101, 8500/102
        self.assertEqual(sells[:2], [116.17, 117.35])       # 11500/99, 11500/98 (올림)


if __name__ == "__main__":
    unittest.main()
