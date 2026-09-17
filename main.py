"""
TradeAI Backend API - v6.2.0
============================
Stage 1 Rule Improvements:
  - Anti-Chase Filter: penalize buy signals after big intraday moves
  - MA200 Veto: reject buys in confirmed downtrends
  - Triple Confirmation: require 2+ independent signals aligned
Endpoints:
  GET /                -> health check + asset count
  GET /prices          -> all 21 assets (live indicators)
  GET /price/{symbol}  -> single asset detail
  GET /backtest        -> simulate rules on 12 months of synthetic history
"""
import os
import time
import asyncio
import statistics
from typing import Dict, List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import aiohttp

# ===================== APP =====================
app = FastAPI(title="TradeAI API", version="6.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== ASSETS =====================
# 21 assets across 5 categories
ASSETS = [
    # Stocks
    {"id": "AAPL",   "symbol": "AAPL",   "name_ar": "أبل",                "name_en": "Apple",             "type": "stocks",     "yahoo": "AAPL",          "coingecko": None},
    {"id": "TSLA",   "symbol": "TSLA",   "name_ar": "تسلا",               "name_en": "Tesla",             "type": "stocks",     "yahoo": "TSLA",          "coingecko": None},
    {"id": "MSFT",   "symbol": "MSFT",   "name_ar": "مايكروسوفت",         "name_en": "Microsoft",         "type": "stocks",     "yahoo": "MSFT",          "coingecko": None},
    {"id": "GOOGL",  "symbol": "GOOGL",  "name_ar": "جوجل",               "name_en": "Alphabet",          "type": "stocks",     "yahoo": "GOOGL",         "coingecko": None},
    {"id": "AMZN",   "symbol": "AMZN",   "name_ar": "أمازون",             "name_en": "Amazon",            "type": "stocks",     "yahoo": "AMZN",          "coingecko": None},
    {"id": "NVDA",   "symbol": "NVDA",   "name_ar": "إنفيديا",            "name_en": "NVIDIA",            "type": "stocks",     "yahoo": "NVDA",          "coingecko": None},
    {"id": "META",   "symbol": "META",   "name_ar": "ميتا",               "name_en": "Meta",              "type": "stocks",     "yahoo": "META",          "coingecko": None},
    {"id": "NFLX",   "symbol": "NFLX",   "name_ar": "نتفلكس",             "name_en": "Netflix",           "type": "stocks",     "yahoo": "NFLX",          "coingecko": None},
    # Crypto
    {"id": "BTC",    "symbol": "BTC",    "name_ar": "بيتكوين",            "name_en": "Bitcoin",           "type": "crypto",     "yahoo": "BTC-USD",       "coingecko": "bitcoin"},
    {"id": "ETH",    "symbol": "ETH",    "name_ar": "إيثريوم",            "name_en": "Ethereum",          "type": "crypto",     "yahoo": "ETH-USD",       "coingecko": "ethereum"},
    {"id": "BNB",    "symbol": "BNB",    "name_ar": "بينانس",             "name_en": "Binance Coin",      "type": "crypto",     "yahoo": "BNB-USD",       "coingecko": "binancecoin"},
    {"id": "SOL",    "symbol": "SOL",    "name_ar": "سولانا",             "name_en": "Solana",            "type": "crypto",     "yahoo": "SOL-USD",       "coingecko": "solana"},
    {"id": "XRP",    "symbol": "XRP",    "name_ar": "ريبل",               "name_en": "Ripple",            "type": "crypto",     "yahoo": "XRP-USD",       "coingecko": "ripple"},
    # Forex
    {"id": "EURUSD", "symbol": "EURUSD", "name_ar": "يورو/دولار",         "name_en": "EUR/USD",           "type": "forex",      "yahoo": "EURUSD=X",      "coingecko": None},
    {"id": "GBPUSD", "symbol": "GBPUSD", "name_ar": "جنيه/دولار",         "name_en": "GBP/USD",           "type": "forex",      "yahoo": "GBPUSD=X",      "coingecko": None},
    {"id": "USDJPY", "symbol": "USDJPY", "name_ar": "دولار/ين",           "name_en": "USD/JPY",           "type": "forex",      "yahoo": "USDJPY=X",      "coingecko": None},
    # Commodities
    {"id": "XAUUSD", "symbol": "XAUUSD", "name_ar": "ذهب",                "name_en": "Gold",              "type": "commodities","yahoo": "GC=F",          "coingecko": None},
    {"id": "WTI",    "symbol": "WTI",    "name_ar": "خام غرب تكساس",      "name_en": "WTI Crude",         "type": "commodities","yahoo": "CL=F",          "coingecko": None},
    {"id": "BRENT",  "symbol": "BRENT",  "name_ar": "خام برنت",           "name_en": "Brent Crude",       "type": "commodities","yahoo": "BZ=F",          "coingecko": None},
    # Indices
    {"id": "SP500",  "symbol": "SP500",  "name_ar": "ستاندرد آند بورز",   "name_en": "S&P 500",           "type": "indices",    "yahoo": "^GSPC",         "coingecko": None},
    {"id": "NASDAQ", "symbol": "NASDAQ", "name_ar": "ناسداك",             "name_en": "NASDAQ Composite",  "type": "indices",    "yahoo": "^IXIC",         "coingecko": None},
]

# ===================== CACHES =====================
price_cache: Dict[str, dict] = {}
indicator_cache: Dict[str, dict] = {}
backtest_cache: dict = {}
CACHE_TTL = 120          # 2 min for prices
INDICATOR_TTL = 900      # 15 min for indicators

# ===================== INDICATORS =====================
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

# ===================== HISTORY SYNTHESIZER (FIXED) =====================
def synth_history(current_price: float, change_pct: float, n: int = 250) -> List[dict]:
    """
    Build a synthetic 250-day history anchored to current_price and change_pct.
    Uses an explicit for-loop to avoid scope/NameError issues with list comprehensions.
    """
    out = []
    price = current_price / (1 + change_pct / 100)  # back-calculate yesterday
    daily_vol = 0.015  # 1.5% daily volatility
    if abs(change_pct) > 5:
        daily_vol = 0.025  # crypto/commodities are more volatile
    seed = int(time.time() * 1000) % 99991
    for i in range(n):
        # Deterministic pseudo-random walk (no external deps)
        seed = (seed * 1103515245 + 12345) & 0x7fffffff
        noise = ((seed % 1000) / 1000.0 - 0.5) * 2 * daily_vol
        drift = (change_pct / 100) / n  # drift toward target
        price = price * (1 + drift + noise * 0.5)
        # Build OHLC for this day
        c = price
        h = c * (1 + abs(noise) * 0.7 + 0.002)
        l = c * (1 - abs(noise) * 0.7 - 0.002)
        out.append({"c": round(c, 6), "h": round(h, 6), "l": round(l, 6)})
    return out

# ===================== STAGE 1 FILTERS (NEW in v6.2) =====================
def anti_chase_filter(action: str, change_pct: float, score_delta: int) -> tuple:
    """
    Penalize buy signals after big intraday moves.
    Returning: (adjusted_score, reason_text)
    """
    if action == "buy" and change_pct > 1.5:
        return (score_delta - 2, "إشارة شراء بعد صعود >1.5% — متأخرة")
    if action == "buy" and change_pct > 1.0:
        return (score_delta - 1, "إشارة شراء بعد صعود >1% — حذف جزئي")
    if action == "sell" and change_pct < -1.5:
        return (score_delta + 1, "إشارة بيع بعد هبوط قوي — تعزيز")
    return (score_delta, None)

def ma200_veto(action: str, price: float, ma200: float, ma50: float) -> str:
    """
    Reject buys in confirmed downtrends (price < MA200 AND MA50 < MA200).
    Returns: original action OR 'wait' if vetoed.
    """
    if action == "buy" and price < ma200 and ma50 < ma200:
        return "wait"
    if action == "sell" and price > ma200 and ma50 > ma200:
        return "wait"
    return action

def triple_confirmation(rsi: Optional[float], macd_signal: Optional[str],
                        price: float, ma200: Optional[float],
                        bb: Optional[dict], action: str) -> int:
    """
    Count how many independent signals confirm the action.
    Returns count (0-4). Caller should require >= 2 for non-wait.
    """
    confirms = 0
    if action == "buy":
        if rsi is not None and rsi < 65 and rsi > 30:
            confirms += 1
        if macd_signal == "bullish":
            confirms += 1
        if ma200 is not None and price > ma200:
            confirms += 1
        if bb is not None and price < bb["upper"] * 0.98:
            confirms += 1
    elif action == "sell":
        if rsi is not None and rsi > 35 and rsi < 70:
            confirms += 1
        if macd_signal == "bearish":
            confirms += 1
        if ma200 is not None and price < ma200:
            confirms += 1
        if bb is not None and price > bb["lower"] * 1.02:
            confirms += 1
    return confirms

# ===================== V5 SCORING ENGINE (v6.2) =====================
def compute_v5_recommendation(asset_data: dict, indicators: dict) -> dict:
    """
    v6.2: Returns action (buy/sell/wait), confidence, score, reasons, levels.
    Applies Stage 1 filters on top of original v5 logic.
    """
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
    
    # --- Original v5 momentum scoring ---
    if change >= 1.5:
        score += 2
        reasons.append("زخم صاعد قوي")
    elif change >= 0.5:
        score += 1
        reasons.append("زخم صاعد")
    elif change <= -1.5:
        score -= 2
        reasons.append("زخم هابط قوي")
    elif change <= -0.5:
        score -= 1
        reasons.append("زخم هابط")
    
    # MA50
    if ma50 is not None:
        if price > ma50 and change > 0:
            score += 1
            reasons.append("فوق MA50")
        elif price < ma50 and change < 0:
            score -= 1
            reasons.append("تحت MA50")
    
    # MACD
    if macd_sig == "bullish":
        score += 1
        reasons.append("MACD صاعد")
    elif macd_sig == "bearish":
        score -= 1
        reasons.append("MACD هابط")
    
    # RSI extremes
    if rsi is not None:
        if rsi >= 75:
            score -= 1
            reasons.append("RSI تشبع شرائي")
        elif rsi <= 25:
            score += 1
            reasons.append("RSI تشبع بيعي")
    
    # BB position
    if bb is not None:
        if price > bb["upper"]:
            score -= 1
            reasons.append("فوق Bollinger العلوي")
        elif price < bb["lower"]:
            score += 1
            reasons.append("تحت Bollinger السفلي")
    
    # MA200 long-term filter
    if ma200 is not None:
        if price > ma200 and change > 0:
            score += 1
            reasons.append("فوق MA200")
        elif price < ma200 and change < 0:
            score -= 1
            reasons.append("تحت MA200")
    
    # --- STAGE 1 FILTERS ---
    # 1) Anti-chase
    score, anti_reason = anti_chase_filter("buy" if score > 0 else "sell", change, score)
    if anti_reason:
        reasons.append(anti_reason)
    
    # 2) MA200 veto
    action = "buy" if score >= 3 else "sell" if score <= -3 else "wait"
    action = ma200_veto(action, price, ma200, ma50)
    if action == "wait" and (score >= 3 or score <= -3):
        reasons.append("MA200 veto: تم الرفض لاتجاه كبير معاكس")
    
    # 3) Triple confirmation
    confirms = triple_confirmation(rsi, macd_sig, price, ma200, bb, action)
    if action != "wait" and confirms < 2:
        action = "wait"
        reasons.append(f"تأكيد ضعيف: {confirms}/4 — تم التحويل لانتظار")
    
    # --- Confidence ---
    abs_score = abs(score)
    if action == "wait":
        confidence = 50
    elif action == "buy":
        confidence = min(85, 55 + abs_score * 5)
    else:
        confidence = min(85, 55 + abs_score * 5)
    
    # --- Levels ---
    levels = None
    if action != "wait" and atr is not None and atr > 0:
        offset = price * (atr / price)
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

# ===================== INDICATOR BUILDER =====================
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

# ===================== YAHOO + COINGECKO FETCH =====================
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
    """Try primary sources for one asset. Returns merged data + indicators."""
    cache_key = asset["id"]
    now = time.time()
    
    # Indicator cache hit
    if cache_key in indicator_cache and (now - indicator_cache[cache_key]["ts"]) < INDICATOR_TTL:
        cached_ind = indicator_cache[cache_key]["data"]
        cached_price = price_cache.get(cache_key, {})
        if cached_price:
            return {**asset, **cached_price, "indicators": cached_ind}
    
    # Fetch fresh price
    price_data = None
    if asset.get("coingecko"):
        price_data = await fetch_coingecko(session, asset["coingecko"])
    if price_data is None and asset.get("yahoo"):
        price_data = await fetch_yahoo(session, asset["yahoo"])
    
    if price_data is None:
        # Fallback: return cached if any
        if cache_key in price_cache:
            price_data = price_cache[cache_key]
        else:
            return {"id": asset["id"], "symbol": asset["symbol"], "error": "no data"}
    
    price_cache[cache_key] = price_data
    
    # Build indicators from synthetic history (anchored to current)
    history = synth_history(price_data["price"], price_data["change"])
    indicators = build_indicators(history, price_data["price"], price_data["change"])
    
    indicator_cache[cache_key] = {"data": indicators, "ts": now}
    
    return {**asset, **price_data, "indicators": indicators}

# ===================== ENDPOINTS =====================
@app.get("/")
async def root():
    return {
        "service": "TradeAI API",
        "version": "6.2.0",
        "stage": "1 improvements applied (Anti-Chase + MA200 Veto + Triple Confirmation)",
        "assets": len(ASSETS),
        "endpoints": ["/", "/prices", "/price/{symbol}", "/backtest"],
        "status": "ok",
    }

@app.get("/prices")
async def prices(refresh: int = Query(0, ge=0, le=1)):
    """All 21 assets with live prices + indicators + v6.2 recommendation."""
    now = time.time()
    if not refresh and price_cache and (now - list(price_cache.values())[0].get("_ts", 0)) < CACHE_TTL:
        # Return cached
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
        rec = compute_v5_recommendation(price_data, ind)
        out.append({**r, "v5_action": rec["action"], "v5_score": rec["score"],
                    "v5_reasons": rec["reasons"], "v5_confidence": rec["confidence"],
                    "v5_levels": rec["levels"]})
    
    return {"assets": out, "cached": False, "ts": now}

@app.get("/price/{symbol}")
async def price(symbol: str):
    """Single asset detail."""
    asset = next((a for a in ASSETS if a["id"].upper() == symbol.upper()), None)
    if not asset:
        from fastapi import HTTPException
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

# ===================== BACKTEST (uses Stage 1 rules) =====================
def simulate_trade(history: List[dict], entry_idx: int, action: str, atr: float) -> dict:
    """
    Walk forward from entry_idx, exit when price hits stop or target,
    or after max_hold days.
    """
    MAX_HOLD = 30
    entry = history[entry_idx]["c"]
    offset = entry * (atr / entry) if atr > 0 else entry * 0.02
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
    
    # Timeout: close at last available price
    last = history[min(entry_idx + MAX_HOLD, len(history) - 1)]["c"]
    pnl = ((last - entry) / entry) * 100 * (1 if action == "buy" else -1)
    return {"exit": "timeout", "pnl_pct": round(pnl, 2), "days": MAX_HOLD}

@app.get("/backtest")
async def backtest(refresh: int = Query(0, ge=0, le=1)):
    """
    Simulate v6.2 rules on 12 months of synthetic history per asset.
    Returns aggregated stats.
    """
    global backtest_cache
    now = time.time()
    if not refresh and backtest_cache and (now - backtest_cache.get("ts", 0)) < 300:
        return backtest_cache["data"]
    
    trades = []
    for asset in ASSETS:
        cache_key = asset["id"]
        if cache_key in price_cache:
            price_data = price_cache[cache_key]
            ind = indicator_cache.get(cache_key, {}).get("data", {})
        else:
            # Synthesize baseline
            base_prices = {
                "AAPL": 195, "TSLA": 250, "MSFT": 410, "GOOGL": 175, "AMZN": 185,
                "NVDA": 130, "META": 510, "NFLX": 660,
                "BTC": 65000, "ETH": 3500, "BNB": 600, "SOL": 150, "XRP": 0.55,
                "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 152.0,
                "XAUUSD": 2650, "WTI": 70, "BRENT": 74, "SP500": 5700, "NASDAQ": 18500,
            }
            base = base_prices.get(asset["id"], 100)
            price_data = {"price": base, "change": 0.5}
            history = synth_history(base, 0.5)
            ind = build_indicators(history, base, 0.5)
        
        history = synth_history(price_data["price"], price_data.get("change", 0), n=250)
        atr = ind.get("atr") or (history[-1]["c"] * 0.02)
        
        # Walk forward through history, only act on signals at least 30 days apart
        last_entry_idx = -999
        for i in range(60, len(history) - 30):
            # Compute indicators at this point (using truncated history)
            sub_hist = history[:i + 1]
            sub_ind = build_indicators(sub_hist, history[i]["c"], 0)
            rec = compute_v5_recommendation({"price": history[i]["c"], "change": 0}, sub_ind)
            
            if rec["action"] in ["buy", "sell"] and (i - last_entry_idx) >= 10:
                trade = simulate_trade(history, i, rec["action"], atr)
                trade["symbol"] = asset["id"]
                trade["action"] = rec["action"]
                trade["confidence"] = rec["confidence"]
                trades.append(trade)
                last_entry_idx = i
    
    if not trades:
        return {"assets_tested": len(ASSETS), "total_trades": 0, "win_rate": 0,
                "avg_pnl": 0, "wins": 0, "losses": 0, "timeouts": 0,
                "best_trade": 0, "worst_trade": 0, "max_drawdown_pct": 0,
                "trades": [], "version": "6.2.0", "rules": "Stage 1: Anti-Chase + MA200 Veto + Triple Confirmation"}
    
    wins = [t for t in trades if t["exit"] == "target"]
    losses = [t for t in trades if t["exit"] == "stop"]
    timeouts = [t for t in trades if t["exit"] == "timeout"]
    win_rate = (len(wins) / len(trades)) * 100 if trades else 0
    avg_pnl = sum(t["pnl_pct"] for t in trades) / len(trades) if trades else 0
    best = max(t["pnl_pct"] for t in trades) if trades else 0
    worst = min(t["pnl_pct"] for t in trades) if trades else 0
    
    # Max drawdown
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
        "trades": trades[:50],  # cap response size
        "version": "6.2.0",
        "rules": "Stage 1: Anti-Chase + MA200 Veto + Triple Confirmation",
    }
    backtest_cache = {"data": result, "ts": now}
    return result

# ===================== STARTUP =====================
@app.on_event("startup")
async def startup():
    print(f"TradeAI v6.2.0 starting — {len(ASSETS)} assets, Stage 1 filters active")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
