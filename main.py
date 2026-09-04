from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tradeai-api")

app = FastAPI(title="TradeAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYMBOLS = {
    "AAPL": "AAPL", "TSLA": "TSLA", "MSFT": "MSFT", "GOOGL": "GOOGL",
    "AMZN": "AMZN", "NVDA": "NVDA", "META": "META", "NFLX": "NFLX",
    "BTC": "BTC-USD", "ETH": "ETH-USD", "BNB": "BNB-USD",
    "SOL": "SOL-USD", "XRP": "XRP-USD",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F", "WTI": "CL=F", "BRENT": "BZ=F",
    "SP500": "^GSPC", "NASDAQ": "^IXIC",
}

PRICE_BOUNDS = {
    "NFLX": (50, 2000), "BTC": (1000, 1_000_000), "ETH": (50, 50_000),
    "AAPL": (50, 1000), "TSLA": (20, 2000), "NVDA": (10, 5000),
    "MSFT": (50, 2000), "GOOGL": (50, 2000), "AMZN": (20, 5000),
    "META": (50, 2000), "XAUUSD": (500, 20000),
    "WTI": (10, 500), "BRENT": (10, 500),
    "SP500": (300, 2000), "NASDAQ": (300, 2000),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_cache = {"data": None, "ts": None}
CACHE_TTL = timedelta(minutes=2)
_indicator_cache = {}
INDICATOR_CACHE_TTL = timedelta(minutes=15)
_backtest_cache = {"data": None, "ts": None}
BACKTEST_CACHE_TTL = timedelta(hours=6)


def is_price_sane(symbol: str, price: float) -> bool:
    bounds = PRICE_BOUNDS.get(symbol)
    if not bounds: return price > 0
    return bounds[0] <= price <= bounds[1]


def _ema(values, period):
    if len(values) < period: return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _sma(values, period):
    if len(values) < period: return None
    return sum(values[-period:]) / period


def _rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(0, diff))
        losses.append(max(0, -diff))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0: return 100.0
    return 100 - (100 / (1 + (avg_gain / avg_loss)))


def _macd_signal(closes):
    if len(closes) < 35: return None
    macd_series = []
    for i in range(26, len(closes) + 1):
        e12 = _ema(closes[:i], 12)
        e26 = _ema(closes[:i], 26)
        if e12 is not None and e26 is not None:
            macd_series.append(e12 - e26)
    if len(macd_series) < 9: return None
    signal = _ema(macd_series, 9)
    return "bullish" if macd_series[-1] > signal else "bearish"


def _std(arr, period):
    if len(arr) < period: return None
    s = arr[-period:]
    mean = sum(s) / period
    return (sum((x - mean) ** 2 for x in s) / period) ** 0.5


def _stochastic(highs, lows, closes, k_period=14, k_smooth=3, d_period=3):
    n = k_period + k_smooth + d_period
    if len(closes) < n: return 50.0, 50.0
    raw_k = []
    for i in range(k_period, len(closes) + 1):
        win_h = max(highs[i - k_period:i])
        win_l = min(lows[i - k_period:i])
        if win_h == win_l: raw_k.append(50.0)
        else: raw_k.append(100.0 * (closes[i - 1] - win_l) / (win_h - win_l))
    if len(raw_k) < k_smooth: return raw_k[-1], 50.0
    sm_k = []
    for i in range(k_smooth, len(raw_k) + 1):
        sm_k.append(sum(raw_k[i - k_smooth:i]) / k_smooth)
    if len(sm_k) < d_period: return sm_k[-1], 50.0
    d_vals = []
    for i in range(d_period, len(sm_k) + 1):
        d_vals.append(sum(sm_k[i - d_period:i]) / d_period)
    return sm_k[-1], d_vals[-1]


def _atr(highs, lows, closes, period=14):
    if len(closes) < period + 1: return None
    trs = []
    for i in range(1, len(closes)):
        h = highs[i]  if i < len(highs)  else closes[i]
        l = lows[i]   if i < len(lows)   else closes[i]
        c = closes[i - 1]
        trs.append(max(h - l, abs(h - c), abs(l - c)))
    if len(trs) < period: return None
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def _sr_levels(highs, lows, lookback=20):
    if len(highs) < lookback: return None, None
    return min(lows[-lookback:]), max(highs[-lookback:])


def _score_v5(closes, highs, lows, vols, i):
    """v5.2 ENSEMBLE + v5.3 trailing/cap. Three strategies vote; only enter
    when total vote reaches +3 (long) or -3 (short)."""
    if i < 60: return None
    window = closes[:i + 1]
    win_h  = highs[:i + 1] if i < len(highs) else window
    win_l  = lows[:i + 1]  if i < len(lows)  else window
    win_v  = vols[:i + 1]  if vols else None
    price  = window[-1]
    ma20   = _sma(window, 20)
    ma50   = _sma(window, 50)
    ma200  = _sma(window, 200) if i >= 199 else None
    rsi    = _rsi(window)
    macd   = _macd_signal(window)
    atr_v  = _atr(win_h, win_l, window, 14) if i >= 14 else None
    sma20  = _sma(window, 20)
    std20  = _std(window, 20) if i >= 19 else None
    if rsi is None or ma50 is None or atr_v is None: return None

    # Strategy 1: Trend
    trend_vote, trend_reasons = 0, []
    trend = 'neutral'
    if ma200:
        if price > ma200 * 1.005: trend = 'up'
        elif price < ma200 * 0.995: trend = 'down'
    if trend == 'up':
        if ma20 and abs(price - ma20) / ma20 < 0.02:
            trend_vote += 2; trend_reasons.append('pullback MA20')
        elif abs(price - ma50) / ma50 < 0.03:
            trend_vote += 1; trend_reasons.append('pullback MA50')
        if rsi < 35: trend_vote += 1; trend_reasons.append('RSI oversold')
        if macd == 'bullish': trend_vote += 1; trend_reasons.append('MACD up')
    elif trend == 'down':
        if ma20 and abs(price - ma20) / ma20 < 0.02:
            trend_vote -= 2; trend_reasons.append('rally MA20')
        elif abs(price - ma50) / ma50 < 0.03:
            trend_vote -= 1; trend_reasons.append('rally MA50')
        if rsi > 65: trend_vote -= 1; trend_reasons.append('RSI overbought')
        if macd == 'bearish': trend_vote -= 1; trend_reasons.append('MACD down')

    # Strategy 2: Mean Reversion (Bollinger touch)
    reversion_vote, reversion_reasons = 0, []
    if sma20 is not None and std20 is not None and std20 > 0:
        bb_lower = sma20 - 2 * std20
        bb_upper = sma20 + 2 * std20
        if price <= bb_lower * 1.01:
            reversion_vote += 2; reversion_reasons.append('BB lower touch')
            if rsi < 30: reversion_vote += 1; reversion_reasons.append('RSI extreme')
        elif price >= bb_upper * 0.99:
            reversion_vote -= 2; reversion_reasons.append('BB upper touch')
            if rsi > 70: reversion_vote -= 1; reversion_reasons.append('RSI extreme')

    # Strategy 3: Breakout (20d high/low + volume)
    breakout_vote, breakout_reasons = 0, []
    if len(win_h) >= 20 and len(win_l) >= 20:
        recent_high = max(win_h[-20:])
        recent_low  = min(win_l[-20:])
        if price >= recent_high * 0.998:
            breakout_vote += 2; breakout_reasons.append('20d high test')
            if win_v and len(win_v) >= 20:
                avg_v = sum(win_v[-20:]) / 20
                if avg_v > 0 and win_v[-1] / avg_v > 1.2:
                    breakout_vote += 1; breakout_reasons.append('volume confirms')
        elif price <= recent_low * 1.002:
            breakout_vote -= 2; breakout_reasons.append('20d low test')
            if win_v and len(win_v) >= 20:
                avg_v = sum(win_v[-20:]) / 20
                if avg_v > 0 and win_v[-1] / avg_v > 1.2:
                    breakout_vote -= 1; breakout_reasons.append('volume confirms')

    # Voting
    total_vote = trend_vote + reversion_vote + breakout_vote
    if total_vote >= 3: action = 'buy'
    elif total_vote <= -3: action = 'sell'
    else: action = 'wait'

    # Levels
    stop, target = None, None
    if action == 'buy':
        atr_stop  = price - 1.5 * atr_v
        ma50_stop = ma50 * 0.975
        stop = max(atr_stop, ma50_stop)
        risk = price - stop
        target = price + 1.5 * risk
    elif action == 'sell':
        atr_stop  = price + 1.5 * atr_v
        ma50_stop = ma50 * 1.025
        stop = min(atr_stop, ma50_stop)
        risk = stop - price
        target = price - 1.5 * risk

    def sign(v): return ('+' if v >= 0 else '') + str(v)
    reasons = []
    if trend_reasons:     reasons.append(f"Trend {sign(trend_vote)}: {','.join(trend_reasons)}")
    if reversion_reasons: reasons.append(f"Reversion {sign(reversion_vote)}: {','.join(reversion_reasons)}")
    if breakout_reasons:  reasons.append(f"Breakout {sign(breakout_vote)}: {','.join(breakout_reasons)}")
    if not reasons: reasons = [f'Total vote {total_vote} (need ±3 to enter)']

    return {
        'action': action, 'score': total_vote, 'reasons': reasons,
        'atr': atr_v, 'stop': stop, 'target': target,
        'trend': trend, 'ma200': ma200,
    }


def _simulate_v5(closes, highs, lows, vols, symbol):
    """v5.3: hard cap 10% + trailing stop.
    v5.3.1: hard cap also applies to timeouts (the original bug)."""
    HARD_CAP_PCT = 0.10
    TRAIL_ARM_1  = 0.01
    TRAIL_ARM_2  = 0.02
    MAX_HOLD     = 10
    trades = []
    i = 60
    while i < len(closes) - 3:
        sig = _score_v5(closes, highs, lows, vols, i)
        if sig is None or sig['action'] != 'buy' or sig['stop'] is None:
            i += 1
            continue
        entry   = closes[i]
        stop    = sig['stop']
        target  = sig['target']
        hard_stop   = entry * (1 - HARD_CAP_PCT)
        active_stop = max(stop, hard_stop)
        highest = entry
        exit_idx, exit_price, outcome = None, None, None
        for j in range(i + 1, min(i + MAX_HOLD + 1, len(closes))):
            cur_high = highs[j] if j < len(highs) else closes[j]
            cur_low  = lows[j]  if j < len(lows)  else closes[j]
            if cur_high > highest: highest = cur_high
            gain = (highest - entry) / entry
            if gain >= TRAIL_ARM_2:
                active_stop = max(active_stop, entry * 1.01)
            elif gain >= TRAIL_ARM_1:
                active_stop = max(active_stop, entry)
            if cur_high >= target:
                exit_idx, exit_price, outcome = j, target, 'win'
                break
            if cur_low <= active_stop:
                exit_idx, exit_price, outcome = j, active_stop, 'loss'
                break
        if exit_idx is None:
            exit_idx = min(i + MAX_HOLD, len(closes) - 1)
            raw_exit = closes[exit_idx]
            # v5.3.1 bugfix: hard cap also applies to timeouts.
            if raw_exit < active_stop:
                exit_price = active_stop
                outcome = 'loss'
            else:
                exit_price = raw_exit
                outcome = 'timeout'
        pnl_pct = ((exit_price - entry) / entry) * 100
        trades.append({
            'symbol': symbol, 'entry_idx': i, 'exit_idx': exit_idx,
            'outcome': outcome, 'pnl_pct': round(pnl_pct, 2),
        })
        i = exit_idx + 1
    return trades


async def fetch_indicators(session, yahoo_symbol, internal_key):
    now = datetime.now()
    if yahoo_symbol in _indicator_cache:
        cached, ts = _indicator_cache[yahoo_symbol]
        if now - ts < INDICATOR_CACHE_TTL: return cached
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        async with session.get(
            url, params={"interval": "1d", "range": "1y"},
            headers=HEADERS, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                logger.warning(f"[{internal_key}] indicators HTTP {resp.status}")
                return None
            data = await resp.json()
        result = data["chart"]["result"][0]
        quotes = result["indicators"]["quote"][0]
        closes = [c for c in quotes["close"] if c is not None]
        highs  = [h for h in quotes["high"]  if h is not None]
        lows   = [l for l in quotes["low"]   if l is not None]
        vols   = [v for v in quotes.get("volume", []) if v is not None]
        if len(closes) < 30: return None
        sig = _score_v5(closes, highs, lows, vols, len(closes) - 1)
        if sig is None: return None
        last_close = closes[-1]
        prev_close = closes[-2] if len(closes) >= 2 else last_close
        prev_high  = highs[-2]  if len(highs)  >= 2 else (highs[-1]  if highs  else last_close)
        prev_low   = lows[-2]   if len(lows)   >= 2 else (lows[-1]   if lows   else last_close)
        sma20 = _sma(closes, 20)
        std20 = _std(closes, 20)
        bb_up = sma20 + 2 * std20 if std20 is not None else None
        bb_lo = sma20 - 2 * std20 if std20 is not None else None
        stoch_k, stoch_d = _stochastic(highs, lows, closes, 14, 3, 3)
        atr_v = _atr(highs, lows, closes, 14)
        pivot    = (prev_high + prev_low + prev_close) / 3
        pivot_r1 = 2 * pivot - prev_low
        pivot_s1 = 2 * pivot - prev_high
        pivot_r2 = pivot + (prev_high - prev_low)
        pivot_s2 = pivot - (prev_high - prev_low)
        support, resistance = _sr_levels(highs, lows, 20)
        result_data = {
            "rsi":         round(_rsi(closes), 2) if _rsi(closes) is not None else None,
            "macd_signal": _macd_signal(closes),
            "ma_50":       round(_sma(closes, 50), 2) if _sma(closes, 50) else None,
            "ma_200":      round(_sma(closes, 200), 2) if len(closes) >= 200 and _sma(closes, 200) else None,
            "bb_upper":    round(bb_up, 4) if bb_up is not None else None,
            "bb_middle":   round(sma20, 4) if sma20 is not None else None,
            "bb_lower":    round(bb_lo, 4) if bb_lo is not None else None,
            "stoch_k":     round(stoch_k, 2),
            "stoch_d":     round(stoch_d, 2),
            "atr":         round(atr_v, 4) if atr_v is not None else None,
            "pivot":       round(pivot, 4),
            "pivot_r1":    round(pivot_r1, 4),
            "pivot_s1":    round(pivot_s1, 4),
            "pivot_r2":    round(pivot_r2, 4),
            "pivot_s2":    round(pivot_s2, 4),
            "support":     round(support, 4) if support is not None else None,
            "resistance":  round(resistance, 4) if resistance is not None else None,
            "last_volume": vols[-1] if vols else None,
            "avg_volume":  round(sum(vols[-20:]) / min(20, len(vols)), 0) if vols else None,
            "v5_action":   sig['action'],
            "v5_score":    sig['score'],
            "v5_reasons":  sig['reasons'],
            "v5_trend":    sig['trend'],
        }
        _indicator_cache[yahoo_symbol] = (result_data, now)
        return result_data
    except Exception as e:
        logger.warning(f"[{internal_key}] indicator fetch failed: {e}")
        return None


def parse_yahoo_response(symbol: str, data: dict):
    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = float(meta.get("regularMarketPrice", 0))
        prev = float(meta.get("previousClose", meta.get("chartPreviousClose", price)))
        if price <= 0: return None
        if not is_price_sane(symbol, price):
            logger.warning(f"[{symbol}] price {price} outside sane bounds — rejected")
            return None
        change = ((price - prev) / prev * 100) if prev else 0
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change_percent": round(change, 2),
            "currency": meta.get("currency", "USD"),
            "high_24": float(meta.get("regularMarketDayHigh", 0)) or None,
            "low_24":  float(meta.get("regularMarketDayLow",  0)) or None,
        }
    except (KeyError, IndexError, TypeError, ValueError) as e:
        logger.warning(f"[{symbol}] parse error: {e}")
        return None


async def fetch_one(session, key):
    yahoo = SYMBOLS.get(key, key)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}"
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                logger.warning(f"[{key}] HTTP {resp.status}")
                return key, None
            data = await resp.json()
            return key, parse_yahoo_response(key, data)
    except Exception as e:
        logger.warning(f"[{key}] fetch error: {e}")
        return key, None


async def fetch_spy_qqq_overrides(session):
    overrides = {}
    for tv_symbol, internal_key in [("SPY", "SP500"), ("QQQ", "NASDAQ")]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{tv_symbol}"
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200: continue
                data = await resp.json()
                parsed = parse_yahoo_response(internal_key, data)
                if parsed: overrides[internal_key] = parsed
        except Exception as e:
            logger.warning(f"[{tv_symbol}] fetch error: {e}")
    return overrides


@app.get("/")
def root():
    return {
        "message": "TradeAI API v5.3.1 (Ensemble + Trailing + Cap on timeout)",
        "status": "active",
        "cache_ttl_seconds": CACHE_TTL.total_seconds(),
        "indicator_cache_ttl_seconds": INDICATOR_CACHE_TTL.total_seconds(),
        "backtest_cache_ttl_seconds": BACKTEST_CACHE_TTL.total_seconds(),
    }


@app.get("/price/{symbol}")
async def get_price(symbol: str):
    return data


@app.get("/prices")
async def get_all_prices():
    if _cache["ts"] and datetime.now() - _cache["ts"] < CACHE_TTL and _cache["data"]:
        return _cache["data"]
    results = {}
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, key) for key in SYMBOLS]
        for key, data in await asyncio.gather(*tasks):
            if data: results[key] = data
        etf_overrides = await fetch_spy_qqq_overrides(session)
        for symbol, data in etf_overrides.items():
            if data and "price" in data:
                results[symbol] = data
        indicator_tasks = [
            fetch_indicators(session, SYMBOLS.get(k, k), k)
            for k in results.keys()
        ]
        for k, ind in zip(results.keys(), await asyncio.gather(*indicator_tasks)):
            if ind: results[k].update(ind)
    if not results:
        raise HTTPException(503, "No data fetched from upstream")
    _cache["data"] = results
    _cache["ts"] = datetime.now()
    return results


@app.get("/backtest")
async def backtest():
    if _backtest_cache["ts"] and datetime.now() - _backtest_cache["ts"] < BACKTEST_CACHE_TTL and _backtest_cache["data"]:
        return _backtest_cache["data"]
    all_trades = []
    by_symbol = {}
    async with aiohttp.ClientSession() as session:
        for sym, yahoo in SYMBOLS.items():
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}"
                async with session.get(
                    url, params={"interval": "1d", "range": "1y"},
                    headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200: continue
                    data = await resp.json()
                result = data["chart"]["result"][0]
                quotes = result["indicators"]["quote"][0]
                closes = [c for c in quotes["close"] if c is not None]
                highs  = [h for h in quotes["high"]  if h is not None]
                lows   = [l for l in quotes["low"]   if l is not None]
                vols   = [v for v in quotes.get("volume", []) if v is not None]
                if len(closes) < 60: continue
                trades = _simulate_v5(closes, highs, lows, vols, sym)
                all_trades.extend(trades)
                by_symbol[sym] = {
                    "trades": len(trades),
                    "wins": sum(1 for t in trades if t["outcome"] == "win"),
                    "losses": sum(1 for t in trades if t["outcome"] == "loss"),
                    "timeouts": sum(1 for t in trades if t["outcome"] == "timeout"),
                    "avg_pnl": round(sum(t["pnl_pct"] for t in trades) / len(trades), 2) if trades else 0,
                }
            except Exception as e:
                logger.warning(f"[{sym}] backtest failed: {e}")

    if not all_trades:
        raise HTTPException(503, "No data for backtest")

    wins = sum(1 for t in all_trades if t["outcome"] == "win")
    losses = sum(1 for t in all_trades if t["outcome"] == "loss")
    timeouts = sum(1 for t in all_trades if t["outcome"] == "timeout")
    total = len(all_trades)
    win_rate = (wins / total * 100) if total > 0 else 0
    avg_pnl = sum(t["pnl_pct"] for t in all_trades) / total if total > 0 else 0
    pnls = [t["pnl_pct"] for t in all_trades]
    median_pnl = sorted(pnls)[total // 2] if total else 0
    eq, peak, max_dd = 100.0, 100.0, 0.0
    for t in all_trades:
        eq *= (1 + t["pnl_pct"] / 100.0)
        if eq > peak: peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd: max_dd = dd

    result_data = {
        "engine": "v5.3.1",
        "period": "1y",
        "assets_tested": len(SYMBOLS),
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "timeouts": timeouts,
        "win_rate": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 2),
        "median_pnl": round(median_pnl, 2),
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
        "max_drawdown_pct": round(max_dd, 2),
        "by_symbol": by_symbol,
    }
    _backtest_cache["data"] = result_data
    _backtest_cache["ts"] = datetime.now()
    return result_data
