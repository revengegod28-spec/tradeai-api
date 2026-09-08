#!/usr/bin/env python3
"""
TradeAI Backend v6.1.0 — ATR Breakout + Chandelier Trailing Exit
FastAPI backend for technical analysis, live prices, and backtesting.

v6.1.0 changes (from v6.0.2):
- New strategy: ATR Breakout entry + Chandelier Trailing Exit (no fixed take-profit)
- New filters: MA200 trend + ADX > 20 (trend only) + per-asset vol cap
- Asset classes collapsed: 5 categories -> 3 (EQUITIES_INDICES, CRYPTO, FOREX_COMMODITIES)
- Parallel fetch: asyncio.gather with Semaphore(4) + 100ms jitter
- Raw response cache: 15-min TTL (no refetch for backtest bursts)
- Backtest timeout cut to 6s/request (was 8s)
- Backtest should complete in <12s on Render (was 50-60s, hitting 503)

v6.0.x kept:
- Hard 2% loss cap per trade
- Per-asset params for vol/hold/RSI thresholds
- Yahoo rate-limit handling (retry on 429/5xx, exponential backoff)
- Per-symbol fetch_stats in backtest response
- v5-compat fields in /prices for frontend (v5_action, v5_score, v5_reasons, v5_trend)
"""

import os
import json
import math
import time
import random
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

app = FastAPI(title="TradeAI API v6.1.0", version="6.1.0")

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
RAW_FETCH_TTL = timedelta(minutes=15)
BACKTEST_CONCURRENCY = 4
BACKTEST_JITTER = 0.1
BACKTEST_RANGE = "1y"
BACKTEST_TIMEOUT = 6
BACKTEST_MAX_RETRIES = 2

HARD_STOP_LOSS_PCT = 2.0
MAX_LOSS_PER_TRADE_PCT = HARD_STOP_LOSS_PCT

SYMBOLS = {
    "AAPL": "AAPL", "TSLA": "TSLA", "MSFT": "MSFT", "GOOGL": "GOOGL",
    "AMZN": "AMZN", "NVDA": "NVDA", "META": "META", "NFLX": "NFLX",
    "BTC": "BTC-USD", "ETH": "ETH-USD", "BNB": "BNB-USD",
    "SOL": "SOL-USD", "XRP": "XRP-USD",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F", "WTI": "CL=F", "BRENT": "BZ=F",
    "SP500": "^GSPC", "NASDAQ": "^IXIC",
}

ASSET_PARAMS = {
    "EQUITIES_INDICES": {
        "atr_mult": 1.5, "max_hold": 10, "vol_cap": 3.5, "chandelier_mult": 2.5,
        "rsi_low": 30, "rsi_high": 70, "size_mult": 1.0,
    },
    "CRYPTO": {
        "atr_mult": 2.0, "max_hold": 7, "vol_cap": 6.0, "chandelier_mult": 3.0,
        "rsi_low": 25, "rsi_high": 75, "size_mult": 0.5,
    },
    "FOREX_COMMODITIES": {
        "atr_mult": 1.2, "max_hold": 12, "vol_cap": 2.0, "chandelier_mult": 2.0,
        "rsi_low": 35, "rsi_high": 65, "size_mult": 1.0,
    },
}

ASSET_CATEGORY = {
    "AAPL": "EQUITIES_INDICES", "TSLA": "EQUITIES_INDICES",
    "MSFT": "EQUITIES_INDICES", "GOOGL": "EQUITIES_INDICES",
    "AMZN": "EQUITIES_INDICES", "NVDA": "EQUITIES_INDICES",
    "META": "EQUITIES_INDICES", "NFLX": "EQUITIES_INDICES",
    "SP500": "EQUITIES_INDICES", "NASDAQ": "EQUITIES_INDICES",
    "BTC": "CRYPTO", "ETH": "CRYPTO", "BNB": "CRYPTO", "SOL": "CRYPTO", "XRP": "CRYPTO",
    "EURUSD": "FOREX_COMMODITIES", "GBPUSD": "FOREX_COMMODITIES",
    "USDJPY": "FOREX_COMMODITIES", "XAUUSD": "FOREX_COMMODITIES",
    "WTI": "FOREX_COMMODITIES", "BRENT": "FOREX_COMMODITIES",
}

PRICE_BOUNDS = {
    "NFLX": (50, 2000), "BTC": (1000, 1_000_000), "ETH": (50, 50_000),
    "AAPL": (50, 1000), "TSLA": (20, 2000), "NVDA": (10, 5000),
    "MSFT": (50, 2000), "GOOGL": (50, 2000), "AMZN": (20, 5000),
    "META": (50, 2000), "XAUUSD": (500, 20000),
    "WTI": (10, 500), "BRENT": (10, 500),
    "SP500": (300, 2000), "NASDAQ": (300, 2000),
}

_cache = {"data": None, "ts": None}
_indicator_cache = {}
_backtest_cache = {"data": None, "ts": None}
_raw_fetch_cache = {}

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


def _volume_signal(vols):
    if not vols or len(vols) < 20: return "normal"
    vol = vols[-1]
    avg = sum(vols[-20:]) / 20
    if avg == 0: return "normal"
    ratio = vol / avg
    if ratio > 2.0: return "very_high"
    elif ratio > 1.5: return "high"
    elif ratio < 0.5: return "low"
    return "normal"
