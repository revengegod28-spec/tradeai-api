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

# v4.5.2: SP500 and NASDAQ now receive ETF prices (SPY/QQQ) instead of
# index values, so bounds match the typical ETF range.
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

# v4.11.2: separate cache for computed technical indicators. Daily candles
# change slowly, so 15 minutes is plenty — turns a ~15s cold start into an
# instant response on every subsequent call within the TTL window.
_indicator_cache = {}  # {yahoo_symbol: (data, timestamp)}
INDICATOR_CACHE_TTL = timedelta(minutes=15)


def is_price_sane(symbol: str, price: float) -> bool:
    bounds = PRICE_BOUNDS.get(symbol)
    if not bounds:
        return price > 0
    return bounds[0] <= price <= bounds[1]

# === v4.5.3: technical indicators (RSI / MACD / MA) ===
# === v4.11: added Bollinger / Stochastic / ATR / Pivot / S/R ===

def _ema(values, period):
    """Exponential moving average."""
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = v * k + ema * (1 - k)
    return ema


def _sma(values, period):
    """Simple moving average."""
    if len(values) < period:
        return None
    return round(sum(values[-period:]) / period, 2)


def _rsi(closes, period=14):
    """RSI using Wilder's smoothing."""
    if len(closes) < period + 1:
        return None
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
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _macd_signal(closes):
    """Returns 'bullish' / 'bearish' / None based on MACD vs signal line."""
    if len(closes) < 35:
        return None
    macd_series = []
    for i in range(26, len(closes) + 1):
        e12 = _ema(closes[:i], 12)
        e26 = _ema(closes[:i], 26)
        if e12 is not None and e26 is not None:
            macd_series.append(e12 - e26)
    if len(macd_series) < 9:
        return None
    signal = _ema(macd_series, 9)
    macd_now = macd_series[-1]
    return "bullish" if macd_now > signal else "bearish"


# === v4.11: NEW HELPERS (Bollinger, Stochastic, ATR, S/R) ===

def _std(arr, period):
    """Population standard deviation of the last `period` values."""
    if len(arr) < period:
        return None
    s = arr[-period:]
    mean = sum(s) / period
    return (sum((x - mean) ** 2 for x in s) / period) ** 0.5


def _stochastic(highs, lows, closes, k_period=14, k_smooth=3, d_period=3):
    """Slow Stochastic Oscillator. Returns (K, D) in 0-100."""
    n = k_period + k_smooth + d_period
    if len(closes) < n:
        return 50.0, 50.0
    raw_k = []
    for i in range(k_period, len(closes) + 1):
        win_h = max(highs[i - k_period:i])
        win_l = min(lows[i - k_period:i])
        if win_h == win_l:
            raw_k.append(50.0)
        else:
            raw_k.append(100.0 * (closes[i - 1] - win_l) / (win_h - win_l))
    if len(raw_k) < k_smooth:
        return raw_k[-1], 50.0
    sm_k = []
    for i in range(k_smooth, len(raw_k) + 1):
        sm_k.append(sum(raw_k[i - k_smooth:i]) / k_smooth)
    if len(sm_k) < d_period:
        return sm_k[-1], 50.0
    d_vals = []
    for i in range(d_period, len(sm_k) + 1):
        d_vals.append(sum(sm_k[i - d_period:i]) / d_period)
    return sm_k[-1], d_vals[-1]


def _atr(highs, lows, closes, period=14):
    """Average True Range (Wilder's smoothing)."""
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        h = highs[i]  if i < len(highs)  else closes[i]
        l = lows[i]   if i < len(lows)   else closes[i]
        c = closes[i - 1]
        trs.append(max(h - l, abs(h - c), abs(l - c)))
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def _sr_levels(highs, lows, lookback=20):
    """Support = min of recent lows, Resistance = max of recent highs."""
    if len(highs) < lookback:
        return None, None
    return min(lows[-lookback:]), max(highs[-lookback:])


async def fetch_indicators(session, yahoo_symbol, internal_key):
    """Fetch 1y of daily candles and compute technical indicators (v4.11).
    v4.11.2: caches results for 15 minutes per symbol so repeated calls
    within the window return instantly without hitting Yahoo."""
    # Cache hit?
    now = datetime.now()
    if yahoo_symbol in _indicator_cache:
        cached_data, cached_ts = _indicator_cache[yahoo_symbol]
        if now - cached_ts < INDICATOR_CACHE_TTL:
            return cached_data

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
        async with session.get(
            url,
            params={"interval": "1d", "range": "1y"},
            headers=HEADERS,
            timeout=aiohttp.ClientTimeout(total=10)
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
        if len(closes) < 30:
            return None

        last_close = closes[-1]
        prev_close = closes[-2] if len(closes) >= 2 else last_close
        prev_high  = highs[-2]  if len(highs)  >= 2 else (highs[-1]  if highs  else last_close)
        prev_low   = lows[-2]   if len(lows)   >= 2 else (lows[-1]   if lows   else last_close)

        # Bollinger Bands (20, 2σ)
        sma20  = _sma(closes, 20)
        std20  = _std(closes, 20)
        bb_up  = sma20 + 2 * std20 if std20 is not None else None
        bb_mid = sma20
        bb_lo  = sma20 - 2 * std20 if std20 is not None else None

        # Stochastic (14, 3, 3)
        stoch_k, stoch_d = _stochastic(highs, lows, closes, 14, 3, 3)

        # ATR (14)
        atr_val = _atr(highs, lows, closes, 14)

        # Pivot Points (Classic) on previous day
        pivot    = (prev_high + prev_low + prev_close) / 3
        pivot_r1 = 2 * pivot - prev_low
        pivot_s1 = 2 * pivot - prev_high
        pivot_r2 = pivot + (prev_high - prev_low)
        pivot_s2 = pivot - (prev_high - prev_low)

        # Support / Resistance from recent 20-day swings
        support, resistance = _sr_levels(highs, lows, 20)

        result_data = {
            "rsi":         _rsi(closes),
            "macd_signal": _macd_signal(closes),
            "ma_50":       _sma(closes, 50),
            "ma_200":      _sma(closes, 200) if len(closes) >= 200 else None,
            "bb_upper":    round(bb_up,  4) if bb_up  is not None else None,
            "bb_middle":   round(bb_mid, 4) if bb_mid is not None else None,
            "bb_lower":    round(bb_lo,  4) if bb_lo  is not None else None,
            "stoch_k":     round(stoch_k, 2),
            "stoch_d":     round(stoch_d, 2),
            "atr":         round(atr_val, 4) if atr_val is not None else None,
            "pivot":       round(pivot, 4),
            "pivot_r1":    round(pivot_r1, 4),
            "pivot_s1":    round(pivot_s1, 4),
            "pivot_r2":    round(pivot_r2, 4),
            "pivot_s2":    round(pivot_s2, 4),
            "support":     round(support,    4) if support    is not None else None,
            "resistance":  round(resistance, 4) if resistance is not None else None,
            "last_volume": vols[-1] if vols else None,
            "avg_volume":  round(sum(vols[-20:]) / min(20, len(vols)), 0) if vols else None,
        }
        # v4.11.2: cache the computed indicators
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
        if price <= 0:
            return None
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


async def fetch_one(session: aiohttp.ClientSession, key: str):
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


# === v4.5.2: override S&P 500 and NASDAQ with ETF prices (SPY / QQQ) ===
async def fetch_spy_qqq_overrides(session: aiohttp.ClientSession):
    overrides = {}
    for tv_symbol, internal_key in [("SPY", "SP500"), ("QQQ", "NASDAQ")]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{tv_symbol}"
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    logger.warning(f"[{tv_symbol}] HTTP {resp.status}")
                    continue
                data = await resp.json()
                parsed = parse_yahoo_response(internal_key, data)
                if parsed:
                    overrides[internal_key] = parsed
        except Exception as e:
            logger.warning(f"[{tv_symbol}] fetch error: {e}")
    return overrides


@app.get("/")
def root():
    return {
        "message": "TradeAI API",
        "status": "active",
        "cache_ttl_seconds": CACHE_TTL.total_seconds(),
        "indicator_cache_ttl_seconds": INDICATOR_CACHE_TTL.total_seconds(),
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
            if data:
                results[key] = data

        # v4.5.2: override S&P 500 and NASDAQ with ETF prices
        etf_overrides = await fetch_spy_qqq_overrides(session)
        for symbol, data in etf_overrides.items():
            if data and "price" in data:
                results[symbol] = data
                        # v4.5.3: compute technical indicators
        indicator_tasks = [
            fetch_indicators(session, SYMBOLS.get(k, k), k)
            for k in results.keys()
        ]
        for k, ind in zip(results.keys(), await asyncio.gather(*indicator_tasks)):
            if ind:
                results[k].update(ind)

    if not results:
        raise HTTPException(503, "No data fetched from upstream")

    _cache["data"] = results
    _cache["ts"] = datetime.now()
    return results
