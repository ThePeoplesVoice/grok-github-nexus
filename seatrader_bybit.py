import time
import requests
import hmac
import hashlib
from math import sqrt
from urllib.parse import urlencode

# ==================== BYBIT CONFIG ====================
API_KEY = ""          # ← Your Bybit API Key
API_SECRET = ""       # ← Your Bybit API Secret
TESTNET = True        # ← Set to False only when ready for real money

# Strategy
LOOKBACK = 24
Z_ENTRY = 2.5
SL_ATR = 1.25
TP_ATR = 1.8
COOLDOWN = 3 * 3600

# Risk
RISK_PERCENT = 0.5            # Very conservative for live
MAX_POSITION_USDT = 50        # Hard cap in USDT

TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""
# ======================================================

BASE_URL = "https://api-testnet.bybit.com" if TESTNET else "https://api.bybit.com"
last_signal_time = 0
in_position = False


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
    params["api_key"] = API_KEY
    params["timestamp"] = timestamp
    params["recv_window"] = 5000

    query = urlencode(sorted(params.items()))
    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    params["sign"] = signature

    url = BASE_URL + endpoint
    if method == "GET":
        r = requests.get(url, params=params, timeout=10)
    else:
        r = requests.post(url, data=params, timeout=10)
    return r.json()


def get_eth_price():
    eth = get_closes("ETH-USD")
    return eth[-1] if eth else None


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


def place_order(side, qty):
    params = {
        "category": "spot",
        "symbol": "ETHUSDT",
        "side": side,  # Buy or Sell
        "orderType": "Market",
        "qty": str(round(qty, 5)),
        "timeInForce": "IOC",
    }
    return bybit_request("POST", "/v5/order/create", params)


def analyse():
    global last_signal_time, in_position

    if in_position:
        return

    eth = get_closes("ETH-USD")
    btc = get_closes("BTC-USD")
    if not eth or not btc:
        return

    min_len = min(len(eth), len(btc))
    eth, btc = eth[-min_len:], btc[-min_len:]
    if min_len < LOOKBACK + 5:
        return

    ratios = [eth[i] / btc[i] for i in range(min_len)]
    window = ratios[-LOOKBACK:]
    mean = sum(window) / LOOKBACK
    var = sum((x - mean) ** 2 for x in window) / LOOKBACK
    std = sqrt(var) if var > 0 else 1e-8
    z = (ratios[-1] - mean) / std

    eth_c, eth_h, eth_l = get_ohlc("ETH-USD")
    if not eth_c:
        return
    atr = calc_atr(eth_h, eth_l, eth_c)
    if atr is None:
        return

    current = eth[-1]
    signal = None
    if z >= Z_ENTRY:
        signal = "Sell"
    elif z <= -Z_ENTRY:
        signal = "Buy"

    if not signal:
        return

    now = time.time()
    if now - last_signal_time < COOLDOWN:
        return
    last_signal_time = now

    # Position size calculation (very conservative)
    risk_usdt = min(MAX_POSITION_USDT * (RISK_PERCENT / 100) * 20, MAX_POSITION_USDT)  # rough
    qty = risk_usdt / current
    qty = max(0.001, min(qty, 0.05))  # hard safety limits

    result = place_order(signal, qty)

    if result.get("retCode") == 0:
        in_position = True
        send(
            f"<b>BYBIT ORDER PLACED</b>\n"
            f"Side: {signal}\n"
            f"Qty: {qty:.5f} ETH\n"
            f"Price ≈ {current:.2f}\n"
            f"Z-Score: {z:.2f}\n"
            f"{'TESTNET' if TESTNET else 'LIVE'}"
        )
    else:
        send(f"Order failed: {result.get('retMsg', 'Unknown error')}")


def main():
    mode = "TESTNET" if TESTNET else "LIVE"
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
