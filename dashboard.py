"""
لوحة تحكم Streamlit — Samer Imperial Bot v4.0
تشغيل: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import json
import os
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Samer Imperial Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

WALLET_FILE = "data/wallet.json"
TRADES_FILE = "data/trades.csv"
BRAIN_FILE  = "data/brain.json"
LOG_FILE    = "logs/bot.log"

# ─────────────────────────────────────────────
#  تحميل البيانات
# ─────────────────────────────────────────────
def load_wallet():
    if os.path.exists(WALLET_FILE):
        with open(WALLET_FILE) as f:
            return json.load(f)
    return {}

def load_brain():
    if os.path.exists(BRAIN_FILE):
        with open(BRAIN_FILE) as f:
            return json.load(f)
    return {}

def load_trades():
    if os.path.exists(TRADES_FILE):
        df = pd.read_csv(TRADES_FILE)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    return pd.DataFrame()

def load_logs(n=100):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    return "لا توجد سجلات بعد."

# ─────────────────────────────────────────────
#  CSS مخصص
# ─────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #3a3a5e;
    text-align: center;
}
.metric-val  { font-size: 2rem; font-weight: bold; color: #00d4aa; }
.metric-lbl  { font-size: 0.85rem; color: #aaa; margin-top: 4px; }
.win  { color: #00d4aa; }
.loss { color: #ff4b4b; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  الشريط الجانبي
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🤖 Samer Imperial Bot")
    st.caption("v4.0 — Self-Learning Edition")
    st.divider()
    auto_refresh = st.toggle("🔄 تحديث تلقائي (15 ث)", value=False)
    if auto_refresh:
        st.cache_data.clear()
        import time; time.sleep(15); st.rerun()
    st.divider()
    page = st.radio("📌 الصفحة", ["📊 لوحة التحكم", "📈 الصفقات", "🧠 نظام التعلم", "📋 السجلات"])

wallet = load_wallet()
brain  = load_brain()
trades = load_trades()

# ═══════════════════════════════════════════════
#  صفحة لوحة التحكم
# ═══════════════════════════════════════════════
if page == "📊 لوحة التحكم":
    st.title("📊 لوحة التحكم الرئيسية")
    st.caption(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not wallet:
        st.warning("⚠️ لم يبدأ البوت بعد — شغّل bot.py أولاً")
        st.stop()

    # ── المقاييس الرئيسية ──
    c1, c2, c3, c4 = st.columns(4)
    init  = wallet.get("initial_balance", 1000)
    curr_bal = wallet.get("usd", 0) + wallet.get("coin", 0) * wallet.get("entry_price", 0)
    pnl_pct  = (curr_bal - init) / init * 100 if init else 0
    n_trades = brain.get("total_trades", 0)
    wins     = brain.get("win_trades", 0)
    wr       = wins / n_trades * 100 if n_trades else 0

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">${curr_bal:,.2f}</div>
            <div class="metric-lbl">💰 إجمالي الرصيد</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        color = "#00d4aa" if pnl_pct >= 0 else "#ff4b4b"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val" style="color:{color}">{pnl_pct:+.2f}%</div>
            <div class="metric-lbl">📈 الربح/الخسارة الكلية</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val">{wr:.1f}%</div>
            <div class="metric-lbl">🎯 معدل الفوز</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        status = "🟢 يتداول" if wallet.get("is_holding") else "🔵 ينتظر"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-val" style="font-size:1.4rem">{status}</div>
            <div class="metric-lbl">⚡ حالة البوت</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # ── رسم منحنى الرصيد ──
    if not trades.empty:
        sells = trades[trades["action"] == "SELL"].copy()
        if not sells.empty:
            sells = sells.sort_values("timestamp")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=sells["timestamp"], y=sells["balance_after"],
                mode="lines+markers", name="الرصيد",
                line=dict(color="#00d4aa", width=2),
                fill="tozeroy", fillcolor="rgba(0,212,170,0.1)"
            ))
            fig.add_hline(y=init, line_dash="dash", line_color="gray",
                          annotation_text="الرصيد الابتدائي")
            fig.update_layout(
                title="📈 منحنى نمو الرصيد",
                xaxis_title="التاريخ", yaxis_title="الرصيد ($)",
                template="plotly_dark", height=350
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── إحصائيات سريعة ──
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📌 المعاملات الحالية للبوت")
        params = {
            "🎯 هدف الربح":   f"{brain.get('take_profit', '-')}%",
            "🛑 وقف الخسارة": f"{brain.get('stop_loss', '-')}%",
            "📉 Trailing":    f"{brain.get('trailing', '-')}%",
            "📊 RSI شراء":    brain.get('rsi_buy_trend', '-'),
            "📊 ADX أدنى":    brain.get('adx_min', '-'),
        }
        for k, v in params.items():
            st.markdown(f"**{k}:** `{v}`")

    with col2:
        st.subheader("📌 إحصائيات اليوم")
        st.markdown(f"**🔄 الصفقات اليومية:** `{wallet.get('daily_trades', 0)}`")
        st.markdown(f"**📉 الخسارة اليومية:** `{wallet.get('daily_loss', 0):.2f}%`")
        st.markdown(f"**💵 الرصيد USD:** `${wallet.get('usd', 0):.2f}`")
        if wallet.get("is_holding"):
            entry = wallet.get("entry_price", 0)
            high  = wallet.get("highest_price", 0)
            st.markdown(f"**🟢 سعر الدخول:** `${entry:.4f}`")
            st.markdown(f"**📈 أعلى سعر:** `${high:.4f}`")

# ═══════════════════════════════════════════════
#  صفحة الصفقات
# ═══════════════════════════════════════════════
elif page == "📈 الصفقات":
    st.title("📈 سجل الصفقات")

    if trades.empty:
        st.info("لا توجد صفقات بعد.")
        st.stop()

    sells = trades[trades["action"] == "SELL"].copy()
    buys  = trades[trades["action"] == "BUY"].copy()

    col1, col2, col3 = st.columns(3)
    col1.metric("إجمالي الصفقات", len(sells))
    col2.metric("صفقات رابحة", len(sells[sells["profit_pct"] > 0]))
    col3.metric("صفقات خاسرة", len(sells[sells["profit_pct"] < 0]))

    st.divider()

    # ── توزيع الأرباح ──
    if not sells.empty:
        fig2 = px.histogram(sells, x="profit_pct", nbins=30,
                            title="توزيع نسب الربح/الخسارة",
                            color_discrete_sequence=["#00d4aa"],
                            template="plotly_dark")
        fig2.add_vline(x=0, line_dash="dash", line_color="white")
        st.plotly_chart(fig2, use_container_width=True)

        # ── جدول الصفقات ──
        st.subheader("📋 آخر الصفقات")
        display = sells[["timestamp","price","profit_pct","profit_usd","balance_after","reason"]].copy()
        display = display.sort_values("timestamp", ascending=False).head(50)
        display.columns = ["الوقت","السعر","الربح %","الربح $","الرصيد بعد","السبب"]

        def color_row(row):
            color = "background-color: rgba(0,212,170,0.15)" if row["الربح %"] > 0 \
                    else "background-color: rgba(255,75,75,0.15)"
            return [color] * len(row)

        st.dataframe(display.style.apply(color_row, axis=1), use_container_width=True)

# ═══════════════════════════════════════════════
#  صفحة نظام التعلم
# ═══════════════════════════════════════════════
elif page == "🧠 نظام التعلم":
    st.title("🧠 نظام التعلم الذاتي")

    if not brain:
        st.info("البوت لم يبدأ بعد.")
        st.stop()

    n      = brain.get("total_trades", 0)
    wins   = brain.get("win_trades", 0)
    losses = brain.get("loss_trades", 0)
    wr     = wins / n * 100 if n else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("إجمالي الصفقات", n)
    c2.metric("Win Rate", f"{wr:.1f}%")
    c3.metric("أفضل ربح", f"{brain.get('best_profit', 0):.2f}%")
    c4.metric("أسوأ خسارة", f"{brain.get('worst_loss', 0):.2f}%")

    st.divider()
    st.subheader("📜 سجل التعلم")

    learning_log = brain.get("learning_log", [])
    if learning_log:
        for entry in reversed(learning_log[-10:]):
            with st.expander(f"🔄 تعلم عند الصفقة #{entry['at_trade']} | Win Rate: {entry['win_rate']}"):
                st.write(f"**متوسط الربح:** {entry['avg_profit']}")
                st.write("**التغييرات:**")
                for c in entry["changes"]:
                    st.write(f"  • {c}")
                st.write("**المعاملات الجديدة:**")
                st.json(entry["new_params"])
    else:
        st.info("البوت يتعلم بعد 20 صفقة — استمر في التشغيل!")

# ═══════════════════════════════════════════════
#  صفحة السجلات
# ═══════════════════════════════════════════════
elif page == "📋 السجلات":
    st.title("📋 سجلات البوت المباشرة")
    n_lines = st.slider("عدد الأسطر", 20, 500, 100)
    logs = load_logs(n_lines)
    st.code(logs, language="bash")
    if st.button("🔄 تحديث"):
        st.rerun()