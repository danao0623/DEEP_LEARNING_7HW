"""以預先固定的 10 題驗證真實模型工具選擇，保存逐題回答和工具軌跡。"""

import argparse
import hashlib
import json
import re
import time
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from openai import OpenAI

from agent import SYSTEM_PROMPT, read_settings, run_agent
from database import BASE_DIR, initialize_database
from store_tools import StoreTools, TOOL_DEFINITIONS

CASE_FILE = BASE_DIR / "tool_choice_cases.json"


def now():
    return datetime.now(ZoneInfo("Asia/Taipei")).isoformat()


def evidence_matches(case, trace):
    """檢查必要參數與資料結果；回答文字另外逐題審閱。"""
    expected = case["evidence"]
    if "info_topic" in expected and not any(
        entry["tool"] == "get_shop_info"
        and entry["arguments"].get("topic") == expected["info_topic"]
        and entry["result"].get("found") is True for entry in trace
        if isinstance(entry["arguments"], dict)
    ):
        return False
    if "product" in expected:
        products = [
            product for entry in trace if entry["tool"] == "search_products"
            for product in entry["result"].get("products", [])
        ]
        if not any(all(product.get(key) == value for key, value in expected["product"].items()) for product in products):
            return False
    if "checkout" in expected:
        quote_expected = expected["checkout"]
        seen_products, valid_quote = set(), False
        for entry in trace:
            if entry["tool"] == "search_products":
                seen_products.update(product["product_id"] for product in entry["result"].get("products", []))
            if entry["tool"] == "calculate_checkout":
                quote = entry["result"]
                quantities = {line["product_id"]: line["quantity"] for line in quote.get("lines", [])}
                if (
                    quote.get("ok") is True
                    and quantities == quote_expected["quantities"]
                    and set(quantities).issubset(seen_products)
                    and all(quote.get(key) == quote_expected[key] for key in ["bag_quantity", "discount_twd", "total_twd"])
                ):
                    valid_quote = True
        if not valid_quote:
            return False
    if expected.get("missing_product") and not any(
        entry["tool"] == "search_products" and entry["result"].get("found") is False for entry in trace
    ):
        return False
    if expected.get("human_contact") and not any(
        entry["tool"] == "transfer_to_human"
        and entry["result"].get("status") == "contact_provided"
        and entry["result"].get("connected") is False
        and bool(entry["result"].get("contact", {}).get("email")) for entry in trace
    ):
        return False
    return True


def grade_case(case, result):
    names = [entry["tool"] for entry in result.trace]
    allowed = set(case["required_tools"] + case["optional_tools"])
    checks = {
        "completed": result.status == "ok",
        "required_tools_present": set(case["required_tools"]).issubset(names),
        "only_acceptable_tools": set(names).issubset(allowed),
        "required_order": all(
            first in names and second in names and names.index(first) < names.index(second)
            for first, second in case["must_precede"]
        ),
        "tool_execution_succeeded": all(
            entry["result"].get("ok") is not False and "error" not in entry["result"] for entry in result.trace
        ),
        "parameters_and_data_match": evidence_matches(case, result.trace),
    }
    return {"checks": checks, "tool_choice_pass": all(checks.values())}


class PacedCompletions:
    """每次真實 API 請求至少間隔 5 秒，最多約 12 次／分鐘。"""

    def __init__(self, client):
        self.client = client
        self.last_started = None

    def create(self, **request):
        if self.last_started is not None:
            delay = 5.0 - (time.monotonic() - self.last_started)
            if delay > 0:
                time.sleep(delay)
        self.last_started = time.monotonic()
        return self.client.chat.completions.create(**request)


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def tools_text(case, english=False):
    required = " → ".join(case["required_tools"]) or ("None" if english else "不呼叫工具")
    if case["optional_tools"]:
        required += ("; optional: " if english else "；可加用：") + ", ".join(case["optional_tools"])
    return required


def write_reports(payload, directory):
    records, metadata = payload["results"], payload["metadata"]
    passed = sum(record["tool_choice_pass"] for record in records)
    reviewed = [record for record in records if record.get("answer_review") is not None]
    content_passed = sum(record["answer_review"]["passed"] for record in reviewed)
    for english, filename in [(False, "report-zh.md"), (True, "report-en.md")]:
        total = len(records)
        score = f"{passed}/{total} ({passed / total:.0%})" if total else "Pending"
        content = f"{content_passed}/{len(reviewed)}" if reviewed else ("Pending review" if english else "尚待逐題檢查")
        lines = [
            "# Tool-Choice Test Results" if english else "# 10 題工具選擇測試結果",
            "",
            (f"Tool-choice accuracy: **{score}**. Content review: **{content}**."
             if english else f"工具選擇準確率：**{score}**。回答內容檢查：**{content}**。"),
            "",
            (f"Model: `{metadata['model']}`. Started: {metadata['started_at']}."
             if english else f"模型：`{metadata['model']}`。開始時間：{metadata['started_at']}（Asia/Taipei）。"),
            "",
            ("Ten questions and their acceptable tools were fixed before the run in `tool_choice_cases.json`. "
             "Each question uses an independent conversation with empty history and the actual application agent. "
             "Requests are sent to the configured real model API, at least five seconds apart. No mocks are used."
             if english else "測試前已在 `tool_choice_cases.json` 固定 10 題問題及可接受工具；"
             "每題使用空白對話歷史，呼叫應用程式原本的 Agent 與真實模型 API，沒有使用模擬回覆。"
             "每次 API 請求至少間隔 5 秒。"),
            "",
            ("A tool-choice pass requires successful completion, all required tools, no tools outside the "
             "predefined acceptable set, the required order, valid execution, and matching data/parameters. "
             "Repeated lookups and explicitly listed optional tools are allowed. Answer content is reviewed "
             "separately against the CSV facts and tool results. For the out-of-scope case, no tool calls "
             "alone do not establish that the model refused."
             if english else "工具判定通過的條件：完成回答、使用所有必要工具、沒有用到允許範圍外的工具、"
             "符合先後順序、工具執行無錯誤，且必要參數與查詢／計算結果正確。可重複查詢，也可使用事前列出的選用工具。"
             "回答內容另外依 CSV 和工具結果逐題檢查；範圍外問題不能只因為沒有呼叫工具就算回答正確。"),
            "",
            ("| ID | Question | Acceptable tools | Actual tools (in order) | Tool result | Content review |"
             if english else "| 題號 | 問題 | 可接受工具 | 實際工具（依序） | 工具判定 | 內容檢查 |"),
            "|---|---|---|---|---|---|",
        ]
        for record in records:
            review = record.get("answer_review")
            judgement = ("Pass" if record["tool_choice_pass"] else "Fail") if english else ("通過" if record["tool_choice_pass"] else "未通過")
            if english:
                content_judgement = ("Pass" if review["passed"] else "Fail") if review is not None else "Pending"
            else:
                content_judgement = ("通過" if review["passed"] else "未通過") if review is not None else "待檢查"
            actual = " → ".join(entry["tool"] for entry in record["trace"]) or ("None" if english else "無")
            question = record["question_en"] if english else record["question"]
            lines.append("| " + " | ".join(map(cell, [record["id"], question, tools_text(record, english), actual, judgement, content_judgement])) + " |")
        lines += ["", "## Detailed Responses" if english else "## 逐題回答與檢查", ""]
        for record in records:
            review = record.get("answer_review")
            lines += [
                f"### {record['id']} — {record['category']}", "",
                ("Expected: " + record["expected_outcome_en"] if english else "預期：" + record["expected_outcome"]),
                "", "**Original model response:**" if english else "**模型原始回答：**", "",
                *["> " + line for line in record["answer"].strip().splitlines()], "",
                (f"Status: `{record['status']}`; model calls: {record['model_calls']}; elapsed: {record['elapsed_seconds']} s."
                 if english else f"狀態：`{record['status']}`；模型呼叫：{record['model_calls']} 次；耗時：{record['elapsed_seconds']} 秒。"),
            ]
            failed_checks = [name for name, value in record["checks"].items() if not value]
            if failed_checks:
                lines += ["", ("Failed checks: " if english else "未通過檢查：") + ", ".join(failed_checks)]
            if review:
                lines += ["", ("Content review: " + review["note_en"] if english else "內容檢查：" + review["note_zh"])]
            lines += [""]
        change_notes = metadata.get("change_notes_en" if english else "change_notes_zh")
        if change_notes:
            lines += ["## Changes and Retesting" if english else "## 修正與重測說明", "", change_notes, ""]
        lines += [
            "## Interpretation and Reproduction" if english else "## 解讀與重跑方式", "",
            ("This score describes this fixed ten-question set. Complete tool arguments/results, timings and "
             "source/data hashes are retained in `results.json`. Answer review notes are by Codex. "
             "These real-model tests are separate from the offline unit tests."
             if english else "此分數代表這組固定 10 題的觀察結果。完整工具參數、回傳結果、耗時，以及程式／資料雜湊保存在 `results.json`。"
             "內容檢查註記由 Codex 依實際回答逐題整理，與離線程式測試分開計算。"),
            "", "```powershell", "python evaluate_tool_choices.py --label repeat", "```", "",
            ("Each run creates a new timestamped directory; earlier runs are preserved. API keys are never saved in the results."
             if english else "每次執行會建立新的時間戳記資料夾，保留先前結果；結果不會存入 API 金鑰。"), "",
        ]
        (directory / filename).write_text("\n".join(lines), encoding="utf-8")


def evaluate(label):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", label):
        raise ValueError("label 僅能使用 1–40 個英數字、底線或連字號。")
    settings = read_settings()
    if not settings["API_KEY"]:
        raise SystemExit("請先在專案 .env 填入 API_KEY。")
    cases = json.loads(CASE_FILE.read_text(encoding="utf-8"))
    if len(cases) != 10 or len({case["id"] for case in cases}) != 10:
        raise ValueError("測試集必須包含 10 題、且題號不得重複。")
    initialize_database()
    stamp = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y%m%d-%H%M%S")
    directory = BASE_DIR / "test-results" / f"tool-choice-{stamp}-{label}"
    directory.mkdir()
    (directory / "cases.json").write_bytes(CASE_FILE.read_bytes())
    (directory / "system-prompt.txt").write_text(SYSTEM_PROMPT, encoding="utf-8")
    (directory / "tool-definitions.json").write_text(json.dumps(TOOL_DEFINITIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    source_files = ["agent.py", "store_tools.py", "database.py", "shop_info.csv", "products.csv", CASE_FILE.name]
    payload = {
        "metadata": {
            "started_at": now(), "model": settings["MODEL_NAME"],
            "provider_host": urlsplit(settings["LLM_API_URL"]).hostname,
            "sdk_version": version("openai"), "planned_questions": 10,
            "max_steps": 6, "request_interval_seconds": 5,
            "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            "source_sha256": {name: hashlib.sha256((BASE_DIR / name).read_bytes()).hexdigest() for name in source_files},
        },
        "results": [],
    }
    output = directory / "results.json"
    save = lambda: output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    save()
    print(f"Results directory: {directory}", flush=True)
    toolkit = StoreTools()
    with OpenAI(api_key=settings["API_KEY"], base_url=settings["LLM_API_URL"], timeout=30.0, max_retries=0) as real_client:
        proxy = SimpleNamespace(chat=SimpleNamespace(completions=PacedCompletions(real_client)))
        for case in cases:
            started = time.monotonic()
            result = run_agent(case["question"], [], client=proxy, toolkit=toolkit)
            record = {
                **case, "tested_at": now(), "status": result.status,
                "model_calls": result.model_calls, "elapsed_seconds": round(time.monotonic() - started, 2),
                "answer": result.answer, "trace": result.trace, **grade_case(case, result),
                "answer_review": None,
            }
            payload["results"].append(record)
            save()
            print(json.dumps({
                "id": case["id"], "question": case["question"],
                "actual_tools": [entry["tool"] for entry in result.trace],
                "tool_choice_pass": record["tool_choice_pass"],
                "failed_checks": [name for name, value in record["checks"].items() if not value],
                "answer": result.answer,
            }, ensure_ascii=False), flush=True)
    payload["metadata"]["finished_at"] = now()
    save()
    write_reports(payload, directory)
    passed = sum(record["tool_choice_pass"] for record in payload["results"])
    print(f"Tool-choice score: {passed}/10. Content review is still pending.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="initial")
    parser.add_argument("--report-only", type=Path, help="既有 results.json；只重新產生報告，不呼叫 API")
    arguments = parser.parse_args()
    if arguments.report_only:
        path = arguments.report_only.resolve()
        write_reports(json.loads(path.read_text(encoding="utf-8")), path.parent)
    else:
        evaluate(arguments.label)
