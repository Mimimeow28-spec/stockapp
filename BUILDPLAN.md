# Stock App — Commercial Build Plan

## What's Already Built
Flask web app at `/home/lvx/stockapp/` running on port 5000.

**Current features:**
- Candlestick charts with LightweightCharts v4.1.3
- Multiple timeframes (5m, 15m, 1h, 4h, 1D)
- Extended hours toggle (pre/after market)
- Fullscreen chart mode
- Volume panel with drag handle to resize
- Volume-weighted trend lines with confidence scores (0-10)
- News feed
- Live price updates (currently via yfinance — needs replacing)
- Technical indicators (RSI, VWAP, Bollinger Bands)

**Stack:**
- Backend: Python / Flask
- Charts: LightweightCharts v4.1.3
- Data: yfinance (to be replaced)
- Deployment: systemd service on local machine

---

## The Vision
A trader-built dashboard for active retail day traders. Not just charts — a **trading co-pilot** that explains what's happening in real time and why. Built by a trader (Manny), for traders.

**Target user:** Active retail day traders watching SPY, QQQ, options, oil stocks.
**Price point:** $15-20/month
**Edge over TradingView:** Explains the WHY — pin risk, options flow, power hour stats, liquidity sweeps.

---

## 12 Features to Build

1. **Options Pin Detector** — Shows open interest at nearby strikes. Flags when price is likely being pinned at a 0DTE strike. Would show: *"Pin risk at $664 — 45k open interest."*

2. **Live Options Flow** — Unusual options activity, large sweeps, big calls/puts being bought. Shows what smart money is doing before price moves.

3. **Relative Strength Monitor** — QQQ vs SPY ratio in real time. Visual indicator showing which index is leading. Auto-detects divergence.

4. **Liquidity Sweep Alerts** — When price spikes through a key level and immediately reverses, flags it: *"Possible stop hunt at $664.38 — watch for continuation."*

5. **AI Co-Pilot** — Real-time plain English commentary explaining what's happening and why. Automated market analysis built into the dashboard.

6. **Key Levels Sidebar** — VWAP, premarket high/low, previous day high/low, major OI strikes — all in one glance with distance from current price.

7. **Power Hour Dashboard** — Historical stats on how QQQ/SPY behave in the last hour under current conditions. *"On ATH breakout days QQQ averages +0.6% in power hour."*

8. **Options Expiration Heatmap** — Visual bar showing where OI is clustered for today's expiration. Makes pins visually obvious at a glance.

9. **Position Tracker** — Enter your options positions directly in the app. See live P&L overlaid on the chart without switching to Webull.

10. **Personal Trade Journal** — Log every trade. Win rate, best setups, biggest mistakes, patterns over time.

11. **0DTE Options Calculator** — Enter strike, expiration, premium. Shows real-time: probability of finishing ITM, how much underlying needs to move and by when, theta decay per minute, estimated broker auto-close time.

12. **Smart Entry/Exit Alerts** — Set a trade idea, app monitors and alerts when conditions align: volume spike, RSI cross, price break, SPY/QQQ divergence.

---

## Data Provider Plan

### Phase 1 — Launch (Free)
**Alpaca Markets — Free Paper Trading Account**
- IEX feed: real-time prices from IEX exchange
- Accurate pricing for SPY, QQQ, NVDA, AAPL, DINO, CVX and all US stocks
- WebSocket streaming — candles build tick by tick
- No credit card, no cost
- Limitation: volume slightly understated (IEX = ~2-3% of total market volume), no options data

**Sign up:** https://alpaca.markets → create paper trading account → get API Key ID + Secret Key

### Phase 2 — Growth ($99-200/month)
**Alpaca SIP feed ($99/month)** — full consolidated tape, all exchanges
OR
**Massive.com (formerly Polygon.io) Stocks $199/month** — professional grade → https://massive.com

### Phase 3 — Full Features ($400+/month)
**Massive.com Stocks $199 + Options $199/month**
- Full real-time stocks + options data
- Open interest, options flow, Greeks
- Powers features 1, 2, 8 (pin detector, flow, heatmap)

### Annual discount
Massive.com offers 20% off annual plans — drops $199 to ~$159/month each.

---

## Business Model

| Subscribers | Revenue (@$15/mo) | Costs | Profit |
|---|---|---|---|
| 15 | $225 | $215 | $10 (break even) |
| 50 | $750 | $215 | $535 |
| 100 | $1,500 | $215 | $1,285 |
| 500 | $7,500 | $215 | $7,285 |

---

## Next Steps — What To Build First

### Step 1: Swap yfinance for Alpaca
- Install `alpaca-py` library
- Replace `get_candles()` function in `app.py` with Alpaca REST API calls
- Replace live price polling with Alpaca WebSocket stream
- Test with QQQ, SPY, NVDA, DINO, CVX

### Step 2: Add User Auth
- Flask-Login for user accounts
- Simple email + password signup
- Session management

### Step 3: Add Payments
- Stripe for subscription billing
- Free tier (delayed/limited) + Pro tier ($15-20/month)
- Webhook to activate/deactivate accounts

### Step 4: Deploy
- Move from local machine to cloud server
- Railway.app or DigitalOcean ($10-20/month)
- Custom domain ($10-15/year)
- SSL certificate (free via Let's Encrypt)

### Step 5: Build the Intelligence Layer
- Options pin detector
- AI co-pilot commentary
- Key levels sidebar
- This is the differentiator — build after the foundation is solid

---

## Alpaca Integration — Code Starting Point

### Install
```bash
pip install alpaca-py
```

### Historical Candles (replaces yfinance)
```python
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

client = StockHistoricalDataClient(API_KEY, API_SECRET)

request = StockBarsRequest(
    symbol_or_symbols="QQQ",
    timeframe=TimeFrame.Minute,
    start=datetime(2026, 4, 28, 9, 30),
    end=datetime(2026, 4, 28, 16, 0),
    feed="iex"
)

bars = client.get_stock_bars(request)
```

### Live WebSocket Stream (replaces polling)
```python
from alpaca.data.live import StockDataStream

stream = StockDataStream(API_KEY, API_SECRET, feed="iex")

async def handle_bar(bar):
    # fires on every new bar/trade
    print(f"{bar.symbol} — ${bar.close} vol:{bar.volume}")

stream.subscribe_bars(handle_bar, "QQQ", "SPY", "NVDA")
stream.run()
```

---

## Key Technical Notes
- Alpaca API keys: store in environment variables, never hardcode
- IEX feed = real-time prices, slightly low volume
- WebSockets give tick-by-tick updates — candles build live
- Current app uses `candleSeries.update()` for live price — same method works with Alpaca data
- Port 5000 conflict fix: `sudo fuser -k 5000/tcp && sudo systemctl restart stockapp`

---

## Data Licensing Note
- yfinance: prohibited for commercial use (Yahoo ToS)
- Alpaca IEX free: permissive, good for launch
- Massive.com: formal redistribution licensing needed at scale, but small apps operate on developer plans until significant revenue
- Always add ToS and disclaimer: "For informational purposes only, not financial advice"
