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

def fetch_historical_prices(tickers: list[str], period: str = "3y") -> pd.DataFrame:
    """
    Fetch adjusted close prices for a list of tickers from yfinance.
    Utilizes local cache_manager to cache tickers individually to prevent redundant downloads.
    """
    if not tickers:
        return pd.DataFrame()

    # Normalize ticker symbols
    normalized_tickers = []
    for t in tickers:
        t_upper = t.upper().strip()
        if not t_upper.endswith(".NS") and not t_upper.endswith(".BO") and not t_upper.startswith("^"):
            t_upper += ".NS"
        normalized_tickers.append(t_upper)
        
    normalized_tickers = sorted(list(set(normalized_tickers)))
    
    ticker_series = {}
    tickers_to_download = []
    
    # Check individual ticker cache
    for ticker in normalized_tickers:
        cache_key = f"yf_price_single_{ticker}_{period}"
        cached_series = cache_manager.get(cache_key)
        if cached_series is not None and not cached_series.empty and not cached_series.isna().all():
            if getattr(cached_series.index, "tz", None) is not None:
                cached_series.index = cached_series.index.tz_localize(None)
            if hasattr(cached_series.index, "normalize"):
                cached_series.index = cached_series.index.normalize()
            logger.info(f"[Analytics] Cache hit for single ticker: {ticker}")
            ticker_series[ticker] = cached_series
        else:
            logger.info(f"[Analytics] Cache miss or invalid/NaN cache for single ticker: {ticker}")
            if cached_series is not None:
                try:
                    import os
                    cache_path = cache_manager._get_cache_path(cache_key)
                    if os.path.exists(cache_path):
                        os.remove(cache_path)
                        logger.info(f"[Analytics] Deleted corrupted NaN cache file for: {ticker}")
                except Exception as ex:
                    logger.warning(f"[Analytics] Failed to delete corrupted cache: {ex}")
            tickers_to_download.append(ticker)
            
    if tickers_to_download:
        logger.info(f"[Analytics] Downloading data from yfinance for: {tickers_to_download}")
        try:
            if len(tickers_to_download) == 1:
                t = tickers_to_download[0]
                data = yf.download(t, period=period, auto_adjust=True, progress=False)
                if data.empty:
                    raise ValueError(f"No price data returned from yfinance for: {t}")
                
                # Extract Close prices
                if "Close" in data:
                    close_col = data["Close"]
                elif "close" in data:
                    close_col = data["close"]
                else:
                    close_col = data
                
                if isinstance(close_col, pd.DataFrame):
                    # Multi-index or dataframe cleanup
                    if t in close_col.columns:
                        close_col = close_col[t]
                    else:
                        close_col = close_col.iloc[:, 0]
                
                if getattr(close_col.index, "tz", None) is not None:
                    close_col.index = close_col.index.tz_localize(None)
                if hasattr(close_col.index, "normalize"):
                    close_col.index = close_col.index.normalize()
                series = close_col.ffill().bfill()
                
                if series.isna().all():
                    raise ValueError(f"Downloaded yfinance data for {t} is entirely NaN.")
                
                ticker_series[t] = series
                cache_manager.set(f"yf_price_single_{t}_{period}", series, expiry_seconds=86400)
            else:
                data = yf.download(tickers_to_download, period=period, auto_adjust=True, progress=False)
                if data.empty:
                    raise ValueError(f"No price data returned from yfinance for: {tickers_to_download}")
                
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
                
                # Check structure
                if isinstance(close_df, pd.Series):
                    # Only one column returned in series form
                    t = tickers_to_download[0]
                    series = close_df.ffill().bfill()
                    if series.isna().all():
                        raise ValueError(f"Downloaded yfinance data for {t} is entirely NaN.")
                    ticker_series[t] = series
                    cache_manager.set(f"yf_price_single_{t}_{period}", series, expiry_seconds=86400)
                else:
                    for t in tickers_to_download:
                        if t in close_df.columns:
                            series = close_df[t].ffill().bfill()
                            if series.isna().all():
                                raise ValueError(f"Downloaded yfinance data for {t} is entirely NaN.")
                            ticker_series[t] = series
                            cache_manager.set(f"yf_price_single_{t}_{period}", series, expiry_seconds=86400)
                        else:
                            # Try to match case-insensitively or search
                            matched_col = next((col for col in close_df.columns if col.upper().strip() == t.upper().strip()), None)
                            if matched_col:
                                series = close_df[matched_col].ffill().bfill()
                                if series.isna().all():
                                    raise ValueError(f"Downloaded yfinance data for {matched_col} is entirely NaN.")
                                ticker_series[t] = series
                                cache_manager.set(f"yf_price_single_{t}_{period}", series, expiry_seconds=86400)
                            else:
                                logger.warning(f"[Analytics] Ticker {t} not found in yfinance download columns {close_df.columns}")
        except Exception as e:
            logger.error(f"[Analytics] Error downloading from yfinance: {e}")
            raise e

    # Build aligned DataFrame of all requested tickers
    for t in ticker_series:
        s = ticker_series[t]
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
        if hasattr(s.index, "normalize"):
            s.index = s.index.normalize()
            
    combined_df = pd.DataFrame(ticker_series)
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
