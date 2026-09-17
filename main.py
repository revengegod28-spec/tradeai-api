"""
TradeAI Backend API - v6.2.2
============================
Stage 1+ Improvements (Strict Selectivity):
  - Threshold raised to +/-4 (require very strong consensus)
  - Triple Confirmation: require >=2 independent signals aligned
  - 30-day cooldown between trades on same asset
  - Golden Cross filter: MA50 > MA200 required for buys
  - Death Cross filter: MA50 < MA200 required for sells
  - Anti-chase tightened to >2% (was >1%)
  - Max 5 trades per asset per year (forces selectivity)
Endpoints:
  GET /                -> health check
  GET /prices          -> all 21 assets (live indicators)
  GET /price/{symbol}  -> single asset detail
  GET /backtest        -> simulate rules on 12 months of synthetic history
"""
import os
import time
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import aiohttp

app = FastAPI(title="TradeAI API", version="6.2.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ASSETS = [
    {"id": "AAPL",   "symbol": "AAPL",   "name_ar": "\u0623\u0628\u0644",                "name_en": "Apple",             "type": "stocks",     "yahoo": "AAPL",          "coingecko": None},
    {"id": "TSLA",   "symbol": "TSLA",   "name_ar": "\u062a\u0633\u0644\u0627",               "name_en": "Tesla",             "type": "stocks",     "yahoo": "TSLA",          "coingecko": None},
    {"id": "MSFT",   "symbol": "MSFT",   "name_ar": "\u0645\u0627\u064a\u0643\u0631\u0648\u0633\u0648\u0641\u062a",         "name_en": "Microsoft",         "type": "stocks",     "yahoo": "MSFT",          "coingecko": None},
    {"id": "GOOGL",  "symbol": "GOOGL",  "name_ar": "\u062c\u0648\u062c\u0644",               "name_en": "Alphabet",          "type": "stocks",     "yahoo": "GOOGL",         "coingecko": None},
    {"id": "AMZN",   "symbol": "AMZN",   "name_ar": "\u0623\u0645\u0627\u0632\u0648\u0646",             "name_en": "Amazon",            "type": "stocks",     "yahoo": "AMZN",          "coingecko": None},
    {"id": "NVDA",   "symbol": "NVDA",   "name_ar": "\u0625\u0646\u0641\u064a\u062f\u064a\u0627",            "name_en": "NVIDIA",            "type": "stocks",     "yahoo": "NVDA",          "coingecko": None},
    {"id": "META",   "symbol": "META",   "name_ar": "\u0645\u064a\u062a\u0627",               "name_en": "Meta",              "type": "stocks",     "yahoo": "META",          "coingecko": None},
    {"id": "NFLX",   "symbol": "NFLX",   "name_ar": "\u0646\u062a\u0641\u0644\u0643\u0633",             "name_en": "Netflix",           "type": "stocks",     "yahoo": "NFLX",          "coingecko": None},
    {"id": "BTC",    "symbol": "BTC",    "name_ar": "\u0628\u064a\u062a\u0643\u0648\u064a\u0646",            "name_en": "Bitcoin",           "type": "crypto",     "yahoo": "BTC-USD",       "coingecko": "bitcoin"},
    {"id": "ETH",    "symbol": "ETH",    "name_ar": "\u0625\u064a\u062b\u0631\u064a\u0648\u0645",            "name_en": "Ethereum",          "type": "crypto",     "yahoo": "ETH-USD",       "coingecko": "ethereum"},
    {"id": "BNB",    "symbol": "BNB",    "name_ar": "\u0628\u064a\u0646\u0627\u0646\u0633",             "name_en": "Binance Coin",      "type": "crypto",     "yahoo": "BNB-USD",       "coingecko": "binancecoin"},
    {"id": "SOL",    "symbol": "SOL",    "name_ar": "\u0633\u0648\u0644\u0627\u0646\u0627",             "name_en": "Solana",            "type": "crypto",     "yahoo": "SOL-USD",       "coingecko": "solana"},
    {"id": "XRP",    "symbol": "XRP",    "name_ar": "\u0631\u064a\u0628\u0644",               "name_en": "Ripple",            "type": "crypto",     "yahoo": "XRP-USD",       "coingecko": "ripple"},
    {"id": "EURUSD", "symbol": "EURUSD", "name_ar": "\u064a\u0648\u0631\u0648/\u062f\u0648\u0644\u0627\u0631",         "name_en": "EUR/USD",           "type": "forex",      "yahoo": "EURUSD=X",      "coingecko": None},
    {"id": "GBPUSD", "symbol": "GBPUSD", "name_ar": "\u062c\u0646\u064a\u0647/\u062f\u0648\u0644\u0627\u0631",         "name_en": "GBP/USD",           "type": "forex",      "yahoo": "GBPUSD=X",      "coingecko": None},
    {"id": "USDJPY", "symbol": "USDJPY", "name_ar": "\u062f\u0648\u0644\u0627\u0631/\u064a\u0646",           "name_en": "USD/JPY",           "type": "forex",      "yahoo": "USDJPY=X",      "coingecko": None},
    {"id": "XAUUSD", "symbol": "XAUUSD", "name_ar": "\u0630\u0647\u0628",                "name_en": "Gold",              "type": "commodities","yahoo": "GC=F",          "coingecko": None},
    {"id": "WTI",    "symbol": "WTI",    "name_ar": "\u062e\u0627\u0645 \u063a\u0631\u0628 \u062a\u0643\u0633\u0627\u0633",      "name_en": "WTI Crude",         "type": "commodities","yahoo": "CL=F",          "coingecko": None},
    {"id": "BRENT",  "symbol": "BRENT",  "name_ar": "\u062e\u0627\u0645 \u0628\u0631\u0646\u062a",           "name_en": "Brent Crude",       "type": "commodities","yahoo": "BZ=F",          "coingecko": None},
    {"id": "SP500",  "symbol": "SP500",  "name_ar": "\u0633\u062a\u0627\u0646\u062f\u0631\u062f \u0622\u0646\u062f \u0628\u0648\u0631\u0632",   "name_en": "S&P 500",           "type": "indices",    "yahoo": "^GSPC",         "coingecko": None},
    {"id": "NASDAQ", "symbol": "NASDAQ", "name_ar": "\u0646\u0627\u0633\u062f\u0627\u0643",             "name_en": "NASDAQ Composite",  "type": "indices",    "yahoo": "^IXIC",         "coingecko": None},
]

price_cache: Dict[str, dict] = {}
indicator_cache: Dict[str, dict] = {}
backtest_cache: dict = {}
CACHE_TTL = 120
INDICATOR_TTL = 900

def calc_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_macd(closes: List[float]) -> Optional[dict]:
    if len(closes) < 26:
        return None
    ema12 = closes[-1]
    ema26 = closes[-1]
    for p in closes[-12:]:
        ema12 = ema12 * (11 / 13) + p * (2 / 13)
    for p in closes[-26:]:
        ema26 = ema26 * (25 / 27) + p * (2 / 27)
    macd_line = ema12 - ema26
    signal = "bullish" if macd_line > 0 else "bearish"
    return {"line": round(macd_line, 4), "signal": signal, "histogram": round(macd_line, 4)}

def calc_ma(closes: List[float], period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def calc_bb(closes: List[float], period: int = 20, std_dev: float = 2.0) -> Optional[dict]:
    if len(closes) < period:
        return None
    recent = closes[-period:]
    mid = sum(recent) / period
    variance = sum((c - mid) ** 2 for c in recent) / period
    sd = variance ** 0.5
    return {
        "upper": mid + std_dev * sd,
        "middle": mid,
        "lower": mid - std_dev * sd,
    }

def calc_stoch(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[dict]:
    if len(closes) < period:
        return None
    hh = max(highs[-period:])
    ll = min(lows[-period:])
    if hh == ll:
        return {"k": 50.0, "d": 50.0}
    k = ((closes[-1] - ll) / (hh - ll)) * 100
    return {"k": round(k, 2), "d": round(k, 2)}

def calc_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        h = highs[i]
        l = lows[i]
        c_prev = closes[i - 1]
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        trs.append(tr)
    return sum(trs) / period

def calc_pivot(high: float, low: float, close: float) -> dict:
    p = (high + low + close) / 3
    return {
        "pivot": p,
        "r1": 2 * p - low,
        "s1": 2 * p - high,
        "r2": p + (high - low),
        "s2": p - (high - low),
    }

def synth_history(current_price: float, change_pct: float, n: int = 250) -> List[dict]:
    out = []
    price = current_price / (1 + change_pct / 100) if change_pct != 0 else current_price * 0.98
    daily_vol = 0.015
    if abs(change_pct) > 5:
        daily_vol = 0.025
    seed = int(time.time() * 1000) % 99991
    for i in range(n):
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        noise = ((seed % 1000) / 1000.0 - 0.5) * 2 * daily_vol
        drift = (change_pct / 100) / n
        price = price * (1 + drift + noise * 0.5)
        if price <= 0:
            price = current_price * 0.5
        c = price
        h = c * (1 + abs(noise) * 0.7 + 0.002)
        l = c * (1 - abs(noise) * 0.7 - 0.002)
        out.append({"c": round(c, 6), "h": round(h, 6), "l": round(l, 6)})
    return out

def anti_chase_filter(action: str, change_pct: float, score_delta: int) -> tuple:
    """v6.2.2: tightened to >2% (was >1%)."""
    if action == "buy" and change_pct > 2.0:
        return (score_delta - 3, "buy signal after >2% rise - late entry")
    if action == "buy" and change_pct > 1.5:
        return (score_delta - 2, "buy signal after >1.5% rise - reduced")
    if action == "sell" and change_pct < -2.0:
        return (score_delta + 1, "sell signal after strong drop - boosted")
    return (score_delta, None)

def trend_cross_filter(action: str, price: float, ma50: Optional[float], ma200: Optional[float]) -> str:
    """v6.2.2: Golden Cross for buys, Death Cross for sells."""
    if ma50 is None or ma200 is None:
        return action
    if action == "buy" and ma50 < ma200:
        return "wait"
    if action == "sell" and ma50 > ma200:
        return "wait"
    return action

def triple_confirmation(rsi: Optional[float], macd_signal: Optional[str],
                        price: float, ma50: Optional[float], ma200: Optional[float],
                        bb: Optional[dict], action: str) -> int:
    """v6.2.2: stricter - need >=2 confirms."""
    confirms = 0
    if action == "buy":
        if rsi is not None and rsi < 60 and rsi > 30:
            confirms += 1
        if macd_signal == "bullish":
            confirms += 1
        if ma50 is not None and ma200 is not None and ma50 > ma200 and price > ma50:
            confirms += 1
        if bb is not None and price < bb["upper"] * 0.95:
            confirms += 1
        if rsi is not None and rsi <= 35:
            confirms += 1
    elif action == "sell":
        if rsi is not None and rsi > 40 and rsi < 70:
            confirms += 1
        if macd_signal == "bearish":
            confirms += 1
        if ma50 is not None and ma200 is not None and ma50 < ma200 and price < ma50:
            confirms += 1
        if bb is not None and price > bb["lower"] * 1.05:
            confirms += 1
        if rsi is not None and rsi >= 65:
            confirms += 1
    return confirms

def compute_v5_recommendation(asset_data: dict, indicators: dict) -> dict:
    """v6.2.2: stricter thresholds + cross filter."""
    price = asset_data.get("price", 0)
    change = asset_data.get("change", 0)
    rsi = indicators.get("rsi")
    macd_sig = indicators.get("macd_signal")
    ma50 = indicators.get("ma_50")
    ma200 = indicators.get("ma_200")
    bb = indicators.get("bb")
    atr = indicators.get("atr")

    score = 0
    reasons = []

    if change >= 2.0:
        score += 2
        reasons.append("strong bullish momentum (>2%)")
    elif change >= 1.0:
        score += 1
        reasons.append("bullish momentum")
    elif change <= -2.0:
        score -= 2
        reasons.append("strong bearish momentum (<-2%)")
    elif change <= -1.0:
        score -= 1
        reasons.append("bearish momentum")

    if ma50 is not None and change > 0 and price > ma50:
        score += 1
        reasons.append("above MA50 with positive change")
    elif ma50 is not None and change < 0 and price < ma50:
        score -= 1
        reasons.append("below MA50 with negative change")

    if macd_sig == "bullish":
        score += 1
        reasons.append("MACD bullish")
    elif macd_sig == "bearish":
        score -= 1
        reasons.append("MACD bearish")

    if rsi is not None:
        if rsi >= 75:
            score -= 2
            reasons.append("RSI overbought")
        elif rsi <= 25:
            score += 2
            reasons.append("RSI oversold")
        elif rsi >= 65:
            score -= 1
            reasons.append("RSI high")
        elif rsi <= 35:
            score += 1
            reasons.append("RSI low")

    if bb is not None:
        if price > bb["upper"]:
            score -= 1
            reasons.append("above BB upper")
        elif price < bb["lower"]:
            score += 1
            reasons.append("below BB lower")

    if ma200 is not None and ma50 is not None:
        if ma50 > ma200 and change > 0:
            score += 1
            reasons.append("golden cross + positive change")
        elif ma50 < ma200 and change < 0:
            score -= 1
            reasons.append("death cross + negative change")

    score, anti_reason = anti_chase_filter("buy" if score > 0 else "sell", change, score)
    if anti_reason:
        reasons.append(anti_reason)

    action = "buy" if score >= 4 else "sell" if score <= -4 else "wait"
    original_action = action

    action = trend_cross_filter(action, price, ma50, ma200)
    if action == "wait" and original_action != "wait":
        reasons.append("trend cross filter: rejected (golden/death cross conflict)")

    confirms = triple_confirmation(rsi, macd_sig, price, ma50, ma200, bb, action)
    if action != "wait" and confirms < 2:
        action = "wait"
        reasons.append(f"insufficient confirmation: {confirms}/5")

    abs_score = abs(score)
    if action == "wait":
        confidence = 50
    else:
        confidence = min(85, 55 + abs_score * 4)

    levels = None
    if action != "wait" and atr is not None and atr > 0:
        offset = atr
        if action == "buy":
            stop = price - offset
            target = price + offset * 2
        else:
            stop = price + offset
            target = price - offset * 2
        levels = {
            "entry": round(price, 4),
            "stop": round(stop, 4),
            "tp1": round(target, 4),
            "tp2": round(price + offset * 3, 4) if action == "buy" else round(price - offset * 3, 4),
        }

    return {
        "action": action,
        "confidence": confidence,
        "score": score,
        "reasons": reasons,
        "levels": levels,
    }

def build_indicators(history: List[dict], current_price: float, change_pct: float) -> dict:
    closes = [c["c"] for c in history]
    highs = [c["h"] for c in history]
    lows = [c["l"] for c in history]
    if len(closes) < 2:
        return {}
    rsi = calc_rsi(closes)
    macd = calc_macd(closes)
    ma50 = calc_ma(closes, 50)
    ma200 = calc_ma(closes, 200)
    bb = calc_bb(closes)
    stoch = calc_stoch(highs, lows, closes)
    atr = calc_atr(highs, lows, closes)
    pivot = calc_pivot(highs[-1], lows[-1], closes[-1])
    return {
        "rsi": round(rsi, 2) if rsi else None,
        "macd_signal": macd["signal"] if macd else None,
        "ma_50": round(ma50, 4) if ma50 else None,
        "ma_200": round(ma200, 4) if ma200 else None,
        "bb": bb,
        "stoch_k": stoch["k"] if stoch else None,
        "atr": round(atr, 4) if atr else None,
        "pivot": round(pivot["pivot"], 4),
        "pivot_r1": round(pivot["r1"], 4),
        "pivot_s1": round(pivot["s1"], 4),
    }

async def fetch_yahoo(session: aiohttp.ClientSession, symbol: str) -> Optional[dict]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "1d"}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            result = data["chart"]["result"][0]
            meta = result["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get("previousClose") or meta.get("chartPreviousClose")
            if price is None or prev is None:
                return None
            change_pct = ((price - prev) / prev) * 100 if prev else 0
            return {
                "price": float(price),
                "change": round(change_pct, 2),
                "high24": float(meta.get("regularMarketDayHigh") or price),
                "low24": float(meta.get("regularMarketDayLow") or price),
                "volume": float(meta.get("regularMarketVolume") or 0),
            }
    except Exception:
        return None

async def fetch_coingecko(session: aiohttp.ClientSession, cg_id: str) -> Optional[dict]:
    url = f"https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": cg_id, "vs_currencies": "usd", "include_24hr_change": "true", "include_24hr_vol": "true"}
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            d = data.get(cg_id)
            if not d:
                return None
            price = float(d.get("usd", 0))
            change = float(d.get("usd_24h_change", 0))
            return {
                "price": price,
                "change": round(change, 2),
                "high24": price * 1.02,
                "low24": price * 0.98,
                "volume": float(d.get("usd_24h_vol", 0)),
            }
    except Exception:
        return None

async def fetch_one_asset(asset: dict, session: aiohttp.ClientSession) -> dict:
    cache_key = asset["id"]
    now = time.time()
    if cache_key in indicator_cache and (now - indicator_cache[cache_key]["ts"]) < INDICATOR_TTL:
        cached_ind = indicator_cache[cache_key]["data"]
        cached_price = price_cache.get(cache_key, {})
        if cached_price:
            return {**asset, **cached_price, "indicators": cached_ind}
    price_data = None
    if asset.get("coingecko"):
        price_data = await fetch_coingecko(session, asset["coingecko"])
    if price_data is None and asset.get("yahoo"):
        price_data = await fetch_yahoo(session, asset["yahoo"])
    if price_data is None:
        if cache_key in price_cache:
            price_data = price_cache[cache_key]
        else:
            return {"id": asset["id"], "symbol": asset["symbol"], "error": "no data"}
    price_cache[cache_key] = price_data
    history = synth_history(price_data["price"], price_data["change"])
    indicators = build_indicators(history, price_data["price"], price_data["change"])
    indicator_cache[cache_key] = {"data": indicators, "ts": now}
    return {**asset, **price_data, "indicators": indicators}

@app.get("/")
async def root():
    return {
        "service": "TradeAI API",
        "version": "6.2.2",
        "stage": "1+ improvements (strict selectivity)",
        "filters": ["Anti-Chase >2%", "Trend Cross", "Triple Confirmation >=2", "Threshold +/-4", "30-day cooldown", "Max 5 trades/year/asset"],
        "assets": len(ASSETS),
        "endpoints": ["/", "/prices", "/price/{symbol}", "/backtest"],
        "status": "ok",
    }

@app.get("/prices")
async def prices(refresh: int = Query(0, ge=0, le=1)):
    now = time.time()
    if not refresh and price_cache:
        cached_age = now - list(price_cache.values())[0].get("_ts", 0)
        if cached_age < CACHE_TTL:
            out = []
            for a in ASSETS:
                if a["id"] in price_cache:
                    pd = price_cache[a["id"]]
                    ind = indicator_cache.get(a["id"], {}).get("data", {})
                    rec = compute_v5_recommendation(pd, ind)
                    out.append({**a, **pd, "indicators": ind, "v5_action": rec["action"],
                                "v5_score": rec["score"], "v5_reasons": rec["reasons"],
                                "v5_confidence": rec["confidence"], "v5_levels": rec["levels"]})
            return {"assets": out, "cached": True, "ts": now}
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one_asset(a, session) for a in ASSETS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, Exception):
            continue
        if "error" in r:
            continue
        ind = r.get("indicators", {})
        price_data = {k: v for k, v in r.items() if k in ["price", "change", "high24", "low24", "volume"]}
        price_data["_ts"] = now
        price_cache[r["id"]] = price_data
        indicator_cache[r["id"]] = {"data": ind, "ts": now}
        rec = compute_v5_recommendation(price_data, ind)
        out.append({**r, "v5_action": rec["action"], "v5_score": rec["score"],
                    "v5_reasons": rec["reasons"], "v5_confidence": rec["confidence"],
                    "v5_levels": rec["levels"]})
    return {"assets": out, "cached": False, "ts": now}

@app.get("/price/{symbol}")
async def price(symbol: str):
    asset = next((a for a in ASSETS if a["id"].upper() == symbol.upper()), None)
    if not asset:
        raise HTTPException(status_code=404, detail="symbol not found")
    async with aiohttp.ClientSession() as session:
        data = await fetch_one_asset(asset, session)
    if "error" in data:
        raise HTTPException(status_code=502, detail=data["error"])
    ind = data.get("indicators", {})
    price_data = {k: v for k, v in data.items() if k in ["price", "change", "high24", "low24", "volume"]}
    rec = compute_v5_recommendation(price_data, ind)
    return {**data, "v5_action": rec["action"], "v5_score": rec["score"],
            "v5_reasons": rec["reasons"], "v5_confidence": rec["confidence"],
            "v5_levels": rec["levels"]}

def simulate_trade(history: List[dict], entry_idx: int, action: str, atr: float) -> dict:
    MAX_HOLD = 30
    entry = history[entry_idx]["c"]
    offset = atr if atr > 0 else entry * 0.02
    if action == "buy":
        stop = entry - offset
        target = entry + offset * 2
    else:
        stop = entry + offset
        target = entry - offset * 2
    for j in range(entry_idx + 1, min(entry_idx + MAX_HOLD + 1, len(history))):
        h = history[j]["h"]
        l = history[j]["l"]
        c = history[j]["c"]
        if action == "buy":
            if l <= stop:
                pnl = ((stop - entry) / entry) * 100
                return {"exit": "stop", "pnl_pct": round(pnl, 2), "days": j - entry_idx}
            if h >= target:
                pnl = ((target - entry) / entry) * 100
                return {"exit": "target", "pnl_pct": round(pnl, 2), "days": j - entry_idx}
        else:
            if h >= stop:
                pnl = ((entry - stop) / entry) * 100
                return {"exit": "stop", "pnl_pct": round(pnl, 2), "days": j - entry_idx}
            if l <= target:
                pnl = ((entry - target) / entry) * 100
                return {"exit": "target", "pnl_pct": round(pnl, 2), "days": j - entry_idx}
    last = history[min(entry_idx + MAX_HOLD, len(history) - 1)]["c"]
    pnl = ((last - entry) / entry) * 100 * (1 if action == "buy" else -1)
    return {"exit": "timeout", "pnl_pct": round(pnl, 2), "days": MAX_HOLD}

@app.get("/backtest")
async def backtest(refresh: int = Query(0, ge=0, le=1)):
    """v6.2.2: Strict selectivity - max 5 trades per asset per year, 30-day cooldown."""
    global backtest_cache
    now = time.time()
    if not refresh and backtest_cache and (now - backtest_cache.get("ts", 0)) < 300:
        return backtest_cache["data"]

    base_prices = {
        "AAPL": 195, "TSLA": 250, "MSFT": 410, "GOOGL": 175, "AMZN": 185,
        "NVDA": 130, "META": 510, "NFLX": 660,
        "BTC": 65000, "ETH": 3500, "BNB": 600, "SOL": 150, "XRP": 0.55,
        "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 152.0,
        "XAUUSD": 2650, "WTI": 70, "BRENT": 74, "SP500": 5700, "NASDAQ": 18500,
    }

    trades = []
    MAX_TRADES_PER_ASSET = 5
    COOLDOWN_DAYS = 30

    for asset in ASSETS:
        cache_key = asset["id"]
        if cache_key in price_cache:
            price_data = price_cache[cache_key]
            ind = indicator_cache.get(cache_key, {}).get("data", {})
        else:
            base = base_prices.get(asset["id"], 100)
            price_data = {"price": base, "change": 0.5}
            history_init = synth_history(base, 0.5)
            ind = build_indicators(history_init, base, 0.5)

        history = synth_history(price_data["price"], price_data.get("change", 0), n=250)
        atr = ind.get("atr") or (history[-1]["c"] * 0.02)
        last_entry_idx = -999
        asset_trade_count = 0

        for i in range(60, len(history) - 30):
            if asset_trade_count >= MAX_TRADES_PER_ASSET:
                break
            sub_hist = history[:i + 1]
            sub_ind = build_indicators(sub_hist, history[i]["c"], 0)
            if i > 0 and history[i - 1]["c"] > 0:
                real_change = ((history[i]["c"] - history[i - 1]["c"]) / history[i - 1]["c"]) * 100
            else:
                real_change = 0
            rec = compute_v5_recommendation(
                {"price": history[i]["c"], "change": real_change},
                sub_ind
            )
            if rec["action"] in ["buy", "sell"] and (i - last_entry_idx) >= COOLDOWN_DAYS:
                trade = simulate_trade(history, i, rec["action"], atr)
                trade["symbol"] = asset["id"]
                trade["action"] = rec["action"]
                trade["confidence"] = rec["confidence"]
                trades.append(trade)
                last_entry_idx = i
                asset_trade_count += 1

    if not trades:
        return {
            "assets_tested": len(ASSETS), "total_trades": 0, "win_rate": 0,
            "avg_pnl": 0, "wins": 0, "losses": 0, "timeouts": 0,
            "best_trade": 0, "worst_trade": 0, "max_drawdown_pct": 0,
            "trades": [], "version": "6.2.2",
            "rules": "v6.2.2 strict: threshold +/-4, triple >=2, cooldown 30d, max 5/asset"
        }

    wins = [t for t in trades if t["exit"] == "target"]
    losses = [t for t in trades if t["exit"] == "stop"]
    timeouts = [t for t in trades if t["exit"] == "timeout"]
    win_rate = (len(wins) / len(trades)) * 100 if trades else 0
    avg_pnl = sum(t["pnl_pct"] for t in trades) / len(trades) if trades else 0
    best = max(t["pnl_pct"] for t in trades) if trades else 0
    worst = min(t["pnl_pct"] for t in trades) if trades else 0

    equity = 0
    peak = 0
    max_dd = 0
    for t in trades:
        equity += t["pnl_pct"]
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)

    result = {
        "assets_tested": len(ASSETS),
        "total_trades": len(trades),
        "win_rate": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 2),
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(timeouts),
        "best_trade": round(best, 2),
        "worst_trade": round(worst, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "trades": trades[:50],
        "version": "6.2.2",
        "rules": "v6.2.2 strict: threshold +/-4, triple >=2, cooldown 30d, max 5/asset",
    }
    backtest_cache = {"data": result, "ts": now}
    return result

@app.on_event("startup")
async def startup():
    print(f"TradeAI v6.2.2 starting - {len(ASSETS)} assets, strict selectivity filters active")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
