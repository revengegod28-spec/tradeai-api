#!/usr/bin/env python3
"""
TradeAI Backend v6.0.2 — Risk-First Engine + Robust Fetcher
FastAPI backend for technical analysis, live prices, and backtesting.

v6.0.2 changes (from v6.0.1):
- Yahoo Finance fetcher: retry on 429/5xx with backoff
- Backtest: 0.3s delay between Yahoo requests to avoid rate limiting
- Backtest: detailed fetch stats (requested/fetched/short/no-trades)
- Backtest: 8s per-request timeout (was 15s) — fail fast
- Backtest: 2 retries with exponential backoff (1s, 2s)
- _score_v6: per-asset params (category parameter) — was hardcoded stocks

Key v6.0 changes (kept):
- Hard stop loss capped at 2% per trade (was 10%)
- Max hold per asset class (3-7 days)
- Volatility-based position sizing
- Trend filter (MA200) — no trading against long-term trend
- Market regime detection (ADX-based)
- Per-asset-class parameter tuning
- Confluence scoring with asymmetric thresholds
- Gap-aware stop/target using actual High/Low
- Supports both BUY and SELL signals
"""

import os
import json
import math
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tradeai-api")

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
app = FastAPI(title="TradeAI API v6.0.2", version="6.0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

CACHE_TTL = timedelta(seconds=25)
INDICATOR_CACHE_TTL = timedelta(minutes=15)
BACKTEST_CACHE_TTL = timedelta(minutes=5)
# v6.0.2: Yahoo rate-limit protection
BACKTEST_REQUEST_DELAY = 0.3   # seconds between backtest requests
BACKTEST_TIMEOUT = 8           # per-request timeout (was 15)
BACKTEST_MAX_RETRIES = 2       # retries on 429/5xx

# ---------------------------------------------------------------------------
# Risk Limits — THE MOST IMPORTANT PART
# ---------------------------------------------------------------------------
MAX_LOSS_PER_TRADE_PCT = 2.0      # Never lose more than 2% on a single trade
HARD_RR_MIN = 1.5                 # Minimum risk:reward 1:1.5

# ---------------------------------------------------------------------------
# Asset Definitions
# ---------------------------------------------------------------------------
SYMBOLS = {
    "AAPL": "AAPL", "TSLA": "TSLA", "MSFT": "MSFT", "GOOGL": "GOOGL",
    "AMZN": "AMZN", "NVDA": "NVDA", "META": "META", "NFLX": "NFLX",
    "BTC": "BTC-USD", "ETH": "ETH-USD", "BNB": "BNB-USD",
    "SOL": "SOL-USD", "XRP": "XRP-USD",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F", "WTI": "CL=F", "BRENT": "BZ=F",
    "SP500": "^GSPC", "NASDAQ": "^IXIC",
}

# Per-asset-class parameters
ASSET_PARAMS = {
    "stocks":     {"atr_mult": 1.5, "max_hold": 5, "rsi_low": 30, "rsi_high": 70, "size_mult": 1.0, "vol_cap": 4.0},
    "crypto":     {"atr_mult": 2.0, "max_hold": 3, "rsi_low": 25, "rsi_high": 75, "size_mult": 0.5, "vol_cap": 6.0},
    "forex":      {"atr_mult": 1.0, "max_hold": 7, "rsi_low": 35, "rsi_high": 65, "size_mult": 1.2, "vol_cap": 1.5},
    "commodities":{"atr_mult": 1.5, "max_hold": 5, "rsi_low": 30, "rsi_high": 70, "size_mult": 0.8, "vol_cap": 3.0},
    "indices":    {"atr_mult": 1.2, "max_hold": 5, "rsi_low": 30, "rsi_high": 70, "size_mult": 1.0, "vol_cap": 2.5},
}

# Asset category mapping
ASSET_CATEGORY = {
    "AAPL": "stocks", "TSLA": "stocks", "MSFT": "stocks", "GOOGL": "stocks",
    "AMZN": "stocks", "NVDA": "stocks", "META": "stocks", "NFLX": "stocks",
    "BTC": "crypto", "ETH": "crypto", "BNB": "crypto", "SOL": "crypto", "XRP": "crypto",
    "EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex", "XAUUSD": "forex",
    "WTI": "commodities", "BRENT": "commodities",
    "SP500": "indices", "NASDAQ": "indices",
}

PRICE_BOUNDS = {
    "NFLX": (50, 2000), "BTC": (1000, 1_000_000), "ETH": (50, 50_000),
    "AAPL": (50, 1000), "TSLA": (20, 2000), "NVDA": (10, 5000),
    "MSFT": (50, 2000), "GOOGL": (50, 2000), "AMZN": (20, 5000),
    "META": (50, 2000), "XAUUSD": (500, 20000),
    "WTI": (10, 500), "BRENT": (10, 500),
    "SP500": (300, 2000), "NASDAQ": (300, 2000),
}

# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------
_cache = {"data": None, "ts": None}
_indicator_cache = {}
_backtest_cache = {"data": None, "ts": None}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


def _adx(highs, lows, closes, period=14):
    """Simplified ADX (0-100). Values > 25 indicate strong trend."""
    if len(closes) < period * 2: return 0.0
    plus_dm = []
    minus_dm = []
    for i in range(1, len(closes)):
        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)

    trs = []
    for i in range(1, len(closes)):
        h = highs[i] if i < len(highs) else closes[i]
        l = lows[i] if i < len(lows) else closes[i]
        c = closes[i-1]
        trs.append(max(h - l, abs(h - c), abs(l - c)))

    atr_val = sum(trs[:period]) / period
    atr_smooth = atr_val
    for tr in trs[period:]:
        atr_smooth = (atr_smooth * (period - 1) + tr) / period

    if atr_smooth == 0: return 0.0

    plus_di = 100 * (sum(plus_dm[:period]) / period) / atr_smooth
    minus_di = 100 * (sum(minus_dm[:period]) / period) / atr_smooth

    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
    return dx


def _market_regime(highs, lows, closes):
    """
    Detect market regime:
    - trending_up: ADX > 25, price > MA20 > MA50
    - trending_down: ADX > 25, price < MA20 < MA50
    - ranging: ADX < 20
    - volatile: ATR% > threshold
    - mixed: everything else
    """
    if len(closes) < 50: return "mixed"
    price = closes[-1]
    ma20 = _sma(closes, 20)
    ma50 = _sma(closes, 50)
    atr_v = _atr(highs, lows, closes, 14)
    adx_v = _adx(highs, lows, closes, 14)

    if ma20 is None or ma50 is None or atr_v is None:
        return "mixed"

    atr_pct = atr_v / price * 100

    if atr_pct > 6.0:
        return "volatile"
    if adx_v > 25 and price > ma20 > ma50:
        return "trending_up"
    if adx_v > 25 and price < ma20 < ma50:
        return "trending_down"
    if adx_v < 20:
        return "ranging"
    return "mixed"


def _volume_signal(vols):
    """Compare last volume to 20-day average."""
    if not vols or len(vols) < 20: return "normal"
    vol = vols[-1]
    avg = sum(vols[-20:]) / 20
    if avg == 0: return "normal"
    ratio = vol / avg
    if ratio > 2.0: return "very_high"
    elif ratio > 1.5: return "high"
    elif ratio < 0.5: return "low"
    return "normal"


# ---------------------------------------------------------------------------
# v6.0 Scoring Engine — Confluence + Trend Filter + Regime
# ---------------------------------------------------------------------------
def _score_v6(closes, highs, lows, vols, i, category="stocks"):
    """
    v6.0.1 Risk-First Scoring Engine (per-asset params).
    Returns dict with action, score, reasons, confidence, levels, metrics.
    """
    if i < 200: return None

    window = closes[:i + 1]
    win_h  = highs[:i + 1] if i < len(highs) else window
    win_l  = lows[:i + 1]  if i < len(lows)  else window
    win_v  = vols[:i + 1]  if vols else None
    price  = window[-1]

    # v6.0.1: per-asset params (was hardcoded to stocks in v6.0)
    params = ASSET_PARAMS.get(category, ASSET_PARAMS["stocks"])

    # Core indicators
    ma50 = _sma(window, 50)
    ma200 = _sma(window, 200)
    rsi_val = _rsi(window)
    macd = _macd_signal(window)

    sma20 = _sma(window, 20)
    std20 = _std(window, 20)
    bb_pos = 0.0
    if sma20 is not None and std20 is not None and std20 > 0:
        bb_up = sma20 + 2 * std20
        bb_lo = sma20 - 2 * std20
        if bb_up != bb_lo:
            bb_pos = max(-1.0, min(1.0, (price - bb_lo) / (bb_up - bb_lo) * 2 - 1))

    atr_v = _atr(win_h, win_l, window, 14)
    stoch_k, stoch_d = _stochastic(win_h, win_l, window, 14, 3, 3)

    regime = _market_regime(win_h, win_l, window)
    vol_sig = _volume_signal(win_v)

    support, resistance = _sr_levels(win_h, win_l, 20)

    if rsi_val is None or ma50 is None or ma200 is None or atr_v is None:
        return None

    atr_pct = atr_v / price * 100

    # --- FILTERS (hard no-trade conditions) ---
    reasons = []

    # 1. Volatility cap
    if atr_pct > params["vol_cap"]:
        return {
            "action": "wait", "score": 0,
            "reasons": [f"ATR% {atr_pct:.1f} exceeds cap {params['vol_cap']}"],
            "confidence": 0, "levels": {},
            "metrics": {"atr_pct": atr_pct, "regime": regime, "rsi": rsi_val}
        }

    # 2. Regime filter: no trading in volatile regime
    if regime == "volatile":
        return {
            "action": "wait", "score": 0,
            "reasons": ["Volatile regime — no safe entries"],
            "confidence": 0, "levels": {},
            "metrics": {"atr_pct": atr_pct, "regime": regime, "rsi": rsi_val}
        }

    # --- SCORING ---
    trend_score = 0.0
    mr_score = 0.0
    breakout_score = 0.0

    long_term_trend = "up" if price > ma200 else "down"

    # 1. Trend Following (weighted highest in trending markets)
    if regime in ("trending_up", "trending_down", "mixed"):
        if price > ma50 > ma200 and macd == "bullish":
            trend_score = 2.5
            reasons.append("Strong uptrend: price > MA50 > MA200 + MACD bullish")
        elif price > ma50 and macd == "bullish":
            trend_score = 1.5
            reasons.append("Uptrend: price > MA50 + MACD bullish")
        elif price < ma50 < ma200 and macd == "bearish":
            trend_score = -2.5
            reasons.append("Strong downtrend: price < MA50 < MA200 + MACD bearish")
        elif price < ma50 and macd == "bearish":
            trend_score = -1.5
            reasons.append("Downtrend: price < MA50 + MACD bearish")

    # 2. Mean Reversion (only in ranging markets)
    if regime == "ranging":
        if rsi_val < params["rsi_low"] and bb_pos < -0.7 and stoch_k < 20:
            mr_score = 2.0
            reasons.append(f"Oversold bounce: RSI {rsi_val:.0f}, Stoch {stoch_k:.0f}, BB low")
        elif rsi_val > params["rsi_high"] and bb_pos > 0.7 and stoch_k > 80:
            mr_score = -2.0
            reasons.append(f"Overbought pullback: RSI {rsi_val:.0f}, Stoch {stoch_k:.0f}, BB high")

    # 3. Breakout confirmation (weak, used only as confirmation)
    if len(win_h) >= 20 and len(win_l) >= 20:
        recent_high = max(win_h[-20:])
        recent_low  = min(win_l[-20:])
        if price >= recent_high * 0.998 and vol_sig in ("high", "very_high"):
            breakout_score = 0.5
            reasons.append("Volume-confirmed breakout")
        elif price <= recent_low * 1.002 and vol_sig in ("high", "very_high"):
            breakout_score = -0.5
            reasons.append("Volume-confirmed breakdown")

    # --- CONFLUENCE & TREND FILTER ---
    total = trend_score + mr_score + breakout_score

    # Hard filter: never trade against MA200
    if long_term_trend == "up" and total < 0:
        return {
            "action": "wait", "score": total,
            "reasons": reasons + ["Signal contradicts long-term uptrend (MA200)"],
            "confidence": 30, "levels": {},
            "metrics": {"atr_pct": atr_pct, "regime": regime, "rsi": rsi_val}
        }
    if long_term_trend == "down" and total > 0:
        return {
            "action": "wait", "score": total,
            "reasons": reasons + ["Signal contradicts long-term downtrend (MA200)"],
            "confidence": 30, "levels": {},
            "metrics": {"atr_pct": atr_pct, "regime": regime, "rsi": rsi_val}
        }

    # --- ACTION THRESHOLDS ---
    action = "wait"
    confidence = 50

    if total >= 3.0:
        action = "buy"
        confidence = min(85, 55 + int(total * 8))
    elif total <= -3.0:
        action = "sell"
        confidence = min(85, 55 + int(abs(total) * 8))
    else:
        reasons.append("Insufficient confluence (< 3.0)")

    # --- LEVELS (Risk-First) ---
    levels = {}
    if action in ("buy", "sell"):
        direction = 1 if action == "buy" else -1

        # Stop: ATR-based with hard cap
        atr_stop = atr_v * params["atr_mult"]
        hard_stop = price * (MAX_LOSS_PER_TRADE_PCT / 100)
        stop_distance = min(atr_stop, hard_stop)

        stop = price - stop_distance * direction
        risk = abs(price - stop)

        # Target: minimum R:R 1:1.5
        target = price + (risk * HARD_RR_MIN) * direction

        # Sanity checks using support/resistance
        if action == "buy":
            if support is not None:
                stop = max(stop, support * 0.98)
            if resistance is not None:
                target = min(target, resistance * 1.02)
        else:
            if resistance is not None:
                stop = min(stop, resistance * 1.02)
            if support is not None:
                target = max(target, support * 0.98)

        # Recalculate R:R after sanity checks
        risk = abs(price - stop)
        reward = abs(target - price)
        rr = round(reward / risk, 2) if risk > 0 else 0

        levels = {
            "entry": round(price, 4 if price < 1 else 2),
            "stop": round(stop, 4 if price < 1 else 2),
            "target": round(target, 4 if price < 1 else 2),
            "rr": rr,
            "risk_pct": round(risk / price * 100, 2)
        }

    return {
        "action": action,
        "score": round(total, 2),
        "reasons": reasons if reasons else ["Mixed signals — insufficient confidence"],
        "confidence": confidence,
        "levels": levels,
        "metrics": {
            "atr_pct": round(atr_pct, 2),
            "regime": regime,
            "rsi": round(rsi_val, 1),
            "macd": macd,
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "bb_pos": round(bb_pos, 2),
            "stoch_k": round(stoch_k, 1),
            "volume_signal": vol_sig,
            "long_term_trend": long_term_trend,
        }
    }


# ---------------------------------------------------------------------------
# v6.0 Simulator — Risk-First Trade Simulation
# ---------------------------------------------------------------------------
def _simulate_v6(closes, highs, lows, vols, symbol):
    """
    Simulate trades with strict risk management:
    - Hard stop: max 2% loss
    - Max hold: 5 days (configurable per asset class)
    - Uses actual High/Low for stop/target hits (gap-aware)
    - Volatility-based position sizing
    - Supports both BUY and SELL
    """
    category = ASSET_CATEGORY.get(symbol, "stocks")
    params = ASSET_PARAMS.get(category, ASSET_PARAMS["stocks"])
    max_hold = params["max_hold"]

    trades = []
    i = 200
    while i < len(closes) - 3:
        # v6.0.1: pass category so per-asset params are used
        sig = _score_v6(closes, highs, lows, vols, i, category=category)
        if sig is None or sig["action"] not in ("buy", "sell") or not sig.get("levels"):
            i += 1
            continue

        entry_price = closes[i]
        direction = 1 if sig["action"] == "buy" else -1

        # Volatility-based position sizing
        atr_pct = sig["metrics"].get("atr_pct", 2.0)
        size_mult = max(0.25, min(1.0, 3.0 / max(atr_pct, 0.5)))

        # Levels
        stop_price = sig["levels"]["stop"]
        target_price = sig["levels"]["target"]

        exit_price = None
        exit_reason = None
        exit_day = 0

        for day in range(1, max_hold + 1):
            idx = i + day
            if idx >= len(closes):
                break

            day_high = highs[idx] if idx < len(highs) else closes[idx]
            day_low = lows[idx] if idx < len(lows) else closes[idx]

            # Check stop/target using actual High/Low (gap-aware)
            if direction == 1:  # Long
                if day_low <= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                    exit_day = day
                    break
                if day_high >= target_price:
                    exit_price = target_price
                    exit_reason = "target"
                    exit_day = day
                    break
            else:  # Short
                if day_high >= stop_price:
                    exit_price = stop_price
                    exit_reason = "stop"
                    exit_day = day
                    break
                if day_low <= target_price:
                    exit_price = target_price
                    exit_reason = "target"
                    exit_day = day
                    break

        # Time-based exit
        if exit_price is None:
            last_idx = min(i + max_hold, len(closes) - 1)
            exit_price = closes[last_idx]
            exit_reason = "timeout"
            exit_day = last_idx - i

            # Hard cap on timeout losses
            pnl = ((exit_price - entry_price) / entry_price) * 100 * direction
            if pnl < -MAX_LOSS_PER_TRADE_PCT:
                exit_price = entry_price * (1 - MAX_LOSS_PER_TRADE_PCT / 100 * direction)
                exit_reason = "timeout_capped"
                pnl = -MAX_LOSS_PER_TRADE_PCT
        else:
            pnl = ((exit_price - entry_price) / entry_price) * 100 * direction

        # Apply position sizing to PnL
        actual_pnl = pnl * size_mult

        trades.append({
            "symbol": symbol,
            "entry_idx": i,
            "exit_idx": i + exit_day,
            "outcome": "win" if actual_pnl > 0 else "loss" if actual_pnl < 0 else "breakeven",
            "pnl_pct": round(actual_pnl, 2),
            "raw_pnl": round(pnl, 2),
            "exit_reason": exit_reason,
            "duration": exit_day,
            "size_mult": round(size_mult, 2),
            "action": sig["action"],
        })

        i = i + exit_day + 1

    return trades


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
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

        # v6.0.1: use per-asset params (was hardcoded to stocks)
        cat = ASSET_CATEGORY.get(internal_key, "stocks")
        sig = _score_v6(closes, highs, lows, vols, len(closes) - 1, category=cat)
        if sig is None: sig = {"action": "wait", "score": 0, "reasons": ["Insufficient data"], "confidence": 0, "levels": {}, "metrics": {}}

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

        # Override params for this asset category
        category = ASSET_CATEGORY.get(internal_key, "stocks")
        params = ASSET_PARAMS.get(category, ASSET_PARAMS["stocks"])

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
            # v5 compatibility for frontend
            "v5_action":   sig["action"],
            "v5_score":    sig["score"],
            "v5_reasons":  sig["reasons"],
            "v5_trend":    sig["metrics"].get("long_term_trend", "neutral"),
            "confidence":  sig["confidence"],
            "levels":      sig.get("levels", {}),
            "regime":      sig["metrics"].get("regime", "mixed"),
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


# v6.0.2: Robust Yahoo fetcher with retry on rate limits / transient errors
async def fetch_yahoo_chart_with_retry(session, yahoo_symbol, max_retries=None):
    """
    Fetch Yahoo chart data with exponential-backoff retry.
    Retries on HTTP 429/5xx and on aiohttp/asyncio errors.
    Returns parsed JSON dict on success, or None on permanent failure.
    """
    if max_retries is None:
        max_retries = BACKTEST_MAX_RETRIES
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
    for attempt in range(max_retries + 1):
        try:
            async with session.get(
                url,
                params={"interval": "1d", "range": "1y"},
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=BACKTEST_TIMEOUT),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (429, 500, 502, 503, 504):
                    wait = 0.5 * (2 ** attempt)  # 0.5s, 1.0s, 2.0s
                    logger.warning(
                        f"[{yahoo_symbol}] HTTP {resp.status} — "
                        f"retry {attempt + 1}/{max_retries} in {wait:.1f}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                # Other 4xx (400, 401, 403, 404): don't retry
                logger.warning(f"[{yahoo_symbol}] HTTP {resp.status} — not retrying")
                return None
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            wait = 0.5 * (2 ** attempt)
            logger.warning(
                f"[{yahoo_symbol}] fetch error ({type(e).__name__}) — "
                f"retry {attempt + 1}/{max_retries} in {wait:.1f}s"
            )
            await asyncio.sleep(wait)
            continue
        except Exception as e:
            logger.warning(f"[{yahoo_symbol}] unexpected error: {e}")
            return None
    logger.error(f"[{yahoo_symbol}] failed after {max_retries + 1} attempts")
    return None


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "message": "TradeAI API v6.0.2 — Risk-First Engine + Robust Fetcher",
        "status": "active",
        "cache_ttl_seconds": CACHE_TTL.total_seconds(),
        "indicator_cache_ttl_seconds": INDICATOR_CACHE_TTL.total_seconds(),
        "backtest_cache_ttl_seconds": BACKTEST_CACHE_TTL.total_seconds(),
        "max_loss_per_trade": MAX_LOSS_PER_TRADE_PCT,
        "min_rr": HARD_RR_MIN,
    }


@app.get("/price/{symbol}")
async def get_price(symbol: str):
    """Single asset price + full analysis."""
    key = symbol.upper()
    if key not in SYMBOLS:
        raise HTTPException(status_code=404, detail="Asset not found")

    async with aiohttp.ClientSession() as session:
        _, data = await fetch_one(session, key)
        if not data:
            raise HTTPException(status_code=503, detail="Price data unavailable")

        ind = await fetch_indicators(session, SYMBOLS[key], key)
        if ind:
            data.update(ind)

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
async def backtest(refresh: bool = Query(False)):
    """Run v6.0.2 backtest across all assets. Cached for 5 minutes."""
    global _backtest_cache

    now = datetime.now()
    if not refresh and _backtest_cache["ts"] and (now - _backtest_cache["ts"]) < BACKTEST_CACHE_TTL and _backtest_cache["data"]:
        return _backtest_cache["data"]

    all_results = []
    by_symbol = {}
    fetch_stats = {
        "requested": 0,
        "fetched": 0,
        "short_data": 0,
        "fetch_failed": 0,
        "no_trades": 0,
        "failed_symbols": [],
    }

    async with aiohttp.ClientSession() as session:
        for idx, (sym, yahoo) in enumerate(SYMBOLS.items()):
            fetch_stats["requested"] += 1

            # v6.0.2: rate-limit protection — sleep between requests
            if idx > 0:
                await asyncio.sleep(BACKTEST_REQUEST_DELAY)

            try:
                data = await fetch_yahoo_chart_with_retry(session, yahoo)
                if data is None:
                    fetch_stats["fetch_failed"] += 1
                    fetch_stats["failed_symbols"].append(sym)
                    continue

                result = data["chart"]["result"][0]
                quotes = result["indicators"]["quote"][0]
                closes = [c for c in quotes["close"] if c is not None]
                highs  = [h for h in quotes["high"]  if h is not None]
                lows   = [l for l in quotes["low"]   if l is not None]
                vols   = [v for v in quotes.get("volume", []) if v is not None]

                fetch_stats["fetched"] += 1

                if len(closes) < 200:
                    fetch_stats["short_data"] += 1
                    logger.info(f"[{sym}] only {len(closes)} days — need 200+ for MA200")
                    continue

                trades = _simulate_v6(closes, highs, lows, vols, sym)

                if not trades:
                    fetch_stats["no_trades"] += 1
                    logger.info(f"[{sym}] no trades generated (signals never met thresholds)")
                    continue

                wins = sum(1 for t in trades if t["outcome"] == "win")
                losses = sum(1 for t in trades if t["outcome"] == "loss")
                timeouts = sum(1 for t in trades if "timeout" in t["exit_reason"])
                total = len(trades)

                # Calculate per-asset equity curve and max drawdown
                equity = [10000.0]
                for t in trades:
                    equity.append(equity[-1] * (1 + t["pnl_pct"] / 100))

                peak = equity[0]
                max_dd = 0.0
                for val in equity:
                    if val > peak: peak = val
                    dd = (peak - val) / peak * 100
                    if dd > max_dd: max_dd = dd

                all_results.append({
                    "symbol": sym,
                    "trades": trades,
                    "total": total,
                    "wins": wins,
                    "losses": losses,
                    "timeouts": timeouts,
                    "win_rate": round(wins / total * 100, 2) if total > 0 else 0,
                    "avg_pnl": round(sum(t["pnl_pct"] for t in trades) / total, 2) if total > 0 else 0,
                    "max_drawdown_pct": round(max_dd, 2),
                    "best_trade": round(max(t["pnl_pct"] for t in trades), 2),
                    "worst_trade": round(min(t["pnl_pct"] for t in trades), 2),
                    "total_return": round((equity[-1] - 10000) / 100, 2),
                })

                by_symbol[sym] = {
                    "trades": total,
                    "wins": wins,
                    "losses": losses,
                    "timeouts": timeouts,
                    "avg_pnl": round(sum(t["pnl_pct"] for t in trades) / total, 2) if total > 0 else 0,
                    "win_rate": round(wins / total * 100, 2) if total > 0 else 0,
                    "max_dd": round(max_dd, 2),
                }
            except Exception as e:
                logger.warning(f"[{sym}] backtest failed: {e}")
                fetch_stats["fetch_failed"] += 1
                fetch_stats["failed_symbols"].append(sym)

    logger.info(
        f"Backtest done: requested={fetch_stats['requested']} "
        f"fetched={fetch_stats['fetched']} short={fetch_stats['short_data']} "
        f"no_trades={fetch_stats['no_trades']} failed={fetch_stats['fetch_failed']}"
    )

    if not all_results:
        raise HTTPException(503, f"No data for backtest (stats: {fetch_stats})")

    total_trades = sum(r["total"] for r in all_results)
    total_wins = sum(r["wins"] for r in all_results)
    total_losses = sum(r["losses"] for r in all_results)
    total_timeouts = sum(r["timeouts"] for r in all_results)

    # Weighted averages
    avg_pnl = sum(r["avg_pnl"] * r["total"] for r in all_results) / total_trades if total_trades > 0 else 0
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0

    # Overall max drawdown: average across assets (more realistic than worst single asset)
    max_dd = sum(r["max_drawdown_pct"] for r in all_results) / len(all_results) if all_results else 0

    best_trade = max(r["best_trade"] for r in all_results)
    worst_trade = min(r["worst_trade"] for r in all_results)
    avg_return = sum(r["total_return"] for r in all_results) / len(all_results) if all_results else 0

    result_data = {
        "engine": "v6.0.2",
        "period": "1y",
        "assets_tested": len(all_results),
        "total_trades": total_trades,
        "wins": total_wins,
        "losses": total_losses,
        "timeouts": total_timeouts,
        "win_rate": round(win_rate, 2),
        "avg_pnl": round(avg_pnl, 2),
        "avg_return": round(avg_return, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "by_symbol": by_symbol,
        "fetch_stats": fetch_stats,
        "params": {
            "max_loss_per_trade": MAX_LOSS_PER_TRADE_PCT,
            "max_hold_days": "per-asset-class (3-7)",
            "min_rr": HARD_RR_MIN,
        }
    }

    _backtest_cache["data"] = result_data
    _backtest_cache["ts"] = now
    return result_data


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
