"""
market_data.py
--------------
Fetches OHLCV (Open, High, Low, Close, Volume) data for Indian equities.

Live mode  → uses yfinance (NSE tickers, e.g. "RELIANCE.NS")
Mock mode  → returns deterministic fake data so agents can run without
             internet / API keys during a demo.

Usage:
    from tools.market_data import get_ohlcv, get_latest_price, MarketDataResult

    df = get_ohlcv("RELIANCE.NS", period="6mo")   # returns a pandas DataFrame
    price = get_latest_price("RELIANCE.NS")        # returns float
"""

import os
import random
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

# Set MARKET_DATA_MODE=live in .env to hit real yfinance endpoints.
# Default is "mock" so the demo works offline / in hackathon Wi-Fi hell.
_MODE = os.getenv("MARKET_DATA_MODE", "mock").lower()

# Supported NSE tickers for the demo universe
DEMO_TICKERS = [
    "RELIANCE.NS",
    "INFY.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "WIPRO.NS",
    "AXISBANK.NS",
    "SBIN.NS",
]

# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class MarketDataResult:
    ticker: str
    df: pd.DataFrame          # columns: open, high, low, close, volume
    latest_price: float
    fetched_at: str
    source: str               # "live" or "mock"


# ── Public API ────────────────────────────────────────────────────────────────

def get_ohlcv(ticker: str, period: str = "6mo") -> MarketDataResult:
    """
    Return OHLCV DataFrame for the given ticker and period.

    period examples: "1mo", "3mo", "6mo", "1y"
    """
    ticker = _normalize_ticker(ticker)

    if _MODE == "live":
        return _fetch_live(ticker, period)
    else:
        return _fetch_mock(ticker, period)


def get_latest_price(ticker: str) -> float:
    """Convenience: just the last closing price."""
    result = get_ohlcv(ticker, period="1mo")
    return result.latest_price


def get_returns(ticker: str, period: str = "6mo") -> pd.Series:
    """Daily percentage returns as a Series."""
    result = get_ohlcv(ticker, period)
    return result.df["close"].pct_change().dropna()


def get_multi_close(tickers: list[str], period: str = "6mo") -> pd.DataFrame:
    """
    Fetch close prices for multiple tickers.
    Returns a DataFrame with tickers as columns.
    """
    frames = {}
    for t in tickers:
        result = get_ohlcv(t, period)
        frames[t] = result.df["close"]
    return pd.DataFrame(frames)


# ── Internal: live fetch ──────────────────────────────────────────────────────

def _fetch_live(ticker: str, period: str) -> MarketDataResult:
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("Install yfinance: pip install yfinance")

    raw = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError(f"No data returned for {ticker}. Check the ticker symbol.")

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index.name = "date"

    return MarketDataResult(
        ticker=ticker,
        df=df,
        latest_price=float(df["close"].iloc[-1]),
        fetched_at=datetime.now(timezone.utc).isoformat(),
        source="live",
    )


# ── Internal: mock fetch ──────────────────────────────────────────────────────

# Seed prices so each ticker always starts at a realistic-ish value
_SEED_PRICES = {
    "RELIANCE.NS": 2850.0,
    "INFY.NS":     1540.0,
    "TCS.NS":      3900.0,
    "HDFCBANK.NS": 1620.0,
    "ICICIBANK.NS": 1100.0,
    "WIPRO.NS":     480.0,
    "AXISBANK.NS":  1050.0,
    "SBIN.NS":       780.0,
}

_PERIOD_DAYS = {
    "1mo": 22,
    "3mo": 66,
    "6mo": 132,
    "1y":  252,
}


def _fetch_mock(ticker: str, period: str) -> MarketDataResult:
    n_days = _PERIOD_DAYS.get(period, 132)
    seed_price = _SEED_PRICES.get(ticker, 1000.0)

    # Deterministic random walk so repeated calls return the same data
    rng = random.Random(hash(ticker) % (2**31))

    prices = [seed_price]
    for _ in range(n_days - 1):
        daily_return = rng.gauss(0.0003, 0.015)   # ~7% annual drift, 24% vol
        prices.append(round(prices[-1] * (1 + daily_return), 2))

    dates = [
        (datetime.today() - timedelta(days=n_days - i)).date()
        for i in range(n_days)
    ]

    df = pd.DataFrame(
        {
            "open":   [round(p * rng.uniform(0.995, 1.002), 2) for p in prices],
            "high":   [round(p * rng.uniform(1.001, 1.020), 2) for p in prices],
            "low":    [round(p * rng.uniform(0.980, 0.999), 2) for p in prices],
            "close":  prices,
            "volume": [int(rng.uniform(500_000, 5_000_000)) for _ in prices],
        },
        index=pd.DatetimeIndex(dates, name="date"),
    )

    return MarketDataResult(
        ticker=ticker,
        df=df,
        latest_price=prices[-1],
        fetched_at=datetime.now(timezone.utc).isoformat(),
        source="mock",
    )


# ── Ticker normalizer ─────────────────────────────────────────────────────────

def _normalize_ticker(ticker: str) -> str:
    """
    Accept bare names like 'RELIANCE' or 'reliance' and
    append .NS so yfinance / mock lookup works correctly.
    """
    ticker = ticker.upper().strip()
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        ticker += ".NS"
    return ticker


# ── Quick smoke test ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    for sym in ["RELIANCE", "INFY", "TCS"]:
        result = get_ohlcv(sym, period="3mo")
        print(f"{result.ticker} | source={result.source} | rows={len(result.df)} | latest=₹{result.latest_price}")
        print(result.df.tail(3))
        print()