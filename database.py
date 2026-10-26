"""啟動時，將同一資料夾的 CSV 載入 SQLite。"""

import csv
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "store.db"


@contextmanager
def connect(db_path=DB_PATH):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def initialize_database(db_path=DB_PATH):
    """CSV 是資料來源；每次啟動都重新載入示範資料。"""
    with (BASE_DIR / "shop_info.csv").open(encoding="utf-8-sig", newline="") as source:
        info = list(csv.DictReader(source))
    with (BASE_DIR / "products.csv").open(encoding="utf-8-sig", newline="") as source:
        products = list(csv.DictReader(source))
    if len(info) < 8 or len(products) < 15:
        raise ValueError("資訊表至少需要 8 筆，商品表至少需要 15 筆。")

    with connect(db_path) as connection, connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS shop_info "
            "(topic TEXT PRIMARY KEY, content TEXT NOT NULL)"
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price_twd INTEGER NOT NULL CHECK(price_twd > 0),
                available INTEGER NOT NULL CHECK(available IN (0, 1)),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                second_item_offer INTEGER NOT NULL CHECK(second_item_offer IN (0, 1)),
                aliases TEXT NOT NULL
            )"""
        )
        connection.execute("DELETE FROM shop_info")
        connection.execute("DELETE FROM products")
        connection.executemany(
            "INSERT INTO shop_info(topic, content) VALUES (?, ?)",
            [(row["topic"], row["content"]) for row in info],
        )
        connection.executemany(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["product_id"], row["name"], row["category"],
                    int(row["price_twd"]), int(row["available"]), int(row["stock"]),
                    int(row["second_item_offer"]), row["aliases"],
                )
                for row in products
            ],
        )
    return {"shop_info": len(info), "products": len(products)}
