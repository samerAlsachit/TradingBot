"""
╔══════════════════════════════════════════════════════════════╗
║           Samer Imperial Bot v4.1 - Self-Learning           ║
║         بوت تداول احترافي مع تعلم ذاتي متطور               ║
║  الإصلاحات v4.1:                                            ║
║  - إصلاح RSI (كان ينزل لـ 0 بسبب بيانات غير كافية)        ║
║  - منع الشراء الفوري بعد البيع (cooldown 5 دقائق)          ║
║  - إضافة فلتر RSI_MIN للشراء (لا يشتري إذا RSI < 20)      ║
║  - إصلاح BB_BOUNCE ليتحقق من RSI قبل الشراء               ║
║  - إضافة شرط BEARISH_EXIT للخروج من خسارة متراكمة          ║
╚══════════════════════════════════════════════════════════════╝
"""

import ccxt
import pandas as pd
import numpy as np
import time
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  إعداد السجلات
# ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════
#  الإعدادات
# ══════════════════════════════════════════════
class Config:
    SYMBOL              = "SOL/USDT"
    TIMEFRAME           = "5m"
    LIMIT               = 350           # زيادة الشموع لضمان RSI صحيح دائماً

    INITIAL_BALANCE     = 1000.0
    RISK_PER_TRADE      = 0.10
    FEE_RATE            = 0.001

    TAKE_PROFIT_PCT     = 2.0
    STOP_LOSS_PCT       = 1.5
    TRAILING_PCT        = 0.5

    MAX_DAILY_TRADES    = 10
    MAX_DAILY_LOSS_PCT  = 5.0
    MIN_TRADE_INTERVAL  = 300           # ✅ 5 دقائق cooldown بعد كل صفقة
    RSI_MIN_TO_BUY      = 20            # ✅ لا نشتري إذا RSI أقل من 20

    WALLET_FILE         = "data/wallet.json"
    TRADES_FILE         = "data/trades.csv"
    BRAIN_FILE          = "data/brain.json"

    LOOP_INTERVAL       = 15


# ══════════════════════════════════════════════
#  نظام التعلم الذاتي
# ══════════════════════════════════════════════
class Brain:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists(Config.BRAIN_FILE):
            with open(Config.BRAIN_FILE, "r") as f:
                return json.load(f)
        return {
            "take_profit":   Config.TAKE_PROFIT_PCT,
            "stop_loss":     Config.STOP_LOSS_PCT,
            "trailing":      Config.TRAILING_PCT,
            "rsi_buy_trend": 55,
            "rsi_buy_dip":   30,
            "rsi_sell":      70,
            "adx_min":       25,
            "total_trades":  0,
            "win_trades":    0,
            "loss_trades":   0,
            "total_profit":  0.0,
            "best_profit":   0.0,
            "worst_loss":    0.0,
            "last_updated":  str(datetime.now()),
            "learning_log":  []
        }

    def save(self):
        self.data["last_updated"] = str(datetime.now())
        with open(Config.BRAIN_FILE, "w") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def record_trade(self, profit_pct: float, signals: dict):
        self.data["total_trades"] += 1
        self.data["total_profit"] += profit_pct
        if profit_pct > 0:
            self.data["win_trades"] += 1
            if profit_pct > self.data["best_profit"]:
                self.data["best_profit"] = profit_pct
        else:
            self.data["loss_trades"] += 1
            if profit_pct < self.data["worst_loss"]:
                self.data["worst_loss"] = profit_pct
        if self.data["total_trades"] % 20 == 0:
            self._adapt()
        self.save()

    def _adapt(self):
        n = self.data["total_trades"]
        if n == 0:
            return
        win_rate   = self.data["win_trades"] / n
        avg_profit = self.data["total_profit"] / n
        note = []

        if win_rate < 0.45:
            self.data["rsi_buy_trend"] = min(self.data["rsi_buy_trend"] + 2, 65)
            self.data["adx_min"]       = min(self.data["adx_min"]       + 2, 35)
            self.data["stop_loss"]     = max(self.data["stop_loss"]     - 0.1, 0.8)
            note.append(f"win_rate={win_rate:.0%} → شددنا شروط الشراء")
        elif win_rate > 0.65:
            self.data["take_profit"]   = min(self.data["take_profit"]   + 0.2, 5.0)
            self.data["trailing"]      = min(self.data["trailing"]      + 0.1, 1.5)
            note.append(f"win_rate={win_rate:.0%} → وسّعنا هدف الربح")

        if avg_profit < -0.3:
            self.data["stop_loss"]     = max(self.data["stop_loss"]     - 0.2, 0.5)
            note.append(f"avg_profit={avg_profit:.2f}% → قلصنا وقف الخسارة")

        if note:
            self.data["learning_log"].append({
                "at_trade":   n,
                "win_rate":   f"{win_rate:.0%}",
                "avg_profit": f"{avg_profit:.2f}%",
                "changes":    note,
                "new_params": {
                    "take_profit": self.data["take_profit"],
                    "stop_loss":   self.data["stop_loss"],
                    "trailing":    self.data["trailing"],
                    "rsi_buy":     self.data["rsi_buy_trend"],
                    "adx_min":     self.data["adx_min"],
                }
            })
            log.info(f"🧠 Brain adapted at trade #{n}: {note}")

    @property
    def win_rate(self) -> float:
        n = self.data["total_trades"]
        return self.data["win_trades"] / n if n > 0 else 0.0

    @property
    def params(self) -> dict:
        return self.data


# ══════════════════════════════════════════════
#  إدارة المحفظة
# ══════════════════════════════════════════════
class Wallet:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self._load()

    def _load(self):
        if os.path.exists(Config.WALLET_FILE):
            with open(Config.WALLET_FILE, "r") as f:
                w = json.load(f)
            self.usd             = w["usd"]
            self.coin            = w["coin"]
            self.is_holding      = w["is_holding"]
            self.entry_price     = w.get("entry_price",    0.0)
            self.highest_price   = w.get("highest_price",  0.0)
            self.daily_trades    = w.get("daily_trades",   0)
            self.daily_loss      = w.get("daily_loss",     0.0)
            self.last_trade_day  = w.get("last_trade_day", str(datetime.today().date()))
            self.last_trade_ts   = w.get("last_trade_ts",  0)
            self.initial_balance = w.get("initial_balance",Config.INITIAL_BALANCE)
        else:
            self.usd             = Config.INITIAL_BALANCE
            self.coin            = 0.0
            self.is_holding      = False
            self.entry_price     = 0.0
            self.highest_price   = 0.0
            self.daily_trades    = 0
            self.daily_loss      = 0.0
            self.last_trade_day  = str(datetime.today().date())
            self.last_trade_ts   = 0
            self.initial_balance = Config.INITIAL_BALANCE
        self._reset_daily_if_needed()

    def _reset_daily_if_needed(self):
        today = str(datetime.today().date())
        if self.last_trade_day != today:
            self.daily_trades   = 0
            self.daily_loss     = 0.0
            self.last_trade_day = today

    def save(self):
        with open(Config.WALLET_FILE, "w") as f:
            json.dump({
                "usd":             self.usd,
                "coin":            self.coin,
                "is_holding":      self.is_holding,
                "entry_price":     self.entry_price,
                "highest_price":   self.highest_price,
                "daily_trades":    self.daily_trades,
                "daily_loss":      self.daily_loss,
                "last_trade_day":  self.last_trade_day,
                "last_trade_ts":   self.last_trade_ts,
                "initial_balance": self.initial_balance,
            }, f, indent=2)

    @property
    def can_trade(self) -> bool:
        self._reset_daily_if_needed()
        if self.daily_trades >= Config.MAX_DAILY_TRADES:
            log.warning("🚫 وصلنا الحد الأقصى للصفقات اليومية")
            return False
        if self.daily_loss >= Config.MAX_DAILY_LOSS_PCT:
            log.warning("🚫 وصلنا الحد الأقصى للخسارة اليومية")
            return False
        elapsed = time.time() - self.last_trade_ts
        if elapsed < Config.MIN_TRADE_INTERVAL:
            remaining = int(Config.MIN_TRADE_INTERVAL - elapsed)
            log.info(f"⏳ Cooldown: {remaining}s متبقية قبل الصفقة التالية")
            return False
        return True


# ══════════════════════════════════════════════
#  المؤشرات الفنية
# ══════════════════════════════════════════════
class Indicators:

    @staticmethod
    def calculate(df: pd.DataFrame) -> pd.DataFrame:
        df    = df.copy()
        close = df["Close"]
        high  = df["High"]
        low   = df["Low"]
        vol   = df["Volume"]

        # ── RSI (14) — Wilder smoothing الصحيح ──
        delta    = close.diff()
        gain     = delta.clip(lower=0)
        loss     = (-delta.clip(upper=0))
        avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"]       = 100 - (100 / (1 + rs))
        df["RSI_valid"] = df["RSI"].between(5, 95)  # ✅ فلتر موثوقية RSI

        # ── EMA ──
        df["EMA_20"]  = close.ewm(span=20,  adjust=False).mean()
        df["EMA_50"]  = close.ewm(span=50,  adjust=False).mean()
        df["EMA_200"] = close.ewm(span=200, adjust=False).mean()

        # ── MACD ──
        ema12             = close.ewm(span=12, adjust=False).mean()
        ema26             = close.ewm(span=26, adjust=False).mean()
        df["MACD"]        = ema12 - ema26
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"]   = df["MACD"] - df["MACD_Signal"]

        # ── Bollinger Bands ──
        sma20          = close.rolling(20).mean()
        std20          = close.rolling(20).std()
        df["BB_Upper"] = sma20 + 2 * std20
        df["BB_Lower"] = sma20 - 2 * std20
        df["BB_Mid"]   = sma20

        # ── ATR ──
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean()

        # ── ADX ──
        df["ADX"] = Indicators._adx(high, low, close, 14)

        # ── Volume ──
        df["Vol_MA"]    = vol.rolling(20).mean()
        df["Vol_Ratio"] = vol / df["Vol_MA"]

        # ── Stochastic RSI ──
        rsi            = df["RSI"]
        rsi_min        = rsi.rolling(14).min()
        rsi_max        = rsi.rolling(14).max()
        df["StochRSI"] = (rsi - rsi_min) / (rsi_max - rsi_min).replace(0, np.nan)

        return df.dropna()

    @staticmethod
    def _adx(high, low, close, period=14) -> pd.Series:
        tr       = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr      = tr.ewm(span=period, adjust=False).mean()
        up       = high.diff()
        down     = -low.diff()
        plus_dm  = pd.Series(np.where((up > down) & (up > 0),   up,   0.0), index=high.index)
        minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)
        plus_di  = 100 * plus_dm.ewm(span=period, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr
        dx       = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        return dx.ewm(span=period, adjust=False).mean()


# ══════════════════════════════════════════════
#  سجل الصفقات
# ══════════════════════════════════════════════
class TradeLogger:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(Config.TRADES_FILE):
            pd.DataFrame(columns=[
                "timestamp", "action", "price", "amount_usd",
                "amount_coin", "profit_pct", "profit_usd",
                "balance_after", "rsi", "adx", "reason"
            ]).to_csv(Config.TRADES_FILE, index=False)

    def log(self, action, price, amount_usd, amount_coin,
            profit_pct, profit_usd, balance_after, rsi, adx, reason):
        pd.DataFrame([{
            "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action":        action,
            "price":         round(price,         4),
            "amount_usd":    round(amount_usd,    2),
            "amount_coin":   round(amount_coin,   6),
            "profit_pct":    round(profit_pct,    4),
            "profit_usd":    round(profit_usd,    2),
            "balance_after": round(balance_after, 2),
            "rsi":           round(rsi,            2),
            "adx":           round(adx,            2),
            "reason":        reason,
        }]).to_csv(Config.TRADES_FILE, mode="a", header=False, index=False)


# ══════════════════════════════════════════════
#  محرك التداول
# ══════════════════════════════════════════════
class TradingEngine:

    def __init__(self):
        self.exchange = ccxt.binance({"enableRateLimit": True})
        self.wallet   = Wallet()
        self.brain    = Brain()
        self.logger   = TradeLogger()
        self.p        = self.brain.params

        log.info("═" * 60)
        log.info("🤖  Samer Imperial Bot v4.1  — Self-Learning Edition")
        log.info(f"💰  الرصيد: ${self.wallet.usd:.2f}")
        log.info(f"📊  الزوج: {Config.SYMBOL} | Timeframe: {Config.TIMEFRAME}")
        log.info(f"🧠  الصفقات: {self.p['total_trades']} | Win Rate: {self.brain.win_rate:.0%}")
        log.info(f"⏳  Cooldown: {Config.MIN_TRADE_INTERVAL}s بين كل صفقة")
        log.info("═" * 60)

    def _fetch(self) -> pd.DataFrame:
        bars = self.exchange.fetch_ohlcv(Config.SYMBOL, Config.TIMEFRAME, limit=Config.LIMIT)
        df   = pd.DataFrame(bars, columns=["Time", "Open", "High", "Low", "Close", "Volume"])
        return Indicators.calculate(df)

    # ──────────────────────────────────────────
    #  إشارات الشراء
    # ──────────────────────────────────────────
    def _buy_signal(self, curr, prev) -> tuple[bool, str]:
        p   = self.p
        rsi = curr["RSI"]
        adx = curr["ADX"]

        # ✅ فلتر أساسي: RSI يجب أن يكون موثوقاً وفوق الحد الأدنى
        if not curr["RSI_valid"] or rsi < Config.RSI_MIN_TO_BUY:
            log.info(f"⚠️  تجاهل الإشارة — RSI غير موثوق أو منخفض جداً: {rsi:.1f}")
            return False, ""

        # ── شرط 1: اتجاه صاعد قوي ──
        trend = (
            curr["Close"]     > curr["EMA_20"]       and
            curr["EMA_20"]    > curr["EMA_50"]        and
            curr["Close"]     > curr["EMA_200"]       and
            rsi               > p["rsi_buy_trend"]    and
            adx               > p["adx_min"]          and
            curr["MACD_Hist"] > 0                     and
            curr["Vol_Ratio"] > 1.2
        )
        if trend:
            return True, "TREND_FOLLOW"

        # ── شرط 2: ارتداد من القاع ──
        dip = (
            prev["RSI"]       < p["rsi_buy_dip"]  and
            rsi               > prev["RSI"] + 2    and  # ✅ ارتداد واضح
            rsi               > 25                 and  # ✅ ليس في ذعر
            curr["Close"]     > curr["BB_Lower"]   and
            curr["MACD_Hist"] > prev["MACD_Hist"]  and
            curr["Vol_Ratio"] > 1.0
        )
        if dip:
            return True, "DIP_REVERSAL"

        # ── شرط 3: ارتداد من Bollinger Band ──
        bb_bounce = (
            prev["Close"]     < prev["BB_Lower"]   and
            curr["Close"]     > curr["BB_Lower"]   and
            curr["StochRSI"]  < 0.3                and
            rsi               > 25                 and  # ✅ فلتر RSI
            rsi               < 50                 and  # ✅ ليس في تشبع
            curr["Vol_Ratio"] > 1.5
        )
        if bb_bounce:
            return True, "BB_BOUNCE"

        return False, ""

    # ──────────────────────────────────────────
    #  إشارات البيع
    # ──────────────────────────────────────────
    def _sell_signal(self, curr, prev, profit_pct: float, drop_pct: float) -> tuple[bool, str]:
        p   = self.p
        rsi = curr["RSI"]

        # ── وقف الخسارة ──
        if profit_pct <= -p["stop_loss"]:
            return True, f"STOP_LOSS ({profit_pct:.2f}%)"

        # ── Trailing Stop ──
        if profit_pct > 0.5 and drop_pct >= p["trailing"]:
            return True, f"TRAILING_STOP (drop={drop_pct:.2f}%)"

        # ── هدف الربح ──
        if profit_pct >= p["take_profit"]:
            return True, f"TAKE_PROFIT ({profit_pct:.2f}%)"

        # ── تشبع شراء ──
        if (curr["RSI_valid"]              and
            rsi               > p["rsi_sell"]      and
            curr["MACD_Hist"] < prev["MACD_Hist"]  and
            curr["Close"]     > curr["BB_Upper"]):
            return True, f"OVERBOUGHT (RSI={rsi:.1f})"

        # ── قطع EMA هبوطي ──
        if (prev["EMA_20"] >= prev["EMA_50"] and
            curr["EMA_20"]  < curr["EMA_50"] and
            profit_pct > 0):
            return True, "DEATH_CROSS"

        # ── انقلاب RSI مع ربح موجب ──
        if (curr["RSI_valid"]                      and
            prev["RSI"]       > curr["RSI"] + 3    and
            curr["RSI"]       < 55                 and
            curr["MACD_Hist"] < prev["MACD_Hist"]  and
            profit_pct        > 0.05):
            return True, f"RSI_REVERSAL ({profit_pct:.2f}%)"

        # ── السوق جانبي ──
        if (abs(profit_pct)   < 0.3  and
            curr["ADX"]       < 20   and
            curr["RSI_valid"] and rsi < 50):
            return True, f"SIDEWAYS_EXIT (ADX={curr['ADX']:.1f})"

        # ── ✅ خسارة متراكمة مع اتجاه هابط واضح ──
        if (profit_pct        < -0.5         and
            curr["RSI_valid"]                and
            rsi               < 35           and
            curr["MACD_Hist"] < 0            and
            curr["EMA_20"]    < curr["EMA_50"]):
            return True, f"BEARISH_EXIT ({profit_pct:.2f}%)"

        return False, ""

    # ──────────────────────────────────────────
    #  تنفيذ الشراء
    # ──────────────────────────────────────────
    def _execute_buy(self, price: float, rsi: float, adx: float, reason: str):
        amount_usd  = self.wallet.usd * Config.RISK_PER_TRADE
        fee         = amount_usd * Config.FEE_RATE
        net_usd     = amount_usd - fee
        amount_coin = net_usd / price

        self.wallet.usd           -= amount_usd
        self.wallet.coin          += amount_coin
        self.wallet.is_holding     = True
        self.wallet.entry_price    = price
        self.wallet.highest_price  = price
        self.wallet.daily_trades  += 1
        self.wallet.last_trade_ts  = time.time()
        self.wallet.save()

        self.logger.log("BUY", price, amount_usd, amount_coin,
                        0, 0, self.wallet.usd + amount_coin * price, rsi, adx, reason)

        log.info(f"🟢 BUY  | {Config.SYMBOL} @ ${price:.4f}")
        log.info(f"        | السبب: {reason} | RSI: {rsi:.1f} | ADX: {adx:.1f}")
        log.info(f"        | الكمية: {amount_coin:.6f} | المبلغ: ${amount_usd:.2f}")
        log.info(f"        | الرصيد المتبقي: ${self.wallet.usd:.2f}")

    # ──────────────────────────────────────────
    #  تنفيذ البيع
    # ──────────────────────────────────────────
    def _execute_sell(self, price: float, rsi: float, adx: float, reason: str):
        amount_coin = self.wallet.coin
        gross_usd   = amount_coin * price
        fee         = gross_usd * Config.FEE_RATE
        net_usd     = gross_usd - fee
        profit_usd  = net_usd - (amount_coin * self.wallet.entry_price)
        profit_pct  = (price - self.wallet.entry_price) / self.wallet.entry_price * 100

        self.wallet.usd           += net_usd
        self.wallet.coin           = 0.0
        self.wallet.is_holding     = False
        self.wallet.last_trade_ts  = time.time()  # ✅ cooldown يبدأ من لحظة البيع
        if profit_pct < 0:
            self.wallet.daily_loss += abs(profit_pct)
        self.wallet.save()

        self.logger.log("SELL", price, net_usd, amount_coin,
                        profit_pct, profit_usd, self.wallet.usd, rsi, adx, reason)
        self.brain.record_trade(profit_pct, {"rsi": rsi, "adx": adx})
        self.p = self.brain.params

        emoji  = "✅" if profit_pct > 0 else "❌"
        status = "WIN" if profit_pct > 0 else "LOSS"
        log.info(f"🔴 SELL | {Config.SYMBOL} @ ${price:.4f}")
        log.info(f"        | {emoji} {status} {profit_pct:+.2f}% (${profit_usd:+.2f})")
        log.info(f"        | السبب: {reason}")
        log.info(f"        | الرصيد: ${self.wallet.usd:.2f}")
        log.info(f"        | Win Rate: {self.brain.win_rate:.0%} من {self.p['total_trades']} صفقة")
        log.info(f"        | ⏳ Cooldown {Config.MIN_TRADE_INTERVAL}s قبل الصفقة التالية")

    # ──────────────────────────────────────────
    #  دورة التداول
    # ──────────────────────────────────────────
    def run_once(self):
        df   = self._fetch()
        curr = df.iloc[-1]
        prev = df.iloc[-2]

        price = curr["Close"]
        rsi   = curr["RSI"]
        adx   = curr["ADX"]

        if not self.wallet.is_holding:
            if not self.wallet.can_trade:
                return
            signal, reason = self._buy_signal(curr, prev)
            if signal:
                self._execute_buy(price, rsi, adx, reason)
        else:
            if price > self.wallet.highest_price:
                self.wallet.highest_price = price
                self.wallet.save()

            profit_pct = (price - self.wallet.entry_price) / self.wallet.entry_price * 100
            drop_pct   = (self.wallet.highest_price - price) / self.wallet.highest_price * 100

            should_sell, reason = self._sell_signal(curr, prev, profit_pct, drop_pct)
            if should_sell:
                self._execute_sell(price, rsi, adx, reason)
            else:
                rsi_tag = f"RSI: {rsi:.1f}" if curr["RSI_valid"] else "RSI: ⚠️غير موثوق"
                log.info(
                    f"📊 HOLD | ${price:.4f} | P&L: {profit_pct:+.2f}% | "
                    f"{rsi_tag} | ADX: {adx:.1f}"
                )

    # ──────────────────────────────────────────
    #  الحلقة الرئيسية
    # ──────────────────────────────────────────
    def run(self):
        log.info("🚀 بدأ البوت — اضغط Ctrl+C للإيقاف")
        while True:
            try:
                self.run_once()
            except ccxt.NetworkError as e:
                log.warning(f"🌐 خطأ شبكة: {e} — إعادة المحاولة بعد 30s")
                time.sleep(30)
                continue
            except ccxt.ExchangeError as e:
                log.error(f"❌ خطأ منصة: {e}")
                time.sleep(60)
                continue
            except KeyboardInterrupt:
                log.info("🛑 تم إيقاف البوت يدوياً")
                self.wallet.save()
                self.brain.save()
                break
            except Exception as e:
                log.error(f"⚠️ خطأ غير متوقع: {e}", exc_info=True)
                time.sleep(30)
                continue
            time.sleep(Config.LOOP_INTERVAL)


# ══════════════════════════════════════════════
#  نقطة الدخول
# ══════════════════════════════════════════════
if __name__ == "__main__":
    bot = TradingEngine()
    bot.run()