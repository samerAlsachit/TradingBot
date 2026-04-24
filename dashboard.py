import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os

# --- إعدادات الواجهة ---
st.set_page_config(page_title="Samer Trading Dashboard", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    .stMetric { background-color: #1f2937; padding: 20px; border-radius: 12px; border: 1px solid #3b82f6; }
    .main { background-color: #0e1117; }
    </style>
    """, unsafe_allow_html=True)

# --- دالة التحميل ---
def load_data():
    wallet = {'usd': 1000.0, 'coin': 0.0, 'is_holding': False}
    if os.path.exists('wallet.json'):
        with open('wallet.json', 'r') as f: wallet = json.load(f)
    
    df = pd.read_csv('trades_memory.csv') if os.path.exists('trades_memory.csv') else None
    if df is not None: df['timestamp'] = pd.to_datetime(df['timestamp'])
    return wallet, df

wallet, df = load_data()

# --- الهيكل العلوي ---
st.title("🏦 إمبراطورية سامر للتداول")
c1, c2, c3 = st.columns(3)
with c1: st.metric("رصيد الدولار", f"${wallet['usd']:.2f}")
with c2: st.metric("رصيد العملة", f"{wallet['coin']:.4f} SOL")
with c3: st.info("🟢 في صفقة حالياً" if wallet['is_holding'] else "🔵 في انتظار فرصة")

if df is not None:
    # الرسم البياني
    st.subheader("📊 تحليل حركة السعر والصفقات")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['price'], name="السعر", line=dict(color='#3b82f6', width=2)))
    
    # نقاط الشراء والبيع
    buys = df[df['action'] == 'BUY']
    sells = df[df['action'].str.contains('SELL', na=False)]
    
    fig.add_trace(go.Scatter(x=buys['timestamp'], y=buys['price'], mode='markers', name='شراء', marker=dict(color='#10b981', size=12, symbol='triangle-up')))
    fig.add_trace(go.Scatter(x=sells['timestamp'], y=sells['price'], mode='markers', name='بيع', marker=dict(color='#ef4444', size=12, symbol='triangle-down')))
    
    fig.update_layout(template="plotly_dark", height=500, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # جدول العمليات
    st.subheader("📜 آخر العمليات المسجلة")
    st.dataframe(df.tail(20).sort_values(by='timestamp', ascending=False), use_container_width=True)

else:
    st.warning("⏳ بانتظار بيانات البوت الأولى...")

if st.button('تحديث الآن'): st.rerun()