# Tool-Choice Test Results

Tool-choice accuracy: **10/10 (100%)**. Content review: **10/10**.

Model: `Furen-large`. Started: 2026-10-26T16:40:53.386568+08:00.

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

> 我們每天的營業時間是早上 07:00 開門，晚上 23:00 打烊。這是每日固定的時間，示範資料中未提供特別節日的調整。若有其他問題，隨時告訴我！

Status: `ok`; model calls: 2; elapsed: 6.41 s.

Content review: The 07:00–23:00 hours match the database; holiday adjustments are correctly described as unspecified.

### T02 — Information

Expected: Confirm cash and credit cards without inventing other payment methods.

**Original model response:**

> 本店接受現金與信用卡付款。若有其他付款方式的需求，建議直接向店員確認。祝您購物愉快！

Status: `ok`; model calls: 2; elapsed: 9.77 s.

Content review: Cash and credit cards are correctly confirmed without inventing another payment method.

### T03 — Information

Expected: State that the store has no dedicated parking and do not invent nearby parking information.

**Original model response:**

> 門市沒有專用停車場。  
> 示範資料中也未提供附近停車資訊。  
> 如需其他店家資訊或商品查詢，隨時告訴我！

Status: `ok`; model calls: 2; elapsed: 10.94 s.

Content review: The response correctly reports no dedicated parking and no nearby parking information.

### T04 — Product lookup

Expected: Report a TWD 55 unit price and stock of 30, with no unnecessary checkout calculation.

**Original model response:**

> 中杯熱拿鐵的售價是 **55 元 TWD**，目前庫存有 **30 杯**。如需購買或有其他問題，隨時告訴我！

Status: `ok`; model calls: 2; elapsed: 9.59 s.

Content review: The TWD 55 price and stock of 30 match P002.

### T05 — Availability

Expected: Clearly report that the umbrella is unavailable or out of stock.

**Original model response:**

> 目前我們的「折疊雨傘」庫存為 0，也就是暫時無法購買。若您想知道何時會補貨，或有其他購物需求，我很樂意為您轉接人工客服協助。請問是否需要我提供真人聯絡方式？

Status: `ok`; model calls: 2; elapsed: 12.84 s.

Content review: The zero stock and unavailability are correct. The offer of further help does not claim an actual completed transfer.

### T06 — Calculation

Expected: Use the calculator's TWD 145 total and correctly describe the same-product second item as 60% of its regular price.

**Original model response:**

> 買 3 杯中杯熱拿鐵（單價 55 元）適用「同商品第二件6折」優惠，商品小計為 143 元；再加購 1 個購物袋（每個 2 元），總計 145 元。優惠詳情為：第二杯拿鐵以原價的 6 折計算（33 元），第一杯與第三杯各 55 元，購物袋費用 2 元。

Status: `ok`; model calls: 3; elapsed: 14.17 s.

Content review: The answer correctly uses the TWD 145 tool total, 60%-price second item and TWD 33 discounted unit price.

### T07 — Calculation

Expected: Use the calculator's TWD 104 total (45 + 55 + 4) and explain that different products cannot form a promotional pair.

**Original model response:**

> 中杯熱美式咖啡 45 元、中杯熱拿鐵 55 元，商品小計 100 元；兩個購物袋每個 2 元，共 4 元，總計 **104 元**。  
> 第二件優惠僅適用於**同一商品**（例如兩杯熱美式咖啡或兩杯熱拿鐵），因此這兩種不同的咖啡無法共用該優惠。  
> 如需其他組合或有其他問題，隨時告訴我！

Status: `ok`; model calls: 4; elapsed: 19.59 s.

Content review: The response correctly disallows mixing products into a pair and reports TWD 100 for goods plus TWD 4 for bags, totaling TWD 104.

### T08 — Missing data

Expected: Search first, acknowledge missing product information and provide human contact details without claiming a real transfer.

**Original model response:**

> 查不到榴榴槤的販售資訊。您可於服務時間內聯絡我們：service@corner-demo.example，服務時間為每日 09:00–18:00。如需進一步協助，請隨時與我們聯絡。

Status: `ok`; model calls: 3; elapsed: 14.12 s.

Content review: The response acknowledges missing data and provides the correct human email and hours. A duplicated Chinese character in the product name is retained as a wording typo; it does not change the tool or factual result.

### T09 — Human contact

Expected: Use the handoff tool to provide service@corner-demo.example and service hours without claiming an actual transfer.

**Original model response:**

> 以下是本店的真人客服聯絡方式，供您客訴時使用：
> 
> - **電子郵件**：service@corner-demo.example  
> - **服務時間**：每日 09:00–18:00  
> 
> （此為示範環境提供的聯絡資訊，實際轉接需由真人客服人員依據情況處理。）如果您有其他關於本店商品、營業資訊或優惠試算的問題，隨時告訴我！

Status: `ok`; model calls: 2; elapsed: 11.12 s.

Content review: The email and 09:00–18:00 service hours are correct, with no claim of a completed transfer.

### T10 — Out of scope

Expected: Call no tools, politely refuse the creative-writing request and redirect to store-related assistance.

**Original model response:**

> 我只能協助本店商品、營業資訊與優惠試算，請問你想查詢什麼？

Status: `ok`; model calls: 1; elapsed: 1.8 s.

Content review: The model refuses the poem, redirects to store assistance and calls no tools.

## Changes and Retesting

The initial formal run passed 10/10. A later screenshot check of the durian question omitted human contact and overstated missing data as confirmed non-sale. I added an explicit found=false workflow and example, confirmed that the same question now called search_products followed by transfer_to_human, and repeated the unchanged ten-question set. The retest passed 10/10. The initial formal results, additional failure and this retest are all retained; the extra manual case is not treated as a different baseline score.

## Interpretation and Reproduction

This score describes this fixed ten-question set. Complete tool arguments/results, timings and source/data hashes are retained in `results.json`. Answer review notes are by Codex. These real-model tests are separate from the offline unit tests.

```powershell
python evaluate_tool_choices.py --label repeat
```

Each run creates a new timestamped directory; earlier runs are preserved. API keys are never saved in the results.
