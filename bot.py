import ccxt
import pandas as pd
import time
import os
import requests
import json

# --- [1] الإعدادات وتنبيهات تيليجرام ---
TELEGRAM_TOKEN = "8735102399:AAHYa1-xbZQyU8lzYFVffOwzUTA8AZ0BcQo"
TELEGRAM_CHAT_ID = "31582902"

def send_msg(text):
    print(text)
    if TELEGRAM_TOKEN != "8735102399:AAHYa1-xbZQyU8lzYFVffOwzUTA8AZ0BcQo":
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage?chat_id={TELEGRAM_CHAT_ID}&text={text}"
        try: requests.get(url, timeout=5)
        except: pass

# --- [2] إعدادات المنصة والمحفظة ---
exchange = ccxt.binance()
SYMBOL = 'SOL/USDT'
TIMEFRAME = '1m'
LOG_FILE = 'trades_memory.csv'

# تحميل المحفظة إذا كانت موجودة أو البدء برصيد جديد
if os.path.exists('wallet.json'):
    with open('wallet.json', 'r') as f:
        wallet = json.load(f)
        balance_usd = wallet['usd']
        balance_coin = wallet['coin']
        is_holding = wallet['is_holding']
        entry_price = wallet.get('entry_price', 0.0)
else:
    balance_usd = 1003.38 
    balance_coin = 0.0
    is_holding = False
    entry_price = 0.0

highest_price = entry_price

def save_wallet():
    with open('wallet.json', 'w') as f:
        json.dump({
            'usd': balance_usd, 'coin': balance_coin, 
            'is_holding': is_holding, 'entry_price': entry_price
        }, f)

def save_to_csv(price, rsi, action):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, 'a') as f:
        if not file_exists:
            f.write("timestamp,price,rsi,action\n")
        f.write(f"{pd.Timestamp.now()},{price},{rsi:.2f},{action}\n")

# --- [3] المحرك الفني ---
def calculate_indicators(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['Vol_Avg'] = df['Volume'].rolling(window=10).mean()
    
    tr = pd.concat([df['High'] - df['Low'], (df['High'] - df['Close'].shift()).abs(), (df['Low'] - df['Close'].shift()).abs()], axis=1).max(axis=1)
    plus_dm = df['High'].diff().where(lambda x: (x > 0) & (x > df['Low'].diff().abs()), 0)
    minus_dm = df['Low'].diff().abs().where(lambda x: (x > 0) & (x > df['High'].diff()), 0)
    df['ADX'] = ( (plus_dm.rolling(14).mean() - minus_dm.rolling(14).mean()).abs() / (plus_dm.rolling(14).mean() + minus_dm.rolling(14).mean()) ).rolling(14).mean() * 100
    return df

def run_trading_engine():
    global balance_usd, balance_coin, is_holding, entry_price, highest_price
    
    bars = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=200)
    df = pd.DataFrame(bars, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df = calculate_indicators(df)
    
    curr = df.iloc[-1]
    p_rsi = df.iloc[-2]['RSI']
    current_price, current_rsi, adx = curr['Close'], curr['RSI'], curr['ADX']
    vol_ok = curr['Volume'] > curr['Vol_Avg']

    save_to_csv(current_price, current_rsi, "MONITOR")

    if not is_holding:
        cond_trend = (current_price > curr['EMA_200'] and current_rsi > 55 and adx > 25 and vol_ok)
        cond_dip = (p_rsi < 25 and current_rsi > p_rsi and vol_ok)

        if cond_trend or cond_dip:
            balance_coin, entry_price = balance_usd / current_price, current_price
            highest_price, balance_usd, is_holding = current_price, 0, True
            save_to_csv(current_price, current_rsi, "BUY")
            send_msg(f"🚀 [BUY] {SYMBOL}\nPrice: {current_price}\nType: {'Trend' if cond_trend else 'Dip'}")

    elif is_holding:
        if current_price > highest_price: highest_price = current_price
        profit = (current_price - entry_price) / entry_price * 100
        drop = (highest_price - current_price) / highest_price * 100

        if (profit > 0.4 and drop > 0.15) or (profit < -0.8) or (current_rsi < 42 and profit > 0.1):
            balance_usd = balance_coin * current_price
            balance_coin, is_holding = 0, False
            status = "WIN" if profit > 0 else "LOSS"
            save_to_csv(current_price, current_rsi, f"SELL_{status}")
            send_msg(f"🛑 [SELL] {SYMBOL}\nPrice: {current_price}\nResult: {profit:.2f}%")
    
    save_wallet()

# --- [4] التشغيل ---
send_msg("🤖 Samer Imperial Bot v3.0 ONLINE")
while True:
    try:
        run_trading_engine()
        time.sleep(10)
    except Exception as e:
        print(f"⚠️ Error: {e}")
        time.sleep(5)