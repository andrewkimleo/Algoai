"""
cache_manager.py
----------------
Local file-based caching system for caching historical market data,
computed indicators, and expensive metrics, preventing redundant fetches and computations.
"""

import os
import time
import pickle
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")

# Ensure cache directory exists
os.makedirs(CACHE_DIR, exist_ok=True)

def _get_cache_path(key: str) -> str:
    """Generate a clean safe cache path for a given string key."""
    safe_key = "".join(c if c.isalnum() else "_" for c in key)
    return os.path.join(CACHE_DIR, f"{safe_key}.cache")

def get(key: str) -> Optional[Any]:
    """Retrieve an item from the cache if it exists and has not expired."""
    path = _get_cache_path(key)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        
        # Check expiry
        expiry = data.get("expiry")
        if expiry is not None and time.time() > expiry:
            logger.debug(f"[CacheManager] Cache expired for key: {key}")
            os.remove(path)
            return None
        
        logger.debug(f"[CacheManager] Hit for key: {key}")
        return data.get("value")
    except Exception as e:
        logger.warning(f"[CacheManager] Error reading cache file for {key}: {e}")
        return None

def set(key: str, value: Any, expiry_seconds: Optional[int] = None) -> None:
    """Write an item to the cache with an optional expiration time."""
    path = _get_cache_path(key)
    expiry = (time.time() + expiry_seconds) if expiry_seconds is not None else None
    
    data = {
        "value": value,
        "expiry": expiry
    }
    
    try:
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.debug(f"[CacheManager] Saved key: {key}")
    except Exception as e:
        logger.error(f"[CacheManager] Error writing cache file for {key}: {e}")

def clear() -> None:
    """Clear all cached files in the cache directory."""
    if not os.path.exists(CACHE_DIR):
        return
    for filename in os.listdir(CACHE_DIR):
        if filename.endswith(".cache"):
            try:
                os.remove(os.path.join(CACHE_DIR, filename))
            except Exception as e:
                logger.warning(f"[CacheManager] Error removing cache file {filename}: {e}")
    logger.info("[CacheManager] All caches cleared.")
