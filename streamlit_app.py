import streamlit as st
import requests
import json
import time
from datetime import datetime
import pandas as pd

# --- 核心逻辑函数 ---
def get_binance_price(symbol):
    if not symbol: return "N/A"
    try:
        url = "https://fapi.binance.com/fapi/v1/ticker/price"
        resp = requests.get(url, params={"symbol": symbol.upper().strip()}, timeout=5)
        return resp.json().get("price", "N/A") if resp.status_code == 200 else f"Error({resp.status_code})"
    except: return "Connect Error"

def get_polymarket_data(slug):
    try:
        resp = requests.get(f"https://gamma-api.polymarket.com/events/slug/{slug}", timeout=10)
        return resp.json().get('markets', []) if resp.status_code == 200 else []
    except: return []

def get_clob_price(token_id):
    try:
        url = "https://clob.polymarket.com/book"
        resp = requests.get(url, params={"token_id": token_id}, timeout=5)
        if resp.status_code == 200:
            bids = resp.json().get('bids', [])
            if bids: return max(bids, key=lambda x: float(x['price']))['price']
        return "N/A"
    except: return "ERR"

def send_feishu(webhook, binance_symbol, binance_price, poly_rows, slug):
    content = [f"🔥 **Binance {binance_symbol.upper()}:** `${binance_price}`", "---"]
    for r in poly_rows:
        content.append(f"**{r['name']}**\n🟢 YES | Bid: **{r['price']}**")
    
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"content": f"📊 监控报告: {slug}", "tag": "plain_text"}, "template": "blue"},
            "elements": [
                {"tag": "div", "text": {"content": f"🕒 **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "tag": "lark_md"}},
                {"tag": "hr"},
                {"tag": "div", "text": {"content": "\n\n".join(content), "tag": "lark_md"}}
            ]
        }
    }
    return requests.post(webhook, json=payload, timeout=10)

# --- UI 布局 ---
st.set_page_config(page_title="Crypto Monitor Pro", layout="wide")

if 'logs' not in st.session_state:
    st.session_state.logs = []

st.title("🛠️ 多源行情监控工作站")

# --- 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 全局配置")
    target_symbol = st.text_input("币安合约代码", value="MEGAUSDT")
    target_slug = st.text_input("Polymarket Slug", value="genius-fdv-above-one-day-after-launch")
    
    # 优先从 Secrets 读取 Webhook，如果没有则手动输入
    default_webhook = st.secrets.get("FEISHU_WEBHOOK", "https://open.feishu.cn/...")
    webhook_url = st.text_input("飞书 Webhook URL", value=default_webhook, type="password")
    
    refresh_rate = st.number_input("监控频率 (秒)", min_value=10, value=300)
    is_active = st.toggle("🚦 启动监控任务", value=False)

# --- 主界面 ---
col_price, col_log = st.columns([1, 2])

# 核心运行逻辑：利用 Streamlit 的自动循环
if is_active:
    b_price = get_binance_price(target_symbol)
    poly_raw = get_polymarket_data(target_slug)
    poly_final = []
    for m in poly_raw:
        m_name = m.get('groupItemTitle', 'Unknown')
        ids = json.loads(m['clobTokenIds']) if isinstance(m['clobTokenIds'], str) else m['clobTokenIds']
        poly_final.append({"name": m_name, "price": get_clob_price(ids[0])})
    
    # 推送并记录日志
    res = send_feishu(webhook_url, target_symbol, b_price, poly_final, target_slug)
    st.session_state.logs.insert(0, {
        "时间": datetime.now().strftime("%H:%M:%S"),
        "最新价": b_price,
        "状态": "成功" if res.status_code == 200 else f"失败({res.status_code})"
    })

    # 显示数据
    with col_price:
        st.metric(f"Binance {target_symbol}", f"${b_price}")
        st.table(pd.DataFrame(poly_final))
    
    with col_log:
        st.dataframe(pd.DataFrame(st.session_state.logs).head(15), use_container_width=True)

    # 关键：强制倒计时刷新
    time.sleep(refresh_rate)
    st.rerun()
else:
    st.info("💡 监控已停止。请开启左侧开关。")