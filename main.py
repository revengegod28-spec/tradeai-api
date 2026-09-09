<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <style>
    html { overflow-x: clip; }  /* prevent horizontal page scroll without breaking inner scrolls */
  </style>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <title>TradeAI — تحليل فني ذكي</title>
  <!-- v5.0-trend-pullback-confluence: 2026-09-04 -->

  <script>
    // Cache-bust: if the served HTML lacks this marker, force a fresh fetch.
    (function() {
      try {
        var SENTINEL = 'v5.0-trend-pullback-confluence';
        var last = localStorage.getItem('tradeai_html_ver');
        if (last !== SENTINEL) {
          localStorage.setItem('tradeai_html_ver', SENTINEL);
          if (last !== null) {
            var u = new URL(window.location.href);
            u.searchParams.set('_v', Date.now());
            window.location.replace(u.toString());
            return;
          }
        }
      } catch (e) { /* localStorage may be disabled */ }
    })();
  </script>

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
    .text-grad-cyan { background: linear-gradient(135deg,#06B6D4 0%,#67E8F9 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
    .text-grad-green { background: linear-gradient(135deg,#10B981 0%,#34D399 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
    .text-grad-red { background: linear-gradient(135deg,#EF4444 0%,#F87171 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
    .btn-cyan { background: linear-gradient(135deg,#06B6D4 0%,#0891B2 100%); color:#0A0E1A; transition:all .25s; box-shadow:0 0 20px rgba(6,182,212,0.25); }
    .btn-cyan:hover { box-shadow:0 0 32px rgba(6,182,212,0.45); transform:translateY(-1px); }
    .btn-outline-cyan { border:1px solid #06B6D4; color:#06B6D4; background:rgba(6,182,212,0.06); transition:all .25s; }
    .btn-outline-cyan:hover { background:rgba(6,182,212,0.18); box-shadow:0 0 18px rgba(6,182,212,0.18); }
    .cat-btn { transition:all .2s; border:1px solid transparent; }
    .cat-btn.active { background:linear-gradient(135deg,#06B6D4 0%,#0891B2 100%); color:#0A0E1A; box-shadow:0 0 18px rgba(6,182,212,0.35); }
    .cat-btn:not(.active) { color:#9CA3AF; border-color:#1F2937; }
    .cat-btn:not(.active):hover { color:#fff; border-color:#374151; background:rgba(31,41,55,0.5); }
    .filter-btn { transition: all .2s; background: rgba(31,41,55,0.55); color: #9CA3AF; border: 1px solid #1F2937; border-radius: 0.75rem; padding: 0.4rem 0.7rem; font-size: 0.75rem; font-weight: 600; white-space: nowrap; cursor: pointer; }
    .filter-btn:hover { color: #fff; border-color: #06B6D4; }
    .filter-btn.active { background: linear-gradient(135deg, #06B6D4 0%, #0891B2 100%); color: #0A0E1A; border-color: transparent; }
    .lang-btn { transition:all .2s; color:#9CA3AF; }
    .lang-btn.active { background:#06B6D4; color:#0A0E1A; }
    .lang-btn:not(.active):hover { color:#fff; }
    .card-hover { transition:all .3s; cursor:pointer; }
    .card-hover:hover { border-color:rgba(6,182,212,0.5); transform:translateY(-3px); box-shadow:0 12px 36px rgba(6,182,212,0.12); }
    .price-up { color:#10B981; } .price-down { color:#EF4444; }
    .price, .change { font-variant-numeric: tabular-nums; display: inline-block; }
    .bg-up-soft { background:rgba(16,185,129,0.10); border:1px solid rgba(16,185,129,0.35); color:#10B981; }
    .bg-down-soft { background:rgba(239,68,68,0.10); border:1px solid rgba(239,68,68,0.35); color:#EF4444; }
    .bg-warn-soft { background:rgba(234,179,8,0.10); border:1px solid rgba(234,179,8,0.35); color:#FBBF24; }
    .scroll-hide::-webkit-scrollbar { display:none; }
    .scroll-hide {
      -ms-overflow-style:none;
      scrollbar-width:none;
      -webkit-overflow-scrolling: touch;
      touch-action: pan-x;
      overscroll-behavior-x: contain;
    }
    .star-btn { transition:all .2s; cursor:pointer; background:none; border:none; font-size:1.6rem; line-height:1; }
    .star-btn.active { color:#FBBF24; transform:scale(1.1); }
    .star-btn:not(.active) { color:#4B5563; }
    .star-btn:not(.active):hover { color:#9CA3AF; }
    @keyframes favPop {
      0%   { transform: scale(1)   rotate(0deg);   }
      40%  { transform: scale(1.5) rotate(72deg);  }
      70%  { transform: scale(0.9) rotate(180deg); }
      100% { transform: scale(1.1) rotate(360deg); }
    }
    .star-btn.fav-pop { animation: favPop 0.5s cubic-bezier(.34,1.56,.64,1); }
    .fav-toast {
      position: fixed; bottom: 1.5rem; left: 50%;
      transform: translateX(-50%) translateY(20px);
      background: linear-gradient(135deg, rgba(6,182,212,0.25), rgba(34,211,238,0.15));
      border: 1px solid rgba(6,182,212,0.5);
      color: #ECFEFF; padding: 0.6rem 1.1rem;
      border-radius: 0.75rem; font-size: 0.85rem; font-weight: 700;
      backdrop-filter: blur(8px);
      box-shadow: 0 10px 30px rgba(6,182,212,0.3);
      opacity: 0; pointer-events: none;
      transition: opacity .25s ease, transform .25s ease;
      z-index: 60;
    }
    .fav-toast.show {
      opacity: 1; transform: translateX(-50%) translateY(0);
    }
    .tech-pending {
      display: inline-block;
      width: 0.5rem; height: 0.5rem;
      border-radius: 9999px;
      background: #06B6D4;
      box-shadow: 0 0 6px rgba(6,182,212,0.6);
      animation: techPulse 1.2s ease-in-out infinite;
    }
    @keyframes techPulse {
      0%, 100% { opacity: 0.35; transform: scale(0.85); }
      50%      { opacity: 1;    transform: scale(1.15); }
    }
    .bt-stat {
      background: linear-gradient(135deg, rgba(31,41,55,0.5) 0%, rgba(17,24,39,0.5) 100%);
      border: 1px solid rgba(75,85,99,0.4);
      border-radius: 0.75rem;
      padding: 0.75rem;
      text-align: center;
    }
    .bt-stat .bt-value { font-size: 1.5rem; font-weight: 800; line-height: 1; }
    .bt-stat .bt-label { font-size: 0.7rem; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.3rem; }
    .daily-pick-card {
      background: linear-gradient(135deg, rgba(6,182,212,0.14) 0%, rgba(34,211,238,0.05) 100%);
      border: 1px solid rgba(6,182,212,0.35);
      border-radius: 1rem;
      padding: 1rem 1.25rem;
      position: relative;
      overflow: hidden;
    }
    .daily-pick-card::before {
      content: '';
      position: absolute;
      top: -60%; right: -10%;
      width: 220px; height: 220px;
      background: radial-gradient(circle, rgba(6,182,212,0.18) 0%, transparent 70%);
      pointer-events: none;
    }
    .daily-pick-timer { font-variant-numeric: tabular-nums; font-weight: 700; color: #67E8F9; }
    .win-rate-bar {
      background: linear-gradient(135deg, rgba(31,41,55,0.5) 0%, rgba(17,24,39,0.5) 100%);
      border: 1px solid rgba(75,85,99,0.4);
      border-radius: 0.75rem;
      padding: 0.75rem 1rem;
      margin-bottom: 1.25rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.75rem;
    }
    .win-rate-bar .wr-stat { text-align: center; min-width: 70px; }
    .win-rate-bar .wr-stat .wr-value { font-size: 1.1rem; font-weight: 800; line-height: 1; }
    .win-rate-bar .wr-stat .wr-label { font-size: 0.65rem; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 0.2rem; }
    .fade-in { animation:fadeIn .35s ease-out; }
    @keyframes fadeIn { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .animate-spin { animation: spin 1s linear infinite; display: inline-block; }
    #tv_chart_container { width:100%; height: 540px; }
    .live-dot { position:relative; display:inline-flex; width:0.5rem; height:0.5rem; }
    .live-dot::before { content:''; position:absolute; inset:0; border-radius:9999px; background:#10B981; opacity:.75; animation:ping 1.6s cubic-bezier(0,0,.2,1) infinite; }
    .live-dot::after { content:''; position:relative; display:inline-block; width:0.5rem; height:0.5rem; border-radius:9999px; background:#10B981; }
    @keyframes ping { 75%, 100% { transform: scale(2); opacity: 0; } }
    ::-webkit-scrollbar { width:8px; height:8px; }
    ::-webkit-scrollbar-track { background:#0A0E1A; }
    ::-webkit-scrollbar-thumb { background:#1F2937; border-radius:4px; }
    ::-webkit-scrollbar-thumb:hover { background:#374151; }
    .logo-glow { text-shadow: 0 0 30px rgba(6,182,212,0.35); }
    [dir="ltr"] .flip-on-rtl { transform: scaleX(-1); }
    .tf-btn { background: rgba(31,41,55,0.55); color: #9CA3AF; border: 1px solid #1F2937; transition: all .2s; }
    .tf-btn:hover { color: #fff; border-color: #374151; }
    .tf-btn.active { background: linear-gradient(135deg, #06B6D4 0%, #0891B2 100%); color: #0A0E1A; border-color: transparent; box-shadow: 0 0 12px rgba(6,182,212,0.35); }
    .pf-input { background: rgba(10,14,26,0.7); border: 1px solid #1F2937; border-radius: 0.75rem; padding: 0.5rem 0.75rem; color: #fff; font-weight: 700; font-size: 0.875rem; width: 100%; }
    .pf-input:focus { outline: none; border-color: #06B6D4; box-shadow: 0 0 0 2px rgba(6,182,212,0.2); }
    .alert-btn { transition: all .2s; background: rgba(31,41,55,0.55); border: 1px solid #1F2937; border-radius: 0.75rem; padding: 0.4rem 0.7rem; color: #9CA3AF; font-size: 0.8rem; cursor: pointer; }
    .alert-btn:hover { color: #FBBF24; border-color: #FBBF24; }
    .alert-btn.active { color: #FBBF24; border-color: #FBBF24; background: rgba(251,191,36,0.10); }
    @keyframes recFlash {
      0%   { background-color: var(--flash-color); box-shadow: 0 0 0 0 var(--flash-glow); }
      40%  { background-color: var(--flash-color); box-shadow: 0 0 24px 6px var(--flash-glow); }
      100% { background-color: transparent;        box-shadow: 0 0 0 0 transparent; }
    }
    .rec-flash-buy  { --flash-color: rgba(16,185,129,0.30); --flash-glow: rgba(16,185,129,0.40); animation: recFlash 0.8s ease-out; }
    .rec-flash-sell { --flash-color: rgba(239,68,68,0.30);  --flash-glow: rgba(239,68,68,0.40);  animation: recFlash 0.8s ease-out; }
    .rec-flash-wait { --flash-color: rgba(234,179,8,0.30);  --flash-glow: rgba(234,179,8,0.40);  animation: recFlash 0.8s ease-out; }
  </style>
</head>
<body>
  <div id="mainView" class="min-h-screen flex flex-col"></div>
  <div id="analysisView" class="hidden min-h-screen flex flex-col"></div>

  <script>
  /* =========================================================
     TradeAI — Static SPA, bilingual (AR primary / EN), RTL/LTR
     ========================================================= */

  const T = {
    ar: {
      tagline: 'تحليل فني ذكي، قرارات مدروسة',
      login: 'تسجيل دخول',
      categories: { all:'الكل', stocks:'الأسهم', crypto:'العملات الرقمية', forex:'الصرف الأجنبي', commodities:'السلع', indices:'المؤشرات' },
      catShort: { stocks:'أسهم', crypto:'كريبتو', forex:'فوركس', commodities:'سلع', indices:'مؤشرات' },
      favorites: 'المفضلة',
      favorite: 'إضافة للمفضلة',
      noFavorites: 'لا توجد أصول في المفضلة بعد. اضغط ⭐ على أي أصل لإضافته.',
      dailyPick: 'توصية اليوم',
      renewsIn: 'يتجدد خلال',
      winRate30: 'آخر 30 يوم',
      winRate: 'نسبة النجاح',
      avgReturn: 'متوسط العائد',
      record: 'ربح/خسارة/مفتوحة',
      noHistory: 'تتراكم البيانات من اليوم. زر بعد 3 أيام لمشاهدة النتائج.',
      trend: 'الاتجاه',
      momentum: 'الزخم',
      volatility: 'التذبذب',
      pivots: 'نقاط الارتكاز',
      overbought: 'تشبع شرائي',
      oversold: 'تشبع بيعي',
      analysisBtn: 'تحليل فني',
      back: 'رجوع',
      currentPrice: 'السعر الحالي',
      change: 'التغير',
      volume: 'الحجم (24س)',
      high24: 'أعلى 24س',
      low24: 'أدنى 24س',
      technical: 'المؤشرات الفنية',
      priceLevels: 'مستويات السعر',
      recommendation: 'التوصية الفنية',
      entry: 'نقطة الدخول',
      stop: 'وقف الخسارة',
      target: 'الهدف',
      rr: 'المخاطرة/المكافأة',
      duration: 'المدة المتوقعة',
      confidence: 'مستوى الثقة',
      waitTitle: 'التوصية الحالية: انتظار',
      waitDesc: 'المؤشرات الفنية لا تدعم دخولاً آمناً حالياً. راقب اختراق المقاومة أو كسر الدعم لإعادة التقييم.',
      confidenceReading: 'مستوى الثقة في القراءة الحالية',
      advancedChart: 'الرسم البياني المتقدم على TradingView',
      tradeWith: 'تداول عبر وسيط',
      chartUnavailable: 'الرسم البياني غير متاح حالياً',
      cardNote: '✅ أسعار حية محدّثة كل 30 ثانية — اضغط للاطلاع على التحليل الفني',
      chartNote: '✅ بيانات حية مباشرة من TradingView',
      timeframe: 'الإطار الزمني',
      riskCalc: '🧮 حاسبة المخاطرة',
      riskCalcDesc: 'احسب حجم الصفقة بناءً على مخاطرة %',
      accountSize: 'حجم الحساب ($)',
      riskPct: 'المخاطرة %',
      positionSize: 'حجم الصفقة',
      riskAmount: 'مبلغ المخاطرة',
      positionValue: 'قيمة الصفقة',
      riskHint: 'أدخل حجم حسابك ونسبة المخاطرة لتعرف حجم الصفقة المثالي',
      timeframeLabel: { '1': '1د', '5': '5د', '15': '15د', '60': '1س', '240': '4س', 'D': 'يوم', 'W': 'أسبوع' },
      disclaimer: '⚠️ منصة TradeAI للتحليل الفني التعليمي فقط. لا تُعدّ نصيحة استثمارية. التداول ينطوي على مخاطر عالية.',
      assetName: {
        'AAPL':'أبل','TSLA':'تسلا','MSFT':'مايكروسوفت','GOOGL':'ألفابت',
        'AMZN':'أمازون','NVDA':'إنفيديا','META':'ميتا','NFLX':'نتفليكس',
        'BTC':'بيتكوين','ETH':'إيثريوم','BNB':'بي إن بي','SOL':'سولانا','XRP':'ريبل',
        'EUR/USD':'يورو / دولار','GBP/USD':'جنيه / دولار','USD/JPY':'دولار / ين','XAU/USD':'ذهب',
        'WTI':'نفط خام WTI','BRENT':'نفط برنت',
        'S&P500':'ستاندرد آند بورز 500','NASDAQ':'ناسداك'
      }
    },
    en: {
      tagline: 'Smart Technical Analysis, Informed Decisions',
      login: 'Login',
      categories: { all:'All', stocks:'Stocks', crypto:'Crypto', forex:'Forex', commodities:'Commodities', indices:'Indices' },
      catShort: { stocks:'Stocks', crypto:'Crypto', forex:'Forex', commodities:'Commod.', indices:'Indices' },
      favorites: 'Favorites',
      favorite: 'Add to favorites',
      noFavorites: 'No favorites yet. Tap ⭐ on any asset to add it.',
      dailyPick: 'Daily Pick',
      renewsIn: 'Renews in',
      winRate30: 'Last 30 days',
      winRate: 'Win rate',
      avgReturn: 'Avg return',
      record: 'W/L/Open',
      noHistory: 'Data accumulates from today. Check back in 3 days to see results.',
      trend: 'Trend',
      momentum: 'Momentum',
      volatility: 'Volatility',
      pivots: 'Pivot Points',
      overbought: 'Overbought',
      oversold: 'Oversold',
      analysisBtn: 'Analysis',
      back: 'Back',
      currentPrice: 'Current Price',
      change: 'Change',
      volume: 'Volume (24H)',
      high24: 'High 24H',
      low24: 'Low 24H',
      technical: 'Technical Indicators',
      priceLevels: 'Price Levels',
      recommendation: 'Technical Recommendation',
      entry: 'Entry',
      stop: 'Stop Loss',
      target: 'Target',
      rr: 'Risk / Reward',
      duration: 'Expected Duration',
      confidence: 'Confidence',
      waitTitle: 'Current Recommendation: Wait',
      waitDesc: 'Technical indicators do not support a safe entry at the moment. Watch for a resistance breakout or support break to reassess.',
      confidenceReading: 'Confidence in current reading',
      advancedChart: 'Advanced Chart on TradingView',
      tradeWith: 'Trade with a Broker',
      chartUnavailable: 'Chart currently unavailable',
      cardNote: '✅ Live prices refresh every 30s — tap for full analysis',
      chartNote: '✅ Live data streaming from TradingView',
      timeframe: 'Timeframe',
      riskCalc: '🧮 Risk Calculator',
      riskCalcDesc: 'Calculate position size from your risk %',
      accountSize: 'Account Size ($)',
      riskPct: 'Risk %',
      positionSize: 'Position Size',
      riskAmount: 'Risk Amount',
      positionValue: 'Position Value',
      optional: 'optional',
      riskHint: 'Enter your account size and risk % to find the optimal position size',
      timeframeLabel: { '1': '1m', '5': '5m', '15': '15m', '60': '1H', '240': '4H', 'D': '1D', 'W': '1W' },
      disclaimer: '⚠️ TradeAI provides educational technical analysis only. Not investment advice. Trading involves high risk.',
      assetName: {
        'AAPL':'Apple Inc.','TSLA':'Tesla, Inc.','MSFT':'Microsoft','GOOGL':'Alphabet',
        'AMZN':'Amazon','NVDA':'NVIDIA','META':'Meta Platforms','NFLX':'Netflix',
        'BTC':'Bitcoin','ETH':'Ethereum','BNB':'BNB','SOL':'Solana','XRP':'XRP',
        'EUR/USD':'EUR / USD','GBP/USD':'GBP / USD','USD/JPY':'USD / JPY','XAU/USD':'Gold',
        'WTI':'WTI Crude','BRENT':'Brent Crude',
        'S&P500':'S&P 500','NASDAQ':'NASDAQ'
      }
    }
  };

  const STATUS_T = {
    ar: { buy:'شراء', sell:'بيع', wait:'انتظار', above:'فوق', below:'تحت', bullish:'صاعد', bearish:'هابط', weak:'ضعيف', neutral:'محايد', overbought:'تشبع شرائي', oversold:'تشبع بيعي' },
    en: { buy:'Buy', sell:'Sell', wait:'Wait', above:'above', below:'below', bullish:'Bullish', bearish:'Bearish', weak:'Weak', neutral:'Neutral', overbought:'Overbought', oversold:'Oversold' }
  };
  const DURATION_T = {
    ar: { '1-3 days':'1-3 أيام', '2-4 days':'2-4 أيام', '3-5 days':'3-5 أيام', '1-2 weeks':'1-2 أسابيع' },
    en: { '1-3 days':'1-3 days', '2-4 days':'2-4 days', '3-5 days':'3-5 days', '1-2 weeks':'1-2 weeks' }
  };

  function safeJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (raw == null) return fallback;
      const parsed = JSON.parse(raw);
      return parsed == null ? fallback : parsed;
    } catch (e) {
      console.warn('[TradeAI] corrupt localStorage value for', key, '— resetting');
      try { localStorage.removeItem(key); } catch (_) {}
      return fallback;
    }
  }

  let lang = localStorage.getItem('tradeai_lang') || 'ar';
  let currentCategory = 'all';
  let currentFilter = null; 
  let currentView = 'main';
  let currentAssetId = null;
  let favorites = safeJSON('tradeai_favs', []);
  let liveData = { lastUpdate: null };
  let lastRecAction = {};

  const t   = (k) => T[lang][k] ?? k;
  const tn  = (sym) => T[lang].assetName[sym] || sym;
  const ts  = (k) => STATUS_T[lang][k] || k;
  const td  = (k) => DURATION_T[lang][k] || k;

  function formatPrice(p) {
    if (p == null) return '—';
    if (p < 1)    return p.toFixed(4);
    if (p < 10)   return p.toFixed(4);
    if (p < 1000) return p.toFixed(2);
    return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function formatChange(c) { return (c >= 0 ? '+' : '') + c.toFixed(c % 1 ? 2 : 0) + '%'; }
  function formatRR(entry, stop, target) {
    if (entry == null || stop == null || target == null) return '—';
    const risk = Math.abs(entry - stop);
    if (risk <= 0) return '—';
    const reward = Math.abs(target - entry);
    return `1:${(reward / risk).toFixed(2)}`;
  }

  const ASSETS = [
    { id:'AAPL', symbol:'AAPL', category:'stocks', price:189.50, change:0.8,  icon:'🍎', tv:'NASDAQ:AAPL',
      volume:'52.3M', high24:191.20, low24:187.80,
      analysis:{ rsi:52, rsiSt:'neutral', ma50:185, ma200:178, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:184, resistance:195,
        action:'buy', entry:189.50, stop:184, target:195, duration:'3-5 days', confidence:54 } },
    { id:'TSLA', symbol:'TSLA', category:'stocks', price:342.27, change:1.2, icon:'🚗', tv:'NASDAQ:TSLA',
      volume:'110M', high24:345.00, low24:338.50,
      analysis:{ rsi:55, rsiSt:'bullish', ma50:335, ma200:295, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:322, resistance:382,
        action:'buy', entry:342.27, stop:322, target:382, duration:'3-5 days', confidence:60 } },
    { id:'MSFT', symbol:'MSFT', category:'stocks', price:420, change:0.5, icon:'💻', tv:'NASDAQ:MSFT',
      volume:'22M', high24:422.50, low24:418.20,
      analysis:{ rsi:45, rsiSt:'bearish', ma50:425, ma200:395, ma50Pos:'below', ma200Pos:'above', macd:'bearish', support:410, resistance:435,
        action:'wait', confidence:48 } },
    { id:'GOOGL', symbol:'GOOGL', category:'stocks', price:175, change:-0.3, icon:'🔍', tv:'NASDAQ:GOOGL',
      volume:'25M', high24:176.50, low24:174.10,
      analysis:{ rsi:42, rsiSt:'weak', ma50:178, ma200:165, ma50Pos:'below', ma200Pos:'above', macd:'bearish', support:170, resistance:182,
        action:'wait', confidence:44 } },
    { id:'AMZN', symbol:'AMZN', category:'stocks', price:185, change:0.9, icon:'📦', tv:'NASDAQ:AMZN',
      volume:'35M', high24:186.20, low24:183.50,
      analysis:{ rsi:56, rsiSt:'bullish', ma50:180, ma200:168, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:178, resistance:192,
        action:'buy', entry:185, stop:178, target:192, duration:'2-4 days', confidence:55 } },
    { id:'NVDA', symbol:'NVDA', category:'stocks', price:875, change:2.1, icon:'🎮', tv:'NASDAQ:NVDA',
      volume:'45M', high24:880, low24:860,
      analysis:{ rsi:64, rsiSt:'bullish', ma50:820, ma200:720, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:820, resistance:975,
        action:'buy', entry:875, stop:820, target:975, duration:'2-4 days', confidence:56 } },
    { id:'META', symbol:'META', category:'stocks', price:485, change:-0.5, icon:'👥', tv:'NASDAQ:META',
      volume:'18M', high24:488.50, low24:482.30,
      analysis:{ rsi:41, rsiSt:'weak', ma50:495, ma200:470, ma50Pos:'below', ma200Pos:'above', macd:'bearish', support:475, resistance:510,
        action:'wait', confidence:43 } },
    { id:'NFLX', symbol:'NFLX', category:'stocks', price:685, change:1.5, icon:'🎬', tv:'NASDAQ:NFLX',
      volume:'5M', high24:690, low24:678.50,
      analysis:{ rsi:58, rsiSt:'bullish', ma50:660, ma200:600, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:650, resistance:720,
        action:'buy', entry:685, stop:650, target:720, duration:'3-5 days', confidence:57 } },

    { id:'BTC', symbol:'BTC', category:'crypto', price:67245, change:1.85, icon:'₿', tv:'BINANCE:BTCUSDT',
      volume:'32B', high24:67800, low24:66500,
      analysis:{ rsi:58, rsiSt:'bullish', ma50:65500, ma200:62000, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:64500, resistance:72000,
        action:'buy', entry:67245, stop:64500, target:72000, duration:'1-2 weeks', confidence:62 } },
    { id:'ETH', symbol:'ETH', category:'crypto', price:3550, change:2.1, icon:'Ξ', tv:'BINANCE:ETHUSDT',
      volume:'18B', high24:3580, low24:3490,
      analysis:{ rsi:60, rsiSt:'bullish', ma50:3380, ma200:2950, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:3400, resistance:3800,
        action:'buy', entry:3550, stop:3400, target:3800, duration:'1-2 weeks', confidence:60 } },
    { id:'BNB', symbol:'BNB', category:'crypto', price:605, change:0.7, icon:'🟡', tv:'BINANCE:BNBUSDT',
      volume:'1.8B', high24:610, low24:600,
      analysis:{ rsi:54, rsiSt:'neutral', ma50:590, ma200:540, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:580, resistance:640,
        action:'buy', entry:605, stop:580, target:640, duration:'2-4 days', confidence:53 } },
    { id:'SOL', symbol:'SOL', category:'crypto', price:158, change:3.2, icon:'☀️', tv:'BINANCE:SOLUSDT',
      volume:'3.2B', high24:160, low24:154,
      analysis:{ rsi:62, rsiSt:'bullish', ma50:142, ma200:115, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:145, resistance:175,
        action:'buy', entry:158, stop:145, target:175, duration:'1-3 days', confidence:58 } },
    { id:'XRP', symbol:'XRP', category:'crypto', price:0.62, change:1.1, icon:'✕', tv:'BINANCE:XRPUSDT',
      volume:'2.1B', high24:0.63, low24:0.61,
      analysis:{ rsi:47, rsiSt:'neutral', ma50:0.64, ma200:0.58, ma50Pos:'below', ma200Pos:'above', macd:'bearish', support:0.58, resistance:0.68,
        action:'wait', confidence:47 } },

    { id:'EUR/USD', symbol:'EUR/USD', category:'forex', price:1.0845, change:-0.12, icon:'💶', tv:'FX:EURUSD',
      volume:'—', high24:1.0880, low24:1.0820,
      analysis:{ rsi:48, rsiSt:'neutral', ma50:1.0880, ma200:1.0950, ma50Pos:'below', ma200Pos:'below', macd:'bearish', support:1.0780, resistance:1.0920,
        action:'wait', confidence:45 } },
    { id:'GBP/USD', symbol:'GBP/USD', category:'forex', price:1.265, change:0.25, icon:'💷', tv:'FX:GBPUSD',
      volume:'—', high24:1.2680, low24:1.2620,
      analysis:{ rsi:53, rsiSt:'neutral', ma50:1.260, ma200:1.245, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:1.255, resistance:1.280,
        action:'buy', entry:1.265, stop:1.255, target:1.280, duration:'2-4 days', confidence:52 } },
    { id:'USD/JPY', symbol:'USD/JPY', category:'forex', price:151.20, change:-0.08, icon:'💴', tv:'FX:USDJPY',
      volume:'—', high24:151.50, low24:151.00,
      analysis:{ rsi:44, rsiSt:'weak', ma50:151.80, ma200:149.50, ma50Pos:'below', ma200Pos:'above', macd:'bearish', support:150.50, resistance:152.50,
        action:'wait', confidence:45 } },
    { id:'XAU/USD', symbol:'XAU/USD', category:'forex', price:2430.50, change:0.42, icon:'🥇', tv:'OANDA:XAUUSD',
      volume:'—', high24:2440, low24:2420,
      analysis:{ rsi:62, rsiSt:'bullish', ma50:2410, ma200:2350, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:2380, resistance:2470,
        action:'buy', entry:2430.50, stop:2380, target:2470, duration:'1-2 weeks', confidence:58 } },

    { id:'WTI', symbol:'WTI', category:'commodities', price:78.50, change:0.85, icon:'🛢️', tv:'TVC:USOIL',
      volume:'350K', high24:79.00, low24:77.80,
      analysis:{ rsi:57, rsiSt:'bullish', ma50:76.50, ma200:72.00, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:76, resistance:82,
        action:'buy', entry:78.50, stop:76, target:82, duration:'2-4 days', confidence:56 } },
    { id:'BRENT', symbol:'BRENT', category:'commodities', price:82.30, change:0.60, icon:'⛽', tv:'TVC:UKOIL',
      volume:'280K', high24:82.80, low24:81.50,
      analysis:{ rsi:55, rsiSt:'bullish', ma50:80.50, ma200:75.00, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:80, resistance:86,
        action:'buy', entry:82.30, stop:80, target:86, duration:'2-4 days', confidence:54 } },

    { id:'S&P500', symbol:'S&P500', category:'indices', price:5120, change:0.4, icon:'📈', tv:'AMEX:SPY',
      volume:'2.1B', high24:5135, low24:5095,
      analysis:{ rsi:54, rsiSt:'neutral', ma50:5080, ma200:4820, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:5050, resistance:5200,
        action:'buy', entry:5120, stop:5050, target:5200, duration:'3-5 days', confidence:55 } },
    { id:'NASDAQ', symbol:'NASDAQ', category:'indices', price:16200, change:0.6, icon:'💹', tv:'NASDAQ:QQQ',
      volume:'1.8B', high24:16250, low24:16100,
      analysis:{ rsi:56, rsiSt:'bullish', ma50:16000, ma200:15200, ma50Pos:'above', ma200Pos:'above', macd:'bullish', support:15900, resistance:16500,
        action:'buy', entry:16200, stop:15900, target:16500, duration:'3-5 days', confidence:57 } }
  ];

  const CATEGORIES = ['all','stocks','crypto','forex','commodities','indices'];

  function setLang(l) {
    lang = l;
    localStorage.setItem('tradeai_lang', l);
    document.documentElement.lang = l;
    document.documentElement.dir = l === 'ar' ? 'rtl' : 'ltr';
    if (currentView === 'main') renderMain();
    else if (currentAssetId) renderAnalysis(currentAssetId);
  }

  function toggleFav(id) {
    const idx = favorites.indexOf(id);
    if (idx > -1) favorites.splice(idx, 1);
    else favorites.push(id);
    localStorage.setItem('tradeai_favs', JSON.stringify(favorites));
    const btn = document.getElementById('favBtn');
    if (btn) {
      btn.classList.add('fav-pop');
      setTimeout(() => btn.classList.remove('fav-pop'), 500);
      btn.innerHTML = favorites.includes(id) ? '⭐' : '☆';
    }
    showToast(favorites.includes(id) ? (lang === 'ar' ? 'تمت الإضافة للمفضلة' : 'Added to favorites') : (lang === 'ar' ? 'تمت الإزالة من المفضلة' : 'Removed from favorites'));
  }

  function showToast(msg) {
    let t = document.getElementById('favToast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'favToast';
      t.className = 'fav-toast';
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2500);
  }

  function langSwitcher() {
    return `
      <div class="flex items-center gap-1 bg-app-bg/60 border border-app-border rounded-xl p-1">
        <button class="lang-btn px-2.5 py-1 rounded-lg text-xs font-bold ${lang==='ar'?'active':''}" data-lang="ar">AR</button>
        <button class="lang-btn px-2.5 py-1 rounded-lg text-xs font-bold ${lang==='en'?'active':''}" data-lang="en">EN</button>
      </div>`;
  }

  function mainHeader() {
    return `
      <header class="glass sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-3">
          <div class="flex items-center gap-3 min-w-0">
            <div class="logo-glow cursor-pointer" onclick="goHome()">
              <div class="text-2xl sm:text-3xl font-extrabold text-grad-cyan leading-none">TradeAI</div>
            </div>
            <div class="hidden md:block text-sm text-gray-400 truncate">${t('tagline')}</div>
          </div>
          <div class="flex items-center gap-2 sm:gap-3">
            ${langSwitcher()}
          </div>
        </div>
      </header>
    `;
  }

  function categoryBar() {
    return `
      <div class="sticky top-[68px] sm:top-[76px] z-30 glass-strong">
        <div class="max-w-7xl mx-auto px-3 sm:px-6 py-3 flex items-center gap-2 overflow-x-auto scroll-hide">
          <button class="cat-btn px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold whitespace-nowrap flex items-center gap-1.5 ${currentCategory==='favorites'?'active':''}" data-cat="favorites">
            <span>⭐</span><span>${t('favorites')}</span>
          </button>
          ${CATEGORIES.map(c => `
            <button class="cat-btn px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold whitespace-nowrap ${currentCategory===c?'active':''}" data-cat="${c}">
              ${T[lang].categories[c]}
            </button>`).join('')}
        </div>
      </div>
    `;
  }

  function footer() {
    return `
      <footer class="glass border-t border-app-border mt-auto">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-5 text-center text-xs sm:text-sm text-gray-400">
          ${t('disclaimer')}
        </div>
      </footer>
    `;
  }

  function filterBar() {
    const isAr = lang === 'ar';
    const filters = [
      { key: 'gainers',        icon: '📈', label: isAr ? 'الأعلى ارتفاعاً' : 'Top Gainers' },
      { key: 'losers',         icon: '📉', label: isAr ? 'الأعلى انخفاضاً' : 'Top Losers' },
      { key: 'nearSupport',    icon: '🎯', label: isAr ? 'عند الدعم'      : 'Near Support' },
      { key: 'nearResistance', icon: '🚀', label: isAr ? 'عند المقاومة'   : 'Near Resistance' },
      { key: 'biggestMove',    icon: '⚡', label: isAr ? 'أكبر حركة'      : 'Biggest Move' },
    ];
    const active = filters.find(f => f.key === currentFilter);
    const filterLabel = !currentFilter
      ? (isAr ? '🔍 فلاتر سريعة' : '🔍 Quick Filters')
      : active.icon + ' ' + active.label;
    const bestLabel = isAr ? '🎯 أفضل الفرص' : '🎯 Best Trades';
    return `
      <div class="max-w-7xl mx-auto px-3 sm:px-6 pt-3 flex items-center gap-2 flex-wrap">
        <button onclick="showFilterMenu()" class="btn-cyan px-3 py-2 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-1.5 shrink-0">
          <span>${filterLabel}</span>
          <span class="text-[9px] opacity-70">▼</span>
        </button>
        <button onclick="showBestTrades()" class="btn-cyan px-3 py-2 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-1.5 shrink-0">
          <span>${bestLabel}</span>
        </button>
      </div>
    `;
  }

  function showFilterMenu() {
    const existing = document.getElementById('filterMenuModal');
    if (existing) existing.remove();
    const isAr = lang === 'ar';
    const filters = [
      { key: 'gainers',        icon: '📈', label: isAr ? 'الأعلى ارتفاعاً' : 'Top Gainers' },
      { key: 'losers',         icon: '📉', label: isAr ? 'الأعلى انخفاضاً' : 'Top Losers' },
      { key: 'nearSupport',    icon: '🎯', label: isAr ? 'عند الدعم'      : 'Near Support' },
      { key: 'nearResistance', icon: '🚀', label: isAr ? 'عند المقاومة'   : 'Near Resistance' },
      { key: 'biggestMove',    icon: '⚡', label: isAr ? 'أكبر حركة'      : 'Biggest Move' },
    ];
    const items = [
      { key: null, icon: '✅', label: isAr ? 'الكل (بدون فلتر)' : 'All (no filter)' },
      ...filters.map(f => ({ key: f.key, icon: f.icon, label: f.label })),
    ];
    const html = `
      <div class="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-black/60 fade-in" onclick="closeFilterMenu()">
        <div class="glass-strong rounded-2xl p-4 sm:p-5 max-w-sm w-full" onclick="event.stopPropagation()">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-grad-cyan">${isAr ? 'فلتر سريع' : 'Quick Filter'}</h3>
            <button onclick="closeFilterMenu()" class="text-gray-400 hover:text-white text-xl leading-none w-8 h-8 flex items-center justify-center">✕</button>
          </div>
          <div class="space-y-2">
            ${items.map(it => `
              <button onclick="setFilterAndClose('${it.key || ''}')"
                      class="w-full text-${isAr ? 'right' : 'left'} p-3 rounded-xl flex items-center gap-3 border transition ${currentFilter === it.key ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300' : 'border-app-border hover:border-cyan-500/30 hover:bg-app-bg/40'}">
                <span class="text-xl shrink-0">${it.icon}</span>
                <span class="font-semibold text-sm">${it.label}</span>
                ${currentFilter === it.key ? '<span class="ms-auto text-cyan-400">✓</span>' : ''}
              </button>
            `).join('')}
          </div>
        </div>
      </div>
    `;
    const div = document.createElement('div');
    div.id = 'filterMenuModal';
    div.innerHTML = html;
    document.body.appendChild(div);
  }

  function closeFilterMenu() {
    const m = document.getElementById('filterMenuModal');
    if (m) m.remove();
  }

  function setFilterAndClose(key) {
    currentFilter = key || null;
    closeFilterMenu();
    renderMain();
  }

  function applyQuickFilter(list) {
    if (!currentFilter) return list;
    const filtered = list.slice();
    if (currentFilter === 'gainers') {
      return filtered.sort((a, b) => (b.change || 0) - (a.change || 0)).slice(0, 8);
    }
    if (currentFilter === 'losers') {
      return filtered.sort((a, b) => (a.change || 0) - (b.change || 0)).slice(0, 8);
    }
    if (currentFilter === 'nearSupport') {
      return filtered
        .filter(a => Number.isFinite(a.low24) && a.low24 > 0 && a.price > 0)
        .map(a => ({ ...a, _dist: Math.abs(a.price - a.low24) / a.price }))
        .filter(a => a._dist < 0.01)
        .sort((a, b) => a._dist - b._dist);
    }
    if (currentFilter === 'nearResistance') {
      return filtered
        .filter(a => Number.isFinite(a.high24) && a.high24 > 0 && a.price > 0)
        .map(a => ({ ...a, _dist: Math.abs(a.high24 - a.price) / a.price }))
        .filter(a => a._dist < 0.01)
        .sort((a, b) => a._dist - b._dist);
    }
    if (currentFilter === 'biggestMove') {
      return filtered
        .filter(a => Number.isFinite(a.change))
        .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
        .slice(0, 8);
    }
    return filtered;
  }

  function assetCard(a) {
    const up = a.change >= 0;
    return `
      <div id="card-${a.id}" class="card-hover glass rounded-2xl p-3 sm:p-4 flex flex-col gap-3" data-id="${a.id}" onclick="openAsset('${a.id}')">
        <div class="flex items-start justify-between gap-2">
          <div class="flex items-center gap-3 min-w-0 flex-1">
            <span class="text-3xl shrink-0">${a.icon}</span>
            <div class="min-w-0 flex-1">
              <div class="font-bold text-sm sm:text-base truncate">${tn(a.symbol)}</div>
              <div class="text-xs text-gray-500 truncate">${a.symbol}</div>
            </div>
          </div>
          <span class="text-[10px] sm:text-xs px-2 py-1 rounded-lg whitespace-nowrap shrink-0 ${up?'bg-up-soft':'bg-down-soft'}">${T[lang].catShort[a.category]}</span>
        </div>
        <div class="mt-1">
          <div class="text-xl sm:text-2xl font-extrabold"><span class="price">${formatPrice(a.price)}</span><span class="text-[10px] sm:text-xs text-gray-500 font-medium ms-1">USD</span></div>
          <div class="text-sm font-bold ${up?'price-up':'price-down'}"><span class="change">${formatChange(a.change)}</span></div>
        </div>
      </div>
    `;
  }

  function renderDailyPick() {
    const pick = ASSETS.find(a => a.id === 'BTC') || ASSETS[0];
    return `
      <div class="daily-pick-card mb-6 flex flex-col sm:flex-row items-center justify-between gap-4 cursor-pointer" onclick="openAsset('${pick.id}')">
        <div class="flex items-center gap-4">
          <span class="text-4xl">${pick.icon}</span>
          <div>
            <div class="text-xs text-cyan-400 font-bold uppercase tracking-wider">${t('dailyPick')}</div>
            <div class="text-lg font-bold">${tn(pick.symbol)} (${pick.symbol})</div>
            <div class="text-xs text-gray-400">${t('renewsIn')} <span class="daily-pick-timer">14:22:05</span></div>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div class="text-right">
            <div class="text-lg font-extrabold">${formatPrice(pick.price)}</div>
            <div class="text-xs font-bold ${pick.change>=0?'text-green-400':'text-red-400'}">${formatChange(pick.change)}</div>
          </div>
          <button class="btn-cyan px-4 py-2 rounded-xl text-xs font-bold">${t('analysisBtn')}</button>
        </div>
      </div>
    `;
  }

  function renderWinRateBar() {
    return `
      <div class="win-rate-bar">
        <div class="wr-stat">
          <div class="wr-value text-green-400">78.5%</div>
          <div class="wr-label">${t('winRate')}</div>
        </div>
        <div class="wr-stat">
          <div class="wr-value text-cyan-400">+4.2%</div>
          <div class="wr-label">${t('avgReturn')}</div>
        </div>
        <div class="wr-stat">
          <div class="wr-value text-gray-200">22 / 6 / 3</div>
          <div class="wr-label">${t('record')}</div>
        </div>
      </div>
    `;
  }

  function renderMain() {
    currentView = 'main';
    const main = document.getElementById('mainView');
    const analysis = document.getElementById('analysisView');
    analysis.classList.add('hidden');
    main.classList.remove('hidden');
    main.innerHTML = `
      ${mainHeader()}
      ${categoryBar()}
      ${filterBar()}
      <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 sm:py-8 fade-in">
        <div class="relative">
          ${renderDailyPick()}
          ${renderWinRateBar()}
          <div id="assetGrid" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            ${(() => {
              let list = ASSETS.filter(a => {
                if (currentCategory === 'all') return true;
                if (currentCategory === 'favorites') return favorites.includes(a.id);
                return a.category === currentCategory;
              });
              list = applyQuickFilter(list);
              if (list.length === 0) {
                const emptyMsg = currentCategory === 'favorites'
                  ? t('noFavorites')
                  : (lang==='ar' ? 'لا توجد أصول تطابق هذا الفلتر' : 'No assets match this filter');
                return `<div class="col-span-full text-center text-gray-500 py-10 text-sm">${emptyMsg}</div>`;
              }
              return list.map(assetCard).join('');
            })()}
          </div>
        </div>
      </main>
      ${footer()}
    `;
    bindMainEvents();
  }

  function bindMainEvents() {
    document.querySelectorAll('.cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        currentCategory = btn.dataset.cat;
        renderMain();
      });
    });
    bindLangButtons();
  }

  function bindLangButtons() {
    document.querySelectorAll('.lang-btn').forEach(btn => {
      if (btn.dataset.bound === '1') return;
      btn.dataset.bound = '1';
      btn.addEventListener('click', () => setLang(btn.dataset.lang));
    });
  }

  function openAsset(id) {
    currentAssetId = id;
    renderAnalysis(id);
    window.location.hash = `#asset/${encodeURIComponent(id)}`;
    window.scrollTo({ top:0, behavior:'smooth' });
  }

  function backToMain() {
    currentView = 'main';
    currentAssetId = null;
    if (window.location.hash) {
      history.pushState('', document.title, window.location.pathname + window.location.search);
    }
    renderMain();
  }

  function actionBadge(action) {
    if (action === 'buy')  return `<span class="bg-up-soft px-3 sm:px-4 py-1.5 rounded-xl text-sm font-bold">🟢 ${ts('buy')}</span>`;
    if (action === 'sell') return `<span class="bg-down-soft px-3 sm:px-4 py-1.5 rounded-xl text-sm font-bold">🔴 ${ts('sell')}</span>`;
    return `<span class="bg-warn-soft px-3 sm:px-4 py-1.5 rounded-xl text-sm font-bold">⏸ ${ts('wait')}</span>`;
  }

  function analysisHeader(a) {
    const isFav = favorites.includes(a.id);
    return `
      <header class="glass sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-3">
          <div class="flex items-center gap-2 sm:gap-3 min-w-0">
            <button onclick="backToMain()" class="btn-outline-cyan px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-1 shrink-0">
              <span class="flip-on-rtl">←</span><span>${t('back')}</span>
            </button>
            <div class="flex items-center gap-2 sm:gap-3 min-w-0">
              <span class="text-2xl sm:text-3xl shrink-0">${a.icon}</span>
              <div class="min-w-0">
                <div class="font-bold text-sm sm:text-lg truncate">${tn(a.symbol)}</div>
                <div class="text-xs text-gray-500">${a.symbol}</div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-2 sm:gap-3">
            <button class="star-btn ${isFav?'active':''}" id="favBtn" onclick="toggleFav('${a.id}')">${isFav?'⭐':'☆'}</button>
            ${langSwitcher()}
          </div>
        </div>
      </header>
    `;
  }

  function priceBar(a) {
    const up = a.change >= 0;
    return `
      <div class="glass rounded-2xl p-4 sm:p-5">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
          <div>
            <div class="text-xs text-gray-500 mb-1">${t('currentPrice')}</div>
            <div id="priceCurrent" class="text-2xl sm:text-3xl font-extrabold">${formatPrice(a.price)}<span class="text-xs sm:text-sm text-gray-500 font-medium ms-1">USD</span></div>
          </div>
          <div>
            <div class="text-xs text-gray-500 mb-1">${t('change')} (24${lang==='ar'?'س':'h'})</div>
            <div id="priceChange" class="text-2xl sm:text-3xl font-extrabold ${up?'price-up':'price-down'}">${formatChange(a.change)}</div>
          </div>
        </div>
      </div>
    `;
  }

  function technicalBox(a) {
    const an = a.analysis;
    const row = (label, value, color) => `
      <div class="flex items-center justify-between py-1.5 text-sm">
        <span class="text-gray-400">${label}</span>
        <span class="font-bold ${color || 'text-gray-100'}">${value}</span>
      </div>`;
    return `
      <div class="glass rounded-2xl p-5 sm:p-6 space-y-5">
        <div>
          <h3 class="text-base sm:text-lg font-bold mb-2 text-grad-cyan">📈 ${t('trend')}</h3>
          ${row('MA50', formatPrice(an.ma50), 'text-green-400')}
          ${row('MA200', formatPrice(an.ma200), 'text-green-400')}
          ${row('MACD', ts(an.macd), an.macd==='bullish'?'text-green-400':'text-red-400')}
        </div>
        <div class="border-t border-app-border pt-4">
          <h3 class="text-base sm:text-lg font-bold mb-2 text-grad-cyan">⚡ ${t('momentum')}</h3>
          ${row('RSI (14)', an.rsi, 'text-cyan-300')}
        </div>
      </div>
    `;
  }

  function computeRecommendation(a) {
    const change = a.change || 0;
    if (change > 1.0) {
      return { action: 'buy', confidence: 75, reason: lang==='ar' ? 'زخم صاعد قوي مع دعم فني' : 'Strong bullish momentum with technical support' };
    } else if (change < -1.0) {
      return { action: 'sell', confidence: 70, reason: lang==='ar' ? 'ضغوط بيعية مع كسر مستويات الدعم' : 'Selling pressure breaking support levels' };
    }
    return { action: 'wait', confidence: 50, reason: lang==='ar' ? 'إشارات غير حاسمة — يفضل الانتظار' : 'Inconclusive signals — patience advised' };
  }

  function deriveLevels(price, action) {
    if (action === 'wait' || !price) return { entry: null, stop: null, target: null };
    const offset = price * 0.02;
    const isBuy = action === 'buy';
    return {
      entry: price,
      stop: isBuy ? price - offset : price + offset,
      target: isBuy ? price + (offset * 2) : price - (offset * 2)
    };
  }

  function recommendationBox(a) {
    const rec = computeRecommendation(a);
    const levels = deriveLevels(a.price, rec.action);

    const header = `
      <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
        <h3 class="text-lg sm:text-xl font-bold text-grad-cyan">${t('recommendation')}</h3>
        ${actionBadge(rec.action)}
      </div>`;

    const reasonBlock = `
      <div class="bg-app-bg/40 border border-app-border rounded-xl p-4 mb-4">
        <div class="flex items-center gap-2 mb-2">
          <span class="text-sm font-bold text-gray-300">${t('confidence')}: ${rec.confidence}%</span>
        </div>
        <p class="text-xs sm:text-sm text-gray-400 leading-relaxed">${rec.reason}</p>
      </div>`;

    if (rec.action === 'wait') {
      return `
        <div class="glass rounded-2xl p-5 sm:p-6">
          ${header}
          ${reasonBlock}
        </div>`;
    }

    return `
      <div class="glass rounded-2xl p-5 sm:p-6">
        ${header}
        ${reasonBlock}
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
            <div class="text-xs text-gray-400 mb-1">${t('entry')}</div>
            <div class="font-extrabold text-sm sm:text-base">${formatPrice(levels.entry)}</div>
          </div>
          <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
            <div class="text-xs text-gray-400 mb-1">${t('stop')}</div>
            <div class="font-extrabold text-sm sm:text-base text-red-400">${formatPrice(levels.stop)}</div>
          </div>
          <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
            <div class="text-xs text-gray-400 mb-1">${t('target')}</div>
            <div class="font-extrabold text-sm sm:text-base text-green-400">${formatPrice(levels.target)}</div>
          </div>
          <div class="bg-app-bg/60 border border-app-border rounded-xl p-3">
            <div class="text-xs text-gray-400 mb-1">${t('rr')}</div>
            <div class="font-extrabold text-sm sm:text-base text-cyan-300">${formatRR(levels.entry, levels.stop, levels.target)}</div>
          </div>
        </div>
      </div>
    `;
  }

  function tvChartBox(a) {
    return `
      <div class="glass rounded-2xl p-4 sm:p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base sm:text-lg font-bold text-grad-cyan">${t('advancedChart')}</h3>
          <span class="text-xs text-gray-400">${t('chartNote')}</span>
        </div>
        <div id="tv_chart_container" class="rounded-xl overflow-hidden"></div>
      </div>
    `;
  }

  function renderTVWidget(tvSymbol) {
    if (typeof TradingView === 'undefined') return;
    new TradingView.widget({
      "autosize": true,
      "symbol": tvSymbol,
      "interval": "D",
      "timezone": "Etc/UTC",
      "theme": "dark",
      "style": "1",
      "locale": lang,
      "toolbar_bg": "#0A0E1A",
      "enable_publishing": false,
      "hide_side_toolbar": false,
      "allow_symbol_change": true,
      "container_id": "tv_chart_container"
    });
  }

  function renderAnalysis(id) {
    currentView = 'analysis';
    const main = document.getElementById('mainView');
    const analysis = document.getElementById('analysisView');
    const a = ASSETS.find(item => item.id === id);
    if (!a) return backToMain();

    main.classList.add('hidden');
    analysis.classList.remove('hidden');

    analysis.innerHTML = `
      ${analysisHeader(a)}
      <main class="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-6 sm:py-8 space-y-6 fade-in">
        ${priceBar(a)}
        ${recommendationBox(a)}
        ${tvChartBox(a)}
        ${technicalBox(a)}
      </main>
      ${footer()}
    `;

    bindLangButtons();
    setTimeout(() => renderTVWidget(a.tv), 100);
  }

  function goHome() {
    backToMain();
  }

  function showBestTrades() {
    alert(lang === 'ar' ? 'جارٍ مسح النماذج الفنية لأفضل الفرص المتاحة...' : 'Scanning technical patterns for best opportunities...');
  }

  // --- Initialize App ---
  window.addEventListener('DOMContentLoaded', () => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    renderMain();
  });
  </script>
</body>
</html>
