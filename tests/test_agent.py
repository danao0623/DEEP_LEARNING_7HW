"""離線驗證資料、計算與工具呼叫協定；不使用真實 API。"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import run_agent
from database import connect, initialize_database
from store_tools import StoreTools


def model_reply(content=None, *, name=None, arguments="{}"):
    calls = [] if name is None else [SimpleNamespace(
        id="call_test", type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )]
    return SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(content=content, tool_calls=calls),
    )])


class ScriptedClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        return next(self.replies)


class AgentTests(unittest.TestCase):
    def setUp(self):
        # 使用專案內的暫存檔，避開 Windows 沙箱無法讀寫系統 Temp 的限制。
        with tempfile.NamedTemporaryFile(dir=Path(__file__).resolve().parent, suffix=".db", delete=False) as temporary:
            self.db_path = Path(temporary.name)
        self.addCleanup(lambda: self.db_path.unlink(missing_ok=True))
        self.counts = initialize_database(self.db_path)
        self.tools = StoreTools(self.db_path)

    def test_database_rebuild_and_literal_search(self):
        self.assertGreaterEqual(self.counts["shop_info"], 8)
        self.assertGreaterEqual(self.counts["products"], 15)
        # 惡意輸入與 LIKE 萬用字元都只當成查詢文字。
        for keyword in ["' OR 1=1 --", "%", "_"]:
            self.assertFalse(self.tools.search_products(keyword)["found"])
        initialize_database(self.db_path)
        with connect(self.db_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM products").fetchone()[0], 15)

    def test_odd_quantity_discount_and_bag_fee_without_stock_change(self):
        result = self.tools.calculate_checkout([{"product_id": "P002", "quantity": 3}], 1)
        self.assertEqual(result["total_twd"], 145)  # 55 + 33 + 55 + 2
        self.assertEqual(result["discount_twd"], 22)
        self.assertEqual(result["original_goods_subtotal_twd"], 165)
        self.assertEqual(result["lines"][0]["promotion_label"], "同商品第二件6折")
        self.assertEqual(result["lines"][0]["discounted_unit_price_twd"], 33)
        self.assertTrue(result["quote_only"])
        self.assertEqual(self.tools.search_products("P002")["products"][0]["stock"], 30)

    def test_duplicate_lines_pair_but_different_products_do_not(self):
        result = self.tools.calculate_checkout([
            {"product_id": "P002", "quantity": 1},
            {"product_id": "p002", "quantity": 1},
        ])
        self.assertEqual(result["total_twd"], 88)
        result = self.tools.calculate_checkout([
            {"product_id": "P001", "quantity": 1},
            {"product_id": "P002", "quantity": 1},
        ])
        self.assertEqual(result["total_twd"], 100)

    def test_promotion_name_and_rounding_follow_database_policy(self):
        with connect(self.db_path) as connection, connection:
            policy = self.tools.get_shop_info("checkout_rules")["content"]
            policy["second_item_percent"] = 50
            connection.execute(
                "UPDATE shop_info SET content = ? WHERE topic = ?",
                (json.dumps(policy), "checkout_rules"),
            )
        result = self.tools.calculate_checkout([{"product_id": "P002", "quantity": 2}])
        self.assertEqual(result["lines"][0]["promotion_label"], "同商品第二件5折")
        self.assertEqual(result["lines"][0]["discounted_unit_price_twd"], 28)
        self.assertEqual(result["total_twd"], 83)

    def test_unavailable_stock_and_invalid_quantity_have_no_quote(self):
        for product_id, quantity in [("P015", 1), ("P002", 31), ("missing", 1)]:
            result = self.tools.calculate_checkout([{"product_id": product_id, "quantity": quantity}])
            self.assertFalse(result["ok"])
            self.assertNotIn("total_twd", result)
        result = self.tools.execute("calculate_checkout", json.dumps({
            "items": [{"product_id": "P002", "quantity": True}],
        }))
        self.assertEqual(result["error"], "invalid_arguments")

    def test_agent_sends_tool_result_and_chat_history_to_model(self):
        client = ScriptedClient([
            model_reply(name="get_shop_info", arguments='{"topic":"opening_hours"}'),
            model_reply("每日 07:00–23:00。"),
        ])
        result = run_agent(
            "那幾點開門？",
            [{"role": "user", "content": [{"type": "text", "text": "我要去買東西。"}]}],
            client=client, toolkit=self.tools,
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(client.requests[0]["messages"][1]["content"], "我要去買東西。")
        tool_message = client.requests[1]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertEqual(tool_message["tool_call_id"], "call_test")
        self.assertTrue(json.loads(tool_message["content"])["found"])
        self.assertEqual(result.trace[0]["tool"], "get_shop_info")

    def test_unknown_tool_and_invalid_json_are_rejected(self):
        for name, arguments, expected in [
            ("execute_sql", '{"sql":"DROP TABLE products"}', "unknown_tool"),
            ("search_products", '{"keyword":', "invalid_json"),
        ]:
            client = ScriptedClient([
                model_reply(name=name, arguments=arguments), model_reply("無法執行這個工具。"),
            ])
            result = run_agent("測試", client=client, toolkit=self.tools)
            self.assertEqual(result.trace[0]["result"]["error"], expected)
        self.assertEqual(len(self.tools.search_products("")["products"]), 15)

    def test_repeated_tool_requests_stop_at_max_steps(self):
        client = ScriptedClient([
            model_reply(name="search_products", arguments='{"keyword":"不存在"}') for _ in range(2)
        ])
        result = run_agent("找商品", client=client, toolkit=self.tools, max_steps=2)
        self.assertEqual(result.status, "step_limit")
        self.assertEqual(len(client.requests), 2)
        self.assertEqual(len(result.trace), 2)

    def test_out_of_scope_reply_needs_no_tool_and_handoff_is_not_a_real_transfer(self):
        client = ScriptedClient([model_reply("我只能回答本店相關問題。")])
        result = run_agent("幫我寫詩", client=client, toolkit=self.tools)
        self.assertEqual(result.trace, [])
        contact = self.tools.transfer_to_human("客訴")
        self.assertEqual(contact["status"], "contact_provided")
        self.assertFalse(contact["connected"])

    def test_missing_key_returns_setup_message_without_creating_client(self):
        with patch("agent.read_settings", return_value={"API_KEY": ""}), patch("agent.OpenAI") as factory:
            result = run_agent("幾點開門？", toolkit=self.tools)
        factory.assert_not_called()
        self.assertEqual(result.status, "not_configured")
        self.assertEqual(result.model_calls, 0)


if __name__ == "__main__":
    unittest.main()
