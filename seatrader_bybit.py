import argparse
import json
import time
import hmac
import hashlib
from itertools import product
from math import sin, sqrt
from statistics import mean, median
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

# Backtest defaults
BACKTEST_START_USDT = 100.0
BACKTEST_FEE_RATE = 0.001  # 0.10% taker
BACKTEST_SLIPPAGE_BPS = 10

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


def build_atr_series(highs, lows, closes, period=14):
    if not highs or not lows or not closes:
        return None
    n = min(len(highs), len(lows), len(closes))
    highs, lows, closes = highs[-n:], lows[-n:], closes[-n:]
    atr = [None] * n
    trs = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
        if len(trs) >= period:
            atr[i] = sum(trs[-period:]) / period
    return atr


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
    mean_window = sum(window) / LOOKBACK
    var = sum((x - mean_window) ** 2 for x in window) / LOOKBACK
    std = sqrt(var) if var > 0 else 1e-8
    z = (ratios[-1] - mean_window) / std

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


def slice_data(eth_c, eth_h, eth_l, btc_c, bars):
    n = min(len(eth_c), len(eth_h), len(eth_l), len(btc_c), bars)
    return eth_c[-n:], eth_h[-n:], eth_l[-n:], btc_c[-n:]


def simulate_single_scenario(eth_c, eth_h, eth_l, btc_c, config):
    lookback = config["lookback"]
    z_entry = config["z_entry"]
    sl_atr = config["sl_atr"]
    tp_atr = config["tp_atr"]
    cooldown_bars = config["cooldown_bars"]
    max_hold_bars = config["max_hold_bars"]
    fee_rate = config["fee_rate"]
    slippage_bps = config["slippage_bps"]
    initial_balance = config["initial_balance"]

    n = min(len(eth_c), len(eth_h), len(eth_l), len(btc_c))
    if n < max(lookback + 5, 80):
        return None

    eth_c, eth_h, eth_l, btc_c = eth_c[-n:], eth_h[-n:], eth_l[-n:], btc_c[-n:]
    atr = build_atr_series(eth_h, eth_l, eth_c, period=14)
    if not atr:
        return None

    ratios = [eth_c[i] / btc_c[i] for i in range(n)]

    cash = initial_balance
    peak_equity = initial_balance
    max_drawdown = 0.0
    last_entry_bar = -10**9
    active_position = None
    trades = []

    for i in range(max(lookback, 15), n):
        current_close = eth_c[i]
        current_high = eth_h[i]
        current_low = eth_l[i]

        if active_position is not None:
            exit_reason = None
            exit_price = None

            sl_hit = current_low <= active_position["sl"]
            tp_hit = current_high >= active_position["tp"]
            timed_out = (i - active_position["entry_bar"]) >= max_hold_bars

            if sl_hit and tp_hit:
                exit_reason = "both_hit_worst_case"
                exit_price = active_position["sl"]
            elif sl_hit:
                exit_reason = "stop_loss"
                exit_price = active_position["sl"]
            elif tp_hit:
                exit_reason = "take_profit"
                exit_price = active_position["tp"]
            elif timed_out:
                exit_reason = "timeout"
                exit_price = current_close

            if exit_reason:
                fill_exit = exit_price * (1 - slippage_bps / 10000)
                proceeds = active_position["qty"] * fill_exit
                exit_fee = proceeds * fee_rate
                cash += proceeds - exit_fee

                pnl = cash - active_position["cash_before_entry"]
                trades.append({"pnl": pnl, "win": pnl > 0, "reason": exit_reason})
                active_position = None

        if active_position is None and (i - last_entry_bar) >= cooldown_bars:
            window = ratios[i - lookback + 1 : i + 1]
            mean_window = sum(window) / lookback
            variance = sum((x - mean_window) ** 2 for x in window) / lookback
            std = sqrt(variance) if variance > 0 else 1e-8
            z = (ratios[i] - mean_window) / std

            if z <= -z_entry and atr[i] is not None and atr[i] > 0:
                risk_usdt = min(MAX_POSITION_USDT * (RISK_PERCENT / 100) * 20, MAX_POSITION_USDT, cash * 0.98)
                if risk_usdt >= MIN_NOTIONAL_USDT:
                    qty = risk_usdt / current_close
                    qty = max(MIN_QTY_ETH, min(qty, MAX_QTY_ETH))
                    entry_fill = current_close * (1 + slippage_bps / 10000)
                    cost = qty * entry_fill
                    entry_fee = cost * fee_rate
                    total_cost = cost + entry_fee

                    if total_cost <= cash and (qty * current_close) >= MIN_NOTIONAL_USDT:
                        stop_loss = current_close - (sl_atr * atr[i])
                        take_profit = current_close + (tp_atr * atr[i])
                        if stop_loss > 0 and take_profit > current_close:
                            cash_before = cash
                            cash -= total_cost
                            active_position = {
                                "qty": qty,
                                "entry_bar": i,
                                "sl": stop_loss,
                                "tp": take_profit,
                                "cash_before_entry": cash_before,
                            }
                            last_entry_bar = i

        if active_position is not None:
            equity = cash + (active_position["qty"] * current_close)
        else:
            equity = cash

        if equity > peak_equity:
            peak_equity = equity
        if peak_equity > 0:
            dd = (peak_equity - equity) / peak_equity
            if dd > max_drawdown:
                max_drawdown = dd

    if active_position is not None:
        final_close = eth_c[-1]
        fill_exit = final_close * (1 - slippage_bps / 10000)
        proceeds = active_position["qty"] * fill_exit
        exit_fee = proceeds * fee_rate
        cash += proceeds - exit_fee
        pnl = cash - active_position["cash_before_entry"]
        trades.append({"pnl": pnl, "win": pnl > 0, "reason": "forced_close_end"})

    total_trades = len(trades)
    wins = sum(1 for t in trades if t["win"])
    losses = total_trades - wins
    win_rate = (wins / total_trades) if total_trades else 0.0
    avg_trade_pnl = (sum(t["pnl"] for t in trades) / total_trades) if total_trades else 0.0

    return {
        "final_equity": cash,
        "return_pct": ((cash / initial_balance) - 1) * 100,
        "max_drawdown_pct": max_drawdown * 100,
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "avg_trade_pnl": avg_trade_pnl,
    }


def build_synthetic_market_data(total_bars=40 * 24):
    eth_c = []
    eth_h = []
    eth_l = []
    btc_c = []

    eth_price = 3200.0
    btc_price = 62000.0

    for i in range(total_bars):
        cycle = sin(i / 18.0)
        regime = 0.00035 if (i // 220) % 2 == 0 else -0.00025

        shock = 0.0
        if i % 173 == 0 and i > 0:
            shock -= 0.035
        if i % 257 == 0 and i > 0:
            shock += 0.028

        eth_ret = regime + (cycle * 0.007) + shock + (((i % 9) - 4) * 0.00065)
        btc_ret = (regime * 0.6) + (sin((i + 11) / 26.0) * 0.0035) + (shock * 0.4) + (((i % 7) - 3) * 0.0004)

        eth_price = max(350.0, eth_price * (1 + eth_ret))
        btc_price = max(9000.0, btc_price * (1 + btc_ret))

        spread = eth_price * (0.004 + (abs(cycle) * 0.003))
        high = eth_price + spread
        low = max(1.0, eth_price - (spread * 1.1))

        eth_c.append(eth_price)
        eth_h.append(high)
        eth_l.append(low)
        btc_c.append(btc_price)

    return eth_c, eth_h, eth_l, btc_c


def run_backtest(brutal_rounds=1):
    eth_c, eth_h, eth_l = get_ohlc(YAHOO_ETH)
    btc_c = get_closes(YAHOO_BTC)
    source = "Yahoo historical"
    if not eth_c or not eth_h or not eth_l or not btc_c:
        eth_c, eth_h, eth_l, btc_c = build_synthetic_market_data()
        source = "Synthetic stress data (Yahoo unavailable)"

    n = min(len(eth_c), len(eth_h), len(eth_l), len(btc_c))
    eth_c, eth_h, eth_l, btc_c = eth_c[-n:], eth_h[-n:], eth_l[-n:], btc_c[-n:]

    slice_map = {
        "full": n,
        "30d": min(n, 30 * 24),
        "14d": min(n, 14 * 24),
        "7d": min(n, 7 * 24),
    }

    scenarios = []
    base_grid = product(
        [2.0, 2.5, 3.0],       # z entry
        [1.0, 1.25, 1.5],      # sl atr
        [1.2, 1.8, 2.4],       # tp atr
        [1, 3, 6],             # cooldown hours
        [24, 48],              # max hold hours
        [0.001, 0.002],        # fee rate per side
        [5, 15],               # slippage bps
    )

    grid_list = list(base_grid)
    total_estimated = len(grid_list) * len(slice_map) * max(1, brutal_rounds)

    print("\n=== SeaTrader Backtest / Stress Mode ===")
    print(f"Starting balance: ${BACKTEST_START_USDT:.2f}")
    print(f"Data source: {source}")
    print(f"Data candles: {n} (1h)")
    print(f"Planned scenarios: {total_estimated}")

    completed = 0
    for round_idx in range(max(1, brutal_rounds)):
        for z_entry, sl_atr, tp_atr, cooldown_h, max_hold_h, fee_rate, slippage_bps in grid_list:
            for label, bars in slice_map.items():
                sc_eth_c, sc_eth_h, sc_eth_l, sc_btc_c = slice_data(eth_c, eth_h, eth_l, btc_c, bars)
                result = simulate_single_scenario(
                    sc_eth_c,
                    sc_eth_h,
                    sc_eth_l,
                    sc_btc_c,
                    {
                        "lookback": LOOKBACK,
                        "z_entry": z_entry,
                        "sl_atr": sl_atr,
                        "tp_atr": tp_atr,
                        "cooldown_bars": cooldown_h,
                        "max_hold_bars": max_hold_h,
                        "fee_rate": fee_rate,
                        "slippage_bps": slippage_bps,
                        "initial_balance": BACKTEST_START_USDT,
                    },
                )
                completed += 1

                if result is not None:
                    scenarios.append(
                        {
                            "round": round_idx + 1,
                            "slice": label,
                            "z": z_entry,
                            "sl": sl_atr,
                            "tp": tp_atr,
                            "cooldown_h": cooldown_h,
                            "max_hold_h": max_hold_h,
                            "fee_rate": fee_rate,
                            "slippage_bps": slippage_bps,
                            **result,
                        }
                    )

                if completed % 300 == 0:
                    print(f"Progress: {completed}/{total_estimated} scenarios...")

    if not scenarios:
        print("No valid scenarios completed.")
        return

    final_equities = [s["final_equity"] for s in scenarios]
    returns = [s["return_pct"] for s in scenarios]
    drawdowns = [s["max_drawdown_pct"] for s in scenarios]
    win_rates = [s["win_rate"] for s in scenarios if s["trades"] > 0]
    trades = [s["trades"] for s in scenarios]

    profitable = sum(1 for x in final_equities if x > BACKTEST_START_USDT)
    profitable_pct = (profitable / len(final_equities)) * 100

    sorted_final = sorted(final_equities)
    p10 = sorted_final[max(0, int(0.10 * (len(sorted_final) - 1)))]
    p50 = sorted_final[max(0, int(0.50 * (len(sorted_final) - 1)))]
    p90 = sorted_final[max(0, int(0.90 * (len(sorted_final) - 1)))]

    best = max(scenarios, key=lambda x: x["final_equity"])
    worst = min(scenarios, key=lambda x: x["final_equity"])

    print("\n=== Stress Results (many historical scenarios) ===")
    print(f"Completed scenarios: {len(scenarios)}")
    print(f"Average final equity (from $100): ${mean(final_equities):.2f}")
    print(f"Median final equity (from $100):  ${median(final_equities):.2f}")
    print(f"Expected return range: min {min(returns):.2f}% | avg {mean(returns):.2f}% | max {max(returns):.2f}%")
    print(f"Profitability across scenarios: {profitable_pct:.2f}%")
    print(f"Equity distribution: p10 ${p10:.2f} | p50 ${p50:.2f} | p90 ${p90:.2f}")
    print(f"Max drawdown pressure: best {min(drawdowns):.2f}% | avg {mean(drawdowns):.2f}% | worst {max(drawdowns):.2f}%")
    print(f"Trade count pressure: min {min(trades)} | avg {mean(trades):.2f} | max {max(trades)}")
    if win_rates:
        print(f"Win-rate across active scenarios: avg {mean(win_rates) * 100:.2f}%")
    else:
        print("Win-rate across active scenarios: no scenarios generated trades")

    print("\nBest scenario:")
    print(
        f"  slice={best['slice']} z={best['z']} sl={best['sl']} tp={best['tp']} "
        f"cooldown={best['cooldown_h']}h hold={best['max_hold_h']}h fee={best['fee_rate']:.3f} "
        f"slip={best['slippage_bps']}bps -> final=${best['final_equity']:.2f}, "
        f"win-rate={best['win_rate'] * 100:.2f}%, MDD={best['max_drawdown_pct']:.2f}%"
    )

    print("Worst scenario:")
    print(
        f"  slice={worst['slice']} z={worst['z']} sl={worst['sl']} tp={worst['tp']} "
        f"cooldown={worst['cooldown_h']}h hold={worst['max_hold_h']}h fee={worst['fee_rate']:.3f} "
        f"slip={worst['slippage_bps']}bps -> final=${worst['final_equity']:.2f}, "
        f"win-rate={worst['win_rate'] * 100:.2f}%, MDD={worst['max_drawdown_pct']:.2f}%"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="SeaTrader Bybit")
    parser.add_argument("--mode", choices=["trade", "backtest"], default="trade")
    parser.add_argument(
        "--brutal-runs",
        type=int,
        default=1,
        help="Repeat full stress grid N times in backtest mode",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.mode == "backtest":
        run_backtest(brutal_rounds=max(1, args.brutal_runs))
        return

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
