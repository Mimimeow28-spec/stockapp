from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from zoneinfo import ZoneInfo
import os
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import (StockBarsRequest, StockLatestTradeRequest,
                                   StockSnapshotRequest, CryptoBarsRequest, CryptoSnapshotRequest)
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
app = Flask(__name__)
CORS(app, origins=[
    "https://stockapp-3vku.onrender.com",
    "https://projectlvx.lovable.app",
    r"https://.*\.lovable\.app",
    r"https://.*\.lovableproject\.com",
    "http://localhost:5173",
    "http://localhost:3000",
])
_alpaca = StockHistoricalDataClient(
    os.environ.get("ALPACA_API_KEY"),
    os.environ.get("ALPACA_API_SECRET")
)
_alpaca_crypto = CryptoHistoricalDataClient(
    os.environ.get("ALPACA_API_KEY"),
    os.environ.get("ALPACA_API_SECRET")
)

CRYPTO_SYMBOLS = {"BTC","ETH","SOL","DOGE","XRP","ADA","AVAX","LINK","DOT","LTC","BCH","MATIC","UNI"}

DEFAULT_TICKERS = ["AAPL", "CVX", "XOM", "DINO"]

SECTORS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLE":  "Energy",
    "XLV":  "Health Care",
    "XLI":  "Industrials",
    "XLY":  "Cons. Discr.",
    "XLP":  "Cons. Staples",
    "XLB":  "Materials",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
    "XLC":  "Comm. Svcs.",
}

FOREX_PAIRS_MAP = [
    {"name": "EUR/USD", "ticker": "EURUSD=X", "lat": 50.0,  "lon":  7.0},
    {"name": "GBP/USD", "ticker": "GBPUSD=X", "lat": 54.0,  "lon": -3.5},
    {"name": "USD/JPY", "ticker": "USDJPY=X", "lat": 36.5,  "lon": 136.0},
    {"name": "USD/CAD", "ticker": "USDCAD=X", "lat": 56.0,  "lon": -96.0},
    {"name": "USD/CHF", "ticker": "USDCHF=X", "lat": 46.8,  "lon":  8.2},
    {"name": "USD/INR", "ticker": "USDINR=X", "lat": 22.0,  "lon":  80.0},
    {"name": "USD/HKD", "ticker": "USDHKD=X", "lat": 21.0,  "lon": 114.2},
    {"name": "USD/CNY", "ticker": "USDCNY=X", "lat": 37.0,  "lon": 107.0},
    {"name": "AUD/USD", "ticker": "AUDUSD=X", "lat": -25.0, "lon": 133.0},
]

WORLD_INDICES = [
    {"name": "S&P 500",   "ticker": "^GSPC",     "lat": 40.71, "lon": -74.00, "label": "New York"},
    {"name": "Nasdaq",    "ticker": "^IXIC",     "lat": 40.78, "lon": -73.96, "label": "New York"},
    {"name": "Dow Jones", "ticker": "^DJI",      "lat": 40.65, "lon": -74.05, "label": "New York"},
    {"name": "TSX",       "ticker": "^GSPTSE",   "lat": 43.65, "lon": -79.38, "label": "Toronto"},
    {"name": "Brazil",    "ticker": "^BVSP",     "lat": -23.55,"lon": -46.63, "label": "São Paulo"},
    {"name": "FTSE 100",  "ticker": "^FTSE",     "lat": 51.51, "lon": -0.12,  "label": "London"},
    {"name": "DAX",       "ticker": "^GDAXI",    "lat": 50.11, "lon":  8.68,  "label": "Frankfurt"},
    {"name": "CAC 40",    "ticker": "^FCHI",     "lat": 48.86, "lon":  2.35,  "label": "Paris"},
    {"name": "IBEX 35",   "ticker": "^IBEX",     "lat": 40.42, "lon": -3.70,  "label": "Madrid"},
    {"name": "Nikkei",    "ticker": "^N225",     "lat": 35.69, "lon": 139.69, "label": "Tokyo"},
    {"name": "KOSPI",     "ticker": "^KS11",     "lat": 37.57, "lon": 126.98, "label": "Seoul"},
    {"name": "Shanghai",  "ticker": "000001.SS", "lat": 31.23, "lon": 121.47, "label": "Shanghai"},
    {"name": "Hang Seng", "ticker": "^HSI",      "lat": 22.32, "lon": 114.17, "label": "Hong Kong"},
    {"name": "ASX 200",   "ticker": "^AXJO",     "lat": -33.87,"lon": 151.21, "label": "Sydney"},
    {"name": "Nifty 50",  "ticker": "^NSEI",     "lat": 19.07, "lon":  72.87, "label": "Mumbai"},
    {"name": "TASI",      "ticker": "^TASI.SR",  "lat": 24.69, "lon":  46.72, "label": "Riyadh"},
]

# ── Cache (thread-safe) ──
_cache = {}
_cache_lock = threading.Lock()

# Different TTLs per key type
_TTL = {
    "fear_greed": 3600,   # updates once a day, cache 1h
    "weather":    1800,   # cache 30 min
    "spy":         300,
    "sectors":     300,
    "world":       300,
    "forex":       300,
    "news":        600,
    "levels":       30,   # VWAP changes constantly during session
}
_DEFAULT_TTL = 300


def cached(key, fn):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        ttl = (_TTL["news"]   if key.startswith("news_") else
               _TTL["levels"] if key.startswith("levels_") else
               _TTL.get(key, _DEFAULT_TTL))
        if entry and now - entry["ts"] < ttl:
            return entry["data"]
    data = fn()
    with _cache_lock:
        _cache[key] = {"data": data, "ts": now}
    return data


def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


def calculate_macd(prices):
    ema12 = prices.ewm(span=12, adjust=False).mean()
    ema26 = prices.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1]


def get_signal(rsi, macd, signal_line):
    score = 0
    if rsi < 35:   score += 2
    elif rsi < 45: score += 1
    elif rsi > 65: score -= 2
    elif rsi > 55: score -= 1
    score += 1 if macd > signal_line else -1
    if score >= 2:  return "BUY",  "#00e676"
    if score <= -2: return "SELL", "#ff1744"
    return "HOLD", "#ffab00"


def get_risk(rsi, change_pct):
    score = 0
    if rsi < 30 or rsi > 70:     score += 3
    elif rsi < 35 or rsi > 65:   score += 2
    elif rsi < 40 or rsi > 60:   score += 1
    if abs(change_pct) > 3:       score += 2
    elif abs(change_pct) > 1.5:  score += 1
    if score >= 4:  return "HIGH RISK", "#ff1744"
    if score >= 2:  return "MED RISK",  "#ffab00"
    return "LOW RISK", "#00e676"


def pct_change(curr, prev):
    if not prev:
        return 0.0
    return round((curr - prev) / prev * 100, 2)


def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = r.json()["data"][0]
        return int(data["value"]), data["value_classification"]
    except Exception:
        return None, "Unavailable"


def get_weather():
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=40.7282&longitude=-73.7949"
            "&current=temperature_2m,weather_code,wind_speed_10m"
            "&temperature_unit=fahrenheit"
        )
        c = requests.get(url, timeout=5).json()["current"]
        CODES = {
            0:("Clear","☀️"),1:("Mostly Clear","🌤️"),2:("Partly Cloudy","⛅"),
            3:("Overcast","☁️"),45:("Foggy","🌫️"),51:("Drizzle","🌦️"),
            61:("Rain","🌧️"),63:("Rain","🌧️"),65:("Heavy Rain","🌧️"),
            71:("Snow","🌨️"),80:("Showers","🌦️"),95:("Thunderstorm","⛈️"),
        }
        desc, icon = CODES.get(c["weather_code"], ("Unknown","🌡️"))
        return {"temp": round(c["temperature_2m"]), "desc": desc, "icon": icon,
                "wind": round(c["wind_speed_10m"] * 0.621371)}
    except Exception:
        return None


def fetch_ticker_summary(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo")
        try:
            info = t.info
        except Exception:
            info = {}
        closes = hist["Close"]
        price = round(float(closes.iloc[-1]), 2)
        prev  = round(float(closes.iloc[-2]), 2)
        change = round(price - prev, 2)
        change_pct = pct_change(price, prev)
        rsi = round(calculate_rsi(closes), 1)
        macd, sig = calculate_macd(closes)
        signal_label, signal_color = get_signal(rsi, macd, sig)
        risk_label, risk_color = get_risk(rsi, change_pct)
        chart_closes = closes.tail(30)
        chart_labels = [d.strftime("%b %d") for d in chart_closes.index]
        chart_prices = [round(float(p), 2) for p in chart_closes.values]
        news_items = []
        try:
            for n in t.news[:4]:
                c = n.get("content", {})
                title = c.get("title", "")
                url = c.get("canonicalUrl", {}).get("url", "#")
                pub = c.get("pubDate", "")
                if title:
                    news_items.append({"title": title, "url": url, "pub": pub[:10] if pub else ""})
        except Exception:
            pass
        return {
            "ticker": ticker, "price": price, "change": change, "change_pct": change_pct,
            "rsi": rsi, "signal": signal_label, "signal_color": signal_color,
            "risk": risk_label, "risk_color": risk_color,
            "chart_labels": chart_labels, "chart_prices": chart_prices,
            "news": news_items, "name": info.get("shortName", ticker),
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def fetch_spy_overview():
    try:
        t = yf.Ticker("SPY")
        hist = t.history(period="6mo")
        closes = hist["Close"]
        price = round(float(closes.iloc[-1]), 2)
        prev  = round(float(closes.iloc[-2]), 2)
        change = round(price - prev, 2)
        change_pct = pct_change(price, prev)
        chart_closes = closes.tail(60)
        chart_labels = [d.strftime("%b %d") for d in chart_closes.index]
        chart_prices = [round(float(p), 2) for p in chart_closes.values]
        week_52_high = round(float(closes.tail(252).max()), 2)
        week_52_low  = round(float(closes.tail(252).min()), 2)
        return {
            "price": price, "change": change, "change_pct": change_pct,
            "chart_labels": chart_labels, "chart_prices": chart_prices,
            "week_high": week_52_high, "week_low": week_52_low,
        }
    except Exception:
        return None


def _fetch_sector(item):
    ticker, name = item
    try:
        # Single fetch covers both 2d change and 5d sparkline
        hist = yf.Ticker(ticker).history(period="5d")
        if len(hist) < 2:
            return None
        closes = hist["Close"]
        curr = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        chg  = pct_change(curr, prev)
        spark = [round(float(p), 2) for p in closes.values]
        return {"ticker": ticker, "name": name, "change": chg, "spark": spark}
    except Exception:
        return None


def get_sector_data():
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_fetch_sector, SECTORS.items()))
    return [r for r in results if r]


def _fetch_world(m):
    try:
        hist = yf.Ticker(m["ticker"]).history(period="2d")
        if len(hist) < 2:
            return None
        curr = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2])
        chg  = pct_change(curr, prev)
        return {**m, "change": chg, "price": round(curr, 2)}
    except Exception:
        return None


def get_world_data():
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(_fetch_world, WORLD_INDICES))
    return [r for r in results if r]


def _fetch_forex(m):
    try:
        hist = yf.Ticker(m["ticker"]).history(period="2d")
        if len(hist) < 2:
            return None
        curr = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2])
        chg  = pct_change(curr, prev)
        return {**m, "change": chg, "price": round(curr, 4)}
    except Exception:
        return None


def get_forex_data():
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(_fetch_forex, FOREX_PAIRS_MAP))
    return [r for r in results if r]


def get_ticker_news(ticker):
    try:
        t = yf.Ticker(ticker)
        out = []
        for n in t.news[:30]:
            content = n.get("content", {})
            title = content.get("title", "")
            url = content.get("canonicalUrl", {}).get("url", "#")
            pub = content.get("pubDate", "")
            if title and pub:
                try:
                    pub_ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()
                    out.append({"title": title, "url": url, "pub": pub[:10], "ts": pub_ts})
                except Exception:
                    pass
        return out
    except Exception:
        return []


def get_stock_detail(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo")
        try:
            info = t.info
        except Exception:
            info = {}
        closes = hist["Close"]
        price = round(float(closes.iloc[-1]), 2)
        prev  = round(float(closes.iloc[-2]), 2)
        change = round(price - prev, 2)
        change_pct = pct_change(price, prev)
        rsi = round(calculate_rsi(closes), 1)
        macd, sig = calculate_macd(closes)
        signal_label, signal_color = get_signal(rsi, macd, sig)
        risk_label, risk_color = get_risk(rsi, change_pct)

        def fmt(n):
            if not n: return "N/A"
            if n >= 1e12: return f"${n/1e12:.2f}T"
            if n >= 1e9:  return f"${n/1e9:.2f}B"
            if n >= 1e6:  return f"${n/1e6:.2f}M"
            return str(n)

        news_items = []
        try:
            short_name = info.get("shortName", ticker)
            keywords = set()
            keywords.add(ticker.lower())
            for word in short_name.lower().split():
                if len(word) > 3 and word not in {"inc.", "corp", "corp.", "llc", "ltd", "the", "and"}:
                    keywords.add(word.rstrip(".,"))

            direct, related = [], []
            for n in t.news[:20]:
                c = n.get("content", {})
                title = c.get("title", "")
                if not title:
                    continue
                url = c.get("canonicalUrl", {}).get("url", "#")
                pub = c.get("pubDate", "")
                source = c.get("provider", {}).get("displayName", "")
                summary = c.get("summary", "")
                item = {
                    "title": title,
                    "url": url,
                    "pub": pub[:10] if pub else "",
                    "source": source,
                    "summary": summary[:160].rstrip() if summary else "",
                }
                if any(kw in title.lower() for kw in keywords):
                    direct.append(item)
                else:
                    related.append(item)
            news_items = (direct + related)[:8]
        except Exception:
            pass

        return {
            "ticker": ticker, "name": info.get("shortName", ticker),
            "price": price, "change": change, "change_pct": change_pct,
            "rsi": rsi, "signal": signal_label, "signal_color": signal_color,
            "risk": risk_label, "risk_color": risk_color,
            "market_cap": fmt(info.get("marketCap")),
            "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
            "week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "week_low":  info.get("fiftyTwoWeekLow",  "N/A"),
            "avg_volume": fmt(info.get("averageVolume")),
            "dividend": info.get("dividendYield", None),
            "news": news_items,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def get_candles(ticker, timeframe, prepost=False):
    _TF_MAP = {
        "1m":  (TimeFrame(1,  TimeFrameUnit.Minute), timedelta(days=7)),
        "2m":  (TimeFrame(2,  TimeFrameUnit.Minute), timedelta(days=7)),
        "5m":  (TimeFrame(5,  TimeFrameUnit.Minute), timedelta(days=55)),
        "15m": (TimeFrame(15, TimeFrameUnit.Minute), timedelta(days=55)),
        "1h":  (TimeFrame(1,  TimeFrameUnit.Hour),   timedelta(days=729)),
        "4h":  (TimeFrame(1,  TimeFrameUnit.Hour),   timedelta(days=729)),
        "1d":  (TimeFrame.Day,                        timedelta(days=3650)),
        "1w":  (TimeFrame.Week,                       timedelta(days=3650)),
        "1mo": (TimeFrame.Month,                      timedelta(days=3650)),
    }
    tf, delta = _TF_MAP.get(timeframe, (TimeFrame.Day, timedelta(days=3650)))
    is_crypto = ticker in CRYPTO_SYMBOLS
    crypto_sym = f"{ticker}/USD"
    if is_crypto:
        req = CryptoBarsRequest(
            symbol_or_symbols=crypto_sym,
            timeframe=tf,
            start=datetime.now() - delta,
            end=datetime.now(),
        )
        df = _alpaca_crypto.get_crypto_bars(req).df
        lookup_key = crypto_sym
    else:
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=tf,
            start=datetime.now() - delta,
            end=datetime.now(),
            feed="iex"
        )
        df = _alpaca.get_stock_bars(req).df
        lookup_key = ticker
    if df.empty:
        return [], []
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(lookup_key, level="symbol")
    if timeframe == "4h":
        df = df.resample("4h").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum"
        }).dropna()
    candles, volumes = [], []
    for idx, row in df.iterrows():
        ts = int(idx.timestamp())
        candles.append({"time": ts,
                        "open":  round(float(row["open"]),  2),
                        "high":  round(float(row["high"]),  2),
                        "low":   round(float(row["low"]),   2),
                        "close": round(float(row["close"]), 2),
                        "volume": int(row["volume"])})
        volumes.append({"time": ts, "value": int(row["volume"]),
                        "color": "rgba(0,230,118,0.4)" if row["close"] >= row["open"] else "rgba(255,23,68,0.4)"})

    if not prepost and timeframe in INTRADAY_TFS:
        et = ZoneInfo("America/New_York")
        def _in_session(ts):
            dt = datetime.fromtimestamp(ts, tz=et)
            if dt.weekday() >= 5:
                return False
            mins = dt.hour * 60 + dt.minute
            return 9 * 60 + 30 <= mins < 16 * 60
        candles = [c for c in candles if _in_session(c["time"])]
        volumes = [v for v in volumes if _in_session(v["time"])]

    return candles, volumes


INTRADAY_TFS = {"1m", "2m", "5m", "15m", "1h", "4h"}


def get_key_levels(ticker):
    """
    Compute key price levels for a ticker:
    - VWAP (session, regular hours only)
    - Previous day high / low
    - Premarket high / low (today)
    - Opening range high / low (first 30 min today)
    Returns dict; missing levels are None.
    """
    et = ZoneInfo("America/New_York")
    now_et = datetime.now(et)
    today_et = now_et.date()

    out = {
        "current": None,
        "vwap": None,
        "prev_day_high": None,
        "prev_day_low": None,
        "premarket_high": None,
        "premarket_low": None,
        "opening_range_high": None,
        "opening_range_low": None,
        "session": "closed",
    }

    # Determine current session
    weekday = now_et.weekday()
    if weekday >= 5:
        out["session"] = "weekend"
    else:
        mins = now_et.hour * 60 + now_et.minute
        if 4 * 60 <= mins < 9 * 60 + 30:
            out["session"] = "premarket"
        elif 9 * 60 + 30 <= mins < 16 * 60:
            out["session"] = "regular"
        elif 16 * 60 <= mins < 20 * 60:
            out["session"] = "afterhours"

    is_crypto = ticker in CRYPTO_SYMBOLS

    # --- Daily candles for prev day H/L ---
    try:
        if is_crypto:
            crypto_sym = f"{ticker}/USD"
            req = CryptoBarsRequest(
                symbol_or_symbols=crypto_sym,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=10),
                end=datetime.now(),
            )
            df_daily = _alpaca_crypto.get_crypto_bars(req).df
            if isinstance(df_daily.index, pd.MultiIndex):
                df_daily = df_daily.xs(crypto_sym, level="symbol")
        else:
            req = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=datetime.now() - timedelta(days=10),
                end=datetime.now(),
                feed="iex",
            )
            df_daily = _alpaca.get_stock_bars(req).df
            if isinstance(df_daily.index, pd.MultiIndex):
                df_daily = df_daily.xs(ticker, level="symbol")

        if not df_daily.empty:
            # Drop today's partial bar if present, take the most recent prior session
            df_daily_sorted = df_daily.sort_index()
            prior = df_daily_sorted[df_daily_sorted.index.date < today_et]
            if not prior.empty:
                last_full = prior.iloc[-1]
                out["prev_day_high"] = round(float(last_full["high"]), 2)
                out["prev_day_low"]  = round(float(last_full["low"]), 2)
            # Current: use the last available close
            out["current"] = round(float(df_daily_sorted["close"].iloc[-1]), 2)
    except Exception:
        pass

    # --- Intraday candles (1-min) for VWAP, premarket, opening range ---
    try:
        if is_crypto:
            crypto_sym = f"{ticker}/USD"
            req = CryptoBarsRequest(
                symbol_or_symbols=crypto_sym,
                timeframe=TimeFrame(1, TimeFrameUnit.Minute),
                start=datetime.now() - timedelta(days=2),
                end=datetime.now(),
            )
            df_min = _alpaca_crypto.get_crypto_bars(req).df
            if isinstance(df_min.index, pd.MultiIndex):
                df_min = df_min.xs(crypto_sym, level="symbol")
        else:
            req = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame(1, TimeFrameUnit.Minute),
                start=datetime.now() - timedelta(days=2),
                end=datetime.now(),
                feed="iex",
            )
            df_min = _alpaca.get_stock_bars(req).df
            if isinstance(df_min.index, pd.MultiIndex):
                df_min = df_min.xs(ticker, level="symbol")

        if not df_min.empty:
            # Convert to ET for filtering
            df_min = df_min.copy()
            df_min.index = df_min.index.tz_convert(et) if df_min.index.tz else df_min.index.tz_localize("UTC").tz_convert(et)
            today_bars = df_min[df_min.index.date == today_et]

            if not today_bars.empty:
                # Premarket: 4:00 AM – 9:30 AM ET
                pre = today_bars[(today_bars.index.hour >= 4) &
                                 ((today_bars.index.hour < 9) |
                                  ((today_bars.index.hour == 9) & (today_bars.index.minute < 30)))]
                if not pre.empty:
                    out["premarket_high"] = round(float(pre["high"].max()), 2)
                    out["premarket_low"]  = round(float(pre["low"].min()),  2)

                # Opening range: 9:30 AM – 10:00 AM ET
                opening = today_bars[(today_bars.index >= today_bars.index.normalize() + pd.Timedelta(hours=9, minutes=30)) &
                                     (today_bars.index <  today_bars.index.normalize() + pd.Timedelta(hours=10))]
                if not opening.empty:
                    out["opening_range_high"] = round(float(opening["high"].max()), 2)
                    out["opening_range_low"]  = round(float(opening["low"].min()),  2)

                # VWAP: regular session 9:30 AM – 4:00 PM ET
                regular = today_bars[(today_bars.index >= today_bars.index.normalize() + pd.Timedelta(hours=9, minutes=30)) &
                                     (today_bars.index <  today_bars.index.normalize() + pd.Timedelta(hours=16))]
                if not regular.empty:
                    typical = (regular["high"] + regular["low"] + regular["close"]) / 3.0
                    vol     = regular["volume"]
                    if vol.sum() > 0:
                        out["vwap"] = round(float((typical * vol).sum() / vol.sum()), 2)

                # Update current to the most recent intraday close (more live than daily)
                out["current"] = round(float(today_bars["close"].iloc[-1]), 2)
    except Exception:
        pass

    return out


# ── Ticker search list ──
TICKER_SEARCH_LIST = [
    ("SPY","SPDR S&P 500 ETF"),("QQQ","Invesco QQQ Nasdaq ETF"),("IWM","iShares Russell 2000"),
    ("DIA","SPDR Dow Jones ETF"),("VTI","Vanguard Total Market ETF"),
    ("AAPL","Apple Inc"),("MSFT","Microsoft Corp"),("NVDA","Nvidia Corp"),
    ("AMZN","Amazon.com Inc"),("GOOGL","Alphabet Inc"),("GOOG","Alphabet Class C"),
    ("META","Meta Platforms"),("TSLA","Tesla Inc"),("AVGO","Broadcom Inc"),
    ("ORCL","Oracle Corp"),("AMD","Advanced Micro Devices"),("INTC","Intel Corp"),
    ("QCOM","Qualcomm Inc"),("AMAT","Applied Materials"),("MU","Micron Technology"),
    ("JPM","JPMorgan Chase"),("BAC","Bank of America"),("WFC","Wells Fargo"),
    ("GS","Goldman Sachs"),("MS","Morgan Stanley"),("C","Citigroup"),
    ("XOM","ExxonMobil Corp"),("CVX","Chevron Corp"),("COP","ConocoPhillips"),
    ("DINO","HF Sinclair Corp"),("MPC","Marathon Petroleum"),("PSX","Phillips 66"),
    ("VLO","Valero Energy"),("OXY","Occidental Petroleum"),("SLB","SLB (Schlumberger)"),
    ("UNH","UnitedHealth Group"),("JNJ","Johnson & Johnson"),("PFE","Pfizer Inc"),
    ("ABBV","AbbVie Inc"),("LLY","Eli Lilly"),("MRK","Merck & Co"),
    ("WMT","Walmart Inc"),("COST","Costco Wholesale"),("TGT","Target Corp"),
    ("HD","Home Depot"),("LOW","Lowe's Companies"),("AMGN","Amgen Inc"),
    ("BA","Boeing Co"),("CAT","Caterpillar Inc"),("GE","GE Aerospace"),
    ("MMM","3M Company"),("RTX","RTX Corp"),("LMT","Lockheed Martin"),
    ("BRK-B","Berkshire Hathaway B"),("V","Visa Inc"),("MA","Mastercard"),
    ("PYPL","PayPal Holdings"),("SQ","Block Inc"),("COIN","Coinbase Global"),
    ("MSTR","MicroStrategy"),("HOOD","Robinhood Markets"),
    ("NFLX","Netflix Inc"),("DIS","Walt Disney Co"),("CMCSA","Comcast Corp"),
    ("T","AT&T Inc"),("VZ","Verizon Communications"),
    ("XLE","Energy Select Sector SPDR"),("XLK","Technology Select Sector SPDR"),
    ("XLF","Financial Select Sector SPDR"),("XLV","Health Care Sector SPDR"),
    ("SOXS","Direxion Semi Bear 3x"),("SOXL","Direxion Semi Bull 3x"),
    ("TQQQ","ProShares UltraPro QQQ"),("SQQQ","ProShares UltraPro Short QQQ"),
    ("SPXU","ProShares UltraPro Short S&P500"),("SPXL","Direxion S&P500 Bull 3x"),
    ("GLD","SPDR Gold Shares"),("SLV","iShares Silver Trust"),
    ("USO","United States Oil Fund"),("UNG","United States Natural Gas"),
    ("TLT","iShares 20+ Yr Treasury"),("HYG","iShares High Yield Corp Bond"),
    # Crypto
    ("BTC","Bitcoin / USD"),("ETH","Ethereum / USD"),("SOL","Solana / USD"),
    ("DOGE","Dogecoin / USD"),("XRP","Ripple / USD"),("ADA","Cardano / USD"),
    ("AVAX","Avalanche / USD"),("LINK","Chainlink / USD"),("LTC","Litecoin / USD"),
    ("MATIC","Polygon / USD"),("UNI","Uniswap / USD"),
    # Commodity ETFs
    ("GDX","VanEck Gold Miners ETF"),("GDXJ","VanEck Junior Gold Miners"),
    ("PDBC","Invesco Optimum Yield Commodities"),("DBO","Invesco DB Oil Fund"),
    ("WEAT","Teucrium Wheat Fund"),("CORN","Teucrium Corn Fund"),
    ("CPER","United States Copper Index"),
]

# ── Routes ──

@app.route("/")
def index():
    theme = request.args.get("theme", "")
    return render_template("index.html", preset_theme=theme)


@app.route("/set-theme")
def set_theme():
    theme = request.args.get("t", "dark")
    redirect_to = request.args.get("to", "/")
    if theme not in ("dark", "light"):
        theme = "dark"
    return f"""<!DOCTYPE html><html><head><script>
localStorage.setItem('mkt-theme','{theme}');
window.location='{redirect_to}';
</script></head><body>Switching theme...</body></html>"""


@app.route("/stock/<ticker>")
def stock_page(ticker):
    return render_template("stock.html", ticker=ticker.upper())


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip().upper()
    if not q:
        return jsonify({"results": []})
    matches = [
        {"symbol": sym, "name": name}
        for sym, name in TICKER_SEARCH_LIST
        if sym.startswith(q) or q in name.upper()
    ][:10]
    return jsonify({"results": matches})


@app.route("/api/data")
def api_data():
    tickers_param = request.args.get("tickers", ",".join(DEFAULT_TICKERS))
    tickers = [t.strip().upper() for t in tickers_param.split(",") if t.strip()]

    # Fear&Greed and weather are cached with long TTLs — won't hit external APIs every call
    fg_score, fg_rating = cached("fear_greed", lambda: get_fear_greed())
    weather = cached("weather", get_weather)

    with ThreadPoolExecutor(max_workers=6) as ex:
        stocks = list(ex.map(fetch_ticker_summary, tickers))

    spy = cached("spy", fetch_spy_overview)

    return jsonify({
        "fear_greed": {"score": fg_score, "rating": fg_rating},
        "stocks": stocks, "weather": weather, "spy": spy,
        "updated": datetime.now().strftime("%I:%M:%S %p"),
    })


@app.route("/api/sectors")
def api_sectors():
    return jsonify(cached("sectors", get_sector_data))


@app.route("/api/world")
def api_world():
    return jsonify(cached("world", get_world_data))


@app.route("/api/forex")
def api_forex():
    return jsonify(cached("forex", get_forex_data))


@app.route("/api/stock/<ticker>")
def api_stock_detail(ticker):
    d = get_stock_detail(ticker.upper())
    if "error" in d:
        return jsonify(d), 502
    return jsonify(d)


@app.route("/api/candles/<ticker>/<timeframe>")
def api_candles(ticker, timeframe):
    prepost = request.args.get("prepost", "false").lower() == "true"
    candles, volumes = get_candles(ticker.upper(), timeframe, prepost=prepost)
    return jsonify({"candles": candles, "volumes": volumes})


@app.route("/api/events/<ticker>/<timeframe>")
def api_events(ticker, timeframe):
    """
    Accepts candle data from the client to avoid a second Alpaca fetch.
    Falls back to fetching candles if not provided.
    """
    try:
        prepost = request.args.get("prepost", "false").lower() == "true"

        # Client can POST candles it already has to avoid double-fetch
        client_candles = None
        if request.method == "POST":
            body = request.get_json(silent=True)
            if body and isinstance(body.get("candles"), list):
                client_candles = body["candles"]

        if client_candles is not None:
            candles = client_candles
        else:
            candles, _ = get_candles(ticker.upper(), timeframe, prepost=prepost)

        thresholds = {"5m": 1.5, "15m": 1.5, "1h": 2.0, "4h": 2.5,
                      "1d": 3.0, "1w": 5.0, "1mo": 8.0}
        threshold = thresholds.get(timeframe, 3.0)

        sig_candles = []
        for c in candles:
            if c["open"] and c["open"] != 0:
                chg = (c["close"] - c["open"]) / c["open"] * 100
                if abs(chg) >= threshold:
                    sig_candles.append({**c, "change_pct": round(chg, 2)})

        raw_news = cached(f"news_{ticker.upper()}", lambda: get_ticker_news(ticker.upper()))

        TWO_DAYS = 2 * 86400
        events = []
        for c in sig_candles:
            matching = [
                {"title": n["title"], "url": n["url"], "pub": n["pub"]}
                for n in raw_news
                if abs(n["ts"] - c["time"]) <= TWO_DAYS
            ]
            events.append({
                "time": c["time"],
                "type": "spike" if c["change_pct"] > 0 else "drop",
                "change_pct": c["change_pct"],
                "price": c["close"],
                "news": matching,
            })

        return jsonify(events)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Support POST for events endpoint (client sends candles to avoid double-fetch)
app.add_url_rule(
    "/api/events/<ticker>/<timeframe>",
    endpoint="api_events_post",
    view_func=api_events,
    methods=["POST"]
)


@app.route("/api/quote/<ticker>")
def api_quote(ticker):
    d = fetch_ticker_summary(ticker.upper())
    if "error" in d:
        return jsonify(d), 502
    return jsonify(d)


@app.route("/api/levels/<ticker>")
def api_levels(ticker):
    t = ticker.upper()
    return jsonify(cached(f"levels_{t}", lambda: get_key_levels(t)))


@app.route("/api/live/<ticker>")
def api_live(ticker):
    try:
        t = ticker.upper()

        if t in CRYPTO_SYMBOLS:
            crypto_sym = f"{t}/USD"
            snap = _alpaca_crypto.get_crypto_snapshot(
                CryptoSnapshotRequest(symbol_or_symbols=crypto_sym)
            )[crypto_sym]
            price = round(float(snap.latest_trade.price), 2)
            prev = round(float(snap.previous_daily_bar.close), 2) if snap.previous_daily_bar else price
        else:
            snap = _alpaca.get_stock_snapshot(
                StockSnapshotRequest(symbol_or_symbols=t, feed="iex")
            )[t]
            price = round(float(snap.latest_trade.price), 2)
            prev = round(float(snap.previous_daily_bar.close), 2) if snap.previous_daily_bar else price

        change = round(price - prev, 2)
        change_pct = round((change / prev) * 100, 2) if prev else 0

        bar = None
        if snap.minute_bar:
            mb = snap.minute_bar
            bar = {
                "time":   int(mb.timestamp.timestamp()),
                "open":   round(float(mb.open),   2),
                "high":   round(float(mb.high),   2),
                "low":    round(float(mb.low),    2),
                "close":  round(float(mb.close),  2),
                "volume": int(mb.volume),
            }

        return jsonify({
            "price": price, "change": change, "change_pct": change_pct,
            "bar": bar,
            "timestamp": datetime.now().strftime("%I:%M:%S %p"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(debug=False, port=5000)
