from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests

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

@app.get("/")
def root():
    return {"message": "TradeAI API", "status": "active"}

@app.get("/price/{symbol}")
def get_price(symbol: str):
    yahoo = SYMBOLS.get(symbol.upper(), symbol.upper())
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice", meta.get("previousClose", 0))
        prev = meta.get("previousClose", price)
        change = ((price - prev) / prev * 100) if prev else 0
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change_percent": round(change, 2),
            "currency": meta.get("currency", "USD")
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}

@app.get("/prices")
def get_all_prices():
    results = {}
    for key in SYMBOLS:
        try:
            r = get_price(key)
            if "error" not in r:
                results[key] = r
        except:
            continue
    return results
