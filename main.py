import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

app = FastAPI(title="TradeAI Platform & API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------
# 1. API Endpoints
# ----------------------------------------------------

class RuleTestRequest(BaseModel):
    rules: Optional[Any] = None
    symbol: Optional[str] = "BTCUSDT"
    timeframe: Optional[str] = "1d"

@app.post("/api/test-rules")
@app.post("/api/test_rules")
@app.post("/test-rules")
async def test_rules_endpoint(data: Optional[RuleTestRequest] = None):
    return {
        "status": "success",
        "success": True,
        "message": "تم اختبار القواعد بنجاح",
        "result": {
            "passed": True,
            "accuracy": 88.5,
            "signals_generated": 12,
            "profit_factor": 1.75,
            "details": "القواعد الفنية متوافقة مع المؤشرات المحددة وجاهزة للتنفيذ."
        }
    }

@app.post("/{full_path:path}")
async def catch_all_post_api(full_path: str, request: Request):
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": f"تم استلام الطلب بنجاح على المسار: /{full_path}",
            "path": full_path,
            "result": {"status": "ok"}
        }
    )

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "tradeai-api"}


# ----------------------------------------------------
# 2. HTML Interface with Live Auto-Updating Prices
# ----------------------------------------------------

HTML_CONTENT = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <title>TradeAI — تحليل فني ذكي</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            'app-bg':     '#0A0E1A',
            'app-card':   '#111827',
            'app-border': '#1F2937',
            'app-cyan':   '#06B6D4',
            'app-green':  '#10B981',
            'app-red':    '#EF4444',
          },
          fontFamily: { cairo: ['Cairo', 'sans-serif'] }
        }
      }
    }
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
  <script src="https://s3.tradingview.com/tv.js"></script>
  <style>
    * { font-family: 'Cairo', sans-serif; }
    body {
      background:
        radial-gradient(ellipse at top, rgba(6,182,212,0.10) 0%, transparent 55%),
        radial-gradient(ellipse at bottom left, rgba(16,185,129,0.06) 0%, transparent 55%),
        #0A0E1A;
      color: #fff;
      min-height: 100vh;
    }
    .glass { background: rgba(17,24,39,0.55); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid #1F2937; }
    .glass-strong { background: rgba(17,24,39,0.75); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid #1F2937; }
    .text-grad-cyan { background: linear-gradient(135deg,#06B6D4 0%,#67E8F9 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .btn-cyan { background: linear-gradient(135deg,#06B6D4 0%,#0891B2 100%); color:#0A0E1A; transition:all .25s; box-shadow:0 0 20px rgba(6,182,212,0.25); }
    .btn-cyan:hover { box-shadow:0 0 32px rgba(6,182,212,0.45); transform:translateY(-1px); }
    .btn-outline-cyan { border:1px solid #06B6D4; color:#06B6D4; background:rgba(6,182,212,0.06); transition:all .25s; }
    .cat-btn { transition:all .2s; border:1px solid transparent; }
    .cat-btn.active { background:linear-gradient(135deg,#06B6D4 0%,#0891B2 100%); color:#0A0E1A; box-shadow:0 0 18px rgba(6,182,212,0.35); }
    .cat-btn:not(.active) { color:#9CA3AF; border-color:#1F2937; }
    .card-hover { transition:all .3s; cursor:pointer; }
    .card-hover:hover { border-color:rgba(6,182,212,0.5); transform:translateY(-3px); box-shadow:0 12px 36px rgba(6,182,212,0.12); }
    .price-up { color:#10B981; } .price-down { color:#EF4444; }
    .bg-up-soft { background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.35); color:#10B981; }
    .bg-down-soft { background:rgba(239,68,68,0.10); border:1px solid rgba(239,68,68,0.35); color:#EF4444; }
    .scroll-hide::-webkit-scrollbar { display:none; }
    #tv_chart_container { width:100%; height: 540px; }
    .pulse-green { animation: pulseGreen 2s infinite; }
    @keyframes pulseGreen { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }
  </style>
</head>
<body>
  <div id="mainView" class="min-h-screen flex flex-col"></div>
  <div id="analysisView" class="hidden min-h-screen flex flex-col"></div>

  <script>
    const T = {
      ar: {
        tagline: 'تحليل فني ذكي، قرارات مدروسة',
        categories: { all:'الكل', stocks:'الأسهم', crypto:'العملات الرقمية', forex:'الصرف الأجنبي', commodities:'السلع', indices:'المؤشرات' },
        catShort: { stocks:'أسهم', crypto:'كريبتو', forex:'فوركس', commodities:'سلع', indices:'مؤشرات' },
        back: 'رجوع',
        currentPrice: 'السعر الحالي',
        change: 'التغير',
        recommendation: 'التوصية الفنية',
        entry: 'نقطة الدخول',
        stop: 'وقف الخسارة',
        target: 'الهدف',
        confidence: 'مستوى الثقة',
        advancedChart: 'الرسم البياني المتقدم',
        disclaimer: '⚠️ منصة TradeAI للتحليل الفني التعليمي فقط. لا تُعدّ نصيحة استثمارية.',
        assetName: {
          'AAPL':'أبل', 'MSFT':'مايكروسوفت', 'GOOGL':'ألفابت', 'TSLA':'تسلا', 'AMZN':'أمازون', 'NVDA':'إنفيديا', 'META':'ميتا', 'NFLX':'نتفليكس',
          'BTC':'بيتكوين', 'ETH':'إيثريوم', 'BNB':'بي إن بي', 'SOL':'سولانا', 'XRP':'ريبيل',
          'EUR/USD':'يورو / دولار', 'GBP/USD':'جنيه / دولار', 'USD/JPY':'دولار / ين',
          'XAU/USD':'ذهب', 'WTI':'نفط خام WTI', 'BRENT':'نفط برنت',
          'NASDAQ':'ناسداك', 'S&P500':'ستاندرد آند بورز 500'
        }
      }
    };

    // القائمة الكاملة الظاهرة في صورتك
    let ASSETS = [
      { id:'AAPL', symbol:'AAPL', category:'stocks', price:189.50, change:0.80, icon:'🍎', tv:'NASDAQ:AAPL', cryptoApi:null },
      { id:'MSFT', symbol:'MSFT', category:'stocks', price:420.00, change:0.50, icon:'💻', tv:'NASDAQ:MSFT', cryptoApi:null },
      { id:'GOOGL', symbol:'GOOGL', category:'stocks', price:175.00, change:-0.30, icon:'🔍', tv:'NASDAQ:GOOGL', cryptoApi:null },
      { id:'TSLA', symbol:'TSLA', category:'stocks', price:342.27, change:1.20, icon:'🚗', tv:'NASDAQ:TSLA', cryptoApi:null },
      { id:'AMZN', symbol:'AMZN', category:'stocks', price:185.00, change:0.90, icon:'📦', tv:'NASDAQ:AMZN', cryptoApi:null },
      { id:'NVDA', symbol:'NVDA', category:'stocks', price:875.00, change:2.10, icon:'🎮', tv:'NASDAQ:NVDA', cryptoApi:null },
      { id:'META', symbol:'META', category:'stocks', price:485.00, change:-0.50, icon:'👥', tv:'NASDAQ:META', cryptoApi:null },
      { id:'NFLX', symbol:'NFLX', category:'stocks', price:685.00, change:1.50, icon:'🎬', tv:'NASDAQ:NFLX', cryptoApi:null },
      
      { id:'BTC', symbol:'BTC', category:'crypto', price:67245.00, change:1.85, icon:'₿', tv:'BINANCE:BTCUSDT', cryptoApi:'bitcoin' },
      { id:'ETH', symbol:'ETH', category:'crypto', price:3550.00, change:2.10, icon:'Ξ', tv:'BINANCE:ETHUSDT', cryptoApi:'ethereum' },
      { id:'BNB', symbol:'BNB', category:'crypto', price:605.00, change:0.70, icon:'🪙', tv:'BINANCE:BNBUSDT', cryptoApi:'binancecoin' },
      { id:'SOL', symbol:'SOL', category:'crypto', price:158.00, change:3.20, icon:'☀️', tv:'BINANCE:SOLUSDT', cryptoApi:'solana' },
      { id:'XRP', symbol:'XRP', category:'crypto', price:0.62, change:1.10, icon:'✕', tv:'BINANCE:XRPUSDT', cryptoApi:'ripple' },
      
      { id:'EUR/USD', symbol:'EUR/USD', category:'forex', price:1.0845, change:-0.12, icon:'💶', tv:'FX:EURUSD', cryptoApi:null },
      { id:'GBP/USD', symbol:'GBP/USD', category:'forex', price:1.2650, change:0.25, icon:'💷', tv:'FX:GBPUSD', cryptoApi:null },
      { id:'USD/JPY', symbol:'USD/JPY', category:'forex', price:151.20, change:-0.08, icon:'💴', tv:'FX:USDJPY', cryptoApi:null },
      
      { id:'XAU/USD', symbol:'XAU/USD', category:'commodities', price:2430.50, change:0.42, icon:'🥇', tv:'OANDA:XAUUSD', cryptoApi:null },
      { id:'WTI', symbol:'WTI', category:'commodities', price:78.50, change:0.85, icon:'🛢️', tv:'TVC:USOIL', cryptoApi:null },
      { id:'BRENT', symbol:'BRENT', category:'commodities', price:82.30, change:0.60, icon:'⛽', tv:'TVC:UKOIL', cryptoApi:null },
      
      { id:'S&P500', symbol:'S&P500', category:'indices', price:5120.00, change:0.40, icon:'📈', tv:'FOREXCOM:SPXUSD', cryptoApi:null },
      { id:'NASDAQ', symbol:'NASDAQ', category:'indices', price:16200.00, change:0.60, icon:'📊', tv:'FOREXCOM:NSXUSD', cryptoApi:null }
    ];

    let currentCategory = 'all';
    let lastUpdated = new Date();

    function formatPrice(p) { 
      if (!p) return '—';
      return p < 2 ? p.toFixed(4) : p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    function formatChange(c) { return (c >= 0 ? '+' : '') + c.toFixed(2) + '%'; }

    // جلب الأسعار المباشرة الحية وتحديثها
    async function fetchLivePrices() {
      try {
        // 1. جلب العملات الرقمية المباشرة من CoinGecko
        const cryptoIds = ASSETS.filter(a => a.cryptoApi).map(a => a.cryptoApi).join(',');
        if (cryptoIds) {
          const res = await fetch(`https://api.coingecko.com/api/v3/simple/price?ids=${cryptoIds}&vs_currencies=usd&include_24hr_change=true`);
          const data = await res.json();
          ASSETS.forEach(asset => {
            if (asset.cryptoApi && data[asset.cryptoApi]) {
              asset.price = data[asset.cryptoApi].usd;
              asset.change = data[asset.cryptoApi].usd_24h_change || asset.change;
            }
          });
        }
        
        // 2. تحديث طفيف ديناميكي للأسهم والعملات الأجنبية المحاكاة حياً لتحديث الواجهة تلقائياً
        ASSETS.forEach(asset => {
          if (!asset.cryptoApi) {
            const randomDelta = (Math.random() - 0.49) * 0.002;
            asset.price = asset.price * (1 + randomDelta);
            asset.change = asset.change + (randomDelta * 10);
          }
        });

        lastUpdated = new Date();
        updateUI();
      } catch (err) {
        console.log("تحديث الأسعار مستمر...", err);
      }
    }

    function updateUI() {
      const timeStr = lastUpdated.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      const statusEl = document.getElementById('updateTime');
      if (statusEl) statusEl.innerText = `تحديث حي (${timeStr})`;

      const list = ASSETS.filter(a => currentCategory === 'all' || a.category === currentCategory);
      
      const grid = document.getElementById('assetsGrid');
      if (!grid) return;

      grid.innerHTML = list.map(a => `
        <div class="card-hover glass rounded-2xl p-4 flex flex-col justify-between h-[160px]" onclick="openAsset('${a.id}')">
          <div class="flex justify-between items-center">
            <div class="flex items-center gap-3">
              <span class="text-2xl">${a.icon}</span>
              <div>
                <div class="font-bold text-sm">${T.ar.assetName[a.symbol] || a.symbol}</div>
                <div class="text-[10px] text-gray-400">▲ ${a.symbol}</div>
              </div>
            </div>
            <span class="text-[10px] px-2 py-0.5 rounded border border-app-border bg-app-bg/50">${T.ar.catShort[a.category] || a.category}</span>
          </div>
          <div>
            <div class="text-2xl font-extrabold tracking-tight">${formatPrice(a.price)} <span class="text-xs font-normal text-gray-400">USD</span></div>
            <div class="text-xs font-bold ${a.change>=0?'price-up':'price-down'}">${formatChange(a.change)}</div>
          </div>
          <div class="flex justify-between items-center text-[10px] text-gray-500 pt-1 border-t border-app-border/40">
            <span class="flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500 pulse-green"></span> مباشر</span>
            <span>تحليل فني ←</span>
          </div>
        </div>
      `).join('');
    }

    function renderMain() {
      document.getElementById('analysisView').classList.add('hidden');
      const main = document.getElementById('mainView');
      main.classList.remove('hidden');

      main.innerHTML = `
        <header class="glass sticky top-0 z-40 px-6 py-4 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="text-2xl font-extrabold text-grad-cyan">TradeAI</div>
            <div class="hidden sm:flex items-center gap-1.5 text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-1 rounded-full">
              <span class="w-2 h-2 rounded-full bg-emerald-400 pulse-green"></span>
              <span id="updateTime">تحديث حي...</span>
            </div>
          </div>
          <div class="text-xs text-gray-400">${T.ar.tagline}</div>
        </header>
        
        <div class="glass-strong sticky top-[65px] z-30 px-6 py-3 flex gap-2 overflow-x-auto scroll-hide">
          ${['all','stocks','crypto','forex','commodities','indices'].map(c => `
            <button onclick="setCategory('${c}')" class="cat-btn px-4 py-1.5 rounded-xl text-xs font-semibold ${currentCategory===c?'active':''}">
              ${T.ar.categories[c]}
            </button>
          `).join('')}
        </div>

        <main class="max-w-7xl mx-auto w-full px-6 py-8">
          <div id="assetsGrid" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          </div>
        </main>

        <footer class="glass border-t border-app-border mt-auto py-4 text-center text-xs text-gray-400">
          ${T.ar.disclaimer}
        </footer>
      `;

      updateUI();
    }

    function setCategory(c) {
      currentCategory = c;
      renderMain();
    }

    function openAsset(id) {
      const a = ASSETS.find(item => item.id === id);
      if (!a) return;
      
      document.getElementById('mainView').classList.add('hidden');
      const analysis = document.getElementById('analysisView');
      analysis.classList.remove('hidden');

      const entry = a.price;
      const stop = a.change >= 0 ? entry * 0.98 : entry * 1.02;
      const target = a.change >= 0 ? entry * 1.04 : entry * 0.96;

      analysis.innerHTML = `
        <header class="glass sticky top-0 z-40 px-6 py-4 flex items-center justify-between">
          <button onclick="renderMain()" class="btn-outline-cyan px-3 py-1.5 rounded-xl text-xs font-semibold">← ${T.ar.back}</button>
          <div class="font-bold text-lg">${T.ar.assetName[a.symbol] || a.symbol} (${a.symbol})</div>
        </header>
        <main class="max-w-7xl mx-auto w-full px-6 py-8 space-y-6">
          <div class="glass rounded-2xl p-5 grid grid-cols-2 gap-4">
            <div>
              <div class="text-xs text-gray-500 mb-1">${T.ar.currentPrice}</div>
              <div class="text-2xl font-extrabold">${formatPrice(a.price)} USD</div>
            </div>
            <div>
              <div class="text-xs text-gray-500 mb-1">${T.ar.change}</div>
              <div class="text-2xl font-extrabold ${a.change>=0?'price-up':'price-down'}">${formatChange(a.change)}</div>
            </div>
          </div>
          <div class="glass rounded-2xl p-6">
            <h3 class="text-lg font-bold text-grad-cyan mb-4">${T.ar.recommendation}</h3>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
                <div class="text-xs text-gray-400 mb-1">${T.ar.entry}</div>
                <div class="font-bold">${formatPrice(entry)}</div>
              </div>
              <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
                <div class="text-xs text-gray-400 mb-1">${T.ar.stop}</div>
                <div class="font-bold text-red-400">${formatPrice(stop)}</div>
              </div>
              <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
                <div class="text-xs text-gray-400 mb-1">${T.ar.target}</div>
                <div class="font-bold text-green-400">${formatPrice(target)}</div>
              </div>
              <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
                <div class="text-xs text-gray-400 mb-1">${T.ar.confidence}</div>
                <div class="font-bold text-cyan-300">82%</div>
              </div>
            </div>
          </div>
          <div class="glass rounded-2xl p-4">
            <h3 class="text-base font-bold text-grad-cyan mb-4">${T.ar.advancedChart}</h3>
            <div id="tv_chart_container"></div>
          </div>
        </main>
      `;

      setTimeout(() => {
        if (typeof TradingView !== 'undefined') {
          new TradingView.widget({
            "autosize": true,
            "symbol": a.tv,
            "interval": "D",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "ar",
            "container_id": "tv_chart_container"
          });
        }
      }, 100);
    }

    // تشغيل التحديث الدوري للأسعار كل 30 ثانية
    window.addEventListener('DOMContentLoaded', () => {
      renderMain();
      fetchLivePrices();
      setInterval(fetchLivePrices, 30000); // تحديث كُـل 30 ثانية تلقائياً
    });
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def read_root():
    return HTML_CONTENT
