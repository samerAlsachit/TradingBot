import ccxt
import pandas as pd
import time
import os

exchange = ccxt.binance()
SYMBOL = 'SOL/USDT'
TIMEFRAME = '1m'

# الرصيد المتبقي بعد الصفقات الأخيرة
balance_usd = 943.17 
balance_coin = 0.0
is_holding = False
entry_price = 0.0

def calculate_indicators(df):
    # حساب RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    
    # حساب EMA 200
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # حساب ADX (لقياس قوة الاتجاه)
    plus_dm = df['High'].diff().where(lambda x: (x > 0) & (x > df['Low'].diff().abs()), 0)
    minus_dm = df['Low'].diff().abs().where(lambda x: (x > 0) & (x > df['High'].diff()), 0)
    tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    df['ADX'] = ( (plus_dm.rolling(14).mean() - minus_dm.rolling(14).mean()).abs() / (plus_dm.rolling(14).mean() + minus_dm.rolling(14).mean()) ).rolling(14).mean() * 100
    
    return df

def run_trading_engine():
    global balance_usd, balance_coin, is_holding, entry_price
    
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
    df = pd.DataFrame(bars, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df = calculate_indicators(df)
    
    current_row = df.iloc[-1]
    current_price = current_row['Close']
    current_rsi = current_row['RSI']
    adx = current_row['ADX']
    ema_200 = current_row['EMA_200']

    print(f"\n📊 {SYMBOL} | السعر: {current_price} | RSI: {current_rsi:.2f} | قوة الترند (ADX): {adx:.2f}")
    
    # الشراء فقط إذا كان الترند قوياً (ADX > 25)
    if not is_holding:
        if current_price > ema_200 and current_rsi > 55 and adx > 25:
            balance_coin = balance_usd / current_price
            entry_price = current_price
            balance_usd = 0
            is_holding = True
            print(f"🚀 [ENTER] دخول قوي مع ترند مؤكد (ADX: {adx:.2f})")
    
    elif is_holding:
        profit_loss = (current_price - entry_price) / entry_price * 100
        # نخرج إذا ضعف الزخم أو ضرب وقف الخسارة
        if current_rsi < 40 or profit_loss < -0.8 or profit_loss > 0.6:
            balance_usd = balance_coin * current_price
            balance_coin = 0
            is_holding = False
            print(f"🛑 [EXIT] النتيجة: {profit_loss:.2f}% | الرصيد الحالي: {balance_usd:.2f}")

print("--- نسخة 'العملاق' المفلترة بـ ADX لمنع الصفقات الفاشلة ---")
while True:
    try:
        run_trading_engine()
        time.sleep(10)
    except Exception as e:
        time.sleep(5)