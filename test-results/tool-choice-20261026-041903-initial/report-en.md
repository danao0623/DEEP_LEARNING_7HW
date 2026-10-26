# Tool-Choice Test Results

Tool-choice accuracy: **10/10 (100%)**. Content review: **10/10**.

Model: `Furen-large`. Started: 2026-10-26T04:19:03.789635+08:00.

Ten questions and their acceptable tools were fixed before the run in `tool_choice_cases.json`. Each question uses an independent conversation with empty history and the actual application agent. Requests are sent to the configured real model API, at least five seconds apart. No mocks are used.

A tool-choice pass requires successful completion, all required tools, no tools outside the predefined acceptable set, the required order, valid execution, and matching data/parameters. Repeated lookups and explicitly listed optional tools are allowed. Answer content is reviewed separately against the CSV facts and tool results. For the out-of-scope case, no tool calls alone do not establish that the model refused.

| ID | Question | Acceptable tools | Actual tools (in order) | Tool result | Content review |
|---|---|---|---|---|---|
| T01 | What time do you open and close each day? | get_shop_info | get_shop_info | Pass | Pass |
| T02 | Can I pay with cash or a credit card? | get_shop_info | get_shop_info | Pass | Pass |
| T03 | Do you have your own parking lot? | get_shop_info | get_shop_info | Pass | Pass |
| T04 | How much is a medium hot latte, and how many are in stock? | search_products | search_products | Pass | Pass |
| T05 | Is the folding umbrella available to buy now? | search_products | search_products | Pass | Pass |
| T06 | What is the total for three medium hot lattes and one shopping bag? Explain the applicable offer. | search_products → calculate_checkout; optional: get_shop_info | search_products → calculate_checkout | Pass | Pass |
| T07 | What is the total for one medium hot Americano, one medium hot latte and two bags? Can the different drinks form a promotional pair? | search_products → calculate_checkout; optional: get_shop_info | search_products → search_products → calculate_checkout | Pass | Pass |
| T08 | Do you sell durian? | search_products → transfer_to_human | search_products → transfer_to_human | Pass | Pass |
| T09 | I want to make a complaint. Please give me the human customer service contact details. | transfer_to_human; optional: get_shop_info | transfer_to_human | Pass | Pass |
| T10 | Please write a poem about a convenience store. | None | None | Pass | Pass |

## Detailed Responses

### T01 — Information

Expected: Report daily opening hours of 07:00–23:00 without inventing holiday hours.

**Original model response:**

> 我們每天的營業時間是早上 07:00 開門，晚上 23:00 打烊。祝您購物愉快！

Status: `ok`; model calls: 2; elapsed: 6.0 s.

Content review: The 07:00 opening time and 23:00 closing time match the information table, with no invented holiday hours.

### T02 — Information

Expected: Confirm cash and credit cards without inventing other payment methods.

**Original model response:**

> 可以。本店接受現金付款及信用卡刷卡，其他付款方式示範資料中未提供。若您還有其他付款相關問題，請隨時告訴我。

Status: `ok`; model calls: 2; elapsed: 10.12 s.

Content review: The response confirms cash and credit cards and states that other payment methods are not specified.

### T03 — Information

Expected: State that the store has no dedicated parking and do not invent nearby parking information.

**Original model response:**

> 我們的門市沒有專用停車場，且目前的示範資料中也沒有提供附近停車資訊。如果您需要了解附近的停車選擇，建議直接前往現場觀察或使用導航App查詢。如有其他問題，歡迎隨時詢問！

Status: `ok`; model calls: 2; elapsed: 11.06 s.

Content review: The response correctly states that there is no dedicated parking and no nearby parking data. It adds generic lookup advice without inventing a parking location.

### T04 — Product lookup

Expected: Report a TWD 55 unit price and stock of 30, with no unnecessary checkout calculation.

**Original model response:**

> 中杯熱拿鐵的售價是 **55 元 TWD**，目前庫存尚有 **30 杯**。如需購買或查詢其他商品，隨時告訴我！

Status: `ok`; model calls: 2; elapsed: 9.53 s.

Content review: The TWD 55 unit price and stock of 30 match product P002.

### T05 — Availability

Expected: Clearly report that the umbrella is unavailable or out of stock.

**Original model response:**

> 折疊雨傘目前庫存為 0，暫時無法購買。您想看看其他類似的商品，或是有其他需要幫忙的嗎？

Status: `ok`; model calls: 2; elapsed: 10.19 s.

Content review: The response correctly interprets available=0 and stock=0 as unavailable rather than treating a search match as available stock.

### T06 — Calculation

Expected: Use the calculator's TWD 145 total and correctly describe the same-product second item as 60% of its regular price.

**Original model response:**

> 買 3 杯中杯熱拿鐵（單價 55 元）適用「同商品第二件6折」優惠，加上 1 個購物袋（每個 2 元），總計 **145 元**（含袋子費 2 元）。
> 
> 明細如下：
> - 中杯熱拿鐵 3 杯：原價 165 元 → 折扣 22 元（第二件 6 折） → 小計 143 元  
> - 購物袋 1 個：2 元  
> - **合計：145 元**  
> 
> 如需其他商品或調整數量，請告訴我！

Status: `ok`; model calls: 3; elapsed: 15.41 s.

Content review: The same-product second-item offer is correctly described as 60% of regular price. The TWD 22 discount, TWD 143 subtotal, TWD 2 bag and TWD 145 total match the tool result.

### T07 — Calculation

Expected: Use the calculator's TWD 104 total (45 + 55 + 4) and explain that different products cannot form a promotional pair.

**Original model response:**

> 合計 104 元（商品小計 100 元 + 2 個購物袋 4 元）。  
> 因為第二件優惠只適用於「同一商品」的第二件，熱美式咖啡和熱拿屬於不同商品，所以無法湊成折扣。  
> 若您想使用優惠，可考慮購買兩杯同款（例如兩杯熱美式咖啡或兩杯熱拿鐵）。

Status: `ok`; model calls: 4; elapsed: 19.92 s.

Content review: The response correctly disallows pairing different products and reports a TWD 100 goods subtotal plus TWD 4 for bags, totaling TWD 104 with no discount.

### T08 — Missing data

Expected: Search first, acknowledge missing product information and provide human contact details without claiming a real transfer.

**Original model response:**

> 我目前查不到店內有販售榴槤的資料。若您想進一步確認或有其他需求，可以透過以下方式聯絡我們：
> 
> - 電子郵件：service@corner-demo.example  
> - 服務時間：每日 09:00–18:00（此為示範系統提供的聯絡方式）  
> 
> 有其他關於本店商品、營業資訊或優惠試算的問題嗎？請告訴我！

Status: `ok`; model calls: 3; elapsed: 15.99 s.

Content review: The response acknowledges missing durian information and provides the demo email address and service hours without claiming an actual notification or transfer.

### T09 — Human contact

Expected: Use the handoff tool to provide service@corner-demo.example and service hours without claiming an actual transfer.

**Original model response:**

> 您好，這裡是提供真人客服的聯絡方式：
> 
> - 電子郵件：service@corner-demo.example  
> - 服務時間：每日 09:00–18:00  
> 
> （此為教學示範資料，僅供參考。）

Status: `ok`; model calls: 2; elapsed: 8.09 s.

Content review: The response provides the correct demo email and 09:00–18:00 service hours without claiming an actual transfer.

### T10 — Out of scope

Expected: Call no tools, politely refuse the creative-writing request and redirect to store-related assistance.

**Original model response:**

> 我只能協助本店商品、營業資訊與優惠試算，請問你想查詢什麼？

Status: `ok`; model calls: 1; elapsed: 5.62 s.

Content review: The response refuses creative writing and redirects to products, opening information and quotes. It produces no poem and calls no tools.

## Changes and Retesting

This was the first formal run of the predefined ten-question set on the current version. All ten tool choices and answer-content checks passed, so no additional fix or retest was needed in this round. The agent, tools, CSV files and predefined questions remained unchanged during the run; their source hashes were checked. Earlier connection checks exposed unwanted poem generation and a 60%-price offer being described as half price. Before the formal run, the scope rules were strengthened, the calculator was extended to return the exact offer label and pricing details, and the model was instructed to quote the returned label. Original failures and retests remain in the parent directory as live-agent-checks.json, live-scope-retest.json, live-gradio.json and live-gradio-final.json. Those earlier integration checks are not treated as a baseline score for this ten-question set.

## Interpretation and Reproduction

This score describes this fixed ten-question set. Complete tool arguments/results, timings and source/data hashes are retained in `results.json`. Answer review notes are by Codex. These real-model tests are separate from the offline unit tests.

```powershell
python evaluate_tool_choices.py --label repeat
```

Each run creates a new timestamped directory; earlier runs are preserved. API keys are never saved in the results.
