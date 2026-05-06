# Market Terminal — Full Project Context
> Share this file at the start of any Claude conversation to get full project context instantly.
> Last updated: 2026-04-29

---

## Who I Am
**Manny (LVX)** — active day trader, 2+ years trading SPY/QQQ options, transitioning into oil stocks and individual equities. Vibe coder — I build with AI assistance. Running on a **MacBook Air M4 15" (16GB/256GB), macOS Sequoia**.

---

## What This App Is

A **stock market dashboard** called **Market Terminal** — a Flask web app I'm building to become a $15–20/month SaaS product for active retail traders.

- **Local path:** `/Users/void/Downloads/stockapp/`
- **Run it:** `python3 app.py` (port 5000)
- **Access:** `http://127.0.0.1:5000` (NOT `localhost:5000` — macOS AirPlay holds that port on IPv6)
- **Restart:** `lsof -i :5000 -t | xargs kill -9 && python3 app.py &`

---

## File Structure

```
stockapp/
├── app.py                    # Flask backend (678 lines)
├── .env                      # API keys (never commit)
├── templates/
│   ├── index.html            # Dashboard home (~1259 lines)
│   └── stock.html            # Stock detail/chart page (~1632 lines)
└── static/
    └── js/
        └── shared.js         # Shared JS module (164 lines)
```

---

## Tech Stack

| Layer | What's Used |
|---|---|
| Backend | Python 3.9.6 (system), Flask |
| Stock candles + live price | **Alpaca Markets** (free paper trading, IEX feed) |
| Stock history, sectors, world, forex, news | **yfinance** (ToS risk for commercial — replace before launch) |
| Fear & Greed Index | `api.alternative.me/fng/` (free, no key) |
| Weather | `api.open-meteo.com` (free, no key, Queens NY coords) |
| Candlestick charts | LightweightCharts v4.1.3 (CDN) |
| Dashboard mini charts | Chart.js 4.4.0 (CDN) |
| World map | D3 v7 + TopoJSON (CDN) |
| Font | Inter (Google Fonts) |
| Shared CSS | `static/css/theme.css` — single source of truth for glassmorphic design tokens, glass primitives, and nav components |
| Python packages | `flask`, `yfinance`, `alpaca-py`, `pandas`, `requests`, `python-dotenv` |

---

## Backend: app.py

### Environment / Startup
- Loads `.env` file for `ALPACA_API_KEY` and `ALPACA_API_SECRET`
- Creates two Alpaca clients: `_alpaca` (stocks, IEX feed) and `_alpaca_crypto`
- `CRYPTO_SYMBOLS` set — used to route to crypto client vs stock client

### Thread-Safe Cache
```python
_cache = {}
_cache_lock = threading.Lock()
_TTL = {"fear_greed": 3600, "weather": 1800, "spy": 300, "sectors": 300, "world": 300, "forex": 300}

def cached(key, fn):
    # Returns cached data if fresh, else calls fn() and caches result
```

### Key Data Functions

| Function | What it does | Data source |
|---|---|---|
| `fetch_ticker_summary(ticker)` | price, change, RSI, MACD, signal, risk, 30d chart, 4 news items | yfinance |
| `fetch_spy_overview()` | SPY price, change, 60d chart, 52w high/low | yfinance |
| `_fetch_sector(item)` | sector ETF change + 5d sparkline (single fetch) | yfinance |
| `_fetch_world(m)` | world index price + % change | yfinance |
| `_fetch_forex(m)` | forex pair price + % change | yfinance |
| `get_stock_detail(ticker)` | full stock info: market cap, PE, 52w range, 8 news items with summaries | yfinance |
| `get_candles(ticker, timeframe)` | OHLCV candles + volume bars; handles stocks and crypto; 4h resampled from 1h | Alpaca IEX |
| `get_fear_greed()` | score (0-100) + rating string | alternative.me API |
| `get_weather()` | temp °F, description, icon emoji, wind mph (Queens NY) | open-meteo API |
| `calculate_rsi(prices, 14)` | RSI via rolling avg gain/loss | — |
| `calculate_macd(prices)` | MACD line + signal line (12/26/9 EMA) | — |
| `get_signal(rsi, macd, signal)` | BUY/HOLD/SELL + color hex | — |
| `get_risk(rsi, change_pct)` | LOW/MED/HIGH RISK + color hex | — |

**Signal logic:** RSI<35 = +2, RSI<45 = +1, RSI>65 = -2, RSI>55 = -1; MACD>signal = +1 else -1; score≥2 = BUY, ≤-2 = SELL, else HOLD

**`get_candles` timeframe map:**
- `1m`, `2m` → 7 days history
- `5m`, `15m` → 55 days
- `1h`, `4h` → 729 days (4h resampled from 1h bars)
- `1d`, `1w`, `1mo` → 3650 days

### API Routes

| Route | Method | Description |
|---|---|---|
| `GET /` | GET | Renders `index.html` |
| `GET /stock/<ticker>` | GET | Renders `stock.html` with ticker in template context |
| `GET /api/search?q=<query>` | GET | Ticker autocomplete, searches `TICKER_SEARCH_LIST` (100+ symbols), returns `{results:[{symbol,name}]}` |
| `GET /api/data?tickers=AAPL,CVX,...` | GET | Main dashboard data: fear_greed, weather, spy, stocks array. Parallel-fetches all tickers. |
| `GET /api/sectors` | GET | Array of `{ticker, name, change, spark[]}` for 11 sector ETFs (cached 5m) |
| `GET /api/world` | GET | Array of `{name, ticker, lat, lon, label, change, price}` for 16 world indices (cached 5m) |
| `GET /api/forex` | GET | Array of `{name, ticker, lat, lon, change, price}` for 9 forex pairs (cached 5m) |
| `GET /api/stock/<ticker>` | GET | Full stock detail: market_cap, pe_ratio, week_high/low, avg_volume, dividend, 8 news items with summary |
| `GET /api/candles/<ticker>/<tf>?prepost=true` | GET | `{candles:[{time,open,high,low,close,volume}], volumes:[{time,value,color}]}` |
| `GET /api/events/<ticker>/<tf>` | GET | Significant candle events matched to nearby news. Falls back to Alpaca fetch. |
| `POST /api/events/<ticker>/<tf>` | POST | Same as GET but body `{candles:[...]}` skips Alpaca re-fetch (client sends candles it already has) |
| `GET /api/live/<ticker>` | GET | Alpaca snapshot: `{price, change, change_pct, bar, timestamp}`. Works for crypto too. |
| `GET /api/quote/<ticker>` | GET | Same as `fetch_ticker_summary` — full stock card data |

**`/api/data` response shape:**
```json
{
  "fear_greed": {"score": 45, "rating": "Fear"},
  "weather": {"temp": 72, "desc": "Partly Cloudy", "icon": "⛅", "wind": 8},
  "spy": {"price": 550.23, "change": 2.1, "change_pct": 0.38, "chart_labels": [...], "chart_prices": [...], "week_high": 589.1, "week_low": 480.2},
  "stocks": [{"ticker":"AAPL","price":189.5,"change":1.2,"change_pct":0.64,"rsi":52.1,"signal":"HOLD","signal_color":"#ffab00","risk":"LOW RISK","risk_color":"#00e676","chart_labels":[...],"chart_prices":[...],"news":[{"title":"...","url":"...","pub":"2026-04-29"}],"name":"Apple Inc"}],
  "updated": "6:34:22 AM"
}
```

### Sectors Tracked (11 ETFs)
XLK Tech, XLF Financials, XLE Energy, XLV Health Care, XLI Industrials, XLY Cons. Discr., XLP Cons. Staples, XLB Materials, XLRE Real Estate, XLU Utilities, XLC Comm. Svcs.

### World Indices (16)
S&P 500, Nasdaq, Dow Jones, TSX (Toronto), Brazil (BVSP), FTSE 100, DAX, CAC 40, IBEX 35, Nikkei, KOSPI, Shanghai, Hang Seng, ASX 200, Nifty 50, TASI (Riyadh)

### Forex Pairs (9)
EUR/USD, GBP/USD, USD/JPY, USD/CAD, USD/CHF, USD/INR, USD/HKD, USD/CNY, AUD/USD

---

## Frontend: index.html (Dashboard)

### Layout & Navigation
- **Glass nav bar** (`.nav-bar`) — sticky at top, glassmorphic frosted-glass pill: brand-left | segmented control center | right actions
- **Center segmented control** (`.seg` + `.seg-item`): `★ Favorites` | `📰 News` | `📓 Journal` — each switches the main view. Active tab gets `.active` with accent-blue accent.
- **Right actions:** glass search input (`.nav-search-input`) | refresh icon-btn | theme icon-btn (all `.nav-icon-btn`)
- **Market Pulse Bar** — slim glass card below nav: signal summary (BUY/SELL/HOLD tickers) · SPY mini price · last updated timestamp

### Views (CSS class `view-section`, `.active` shows it)

#### Favorites View (`#view-favorites`) — default
1. **Floating Info Panel (`.info-float`)** — near-transparent glass (`background: rgba(255,255,255,0.018)`, `backdrop-filter: blur(24px)`). NOT a solid card — designed to feel like it floats over the background:
   - **Weather row:** icon, temp °F, description, wind, "Queens NY" location
   - **F&G row:** score (colored number), rating, gradient meter bar with animated thumb, context sentence
2. **Global Markets map** — D3 Natural Earth projection, world TopoJSON, colored circular markers for each index/forex, collision separation (`separateOverlaps()` 40-iter force push), hover tooltip. Toggle Index/Forex mode.
3. **Sector Performance grid** — 11 sector cards with change%, bull/bear tag, 5d sparkline. **Clicking a sector opens the Sector Stock Modal.**
4. **Watchlist** with sub-tabs: ⭐ Favorites / All Stocks. Add ticker via search autocomplete.

#### News View (`#view-news`)
- Full-page list of all news from all watchlist stocks
- Each item: `[TICKER]` badge + `[BULLISH/BEARISH/NEUTRAL]` sentiment tag + date + headline link
- Sentiment determined client-side by keyword matching

#### Journal View (`#view-journal`)
- `<textarea>` with autosave to `localStorage` key `mkt-journal`
- Debounced save (600ms), "Saved" flash indicator, character count, Clear button

### Sector Stock Modal (`#sector-modal`)
- Bottom-sheet modal (slides up from bottom)
- Shows top 10 stocks for the clicked sector (hardcoded `SECTOR_STOCKS` map)
- Fetches `/api/data?tickers=...` for those stocks
- Renders list rows: ticker | company name | price | change% | 30d sparkline
- Clicking a row navigates to `/stock/TICKER`
- Chart instances tracked in `smodCharts{}`, destroyed on close

### Stock Cards (in Favorites/All Stocks view)
Each card shows: ticker, company name, BUY/HOLD/SELL badge, LOW/MED/HIGH RISK badge, price, change%, 30-day Chart.js sparkline, RSI with mini bar, 30d price range, news list with **BULLISH/BEARISH/NEUTRAL** sentiment tags on each headline. Fav star (⭐) persists to `mkt-favorites` localStorage. Card click → `/stock/TICKER`.

### Theme System (via shared.js + theme.css)
- Base theme driven by `data-theme="dark"|"light"` attribute on `<html>` (set by `applyPreset()`)
- `localStorage` key `mkt-theme`: stores `'dark'` or `'light'` (string, not JSON)
- `localStorage` key `mkt-theme-overrides`: JSON of individual CSS var overrides from custom color picker
- Early-apply head script reads both keys, sets `data-theme` and overrides before first paint (no FOUC)
- Custom color picker panel (slide-in from right, `#theme-panel`)
- `updateChartTheme()` called after theme change — redraws chart and world map

### Map Theme Awareness
`getMapColors()` reads `document.documentElement.dataset.theme` directly to detect dark vs light mode and adjusts map background, country fill, and stroke colors accordingly. `updateChartTheme()` is called by shared.js on theme change → redraws the entire map base + markers.

### Key JS State & Functions (index.html)

```js
// State
let activeView = 'favorites';   // 'favorites' | 'news' | 'journal'
let activeTab  = 'favorites';   // watchlist subtab
let allStocksData = [];         // last loaded stocks array
const miniCharts = {};          // Chart.js instances by canvas ID
let smodCharts = {};            // sector modal chart instances

// Data fetch cycle
loadStocks()    // → /api/data → renders weather, FG, SPY pulse, stock cards, greetsub, news view if active
loadSectors()   // → /api/sectors → renders sector grid
loadWorld()     // → /api/world → initD3WorldMap; also silently pre-fetches /api/forex

// Auto-refresh: setInterval(loadStocks, 60000)

// Key render functions
renderFG(fg)              // updates score, rating, meter thumb, context text
renderWeather(w)          // updates icon, temp, desc, wind
renderSpy(spy)            // updates #spy-pulse in pulse bar only (no hero card)
renderStockCards(stocks)  // filters by activeTab, builds card HTML, creates Chart.js instances
renderSectors(sectors)    // builds sector grid with sparklines, attaches onclick → openSectorModal
renderNewsView()          // builds news feed from allStocksData with sentiment tags
renderGreetingSub(stocks) // BUY/SELL/HOLD summary in pulse bar

// Sentiment
getNewsSentiment(title)   // returns 'bullish'|'bearish'|'neutral' via keyword arrays

// Sector modal
openSectorModal(ticker, name, change)
loadSectorStocks(etf, name)  // fetches /api/data for SECTOR_STOCKS[etf]
renderSectorStocks(stocks)   // builds modal rows + sparklines
closeSectorModal()           // destroys smodCharts, removes .open

// Map
initD3WorldMap(markets)   // async, fetches world-atlas once, caches in _worldGeoData, calls drawWorldBase()
drawWorldBase()           // draws map with current theme colors (reads getMapColors())
renderMapMarkers(data, mode)  // projects coords, separates overlaps, draws circles + labels + tooltip
separateOverlaps(nodes, r, padding)  // 40-iter O(n²) force push to prevent marker overlap
setMapMode(mode)          // 'index' or 'forex'
updateChartTheme()        // called by shared.js on theme change → redraws map

// Journal
initJournal()     // loads from localStorage, wires oninput autosave
autoSaveJournal() // debounced 600ms → localStorage
clearJournal()    // confirm dialog → clears

// View switching
switchView(view)  // toggles .active on view sections + nav tabs
switchTab(tab)    // toggles watchlist sub-tabs, destroys orphaned miniCharts
```

### localStorage Keys Used (index.html)
| Key | Contents |
|---|---|
| `mkt-watchlist` | `["AAPL","CVX","XOM","DINO"]` — watchlist tickers |
| `mkt-favorites` | `["AAPL","CVX","XOM","DINO"]` — favorited tickers |
| `mkt-theme` | `'dark'` or `'light'` — base theme name |
| `mkt-theme-overrides` | `{"--accent-blue":"#ff0000",...}` — custom color picker overrides (applied on top of base theme) |
| `mkt-journal` | Raw journal text string |

---

## Frontend: stock.html (Stock Detail Page)

### Features
- **Candlestick chart** via LightweightCharts v4.1.3 (full OHLCV)
- **Timeframes:** 1m, 2m, 5m, 15m, 1h, 4h, 1D, 1W, 1M
- **Extended hours toggle** (`?prepost=true` param to `/api/candles`)
- **Volume panel** below chart, drag-to-resize handle
- **Live price polling** via `/api/live/<ticker>`: 10s during market hours (9:30–16:00 UTC-5 weekdays), 60s after-hours
- **Technical overlays:** RSI (14), VWAP, Bollinger Bands (20, 2σ), SMA 50/200
- **Auto Trend Lines** — VWA-weighted trend detection with confidence 0–10, stored per symbol in localStorage
- **Price Events** — spike/drop markers on chart with news correlation (`/api/events` — POST sends existing candles to avoid double Alpaca fetch)
- **Draw mode** — manual trend lines / horizontal levels, stored per ticker in localStorage
- **Fullscreen mode**
- **Ticker search** autocomplete (same shared.js factory as index.html)
- **Theme panel** (same shared.js system)

### Key Endpoints Used by stock.html
- `GET /api/stock/<ticker>` — loads header info (market cap, PE, week range, etc.)
- `GET /api/candles/<ticker>/<tf>?prepost=<bool>` — initial candle load
- `POST /api/events/<ticker>/<tf>` — sends candles in body, gets events back
- `GET /api/live/<ticker>` — polled for live price + latest minute bar
- `GET /api/search?q=<q>` — autocomplete

---

## shared.js (164 lines)

Loaded by both `index.html` and `stock.html` via `<script src="/static/js/shared.js"></script>` (non-deferred, synchronous load so inline scripts can use its functions immediately).

**Contains:**
1. **Theme system** — `COLOR_VARS`, `getCSSVar`, `setCSSVar`, `applyPreset` (sets `data-theme`), `resetTheme`, `buildColorRows`, `pickColor` (saves overrides to `mkt-theme-overrides`), `openTheme`, `closeTheme`
2. **Matrix rain canvas animation** (skipped if no `#matrix-canvas` element — index.html doesn't have one, stock.html may)
3. **Ticker search factory** — `initTickerSearch(inputId, dropdownId, onSelect)` — debounced 180ms, fetches `/api/search`, renders dropdown, calls `onSelect(symbol, inputEl)` on click

**`updateChartTheme()`** — if defined in the page, shared.js calls it after applying a preset or picking a color. index.html defines it to redraw the world map.

---

## Design System (CSS Variables)

All tokens live in `static/css/theme.css`. Theme switching is done by setting `data-theme="light"|"dark"` on `<html>` (`:root[data-theme="light"]` in CSS). `shared.js` `applyPreset('light'|'dark')` does this and saves the name to `localStorage('mkt-theme')`. Custom color overrides are stored in `localStorage('mkt-theme-overrides')` as individual var overrides applied on top.

```css
:root {                         /* dark (default) */
  --text:               #f0f0f4;
  --text-2:             rgba(240,240,255,0.65);
  --text-muted:         rgba(240,240,255,0.40);
  --glass-fill:         rgba(255,255,255,0.012);
  --glass-fill-hover:   rgba(255,255,255,0.04);
  --glass-fill-active:  rgba(255,255,255,0.07);
  --glass-border:       rgba(255,255,255,0.07);
  --glass-border-hover: rgba(255,255,255,0.16);
  --glass-rim-top:      rgba(255,255,255,0.40);
  --glass-rim-bottom:   rgba(0,0,0,0.18);
  --glass-shadow:       0 14px 40px rgba(0,0,0,0.35);
  --glass-blur:         blur(40px) saturate(220%);
  --green:              #30d158;
  --red:                #ff453a;
  --yellow:             #ffd60a;
  --orange:             #ff9f0a;
  --accent-blue:        #4d7cff;
  --accent-purple:      #7a4cff;
  --accent-grad:        linear-gradient(135deg, #4d7cff, #7a4cff);
  --cta-bg:             linear-gradient(180deg, #1a1f3d 0%, #08092b 100%);
  /* compat aliases: --bg, --surface, --surface2, --border, --cyan, --text2, --muted */
}
:root[data-theme="light"] { /* light overrides — glass fill 45%, rim 85%, text inverts to navy */ }
```

**Background:** 5-layer radial + linear deep blue gradient (dark) / light periwinkle gradient (light). Diagonal light streaks via `body::before/after` pseudo-elements.

**Glass primitives** (in `theme.css`): `.glass-pill` (action button), `.glass-cta` (CTA), `.icon-card`, `.glass-toggle` (pill toggle), `.glass-pagi` (circular timeframe btn), `.glass-card` (large surface), `.glass-input` (text input).

**Nav components** (in `theme.css`): `.nav-bar`, `.nav-brand`, `.nav-dot`, `.seg`, `.seg-item`, `.nav-actions`, `.nav-icon-btn`, `.nav-search-input`, dropdown styling.

**Rule:** Never hardcode `rgba(255,255,255,X)` for surfaces — always use `var(--glass-fill)` etc. That's what makes theme switching work.

---

## Known Quirks & Gotchas

1. **Port 5000 + macOS AirPlay** — macOS AirPlay Receiver binds port 5000 on IPv6 (`::1`). Flask also binds 5000 but only on IPv4 `127.0.0.1`. `curl localhost:5000` hits AirPlay (403). Always use `http://127.0.0.1:5000`.

2. **yfinance ToS** — still used for: stock history/overview (`/api/data`, sectors, world, forex), stock detail page (`/api/stock`), events news matching. Alpaca only handles candles and live price. yfinance is not legal for commercial redistribution — must replace before launch.

3. **Alpaca IEX feed** — free, real-time, but IEX is ~2-3% of total market volume. Prices are accurate, volume is understated vs consolidated tape. Alpaca SIP feed ($99/mo) has full volume.

4. **Crypto routing** — `CRYPTO_SYMBOLS` set determines whether `get_candles` uses `_alpaca_crypto` (crypto client) vs `_alpaca` (stock client). Crypto symbols formatted as `{SYM}/USD`.

5. **4h candle resampling** — Alpaca doesn't have a native 4h timeframe. `get_candles` fetches 1h bars then resamples with pandas `resample("4h").agg(...)`.

6. **`/api/events` double-fetch optimization** — stock.html POSTs its already-loaded candles in the request body so the server doesn't re-fetch from Alpaca.

7. **Chart.js orphan leak** — `switchTab()` in index.html destroys all `miniCharts` instances before wiping DOM, preventing memory leak from orphaned Chart.js instances.

8. **Map TopoJSON fetch** — `_worldGeoData` is cached in-memory after first load. Theme changes call `drawWorldBase()` without re-fetching the atlas.

9. **Light mode map** — `getMapColors()` reads `--bg` CSS var. If first hex char is c/d/e/f = light palette; otherwise dark palette. Called on every `drawWorldBase()`.

---

## Business Vision

**Goal:** $15–20/month SaaS subscription for active retail day traders.  
**Break-even:** ~15 subscribers. **Target:** 100–500 subscribers.

### 12 Features Planned (priority order for revenue)
1. **Options Pin Detector** — flags price pinning at high OI strikes
2. **Live Options Flow** — unusual activity, big sweeps, smart money
3. **AI Co-Pilot** — real-time plain-English explanation of what's happening and why
4. **Position Tracker** — enter options positions, live P&L overlay on chart
5. **0DTE Options Calculator** — ITM probability, theta/minute, auto-close estimate
6. **Relative Strength Monitor** — QQQ vs SPY ratio, detects which is leading
7. **Liquidity Sweep Alerts** — stop hunt detection
8. **Key Levels Sidebar** — VWAP, premarket high/low, prev day high/low, major OI strikes
9. **Power Hour Dashboard** — historical final-hour behavior stats
10. **Options Expiration Heatmap** — OI clustering visual
11. **Smart Entry/Exit Alerts** — monitors setups, alerts on alignment
12. **Personal Trade Journal** ✓ **(already built in MVP — local localStorage)**

Features 1, 3, 4, 5 are highest revenue potential — traders pay for those alone.

### Build Roadmap
1. Replace yfinance → Alpaca for history (Alpaca SIP or keep IEX)
2. Deploy to cloud (Railway.app ~$5-15/mo, or DigitalOcean)
3. Add auth (Flask-Login, email + password)
4. Add Stripe payments (free tier + pro tier)
5. Build intelligence features
6. Upgrade data provider when revenue justifies

### Data Provider Tiers
| Phase | Provider | Cost | Features |
|---|---|---|---|
| Now | Alpaca IEX (free) + yfinance | $0 | Candles, live price, history |
| Phase 2 | Alpaca SIP | $99/mo | Full consolidated tape |
| Phase 3 | Massive.com stocks + options | ~$400/mo | Everything including options flow |

---

## How to Run

```bash
cd /Users/void/Downloads/stockapp
python3 app.py
# → http://127.0.0.1:5000

# Restart (kill old process first):
lsof -i :5000 -t | xargs kill -9 2>/dev/null; sleep 1; python3 app.py &

# Check logs:
tail -f /tmp/stockapp.log
```

**.env file (required):**
```
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
```

**Python packages:**
```bash
pip3 install flask yfinance alpaca-py pandas requests python-dotenv --user
```
(Installs to `~/Library/Python/3.9/lib/python/site-packages` on macOS system Python)

---

## What Claude (MIMI) Has Built / Changed

### MIMI 3.0 (prior session)
- Full app.py rewrite: thread-safe cache, per-key TTLs, single yfinance fetch in `_fetch_sector`, POST support on `/api/events`
- `shared.js` — extracted theme + matrix rain + ticker search code into a shared module
- index.html — macOS-style nav, floating weather+F&G panel, sector modal, news sentiment, journal autosave
- stock.html — adaptive live polling, trend click handler, POST candles to events endpoint
- Collision detection for world map markers (40-iter force separation)

### MIMI 4.0 — Glassmorphic redesign (2026-04-29)
- **7 bug fixes** in app.py: extended-hours filter, HTTP 200 on errors, yfinance `.info` crash, pct_change helper, news TTL, `res.ok` checks on frontend
- **`static/css/theme.css`** (new file) — complete design system: CSS tokens, gradient backgrounds, light streaks, glass primitives, nav components
- **Theme switching** rebuilt: `data-theme` attribute on `<html>` drives `:root[data-theme]` CSS, replacing per-var overrides. FOUC-free.
- **New glass nav** on both pages: `.nav-bar` with `.seg` segmented control (index: Favorites/News/Journal; stock: timeframes 1m–1W) + icon buttons
- **Glass kit applied**: stock cards, sector tiles, info float panel, stat cards, chart sections, theme panels — all use `var(--glass-fill)`, `var(--glass-border)`, `var(--glass-rim-top)` etc.
- **Light mode fixed**: `getChartBg/Text/Grid()` read `data-theme`; `getMapColors()` reads `data-theme`; sparklines use `getCSSVar('--green'|'--red')`; chart tooltips use glass vars
