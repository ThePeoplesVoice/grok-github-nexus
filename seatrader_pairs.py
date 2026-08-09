"""
SeaTrader Pairs – Signal Bot (Manual Execution Mode)
Sends clear, actionable ETH/BTC ratio Z-score signals via Telegram.
No orders are placed — execution is manual.
"""

import time
import requests
from datetime import datetime
from math import sqrt

# ==================== CONFIG ====================
CHECK_EVERY = 120
INTERVAL = "1h"
RANGE = "40d"

LOOKBACK = 24
Z_ENTRY = 2.5

SL_ATR = 1.25
TP_ATR = 1.8
COOLDOWN_SECONDS = 3 * 3600

RISK_PERCENT = 0.75          # Suggested % of account (message only — no order placed)

TELEGRAM_TOKEN = ""          # Set via environment or fill in
TELEGRAM_CHAT_ID = ""
# ================================================

last_signal_time = 0


def send(msg):
    print("\n" + msg + "\n")
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": msg,
                "parse_mode": "HTML"
            }, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")


def get_closes(symbol):
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?interval={INTERVAL}&range={RANGE}"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return [c for c in closes if c is not None]
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def get_ohlc(symbol):
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?interval={INTERVAL}&range={RANGE}"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        closes = [c for c in q["close"] if c is not None]
        highs  = [h for h in q["high"]  if h is not None]
        lows   = [l for l in q["low"]   if l is not None]
        n = min(len(closes), len(highs), len(lows))
        return closes[-n:], highs[-n:], lows[-n:]
    except Exception:
        return None, None, None


def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None
    trs = [
        max(highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i]  - closes[i - 1]))
        for i in range(1, len(closes))
    ]
    return sum(trs[-period:]) / period


def analyse():
    global last_signal_time

    eth = get_closes("ETH-USD")
    btc = get_closes("BTC-USD")
    if not eth or not btc:
        return None

    min_len = min(len(eth), len(btc))
    eth, btc = eth[-min_len:], btc[-min_len:]
    if min_len < LOOKBACK + 5:
        return None

    ratios = [eth[i] / btc[i] for i in range(min_len)]
    window = ratios[-LOOKBACK:]
    mean = sum(window) / LOOKBACK
    var  = sum((x - mean) ** 2 for x in window) / LOOKBACK
    std  = sqrt(var) if var > 0 else 1e-8
    z    = (ratios[-1] - mean) / std

    eth_c, eth_h, eth_l = get_ohlc("ETH-USD")
    if not eth_c:
        return None
    atr = calc_atr(eth_h, eth_l, eth_c)
    if atr is None:
        return None

    current = eth[-1]
    signal  = None
    reason  = ""

    if z >= Z_ENTRY:
        signal = "SELL"
        reason = "ETH is expensive relative to BTC"
    elif z <= -Z_ENTRY:
        signal = "BUY"
        reason = "ETH is cheap relative to BTC"

    if not signal:
        return None

    now = time.time()
    if now - last_signal_time < COOLDOWN_SECONDS:
        return None
    last_signal_time = now

    if signal == "BUY":
        stop   = current - atr * SL_ATR
        target = current + atr * TP_ATR
        direction = "BUY ETH"
    else:
        stop   = current + atr * SL_ATR
        target = current - atr * TP_ATR
        direction = "SELL ETH"

    risk_distance = abs(current - stop)
    rr = abs(target - current) / risk_distance if risk_distance > 0 else 0

    return (
        f"<b>PAIRS SIGNAL – {direction}</b>\n\n"
        f"<b>Reason:</b> {reason}\n"
        f"Z-Score: <b>{z:.2f}</b>\n\n"
        f"<b>Entry:</b>       <code>{current:.2f}</code>\n"
        f"<b>Stop Loss:</b>   <code>{stop:.2f}</code>\n"
        f"<b>Take Profit:</b> <code>{target:.2f}</code>\n\n"
        f"Risk:Reward ≈ 1:{rr:.1f}\n"
        f"Suggested risk: {RISK_PERCENT}% of account\n\n"
        f"ETH/BTC Ratio: {ratios[-1]:.6f}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )


def main():
    send(
        "<b>SeaTrader Pairs – Manual Mode</b>\n"
        f"Z={Z_ENTRY} | Lookback={LOOKBACK}\n"
        "Clear execution messages active — no orders placed automatically"
    )
    print("Manual signal bot running...")

    while True:
        try:
            result = analyse()
            if result:
                send(result)
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    main()
