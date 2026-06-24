"""
portfolio_returns.py
--------------------
Handles fetching historical Close prices from yfinance (reusing cache_manager)
and calculating daily return series for the portfolio or specific agents.
"""

import logging
import pandas as pd
import yfinance as yf
import tools.cache_manager as cache_manager

logger = logging.getLogger(__name__)

MIN_POINTS = 30

def is_valid_series(series: pd.Series) -> bool:
    return (
        series is not None
        and not series.empty
        and len(series.dropna()) >= MIN_POINTS
    )

TICKER_ALIASES = {
    "LTI": "LTIM.NS",
    "LTI.NS": "LTIM.NS",
    "TATAMOTORS": "TATAMOTORS.NS",
    "BOB": "BOB.NS",
    "RECL": "RECL.NS",
    "GMRINFRA": "GMRINFRA.NS",
    "ZOMATO": "ZOMATO.NS"
}

def fetch_historical_prices(tickers: list[str], period: str = "3y") -> pd.DataFrame:
    """
    Fetch adjusted close prices for a list of tickers from yfinance.
    Utilizes local cache_manager to cache tickers individually to prevent redundant downloads.
    """
    if not tickers:
        return pd.DataFrame()

    # Normalize ticker symbols and apply aliases
    normalized_tickers = []
    for t in tickers:
        t_upper = t.upper().strip()
        if t_upper in TICKER_ALIASES:
            t_upper = TICKER_ALIASES[t_upper]
        if not t_upper.endswith(".NS") and not t_upper.endswith(".BO") and not t_upper.startswith("^"):
            t_upper += ".NS"
        if t_upper in TICKER_ALIASES:
            t_upper = TICKER_ALIASES[t_upper]
        normalized_tickers.append(t_upper)
        
    normalized_tickers = sorted(list(set(normalized_tickers)))
    
    ticker_series = {}
    tickers_to_download = []
    
    # Check if mock mode is active
    import os
    mode = os.getenv("MARKET_DATA_MODE", "mock").lower()
    
    if mode == "mock":
        logger.info(f"[Analytics] Mock mode active. Generating mock price data.")
        from tools.market_data import _fetch_mock
        for ticker in normalized_tickers:
            res = _fetch_mock(ticker, period)
            series = res.df["close"]
            if getattr(series.index, "tz", None) is not None:
                series.index = series.index.tz_localize(None)
            if hasattr(series.index, "normalize"):
                series.index = series.index.normalize()
            ticker_series[ticker] = series
            
        combined_df = pd.DataFrame(ticker_series)
        combined_df = combined_df.ffill().bfill()
        
        for ticker in ticker_series:
            print(f"[Analytics] {ticker}: valid_points={len(ticker_series[ticker].dropna())}")
        print(f"prices.shape: {combined_df.shape}")
        return combined_df
        
    # Check individual ticker cache
    for ticker in normalized_tickers:
        cache_key = f"yf_price_single_{ticker}_{period}"
        cache_path = cache_manager._get_cache_path(cache_key)
        try:
            cached_series = cache_manager.get(cache_key)
        except Exception as e:
            logger.warning(f"[Cache Recovery] Exception reading cache file for {ticker}: {e}")
            cached_series = None
            
        if cached_series is not None:
            # Get file creation/modification timestamp
            import os
            from datetime import datetime
            created_timestamp = "N/A"
            if os.path.exists(cache_path):
                try:
                    mtime = os.path.getmtime(cache_path)
                    created_timestamp = datetime.fromtimestamp(mtime).isoformat()
                except Exception:
                    pass
            logger.info(
                f"[Cache Investigation] Cache hit details for {ticker}: "
                f"cache_file={cache_path} "
                f"created_timestamp={created_timestamp} "
                f"row_count={len(cached_series)}"
            )
            
            # If the cached series is valid but contains fewer than 252 observations
            if len(cached_series.dropna()) < 252:
                logger.warning(f"[Cache Investigation] Cached data for {ticker} has only {len(cached_series.dropna())} non-NaN observations (fewer than 252 required). Deleting cache and forcing redownload.")
                try:
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                        logger.info(f"[Cache Investigation] Deleted cache file: {cache_path}")
                except Exception as del_err:
                    logger.error(f"[Cache Investigation] Failed to delete cache file: {del_err}")
                tickers_to_download.append(ticker)
            else:
                if getattr(cached_series.index, "tz", None) is not None:
                    cached_series.index = cached_series.index.tz_localize(None)
                if hasattr(cached_series.index, "normalize"):
                    cached_series.index = cached_series.index.normalize()
                logger.info(f"[Analytics] Cache hit for single ticker: {ticker}")
                
                # Log instrumentation after cache retrieval
                logger.info(
                    f"[{ticker}] "
                    f"cache_hit=True "
                    f"period={period} "
                    f"cache_file_path={cache_path} "
                    f"rows={len(cached_series)} "
                    f"start={cached_series.index.min()} "
                    f"end={cached_series.index.max()} "
                    f"non_nan={cached_series.dropna().shape[0]}"
                )
                ticker_series[ticker] = cached_series
        else:
            logger.warning(f"[Cache Recovery] Cache miss or invalid cache detected for {ticker}")
            tickers_to_download.append(ticker)
            
    if tickers_to_download:
        logger.info(f"[Analytics] Downloading batch data from yfinance for: {tickers_to_download}")
        for t in tickers_to_download:
            logger.info(f"Downloading ticker: {t}")
            
        failed_to_retry = []
        try:
            # Batch download using threads=True
            data = yf.download(tickers_to_download, period=period, auto_adjust=True, progress=False, threads=True)
            
            if data.empty:
                logger.warning(f"[Analytics] Batch download returned empty DataFrame. All batch tickers will be retried individually.")
                failed_to_retry = list(tickers_to_download)
            else:
                # Extract Close prices
                if "Close" in data:
                    close_df = data["Close"]
                elif "close" in data:
                    close_df = data["close"]
                else:
                    close_df = data
                
                if getattr(close_df.index, "tz", None) is not None:
                    close_df.index = close_df.index.tz_localize(None)
                if hasattr(close_df.index, "normalize"):
                    close_df.index = close_df.index.normalize()
                
                # Check structure and extract each ticker's series
                for t in tickers_to_download:
                    series = None
                    if isinstance(close_df, pd.Series):
                        if len(tickers_to_download) == 1 and tickers_to_download[0] == t:
                            series = close_df
                    elif isinstance(close_df, pd.DataFrame):
                        if t in close_df.columns:
                            series = close_df[t]
                        else:
                            matched_col = next((col for col in close_df.columns if col.upper().strip() == t.upper().strip()), None)
                            if matched_col:
                                series = close_df[matched_col]
                    
                    if series is not None:
                        series = series.ffill().bfill()
                        if is_valid_series(series):
                            ticker_series[t] = series
                            cache_manager.set(f"yf_price_single_{t}_{period}", series, expiry_seconds=86400)
                            
                            # Log instrumentation after download
                            logger.info(
                                f"[{t}] "
                                f"cache_hit=False "
                                f"period={period} "
                                f"cache_file_path={cache_manager._get_cache_path(f'yf_price_single_{t}_{period}')} "
                                f"rows={len(series)} "
                                f"start={series.index.min()} "
                                f"end={series.index.max()} "
                                f"non_nan={series.dropna().shape[0]}"
                            )
                            continue
                    
                    # If extraction failed or returned invalid series, mark for retry
                    failed_to_retry.append(t)
        except Exception as batch_err:
            logger.warning(f"[Analytics] Batch download failed with error: {batch_err}. Retrying all tickers individually.")
            failed_to_retry = list(tickers_to_download)
            
        # Retry failed tickers individually
        if failed_to_retry:
            logger.info(f"[Analytics] Retrying {len(failed_to_retry)} failed tickers individually: {failed_to_retry}")
            for t in failed_to_retry:
                try:
                    logger.info(f"Downloading ticker: {t}")
                    single_data = yf.download(t, period=period, auto_adjust=True, progress=False)
                    if single_data.empty:
                        logger.warning(f"[Analytics Retry Failed] Individual download for {t} returned empty data.")
                        continue
                    
                    if "Close" in single_data:
                        close_col = single_data["Close"]
                    elif "close" in single_data:
                        close_col = single_data["close"]
                    else:
                        close_col = single_data
                    
                    if isinstance(close_col, pd.DataFrame):
                        if t in close_col.columns:
                            close_col = close_col[t]
                        else:
                            close_col = close_col.iloc[:, 0]
                            
                    if getattr(close_col.index, "tz", None) is not None:
                        close_col.index = close_col.index.tz_localize(None)
                    if hasattr(close_col.index, "normalize"):
                        close_col.index = close_col.index.normalize()
                        
                    series = close_col.ffill().bfill()
                    if is_valid_series(series):
                        logger.info(f"[Analytics] Retry success for ticker: {t}")
                        ticker_series[t] = series
                        cache_manager.set(f"yf_price_single_{t}_{period}", series, expiry_seconds=86400)
                        
                        # Log instrumentation after retry download
                        logger.info(
                            f"[{t}] "
                            f"cache_hit=False "
                            f"period={period} "
                            f"cache_file_path={cache_manager._get_cache_path(f'yf_price_single_{t}_{period}')} "
                            f"rows={len(series)} "
                            f"start={series.index.min()} "
                            f"end={series.index.max()} "
                            f"non_nan={series.dropna().shape[0]}"
                        )
                    else:
                        logger.warning(f"[Analytics Retry Failed] Individual download for {t} is invalid or entirely NaN.")
                except Exception as retry_err:
                    logger.warning(f"[Analytics Retry Failed] Error downloading {t} individually: {retry_err}")

    # Build aligned DataFrame of all successfully retrieved tickers
    for t in list(ticker_series.keys()):
        s = ticker_series[t]
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
        if hasattr(s.index, "normalize"):
            s.index = s.index.normalize()
            
    combined_df = pd.DataFrame(ticker_series)
    if not combined_df.empty:
        combined_df = combined_df.ffill().bfill()
        if getattr(combined_df.index, "tz", None) is not None:
            combined_df.index = combined_df.index.tz_localize(None)
        if hasattr(combined_df.index, "normalize"):
            combined_df.index = combined_df.index.normalize()
            
    logger.info(f"[Analytics] Combined prices DataFrame shape: {combined_df.shape}")
    print(f"prices.shape: {combined_df.shape}")
    return combined_df

def compute_weighted_returns(prices_df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """
    Computes daily return series for a portfolio of weighted assets.
    Weights is a dict mapping ticker -> float (decimal between 0.0 and 1.0).
    """
    if prices_df.empty or not weights:
        return pd.Series(dtype='float64')

    # Normalize weight ticker keys to match prices_df columns
    normalized_weights = {}
    for ticker, wt in weights.items():
        t_upper = ticker.upper().strip()
        if not t_upper.endswith(".NS") and not t_upper.endswith(".BO") and not t_upper.startswith("^"):
            t_upper += ".NS"
        normalized_weights[t_upper] = wt

    # Compute daily percent returns for all columns in prices
    pct_changes = prices_df.pct_change()
    returns_df = pct_changes.dropna()
    logger.info(f"[Analytics] Returns DataFrame shape before dropna: {pct_changes.shape}")
    logger.info(f"[Analytics] Calculated returns DataFrame shape after dropna: {returns_df.shape}")
    
    # Calculate weighted daily returns
    portfolio_returns = pd.Series(0.0, index=returns_df.index)
    for ticker, weight in normalized_weights.items():
        if ticker in returns_df.columns:
            portfolio_returns += returns_df[ticker] * weight
        else:
            logger.warning(f"[Analytics] Ticker {ticker} not found in historical price columns {returns_df.columns}")
            
    return portfolio_returns
