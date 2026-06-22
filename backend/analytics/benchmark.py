"""
benchmark.py
------------
Downloads NIFTY Index prices (^NSEI) from yfinance (caching data)
and returns daily benchmark returns.
"""

import logging
import pandas as pd
import yfinance as yf
import tools.cache_manager as cache_manager

logger = logging.getLogger(__name__)

def fetch_benchmark_returns(benchmark_symbol: str = "^NSEI", period: str = "3y") -> pd.Series:
    """
    Downloads NIFTY index close prices and calculates daily percent returns.
    Utilizes cache_manager to prevent redundant downloads.
    """
    benchmark_symbol = benchmark_symbol.upper().strip()
    cache_key = f"yf_benchmark_{benchmark_symbol}_{period}"
    
    cached = cache_manager.get(cache_key)
    if cached is not None:
        if getattr(cached.index, "tz", None) is not None:
            cached.index = cached.index.tz_localize(None)
        if hasattr(cached.index, "normalize"):
            cached.index = cached.index.normalize()
        logger.info(f"[Analytics] Benchmark cache hit for: {benchmark_symbol}")
        logger.info(f"[Analytics] Benchmark returns shape from cache: {cached.shape}")
        print(f"benchmark.shape: {cached.shape}")
        return cached

    logger.info(f"[Analytics] Benchmark cache miss. Downloading: {benchmark_symbol}")
    try:
        data = yf.download(benchmark_symbol, period=period, auto_adjust=True, progress=False)
        if data.empty:
            raise ValueError(f"No price data returned from yfinance for benchmark {benchmark_symbol}")

        if "Close" in data:
            close_prices = data["Close"]
        elif "close" in data:
            close_prices = data["close"]
        else:
            close_prices = data

        if isinstance(close_prices, pd.DataFrame):
            close_prices = close_prices.iloc[:, 0]

        # Clean series
        close_prices = close_prices.ffill().bfill()
        if getattr(close_prices.index, "tz", None) is not None:
            close_prices.index = close_prices.index.tz_localize(None)
        if hasattr(close_prices.index, "normalize"):
            close_prices.index = close_prices.index.normalize()
        
        # Calculate daily percent returns
        returns = close_prices.pct_change().dropna()
        
        if getattr(returns.index, "tz", None) is not None:
            returns.index = returns.index.tz_localize(None)
        if hasattr(returns.index, "normalize"):
            returns.index = returns.index.normalize()
        
        # Save to cache (24 hours expiry)
        cache_manager.set(cache_key, returns, expiry_seconds=86400)
        logger.info(f"[Analytics] Benchmark returns shape: {returns.shape}")
        print(f"benchmark.shape: {returns.shape}")
        return returns
    except Exception as e:
        logger.error(f"[Analytics] Error fetching benchmark returns: {e}")
        raise e
