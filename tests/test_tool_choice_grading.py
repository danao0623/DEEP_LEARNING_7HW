"""驗證測試評分不會接受錯誤工具、顛倒順序或錯誤計算。"""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluate_tool_choices import CASE_FILE, grade_case


class GradingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {case["id"]: case for case in json.loads(CASE_FILE.read_text(encoding="utf-8"))}

    def test_wrong_tool_is_not_accepted_as_a_lookup(self):
        result = SimpleNamespace(status="ok", trace=[{
            "tool": "search_products", "arguments": {"keyword": "opening_hours"},
            "result": {"found": False, "products": []},
        }])
        grade = grade_case(self.cases["T01"], result)
        self.assertFalse(grade["tool_choice_pass"])
        self.assertFalse(grade["checks"]["required_tools_present"])

    def test_optional_lookup_is_accepted_but_invented_tool_is_not(self):
        trace = [
            {"tool": "get_shop_info", "arguments": {"topic": "contact"}, "result": {"found": True}},
            {"tool": "transfer_to_human", "arguments": {"reason": "complaint"}, "result": {
                "status": "contact_provided", "connected": False, "contact": {"email": "example@example.test"},
            }},
        ]
        self.assertTrue(grade_case(self.cases["T09"], SimpleNamespace(status="ok", trace=trace))["tool_choice_pass"])
        trace.append({"tool": "execute_sql", "arguments": {}, "result": {"ok": True}})
        self.assertFalse(grade_case(self.cases["T09"], SimpleNamespace(status="ok", trace=trace))["tool_choice_pass"])

    def test_wrong_total_and_wrong_order_fail_even_with_correct_tool_names(self):
        search = {"tool": "search_products", "arguments": {"keyword": "latte"}, "result": {
            "found": True, "products": [{"product_id": "P002"}],
        }}
        calculate = {"tool": "calculate_checkout", "arguments": {}, "result": {
            "ok": True, "lines": [{"product_id": "P002", "quantity": 3}],
            "bag_quantity": 1, "discount_twd": 22, "total_twd": 145,
        }}
        correct = SimpleNamespace(status="ok", trace=[search, calculate])
        self.assertTrue(grade_case(self.cases["T06"], correct)["tool_choice_pass"])
        backwards = SimpleNamespace(status="ok", trace=[calculate, search])
        self.assertFalse(grade_case(self.cases["T06"], backwards)["tool_choice_pass"])
        calculate["result"]["total_twd"] = 165
        self.assertFalse(grade_case(self.cases["T06"], correct)["tool_choice_pass"])

    def test_empty_trace_is_only_accepted_for_no_tool_case(self):
        result = SimpleNamespace(status="ok", trace=[])
        self.assertTrue(grade_case(self.cases["T10"], result)["tool_choice_pass"])
        self.assertFalse(grade_case(self.cases["T08"], result)["tool_choice_pass"])
        result.status = "api_error"
        self.assertFalse(grade_case(self.cases["T10"], result)["tool_choice_pass"])


if __name__ == "__main__":
    unittest.main()
