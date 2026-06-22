"""
indicator_engine.py
-------------------
Calculates vectorized technical indicators, detects strategy-specific candidates
across a large universe of stocks, performs sector diversification filtering,
and incorporates market regime bias.
"""

import os
import logging
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, List, Tuple, Any

from tools import cache_manager
from tools.sebi_rules import TRADING_SECONDS_PER_DAY

logger = logging.getLogger(__name__)

# Sector map for standard NIFTY stocks
SECTOR_MAP = {
    "RELIANCE": "Energy",
    "INFY": "IT",
    "TCS": "IT",
    "WIPRO": "IT",
    "HCLTECH": "IT",
    "TECHM": "IT",
    "HDFCBANK": "Finance",
    "ICICIBANK": "Finance",
    "AXISBANK": "Finance",
    "SBIN": "Finance",
    "KOTAKBANK": "Finance",
    "BAJFINANCE": "Finance",
    "BAJAJFINSV": "Finance",
    "TATAMOTORS": "Automobile",
    "M&M": "Automobile",
    "MARUTI": "Automobile",
    "BHARTIARTL": "Telecom",
    "ITC": "FMCG",
    "HINDUNILVR": "FMCG",
    "NESTLEIND": "FMCG",
    "LT": "Infrastructure",
    "TATASTEEL": "Metal",
    "JSWSTEEL": "Metal",
    "SUNPHARMA": "Healthcare",
    "CIPLA": "Healthcare",
}

def get_sector(ticker: str) -> str:
    """Resolve sector name for a given ticker."""
    clean = ticker.upper().replace(".NS", "").replace(".BO", "").strip()
    return SECTOR_MAP.get(clean, "Other")

# ── Indicator Functions ───────────────────────────────────────────────────────

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = sma + (num_std * std)
    lower = sma - (num_std * std)
    return upper, sma, lower

def calculate_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    mean = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    return (series - mean) / (std + 1e-9)

def calculate_volatility(returns: pd.Series, window: int = 20) -> float:
    return float(returns.rolling(window=window).std().iloc[-1] * (252 ** 0.5))

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.06) -> float:
    if len(returns) < 10:
        return 0.0
    mean_ret = returns.mean() * 252
    std_ret = returns.std() * (252 ** 0.5)
    return float((mean_ret - risk_free_rate) / (std_ret + 1e-9))

def calculate_win_rate(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    wins = returns[returns > 0].count()
    return float((wins / len(returns)) * 100)

def calculate_max_drawdown(series: pd.Series) -> float:
    roll_max = series.cummax()
    drawdown = (series - roll_max) / roll_max
    return float(abs(drawdown.min()) * 100)

# ── Batch Downloader ──────────────────────────────────────────────────────────

def fetch_batch_data(tickers: List[str], period: str = "6mo") -> Dict[str, pd.DataFrame]:
    """Download prices in batch and cache them."""
    cache_key = f"batch_prices_{'_'.join(sorted(tickers)[:5])}_{len(tickers)}_{period}"
    cached = cache_manager.get(cache_key)
    if cached is not None:
        return cached

    logger.info(f"Downloading batch market data for {len(tickers)} tickers...")
    
    # Use live batch download with threads
    try:
        raw = yf.download(
            tickers=tickers,
            period=period,
            group_by="ticker",
            threads=True,
            progress=False
        )
    except Exception as e:
        logger.error(f"YFinance batch download failed: {e}")
        return {}

    processed = {}
    
    # Handle single ticker DataFrame format vs multi-ticker Panel
    if len(tickers) == 1:
        ticker = tickers[0]
        if not raw.empty:
            df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            processed[ticker] = df
    else:
        for ticker in tickers:
            try:
                if ticker in raw.columns.levels[0]:
                    df = raw[ticker][["Open", "High", "Low", "Close", "Volume"]].copy()
                    df.columns = ["open", "high", "low", "close", "volume"]
                    df = df.dropna()
                    if not df.empty:
                        processed[ticker] = df
            except Exception:
                # Fallback to single fetch if column missing
                try:
                    single = yf.Ticker(ticker).history(period=period)
                    if not single.empty:
                        df = single[["Open", "High", "Low", "Close", "Volume"]].copy()
                        df.columns = ["open", "high", "low", "close", "volume"]
                        processed[ticker] = df
                except Exception:
                    pass

    # Save to cache for 1 hour
    cache_manager.set(cache_key, processed, expiry_seconds=3600)
    return processed

# ── Strategy Rankings ─────────────────────────────────────────────────────────

def rank_momentum(price_data: Dict[str, pd.DataFrame], regime: str) -> List[Dict[str, Any]]:
    """Rank universe for Momentum: 20d & 60d return trend, volatility adjusted."""
    results = []
    
    # Regime coefficient
    regime_coeff = 1.2 if regime == "bull" else (0.8 if regime == "sideways" else 0.5)

    for ticker, df in price_data.items():
        try:
            close = df["close"]
            returns = close.pct_change().dropna()
            
            # Key indicators
            mom_20 = float((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) if len(close) >= 20 else 0.0
            mom_60 = float((close.iloc[-1] - close.iloc[-60]) / close.iloc[-60]) if len(close) >= 60 else 0.0
            
            vol = calculate_volatility(returns)
            sharpe = calculate_sharpe_ratio(returns)
            win_rate = calculate_win_rate(returns)
            drawdown = calculate_max_drawdown(close)
            
            ema_20 = calculate_rsi(close, 20).iloc[-1] # use RSI as momentum proxy
            rsi_14 = calculate_rsi(close, 14).iloc[-1]
            
            # Composite Momentum Score
            score = ((mom_20 * 0.6) + (mom_60 * 0.4)) * 100
            
            # Penalize volatility slightly
            score = score - (vol * 10)
            
            # Scale by regime
            final_score = round(score * regime_coeff, 2)
            
            results.append({
                "ticker": ticker,
                "score": final_score,
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(drawdown, 2),
                "win_rate": round(win_rate, 2),
                "sector": get_sector(ticker),
                "metrics": {
                    "RSI": round(rsi_14, 1),
                    "20d_Return": f"{mom_20*100:+.1f}%",
                    "60d_Return": f"{mom_60*100:+.1f}%",
                    "Volatility": f"{vol*100:.1f}%"
                }
            })
        except Exception:
            pass

    # Sort descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def rank_mean_reversion(price_data: Dict[str, pd.DataFrame], regime: str) -> List[Dict[str, Any]]:
    """Rank universe for Mean Reversion: Oversold indicators (Z-score, RSI, BB Lower Band)."""
    results = []

    # Regime coefficient
    regime_coeff = 1.2 if regime == "sideways" else (0.8 if regime == "bull" else 0.6)

    for ticker, df in price_data.items():
        try:
            close = df["close"]
            returns = close.pct_change().dropna()
            
            z_score = calculate_zscore(close).iloc[-1]
            rsi = calculate_rsi(close).iloc[-1]
            upper, middle, lower = calculate_bollinger_bands(close)
            
            vol = calculate_volatility(returns)
            sharpe = calculate_sharpe_ratio(returns)
            win_rate = calculate_win_rate(returns)
            drawdown = calculate_max_drawdown(close)
            
            # Distance from lower band as percentage
            current_price = close.iloc[-1]
            lower_val = lower.iloc[-1]
            bb_distance = ((current_price - lower_val) / current_price) * 100
            
            # Score formula: We want low Z-score and low RSI (oversold)
            # Higher score = more oversold (best opportunities)
            score = (-z_score * 30) + (50 - rsi)
            
            final_score = round(score * regime_coeff, 2)
            
            results.append({
                "ticker": ticker,
                "score": final_score,
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(drawdown, 2),
                "win_rate": round(win_rate, 2),
                "sector": get_sector(ticker),
                "metrics": {
                    "Z-Score": round(z_score, 2),
                    "RSI": round(rsi, 1),
                    "BB_Lower_Distance": f"{bb_distance:+.1f}%",
                    "Volatility": f"{vol*100:.1f}%"
                }
            })
        except Exception:
            pass

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def rank_sentiment(price_data: Dict[str, pd.DataFrame], regime: str) -> List[Dict[str, Any]]:
    """Rank universe for Sentiment: deterministic headline scanning scores."""
    from tools.news_scraper import fetch_news
    from agents.sentiment_agent import _score_headline
    
    results = []
    
    for ticker, df in price_data.items():
        try:
            close = df["close"]
            returns = close.pct_change().dropna()
            
            # Fetch news (cached by news_scraper)
            articles = fetch_news(ticker, max_results=6)
            if not articles:
                continue
                
            scored = []
            for a in articles:
                score, reason = _score_headline(a.title)
                scored.append(score)
                
            avg_sentiment = sum(scored) / len(scored)
            volume_score = min(len(articles) / 6.0, 1.0)
            composite_score = round((avg_sentiment * 0.7) + (volume_score * 0.3), 3)
            
            sharpe = calculate_sharpe_ratio(returns)
            drawdown = calculate_max_drawdown(close)
            win_rate = calculate_win_rate(returns)
            
            # Scale sentiment score to 0-100 scale for UI readability
            final_score = round((composite_score + 1.0) * 50, 2)
            
            results.append({
                "ticker": ticker,
                "score": final_score,
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(drawdown, 2),
                "win_rate": round(win_rate, 2),
                "sector": get_sector(ticker),
                "metrics": {
                    "Sentiment_Index": round(composite_score, 2),
                    "Article_Volume": len(articles),
                    "Positive_Ratio": f"{sum(1 for s in scored if s > 0) / len(scored) * 100:.0f}%"
                }
            })
        except Exception:
            pass
            
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# ── Sector Exposure Filter ────────────────────────────────────────────────────

def apply_sector_filter(ranked_candidates: List[Dict[str, Any]], limit: int = 8, max_per_sector: int = 2) -> List[Dict[str, Any]]:
    """Ensure sector diversification by keeping at most N candidates per sector."""
    filtered = []
    sector_counts = {}
    
    for cand in ranked_candidates:
        if len(filtered) >= limit:
            break
            
        sec = cand["sector"]
        count = sector_counts.get(sec, 0)
        
        if count < max_per_sector:
            filtered.append(cand)
            sector_counts[sec] = count + 1
            
    return filtered
