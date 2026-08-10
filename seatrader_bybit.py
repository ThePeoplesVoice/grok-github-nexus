import json
import time
import hmac
import hashlib
from math import sqrt
from urllib.parse import urlencode

import requests

# ==================== BYBIT CONFIG ====================
API_KEY = ""          # ← Your Bybit API Key
API_SECRET = ""       # ← Your Bybit API Secret
TESTNET = True         # ← Set to False only when ready for real money
ALLOW_LIVE_TRADING = False  # hard safety gate for real-money mode
DRY_RUN = True         # set False for actual testnet/live orders

# Strategy
LOOKBACK = 24
Z_ENTRY = 2.5
SL_ATR = 1.25
TP_ATR = 1.8
COOLDOWN = 3 * 3600
MAX_HOLD_SECONDS = 24 * 3600

# Risk
RISK_PERCENT = 0.5
MAX_POSITION_USDT = 50
MIN_NOTIONAL_USDT = 1.0
MAX_QTY_ETH = 0.05
MIN_QTY_ETH = 0.001

# Market
SYMBOL = "ETHUSDT"
YAHOO_ETH = "ETH-USD"
YAHOO_BTC = "BTC-USD"

TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""
# ======================================================

BASE_URL = "https://api-testnet.bybit.com" if TESTNET else "https://api.bybit.com"
last_signal_time = 0
position = None


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


def bybit_request(method, endpoint, params=None):
    if params is None:
        params = {}

    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"

    if method == "GET":
        payload = urlencode(sorted(params.items()))
    else:
        payload = json.dumps(params, separators=(",", ":"))

    to_sign = f"{timestamp}{API_KEY}{recv_window}{payload}"
    signature = hmac.new(API_SECRET.encode("utf-8"), to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    headers = {
        "X-BAPI-API-KEY": API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature,
        "X-BAPI-SIGN-TYPE": "2",
        "Content-Type": "application/json",
    }

    url = BASE_URL + endpoint
    if method == "GET":
        r = requests.get(url, params=params, headers=headers, timeout=12)
    else:
        r = requests.post(url, json=params, headers=headers, timeout=12)
    return r.json()


def get_closes(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=40d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        closes = r.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        return [c for c in closes if c is not None]
    except Exception:
        return None


def get_ohlc(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1h&range=40d"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        q = r.json()["chart"]["result"][0]["indicators"]["quote"][0]
        closes = [c for c in q["close"] if c is not None]
        highs = [h for h in q["high"] if h is not None]
        lows = [l for l in q["low"] if l is not None]
        n = min(len(closes), len(highs), len(lows))
        return closes[-n:], highs[-n:], lows[-n:]
    except Exception:
        return None, None, None


def calc_atr(h, l, c, period=14):
    if len(c) < period + 1:
        return None
    trs = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    return sum(trs[-period:]) / period


def get_coin_balance(coin):
    if DRY_RUN:
        return None
    result = bybit_request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED", "coin": coin})
    if result.get("retCode") != 0:
        return None

    try:
        wallets = result["result"]["list"]
        for wallet in wallets:
            for item in wallet.get("coin", []):
                if item.get("coin") == coin:
                    bal = item.get("walletBalance") or item.get("availableToWithdraw") or "0"
                    return float(bal)
    except Exception:
        return None
    return None


def place_order(side, qty):
    if DRY_RUN:
        return {
            "retCode": 0,
            "retMsg": "OK",
            "result": {"orderId": f"dry-{int(time.time())}", "side": side, "qty": str(qty)},
            "dryRun": True,
        }

    if not API_KEY or not API_SECRET:
        return {"retCode": -1, "retMsg": "Missing API credentials"}

    params = {
        "category": "spot",
        "symbol": SYMBOL,
        "side": side,
        "orderType": "Market",
        "qty": str(round(qty, 5)),
        "timeInForce": "IOC",
    }
    return bybit_request("POST", "/v5/order/create", params)


def calc_order_qty(current_price):
    risk_usdt = min(MAX_POSITION_USDT * (RISK_PERCENT / 100) * 20, MAX_POSITION_USDT)

    usdt_balance = get_coin_balance("USDT")
    if usdt_balance is not None:
        risk_usdt = min(risk_usdt, usdt_balance * 0.98)

    if risk_usdt < MIN_NOTIONAL_USDT:
        return None

    qty = risk_usdt / current_price
    qty = max(MIN_QTY_ETH, min(qty, MAX_QTY_ETH))

    if qty * current_price < MIN_NOTIONAL_USDT:
        return None
    return round(qty, 5)


def manage_open_position(current_price):
    global position

    if not position:
        return

    should_exit = False
    reason = None

    if current_price <= position["stop_loss"]:
        should_exit = True
        reason = "Stop loss"
    elif current_price >= position["take_profit"]:
        should_exit = True
        reason = "Take profit"
    elif (time.time() - position["opened_at"]) >= MAX_HOLD_SECONDS:
        should_exit = True
        reason = "Max hold time"

    if not should_exit:
        return

    result = place_order("Sell", position["qty"])
    if result.get("retCode") == 0:
        send(
            f"<b>EXIT EXECUTED</b>\n"
            f"Reason: {reason}\n"
            f"Qty: {position['qty']:.5f} ETH\n"
            f"Entry: {position['entry_price']:.2f}\n"
            f"Exit ≈ {current_price:.2f}\n"
            f"{('DRY RUN' if DRY_RUN else ('TESTNET' if TESTNET else 'LIVE'))}"
        )
        position = None
    else:
        send(f"Exit failed: {result.get('retMsg', 'Unknown error')}")


def analyse():
    global last_signal_time, position

    eth = get_closes(YAHOO_ETH)
    btc = get_closes(YAHOO_BTC)
    if not eth or not btc:
        return

    min_len = min(len(eth), len(btc))
    eth, btc = eth[-min_len:], btc[-min_len:]
    if min_len < LOOKBACK + 5:
        return

    current = eth[-1]
    if position:
        manage_open_position(current)
        return

    ratios = [eth[i] / btc[i] for i in range(min_len)]
    window = ratios[-LOOKBACK:]
    mean = sum(window) / LOOKBACK
    var = sum((x - mean) ** 2 for x in window) / LOOKBACK
    std = sqrt(var) if var > 0 else 1e-8
    z = (ratios[-1] - mean) / std

    eth_c, eth_h, eth_l = get_ohlc(YAHOO_ETH)
    if not eth_c:
        return

    atr = calc_atr(eth_h, eth_l, eth_c)
    if atr is None or atr <= 0:
        return

    signal = None
    if z >= Z_ENTRY:
        signal = "Sell"
    elif z <= -Z_ENTRY:
        signal = "Buy"

    if not signal:
        return

    if signal == "Sell":
        send(f"Signal=Sell z={z:.2f} ignored (spot long-only entry logic).")
        return

    now = time.time()
    if now - last_signal_time < COOLDOWN:
        return
    last_signal_time = now

    qty = calc_order_qty(current)
    if qty is None:
        send("Entry skipped: insufficient notional/balance for safe order size.")
        return

    stop_loss = current - (SL_ATR * atr)
    take_profit = current + (TP_ATR * atr)

    result = place_order("Buy", qty)
    if result.get("retCode") == 0:
        position = {
            "side": "Buy",
            "qty": qty,
            "entry_price": current,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "opened_at": time.time(),
        }
        send(
            f"<b>ENTRY EXECUTED</b>\n"
            f"Side: Buy\n"
            f"Qty: {qty:.5f} ETH\n"
            f"Entry ≈ {current:.2f}\n"
            f"SL: {stop_loss:.2f}\n"
            f"TP: {take_profit:.2f}\n"
            f"Z-Score: {z:.2f}\n"
            f"{('DRY RUN' if DRY_RUN else ('TESTNET' if TESTNET else 'LIVE'))}"
        )
    else:
        send(f"Order failed: {result.get('retMsg', 'Unknown error')}")


def main():
    mode = "DRY RUN" if DRY_RUN else ("TESTNET" if TESTNET else "LIVE")

    if not TESTNET and not ALLOW_LIVE_TRADING:
        send("LIVE mode blocked: set ALLOW_LIVE_TRADING=True only when ready for real money.")
        return

    if not DRY_RUN and (not API_KEY or not API_SECRET):
        send("Missing API credentials. Populate API_KEY and API_SECRET before non-dry-run mode.")
        return

    send(f"<b>SeaTrader Bybit {mode}</b>\nZ={Z_ENTRY} | Lookback={LOOKBACK}")
    print(f"Bybit bot running ({mode})...")

    while True:
        try:
            analyse()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(120)


if __name__ == "__main__":
    main()
