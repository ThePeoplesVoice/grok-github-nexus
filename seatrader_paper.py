"""
SeaTrader – Paper Trading Mode
Simulates trades against live prices, tracks paper equity, no real orders.
State is persisted to paper_state.json between runs.
"""

import json
import os
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
COOLDOWN = 3 * 3600

STARTING_EQUITY = 10_000     # Paper balance in USD
RISK_PERCENT = 0.75          # % of equity risked per trade

TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""
STATE_FILE = "paper_state.json"
# ================================================

last_signal_time = 0
state = {
    "equity": STARTING_EQUITY,
    "trades": [],
    "open_trade": None,
}


def load_state():
    global state
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)


def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def send(msg):
    print("\n" + msg + "\n")
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception:
            pass


def get_closes(symbol):
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            f"?interval={INTERVAL}&range={RANGE}"
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return [c for c in closes if c is not None]
    except Exception:
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


def calc_atr(h, l, c, period=14):
    if len(c) < period + 1:
        return None
    trs = [
        max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        for i in range(1, len(c))
    ]
    return sum(trs[-period:]) / period


def check_open_trade(current_price):
    trade = state["open_trade"]
    if not trade:
        return

    direction   = trade["direction"]
    stop        = trade["stop"]
    target      = trade["target"]
    entry       = trade["entry"]
    risk_amount = trade["risk_amount"]

    closed   = False
    result_r = 0.0

    if direction == "BUY":
        if current_price <= stop:
            result_r = -1.0
            closed = True
        elif current_price >= target:
            result_r = (target - entry) / (entry - stop)
            closed = True
    else:  # SELL
        if current_price >= stop:
            result_r = -1.0
            closed = True
        elif current_price <= target:
            result_r = (entry - target) / (stop - entry)
            closed = True

    if closed:
        pnl = risk_amount * result_r
        state["equity"] += pnl
        trade.update({
            "result_r":   result_r,
            "pnl":        pnl,
            "exit_price": current_price,
            "exit_time":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        state["trades"].append(trade)
        state["open_trade"] = None
        save_state()

        send(
            f"<b>PAPER TRADE CLOSED</b>\n"
            f"Direction: {direction}\n"
            f"Result: {result_r:+.2f}R\n"
            f"PnL: ${pnl:+.2f}\n"
            f"New Equity: ${state['equity']:.2f}"
        )


def analyse():
    global last_signal_time

    eth = get_closes("ETH-USD")
    btc = get_closes("BTC-USD")
    if not eth or not btc:
        return

    min_len = min(len(eth), len(btc))
    eth, btc = eth[-min_len:], btc[-min_len:]
    if min_len < LOOKBACK + 5:
        return

    current_price = eth[-1]
    check_open_trade(current_price)

    if state["open_trade"]:
        return  # one trade at a time

    ratios = [eth[i] / btc[i] for i in range(min_len)]
    window = ratios[-LOOKBACK:]
    mean   = sum(window) / LOOKBACK
    var    = sum((x - mean) ** 2 for x in window) / LOOKBACK
    std    = sqrt(var) if var > 0 else 1e-8
    z      = (ratios[-1] - mean) / std

    eth_c, eth_h, eth_l = get_ohlc("ETH-USD")
    if not eth_c:
        return
    atr = calc_atr(eth_h, eth_l, eth_c)
    if atr is None:
        return

    signal = None
    if z >= Z_ENTRY:
        signal = "SELL"
    elif z <= -Z_ENTRY:
        signal = "BUY"

    if not signal:
        return

    now = time.time()
    if now - last_signal_time < COOLDOWN:
        return
    last_signal_time = now

    if signal == "BUY":
        stop   = current_price - atr * SL_ATR
        target = current_price + atr * TP_ATR
    else:
        stop   = current_price + atr * SL_ATR
        target = current_price - atr * TP_ATR

    risk_amount = state["equity"] * (RISK_PERCENT / 100)

    state["open_trade"] = {
        "direction":  signal,
        "entry":      current_price,
        "stop":       stop,
        "target":     target,
        "z":          z,
        "risk_amount": risk_amount,
        "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_state()

    send(
        f"<b>PAPER TRADE OPENED – {signal} ETH</b>\n\n"
        f"Entry:  <code>{current_price:.2f}</code>\n"
        f"Stop:   <code>{stop:.2f}</code>\n"
        f"Target: <code>{target:.2f}</code>\n"
        f"Z-Score: {z:.2f}\n"
        f"Risking: ${risk_amount:.2f} ({RISK_PERCENT}%)\n"
        f"Current Equity: ${state['equity']:.2f}"
    )


def main():
    load_state()
    send(
        f"<b>SeaTrader Paper Trading</b>\n"
        f"Equity: ${state['equity']:.2f}\n"
        f"Z={Z_ENTRY} | Lookback={LOOKBACK} | No real orders"
    )
    print("Paper trading mode running...")

    while True:
        try:
            analyse()
        except Exception as e:
            print(f"Loop error: {e}")
        time.sleep(CHECK_EVERY)


if __name__ == "__main__":
    main()
