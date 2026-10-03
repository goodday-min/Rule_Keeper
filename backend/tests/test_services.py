"""서비스 계층 테스트: 메모리 저장소 + 가짜 시세 + 가짜 GPT로 전체 흐름을 확인한다."""
import json
import math
import random
import unittest
from datetime import date, timedelta
from types import SimpleNamespace as NS

from app.repo.base import CONVERSATIONS, DATA, ORDER_SHEETS, PRICES, VR_SNAPSHOTS
from app.repo.memory import MemoryRepo
from app.services import chat as chat_svc
from app.services import conversations as conv_svc
from app.services import data as data_svc
from app.services import prices as price_svc
from app.services import strategies as svc
from app.services import summary as sum_svc
from app.services.common import Conflict, next_trading_day


def fake_provider(n=260, start="2025-09-01"):
    def provider(ticker, since):
        rnd = random.Random(hash(ticker) % 1000)
        p, d, out = 50.0 if ticker == "TQQQ" else 25.0, date.fromisoformat(start), []
        while len(out) < n:
            if d.weekday() < 5:
                c = round(p * math.exp(0.0005 + 0.035 * rnd.gauss(0, 1)), 2)
                out.append({"date": d.isoformat(), "open": p, "high": round(max(p, c) * 1.01, 2),
                            "low": round(min(p, c) * 0.99, 2), "close": c})
                p = c
            d += timedelta(days=1)
        return [r for r in out if r["date"] >= since]
    return provider


def add_price(repo, ticker, d, close, high=None):
    repo.put(PRICES, f"{ticker}_{d}", {"ticker": ticker, "date": d, "close": close, "high": high or close,
                                       "open": close, "low": close})


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = MemoryRepo()
        r = price_svc.sync(self.repo, ["TQQQ", "SOXL"], "2025-09-01", fake_provider())
        self.assertEqual(r["TQQQ"]["added"], 260)
        self.last = r["TQQQ"]["last_date"]

    def v4(self, **kw):
        body = {"type": "infinite", "ticker": "TQQQ", "rule_version": "v4.0", "splits": 40,
                "principal": 20000, "account_memo": "A", "start_date": next_trading_day(self.last), **kw}
        return svc.create_strategy(self.repo, body)


class PriceSync(Base):
    def test_incremental(self):
        r = price_svc.sync(self.repo, ["TQQQ"], "2025-09-01", fake_provider(n=262))
        self.assertEqual(r["TQQQ"]["added"], 2)          # 빠진 날짜만

    def test_provider_error_kept(self):
        def boom(t, s):
            raise RuntimeError("network")
        r = price_svc.sync(self.repo, ["TQQQ"], "2025-09-01", boom)
        self.assertIn("error", r["TQQQ"])


class StrategyFlow(Base):
    def test_duplicate_warning(self):
        self.v4()
        s2 = self.v4(splits=20)
        self.assertTrue(s2["warnings"])
        s3 = self.v4(account_memo="B")
        self.assertFalse(s3["warnings"])

    def test_invalid_rejected(self):
        with self.assertRaises(ValueError):
            self.v4(ticker="QQQ")
        with self.assertRaises(ValueError):
            self.v4(splits=30)

    def test_sheet_judge_confirm_replay(self):
        s = self.v4()
        sheet = svc.build_next_sheet(self.repo, s["id"])
        self.assertEqual(sheet["date"], next_trading_day(self.last))
        self.assertEqual(sheet["lines"][0]["role"], "big")
        self.assertFalse(sheet["provisional"])
        # 그날 시세가 들어오면 판정 → 확정
        last_close = self.repo.get(PRICES, f"TQQQ_{self.last}")["close"]
        add_price(self.repo, "TQQQ", sheet["date"], round(last_close * 0.99, 2))
        nxt = svc.build_next_sheet(self.repo, s["id"])
        self.assertTrue(nxt["provisional"])                 # 확정 전 주문표는 임시
        j = svc.judge_sheet(self.repo, s["id"], sheet["date"])
        self.assertTrue(j["judged"][0]["filled"])
        res = svc.confirm_sheet(self.repo, s["id"], sheet["date"])
        self.assertGreater(res["fills_created"], 0)
        st = res["status"]
        self.assertEqual(st["t"], 1.0)
        self.assertGreater(st["qty"], 0)
        self.assertEqual(st["phase"], "first_half")
        with self.assertRaises(Conflict):
            svc.confirm_sheet(self.repo, s["id"], sheet["date"])
        nxt = svc.build_next_sheet(self.repo, s["id"])
        self.assertFalse(nxt["provisional"])
        roles = [l["role"] for l in nxt["lines"]]
        self.assertIn("star_buy", roles)
        self.assertIn("limit_sell", roles)

    def test_confirm_with_override(self):
        s = self.v4()
        sheet = svc.build_next_sheet(self.repo, s["id"])
        add_price(self.repo, "TQQQ", sheet["date"], 1000.0)   # 판정상 미체결
        res = svc.confirm_sheet(self.repo, s["id"], sheet["date"],
                                [{"line_id": 0, "filled": True, "price": 51.0, "qty": 10}])
        self.assertEqual(res["fills_created"], 1)
        self.assertEqual(res["status"]["qty"], 10)

    def test_manual_data_crud_recomputes(self):
        s = self.v4()
        d = data_svc.create_data(self.repo, {"strategy_id": s["id"], "date": self.last, "value": 50.0, "qty": 10,
                                             "side": "buy", "role": "big", "memo": "첫 매수"})
        self.assertEqual(svc.status(self.repo, s["id"])["qty"], 10)
        data_svc.update_data(self.repo, d["id"], {"qty": 12, "role": "ignored"})
        self.assertEqual(svc.status(self.repo, s["id"])["qty"], 12)
        self.assertEqual(self.repo.get(DATA, d["id"])["role"], "big")       # 역할은 수정 불가
        data_svc.delete_data(self.repo, d["id"])
        self.assertEqual(svc.status(self.repo, s["id"])["qty"], 0)
        with self.assertRaises(ValueError):
            data_svc.create_data(self.repo, {"strategy_id": s["id"], "date": self.last, "value": 50.0, "qty": 1,
                                             "side": "buy", "role": "limit_sell"})

    def test_export(self):
        s = self.v4()
        data_svc.create_data(self.repo, {"strategy_id": s["id"], "date": self.last, "value": 50.0, "qty": 10,
                                         "side": "buy", "role": "big", "memo": "한글 메모"})
        text, ctype = data_svc.export_data(data_svc.list_data(self.repo), "csv")
        self.assertIn("한글 메모", text)
        self.assertTrue(ctype.startswith("text/csv"))
        text, _ = data_svc.export_data(data_svc.list_data(self.repo), "json")
        self.assertEqual(json.loads(text)[0]["memo"], "한글 메모")


class Simulation(Base):
    def test_backtest_creates_100_plus_fills(self):
        s = svc.create_strategy(self.repo, {"type": "infinite", "ticker": "SOXL", "rule_version": "v2.2",
                                            "splits": 40, "principal": 20000, "is_simulation": True})
        res = svc.backtest(self.repo, s["id"], "2025-09-02")
        self.assertGreater(res["fills_created"], 100)       # 과제: data 100건 이상
        st = svc.status(self.repo, s["id"])
        self.assertEqual(st["cycle_no"], res["cycles"] + 1)
        # 다시 돌리면 이전 가상 체결을 지우고 새로 만든다
        res2 = svc.backtest(self.repo, s["id"], "2025-09-02")
        self.assertEqual(len(self.repo.where(DATA, "strategy_id", s["id"])), res2["fills_created"])

    def test_backtest_real_strategy_refused(self):
        s = StrategyFlow.v4(self)
        with self.assertRaises(Conflict):
            svc.backtest(self.repo, s["id"], "2025-09-02")


class VRFlow(Base):
    def test_vr_status_and_rebalance(self):
        s = svc.create_strategy(self.repo, {"type": "vr", "ticker": "TQQQ", "vr_type": "installment",
                                            "start_v": 8000, "start_pool": 2000, "cycle_amount": 250,
                                            "g": 10, "initial_qty": 160, "start_date": "2026-06-01"})
        st = svc.status(self.repo, s["id"])
        self.assertTrue(st["rebalance_due"])
        prev = svc.vr_rebalance(self.repo, s["id"], dry_run=True)["preview"]
        self.assertAlmostEqual(prev["v"], 8000 + 2000 / 10 + 250, places=2)
        self.assertEqual(self.repo.where(VR_SNAPSHOTS), [])
        res = svc.vr_rebalance(self.repo, s["id"])
        self.assertEqual(res["status"]["v"], 8450.0)
        self.assertFalse(res["status"]["rebalance_due"])
        sheet = svc.build_next_sheet(self.repo, s["id"])
        self.assertTrue(all(l["role"] in ("vr_buy", "vr_sell") for l in sheet["lines"]))

    def test_vr_backtest(self):
        s = svc.create_strategy(self.repo, {"type": "vr", "ticker": "TQQQ", "vr_type": "lump_sum",
                                            "start_v": 8000, "start_pool": 2000, "is_simulation": True})
        res = svc.backtest(self.repo, s["id"], "2025-09-02")
        self.assertGreater(res["snapshots"], 10)
        st = svc.status(self.repo, s["id"])
        self.assertEqual(st["qty"], res["final_qty"])


class Summary(Base):
    def test_summary_text(self):
        s = StrategyFlow.v4(self)
        out = sum_svc.build_summary(self.repo, ["TQQQ", "SOXL"], s["id"])
        p = out["prices"]["TQQQ"]
        self.assertEqual(p["count"], 260)
        self.assertIn(p["trend_30d"], ("상승", "하락", "유지"))
        self.assertIn("[시세 요약]", out["text"])
        self.assertIn(f"id={s['id']}", out["text"])
        self.assertIn("[오늘 주문표", out["text"])
        stats = sum_svc.statistics(self.repo, ["TQQQ"])
        self.assertIn("max_drawdown_pct", stats["prices"]["TQQQ"])

    def test_orders_today(self):
        StrategyFlow.v4(self)
        items = svc.orders_today(self.repo)
        self.assertEqual(len(items), 1)
        self.assertIn("today", items[0])


# ---- 가짜 OpenAI -----------------------------------------------------------


class FakeOpenAI:
    """첫 호출은 도구 호출, 두 번째는 답변."""

    def __init__(self, tool_name, tool_args):
        self.calls = []
        self.tool_name, self.tool_args = tool_name, tool_args
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        kw = {**kw, "messages": list(kw["messages"])}     # 호출 시점의 메시지 목록을 남긴다
        self.calls.append(kw)
        if len(self.calls) == 1:
            tc = NS(id="call_1", function=NS(name=self.tool_name, arguments=json.dumps(self.tool_args)))
            return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
        tool_msg = [m for m in kw["messages"] if m["role"] == "tool"][-1]
        return NS(choices=[NS(message=NS(content=f"도구 결과 확인: {tool_msg['content'][:40]}", tool_calls=None))])


class Chat(Base):
    def test_chat_tool_call_and_saved(self):
        s = StrategyFlow.v4(self)
        fake = FakeOpenAI("get_strategy_status", {"strategy_id": s["id"]})
        r = chat_svc.chat(self.repo, fake, "test-model", ["TQQQ", "SOXL"], "지금 T가 몇이야?", strategy_id=s["id"])
        self.assertEqual(r["tools_used"][0]["name"], "get_strategy_status")
        self.assertTrue(r["tools_used"][0]["ok"])
        system = fake.calls[0]["messages"][0]["content"]
        self.assertIn("[요약]", system)
        self.assertIn("직접 계산", system)
        self.assertEqual(len(fake.calls[0]["tools"]), 5)
        conv = conv_svc.get(self.repo, r["conversation_id"])
        self.assertEqual([m["role"] for m in conv["messages"]], ["user", "assistant"])
        self.assertEqual(conv["title"], "지금 T가 몇이야?")
        # 이어서 질문하면 같은 대화에 쌓이고 이전 대화가 GPT에 전달된다
        fake2 = FakeOpenAI("get_price_stats", {"ticker": "TQQQ", "days": 30})
        chat_svc.chat(self.repo, fake2, "m", ["TQQQ"], "추세는?", conversation_id=r["conversation_id"])
        self.assertEqual(len(conv_svc.get(self.repo, r["conversation_id"])["messages"]), 4)
        roles = [m["role"] for m in fake2.calls[0]["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        listing = conv_svc.list_all(self.repo)
        self.assertNotIn("messages", listing[0])
        self.assertEqual(listing[0]["message_count"], 4)

    def test_tool_error_is_reported_not_raised(self):
        fake = FakeOpenAI("get_strategy_status", {"strategy_id": "nope"})
        r = chat_svc.chat(self.repo, fake, "m", ["TQQQ"], "상태?")
        self.assertFalse(r["tools_used"][0]["ok"])
        self.assertIn("error", fake.calls[1]["messages"][-1]["content"])

    def test_all_tools_run(self):
        s = StrategyFlow.v4(self)
        for name, args in [("get_portfolio_summary", {}), ("get_today_orders", {}),
                           ("get_today_orders", {"strategy_id": s["id"]}),
                           ("get_fill_history", {"strategy_id": s["id"]}), ("get_price_stats", {"ticker": "SOXL"})]:
            out = chat_svc.run_tool(self.repo, ["TQQQ", "SOXL"], name, args)
            json.dumps(out, ensure_ascii=False, default=str)


if __name__ == "__main__":
    unittest.main()
