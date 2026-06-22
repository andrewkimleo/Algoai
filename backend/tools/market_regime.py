"""
market_regime.py
----------------
Detects whether the overall Indian stock market is in a Bull, Sideways, or Bear regime
using NIFTY 50 trend indicators (SMA50 vs SMA200).
"""

import os
import logging
import yfinance as yf
from typing import Dict, Any

from tools import cache_manager

logger = logging.getLogger(__name__)

def detect_market_regime() -> Dict[str, Any]:
    """
    Analyzes the NIFTY 50 index (^NSEI) to identify the broad market regime.
    Uses cached metrics if available to prevent API calls.
    """
    cache_key = "market_regime_status"
    cached = cache_manager.get(cache_key)
    if cached is not None:
        return cached

    # Default fallback for offline demo / hackathon runs
    regime_info = {
        "regime": "bull",
        "confidence": 0.85,
        "nifty_price": 23500.0,
        "sma_50": 23200.0,
        "sma_200": 22400.0
    }

    mode = os.getenv("MARKET_DATA_MODE", "mock").lower()
    if mode == "mock":
        # Save to cache for 4 hours
        cache_manager.set(cache_key, regime_info, expiry_seconds=14400)
        return regime_info

    try:
        # Fetch NIFTY 50 index data
        logger.info("[MarketRegime] Fetching NIFTY 50 history...")
        nifty = yf.Ticker("^NSEI")
        df = nifty.history(period="1y")
        
        if df.empty or len(df) < 200:
            logger.warning("[MarketRegime] Insufficient NIFTY50 data, using default fallback.")
            cache_manager.set(cache_key, regime_info, expiry_seconds=14400)
            return regime_info

        close = df["Close"]
        current_price = float(close.iloc[-1])
        
        sma50 = float(close.rolling(window=50).mean().iloc[-1])
        sma200 = float(close.rolling(window=200).mean().iloc[-1])

        # Classification Rules
        if current_price > sma50 and sma50 > sma200:
            regime = "bull"
            # Confidence is based on distance above SMA50 (capped at 1.0)
            dist = (current_price - sma50) / sma50
            confidence = min(0.6 + dist * 5, 0.95)
        elif current_price < sma50 and sma50 < sma200:
            regime = "bear"
            dist = (sma50 - current_price) / sma50
            confidence = min(0.6 + dist * 5, 0.95)
        else:
            regime = "sideways"
            confidence = 0.75

        regime_info = {
            "regime": regime,
            "confidence": round(confidence, 2),
            "nifty_price": round(current_price, 2),
            "sma_50": round(sma50, 2),
            "sma_200": round(sma200, 2)
        }
        
        # Save to cache for 4 hours
        cache_manager.set(cache_key, regime_info, expiry_seconds=14400)
        logger.info(f"[MarketRegime] Detected regime: {regime} (confidence: {confidence:.2f})")
        return regime_info

    except Exception as e:
        logger.error(f"[MarketRegime] Error detecting market regime: {e}")
        # Default fallback
        return regime_info
