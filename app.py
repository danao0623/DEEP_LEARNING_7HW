"""HW7：Gradio 介面 -> AI Agent -> 工具 -> SQLite。"""

import gradio as gr

from agent import read_settings, run_agent
from database import initialize_database
from store_tools import StoreTools


GREETING = "你好！我是巷口便利商店的小幫手，可以查詢商品、營業資訊，或幫你試算優惠後的金額。"
EXAMPLES = [
    "你們幾點營業？",
    "熱拿鐵多少錢？還有庫存嗎？",
    "買 3 杯中杯熱拿鐵，再加 1 個購物袋，總共多少錢？",
    "你們有賣榴槤嗎？",
    "我要找真人客服。",
    "幫我寫一首詩。",
]


def create_app():
    # 1. 啟動時：從兩份 CSV 建立資料庫。
    initialize_database()
    toolkit = StoreTools()

    def respond(message, history):
        # 2. 送出問題時：把本次問題與對話歷史交給 AI Agent。
        result = run_agent(message, history, toolkit=toolkit)
        # 3. 同時更新聊天回答和右側工具軌跡。
        return result.answer, result.trace

    with gr.Blocks(title="巷口便利商店客服", analytics_enabled=False) as demo:
        gr.Markdown("# 巷口便利商店客服")
        gr.Markdown("教學示範商店，商品、價格、地址與聯絡資訊均為虛構；提供查詢與優惠試算。")
        if not read_settings()["API_KEY"]:
            gr.Markdown("**尚未設定模型金鑰：** 請在專案的 `.env` 填入 `API_KEY`，再開始提問。")
        trace = gr.JSON(value=[], label="工具軌跡：名稱、參數、結果", render=False, open=True, max_height=540)
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    value=[{"role": "assistant", "content": GREETING}], height=460,
                    label="客服對話", buttons=["copy"],
                )
                gr.ChatInterface(
                    fn=respond, chatbot=chatbot, additional_outputs=[trace],
                    textbox=gr.Textbox(placeholder="輸入你的問題…", label="問題"),
                    examples=EXAMPLES, examples_label="試試這些問題", run_examples_on_click=False,
                    flagging_mode="never", analytics_enabled=False, api_name="chat", fill_height=False,
                )
            with gr.Column(scale=2):
                trace.render()
        chatbot.clear(fn=lambda: [], outputs=trace, queue=False)
    return demo


if __name__ == "__main__":
    create_app().launch(inbrowser=True, server_name="127.0.0.1", share=False)
