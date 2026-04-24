import ccxt
import pandas as pd
import time
import os
import numpy as np

# --- الإعدادات الفنية ---
exchange = ccxt.binance()
SYMBOL = 'SOL/USDT'
TIMEFRAME = '1m'

# --- المحفظة الرقمية ---
balance_usd = 1003.38 
balance_coin = 0.0
is_holding = False
entry_price = 0.0
highest_price = 0.0  # لملاحقة الأرباح (Trailing)

def calculate_indicators(df):
    # 1. حساب RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # 2. حساب المتوسطات والسيولة
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['Vol_Avg'] = df['Volume'].rolling(window=10).mean()
    
    # 3. حساب الانحراف المعياري (لقياس قوة الانفجار السعري)
    df['Std_Dev'] = df['Close'].rolling(window=20).std()
    return df

def run_trading_engine():
    global balance_usd, balance_coin, is_holding, entry_price, highest_price
    
    # جلب البيانات
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=200)
    df = pd.DataFrame(bars, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df = calculate_indicators(df)
    
    current_row = df.iloc[-1]
    current_price = current_row['Close']
    current_rsi = current_row['RSI']
    ema_200 = current_row['EMA_200']
    vol_ok = current_row['Volume'] > current_row['Vol_Avg']
    
    # قياس قوة الحركة (Volatility Check)
    is_volatile = current_row['Std_Dev'] > (df['Std_Dev'].mean() * 1.5)

    print(f"\n📊 {SYMBOL} | السعر: {current_price} | RSI: {current_rsi:.2f}")
    print(f"💰 المحفظة: {balance_usd:.2f} USD | الحوزة: {balance_coin:.4f} SOL")

    # --- منطق الدخول (Entry) ---
    # شروط: ترند صاعد + سيولة + RSI مناسب + ليس تذبذباً عشوائياً
    if not is_holding:
        if current_price > ema_200 and current_rsi > 52 and vol_ok and not is_volatile:
            balance_coin = (balance_usd * 0.98) / current_price # ترك 2% رسوم ومهمش أمان
            entry_price = current_price
            highest_price = current_price
            balance_usd = 0
            is_holding = True
            print(f"🚀 [ENTER] دخول احترافي عند {current_price}")

    # --- منطق الخروج الذكي (Exit & Trailing) ---
    elif is_holding:
        # تحديث أعلى سعر وصل له السعر منذ الدخول
        if current_price > highest_price:
            highest_price = current_price
            
        profit_loss = (current_price - entry_price) / entry_price * 100
        drop_from_peak = (highest_price - current_price) / highest_price * 100

        # شروط الخروج:
        # 1. Trailing Stop: إذا نزل السعر 0.3% عن أعلى قمة وصل لها (حجز أرباح متحرك)
        # 2. Hard Stop Loss: خسارة 1%
        # 3. إشارة ضعف RSI تحت 40
        
        should_exit = False
        if profit_loss > 0.3 and drop_from_peak > 0.15: # حجز ربح عند أول ارتداد من القمة
            reason = "Trailing Profit"
            should_exit = True
        elif profit_loss < -1.0:
            reason = "Stop Loss"
            should_exit = True
        elif current_rsi < 40:
            reason = "Weak Momentum"
            should_exit = True

        if should_exit:
            balance_usd = balance_coin * current_price
            balance_coin = 0
            is_holding = False
            print(f"🛑 [EXIT] السبب: {reason} | النتيجة: {profit_loss:.2f}% | الرصيد: {balance_usd:.2f}")

# --- تشغيل الإمبراطورية ---
print(f"--- Samer Institutional Bot v2.0 | 'العملاق' قيد التشغيل ---")
while True:
    try:
        run_trading_engine()
        time.sleep(10)
    except Exception as e:
        print(f"⚠️ تنبيه فني: {e}")
        time.sleep(5)