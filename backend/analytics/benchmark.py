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
    cache_path = cache_manager._get_cache_path(cache_key)
    
    import os
    from datetime import datetime
    
    cached = cache_manager.get(cache_key)
    if cached is not None:
        created_timestamp = "N/A"
        if os.path.exists(cache_path):
            try:
                mtime = os.path.getmtime(cache_path)
                created_timestamp = datetime.fromtimestamp(mtime).isoformat()
            except Exception:
                pass
        
        logger.info(
            f"[Cache Investigation] Benchmark cache hit details for {benchmark_symbol}: "
            f"cache_file={cache_path} "
            f"created_timestamp={created_timestamp} "
            f"row_count={len(cached)}"
        )
        
        # If cache contains fewer than 252 observations
        if len(cached.dropna()) < 252:
            logger.warning(f"[Cache Investigation] Cached benchmark returns for {benchmark_symbol} has only {len(cached.dropna())} rows (fewer than 252 required). Deleting cache and forcing redownload.")
            try:
                if os.path.exists(cache_path):
                    os.remove(cache_path)
                    logger.info(f"[Cache Investigation] Deleted cache file: {cache_path}")
            except Exception as del_err:
                logger.error(f"[Cache Investigation] Failed to delete cache file: {del_err}")
            cached = None
            
    if cached is not None:
        if getattr(cached.index, "tz", None) is not None:
            cached.index = cached.index.tz_localize(None)
        if hasattr(cached.index, "normalize"):
            cached.index = cached.index.normalize()
        logger.info(f"[Analytics] Benchmark cache hit for: {benchmark_symbol}")
        
        # Log instrumentation
        logger.info(
            f"[{benchmark_symbol}] "
            f"cache_hit=True "
            f"period={period} "
            f"cache_file_path={cache_path} "
            f"rows={len(cached)} "
            f"start={cached.index.min()} "
            f"end={cached.index.max()} "
            f"non_nan={cached.dropna().shape[0]}"
        )
        print(f"benchmark.shape: {cached.shape}")
        return cached

    logger.info(f"[Analytics] Benchmark cache miss. Downloading: {benchmark_symbol}")
    try:
        logger.info(f"Downloading ticker: {benchmark_symbol}")
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
        
        # Log instrumentation
        logger.info(
            f"[{benchmark_symbol}] "
            f"cache_hit=False "
            f"period={period} "
            f"cache_file_path={cache_path} "
            f"rows={len(returns)} "
            f"start={returns.index.min()} "
            f"end={returns.index.max()} "
            f"non_nan={returns.dropna().shape[0]}"
        )
        print(f"benchmark.shape: {returns.shape}")
        return returns
    except Exception as e:
        logger.error(f"[Analytics] Error fetching benchmark returns: {e}")
        raise e
