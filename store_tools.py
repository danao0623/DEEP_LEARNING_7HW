"""AI 可以呼叫的四個工具；只有這裡負責查詢和計算。"""

import json
import sqlite3
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from database import DB_PATH, connect

TOPICS = [
    "store_name", "opening_hours", "address", "payment", "parking", "services",
    "pickup", "returns", "contact", "checkout_rules",
]


def tool_definition(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object", "properties": properties,
                "required": required, "additionalProperties": False,
            },
        },
    }


TOOL_DEFINITIONS = [
    tool_definition(
        "get_shop_info",
        "查便利商店資訊。營業時間 opening_hours、地址 address、付款 payment、停車 parking、"
        "服務 services、自取 pickup、退換貨 returns、聯絡 contact、優惠及袋子費 checkout_rules。",
        {"topic": {"type": "string", "enum": TOPICS}}, ["topic"],
    ),
    tool_definition(
        "search_products",
        "按商品名稱、別名、分類或商品編號查價格、庫存、是否供應和第二件優惠。"
        "例如拿鐵、飲料、P002；空字串可列出所有商品。計算前先用此工具取得商品編號。",
        {"keyword": {"type": "string"}}, ["keyword"],
    ),
    tool_definition(
        "calculate_checkout",
        "試算購物總價：從資料庫取得售價和優惠，同商品每兩件套用第二件優惠，再加購物袋費。"
        "商品需使用 search_products 查到的 product_id。這是報價，不會下單、付款或扣庫存。",
        {
            "items": {
                "type": "array", "minItems": 1, "maxItems": 30,
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["product_id", "quantity"], "additionalProperties": False,
                },
            },
            "bag_quantity": {"type": "integer", "minimum": 0, "maximum": 20},
        }, ["items"],
    ),
    tool_definition(
        "transfer_to_human",
        "客人要求真人、客訴，或工具查不到所需資訊時，提供真人聯絡方式。"
        "只提供聯絡資訊，不代表已經轉接或通知任何人。",
        {"reason": {"type": "string"}}, ["reason"],
    ),
]


class StoreTools:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.functions = {
            "get_shop_info": self.get_shop_info,
            "search_products": self.search_products,
            "calculate_checkout": self.calculate_checkout,
            "transfer_to_human": self.transfer_to_human,
        }

    def get_shop_info(self, topic):
        if not isinstance(topic, str):
            raise ValueError("topic 必須是文字。")
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT topic, content FROM shop_info WHERE topic = ?", (topic,)
            ).fetchone()
        if row is None:
            return {"found": False, "topic": topic, "available_topics": TOPICS}
        content = row["content"]
        if content.startswith("{"):
            content = json.loads(content)
        return {"found": True, "topic": topic, "content": content}

    def search_products(self, keyword):
        if not isinstance(keyword, str) or len(keyword) > 100:
            raise ValueError("keyword 必須是 100 字以內的文字。")
        keyword = keyword.strip()
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """SELECT * FROM products WHERE
                   instr(lower(name), lower(?)) > 0 OR
                   instr(lower(aliases), lower(?)) > 0 OR
                   instr(lower(category), lower(?)) > 0 OR
                   lower(product_id) = lower(?) ORDER BY product_id""",
                (keyword, keyword, keyword, keyword),
            ).fetchall()
        return {"found": bool(rows), "currency": "TWD", "products": [dict(row) for row in rows]}

    def calculate_checkout(self, items, bag_quantity=0):
        if type(bag_quantity) is not int or not 0 <= bag_quantity <= 20:
            raise ValueError("bag_quantity 必須是 0–20 的整數。")
        if not isinstance(items, list) or not 1 <= len(items) <= 30:
            raise ValueError("items 必須包含 1–30 筆商品。")
        quantities = defaultdict(int)
        for item in items:
            if not isinstance(item, dict) or set(item) != {"product_id", "quantity"}:
                raise ValueError("每筆商品只能包含 product_id 和 quantity。")
            product_id, quantity = item["product_id"], item["quantity"]
            if not isinstance(product_id, str) or type(quantity) is not int or not 1 <= quantity <= 100:
                raise ValueError("商品編號需為文字，數量需為 1–100 的整數。")
            quantities[product_id.strip().upper()] += quantity
        if any(quantity > 100 for quantity in quantities.values()):
            raise ValueError("同商品合計最多 100 件。")

        policy = self.get_shop_info("checkout_rules")["content"]
        lines, issues = [], []
        with connect(self.db_path) as connection:
            for product_id, quantity in quantities.items():
                row = connection.execute(
                    "SELECT * FROM products WHERE product_id = ?", (product_id,)
                ).fetchone()
                if row is None:
                    issues.append({"product_id": product_id, "error": "not_found"})
                    continue
                if not row["available"] or quantity > row["stock"]:
                    issues.append({
                        "product_id": product_id, "error": "unavailable_or_insufficient_stock",
                        "available": bool(row["available"]), "stock": row["stock"],
                    })
                    continue
                price = row["price_twd"]
                discounted_units = quantity // 2 if row["second_item_offer"] else 0
                second_price = int(
                    (Decimal(price) * Decimal(policy["second_item_percent"]) / 100)
                    .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
                discount = discounted_units * (price - second_price)
                lines.append({
                    "product_id": product_id, "name": row["name"], "quantity": quantity,
                    "unit_price_twd": price, "discounted_units": discounted_units,
                    "original_subtotal_twd": quantity * price,
                    "discounted_unit_price_twd": second_price if discounted_units else None,
                    "promotion_label": (
                        f"同商品第二件{Decimal(policy['second_item_percent']) / 10:g}折"
                        if discounted_units else None
                    ),
                    "discount_twd": discount, "subtotal_twd": quantity * price - discount,
                })
        if issues:
            return {"ok": False, "issues": issues}
        subtotal = sum(line["subtotal_twd"] for line in lines)
        bag_fee = bag_quantity * policy["bag_price_twd"]
        return {
            "ok": True, "currency": "TWD", "quote_only": True, "lines": lines,
            "original_goods_subtotal_twd": sum(line["original_subtotal_twd"] for line in lines),
            "goods_subtotal_twd": subtotal, "discount_twd": sum(line["discount_twd"] for line in lines),
            "bag_quantity": bag_quantity, "bag_unit_price_twd": policy["bag_price_twd"],
            "bag_fee_twd": bag_fee, "total_twd": subtotal + bag_fee,
        }

    def transfer_to_human(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason 必須是非空白文字。")
        return {
            "status": "contact_provided", "connected": False, "reason": reason,
            "contact": self.get_shop_info("contact")["content"],
        }

    def execute(self, name, raw_arguments):
        """工具白名單；不執行模型提供的 SQL 或任意程式。"""
        if name not in self.functions:
            return {"ok": False, "error": "unknown_tool"}
        try:
            arguments = json.loads(raw_arguments)
        except (json.JSONDecodeError, TypeError):
            return {"ok": False, "error": "invalid_json"}
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "arguments_must_be_object"}
        try:
            return self.functions[name](**arguments)
        except (TypeError, ValueError) as error:
            return {"ok": False, "error": "invalid_arguments", "detail": str(error)}
        except sqlite3.Error:
            return {"ok": False, "error": "database_error"}
