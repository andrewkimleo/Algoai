"""
__init__.py
-----------
Orchestration layer exposing compute_portfolio_analytics function to FastAPI endpoint.
"""

import logging
from datetime import datetime, timezone
import pandas as pd

from .portfolio_returns import fetch_historical_prices, compute_weighted_returns
from .equity_curve import compute_equity_curve
from .drawdown import compute_drawdown_series
from .benchmark import fetch_benchmark_returns
from .metrics import calculate_metrics

logger = logging.getLogger(__name__)

def compute_strategy_analytics(weights: dict[str, float], period: str = "3y", benchmark_symbol: str = "^NSEI") -> dict:
    """
    Core engine that computes complete historical performance analytics: returns, compounding curves,
    drawdowns, benchmark metrics, and risk ratios for any weight dictionary.
    """
    # STEP 2: VALIDATE PORTFOLIO INPUTS (Check weights and asset list inside orchestrator)
    if not weights or len(weights) == 0:
        logger.error("[Validation Failed] Portfolio weights dictionary is empty.")
        return {
            "status": "error",
            "stage": "portfolio_input_validation",
            "reason": "Portfolio weights dictionary is empty."
        }

    tickers = list(weights.keys())
    logger.info(f"[Validation] Asset list: {tickers}")
    logger.info(f"[Validation] Weight vector: {weights}")
    
    for ticker, wt in weights.items():
        if wt <= 0:
            logger.error(f"[Validation Failed] Asset {ticker} has non-positive weight: {wt}")
            return {
                "status": "error",
                "stage": "portfolio_input_validation",
                "reason": f"Weight for asset {ticker} is zero or negative: {wt}"
            }

    # STEP 2 (Ticker validation): Validate ticker symbols are valid
    invalid_tickers = [t for t in tickers if not isinstance(t, str) or not t or t.upper().strip() in ["STRING", "N/A", "UNKNOWN"]]
    if invalid_tickers:
        logger.error(f"[Validation Failed] Ticker symbols are invalid: {invalid_tickers}")
        return {
            "status": "error",
            "stage": "portfolio_input_validation",
            "reason": f"Ticker symbols are invalid: {invalid_tickers}"
        }

    # STEP 3: VALIDATE MARKET DATA DOWNLOAD
    try:
        prices_df = fetch_historical_prices(tickers, period=period)
    except Exception as e:
        logger.error(f"[Market Download Failed] Error downloading historical data: {e}")
        return {
            "status": "error",
            "stage": "market_download",
            "reason": f"ticker data unavailable: {str(e)}"
        }

    if prices_df is None or prices_df.empty:
        logger.error("[Market Download Failed] Historical price dataframe is empty.")
        return {
            "status": "error",
            "stage": "market_download",
            "reason": "ticker data unavailable: returned empty prices dataframe"
        }

    # Log/trace downloaded prices info for every ticker
    logger.info(f"[Market Download] Historical price dataframe shape: {prices_df.shape}")
    logger.info(f"[Market Download] Historical price dataframe columns: {list(prices_df.columns)}")
    
    for ticker in tickers:
        t_norm = ticker.upper().strip()
        if not t_norm.endswith(".NS") and not t_norm.endswith(".BO") and not t_norm.startswith("^"):
            t_norm += ".NS"
            
        if t_norm in prices_df.columns:
            series = prices_df[t_norm].dropna()
            if not series.empty:
                logger.info(f"[Market Download Details] Ticker: {t_norm} | Rows: {len(series)} | First Date: {series.index[0].date()} | Last Date: {series.index[-1].date()}")
                print(f"Ticker: {t_norm} | rows: {len(series)}")
            else:
                logger.error(f"[Market Download Failed] Ticker: {t_norm} has all NaN data.")
                return {
                    "status": "error",
                    "stage": "market_download",
                    "reason": f"ticker data empty or all NaN for {t_norm}"
                }
        else:
            logger.error(f"[Market Download Failed] Ticker: {t_norm} column missing from prices dataframe.")
            return {
                "status": "error",
                "stage": "market_download",
                "reason": f"ticker data unavailable for {t_norm}"
            }

    # Check for all-NaN columns or NaN values
    all_nan_cols = [col for col in prices_df.columns if prices_df[col].isna().all()]
    if all_nan_cols:
        logger.error(f"[Market Download Failed] The following columns contain only NaN values: {all_nan_cols}")
        return {
            "status": "error",
            "stage": "market_download",
            "reason": f"ticker data unavailable: columns contain only NaNs: {all_nan_cols}"
        }

    # STEP 4: CHECK COLUMN MATCHING
    normalized_weights = {}
    for ticker, wt in weights.items():
        t_upper = ticker.upper().strip()
        if not t_upper.endswith(".NS") and not t_upper.endswith(".BO") and not t_upper.startswith("^"):
            t_upper += ".NS"
        normalized_weights[t_upper] = wt
        
    mismatched_keys = [k for k in normalized_weights.keys() if k not in prices_df.columns]
    if mismatched_keys:
        logger.error(f"[Validation Failed] DataFrame columns do not match allocation keys. Missing: {mismatched_keys}")
        return {
            "status": "error",
            "stage": "column_matching",
            "reason": f"allocation keys mismatch downloaded dataframe columns: missing {mismatched_keys}"
        }
    logger.info(f"[Validation] Weight vector used: {normalized_weights}")

    # STEP 3: Validate Benchmark download
    try:
        bench_returns = fetch_benchmark_returns(benchmark_symbol, period=period)
    except Exception as e:
        logger.error(f"[Benchmark Download Failed] Error fetching benchmark returns: {e}")
        return {
            "status": "error",
            "stage": "benchmark_download",
            "reason": f"benchmark data unavailable: {str(e)}"
        }
        
    if bench_returns is None or bench_returns.empty:
        logger.error("[Benchmark Download Failed] Benchmark returns series is empty.")
        return {
            "status": "error",
            "stage": "benchmark_download",
            "reason": "benchmark data unavailable: empty benchmark returns"
        }

    # Normalize indexes timezone & time components
    def normalize_index(idx: pd.Index) -> pd.Index:
        if idx is None or len(idx) == 0:
            return idx
        if not isinstance(idx, pd.DatetimeIndex):
            idx = pd.to_datetime(idx)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        if hasattr(idx, "normalize"):
            idx = idx.normalize()
        return idx

    prices_df.index = normalize_index(prices_df.index)
    bench_returns.index = normalize_index(bench_returns.index)

    # STEP 5: CHECK DATE ALIGNMENT & STEP 6: CHECK PORTFOLIO RETURNS
    pct_changes = prices_df.pct_change()
    returns_df = pct_changes.dropna()
    
    logger.info(f"[Date Alignment] Shape before dropna (prices_df): {prices_df.shape}")
    logger.info(f"[Date Alignment] Shape of pct_change: {pct_changes.shape}")
    logger.info(f"[Date Alignment] Shape after dropna (returns_df): {returns_df.shape}")
    
    if returns_df.empty:
        logger.error("[Date Alignment Failed] Daily returns DataFrame is empty after dropna.")
        return {
            "status": "error",
            "stage": "date_alignment",
            "reason": "returns dataframe empty after date alignment and dropna"
        }

    # Calculate portfolio returns
    port_returns = compute_weighted_returns(prices_df, weights)
    if port_returns is not None and not port_returns.empty:
        port_returns.index = normalize_index(port_returns.index)

    # STEP 6 (Portfolio returns inspection)
    logger.info(f"[Portfolio Returns] Shape: {port_returns.shape if port_returns is not None else 'None'}")
    if port_returns is None or port_returns.empty:
        logger.error("[Portfolio Returns Failed] Portfolio return series is empty.")
        return {
            "status": "error",
            "stage": "portfolio_returns",
            "reason": "portfolio returns series empty after weight calculation"
        }
        
    logger.info(f"[Portfolio Returns] Head:\n{port_returns.head(5)}")
    logger.info(f"[Portfolio Returns] Tail:\n{port_returns.tail(5)}")

    # STEP 7: LOOKBACK PERIOD VALIDATION
    # Verify every selected asset has at least 3 years of history
    for ticker in tickers:
        t_norm = ticker.upper().strip()
        if not t_norm.endswith(".NS") and not t_norm.endswith(".BO") and not t_norm.startswith("^"):
            t_norm += ".NS"
            
        series = prices_df[t_norm].dropna()
        first_date = series.index[0]
        last_date = series.index[-1]
        history_days = (last_date - first_date).days
        logger.info(f"[Lookback Validation] Ticker: {t_norm} | history span: {history_days} calendar days.")
        
        # Expect at least ~1000 calendar days for a 3-year lookback
        if history_days < 1000:
            logger.error(f"[Lookback Validation Failed] Ticker {t_norm} has only {history_days} calendar days of history (requires 3 years).")
            return {
                "status": "error",
                "stage": "lookback_validation",
                "reason": f"ticker {t_norm} has insufficient history: {history_days} days (requires at least 3 years)"
            }

    # Verify benchmark (^NSEI) has matching dates
    bench_first = bench_returns.index[0]
    bench_last = bench_returns.index[-1]
    bench_days = (bench_last - bench_first).days
    logger.info(f"[Lookback Validation] Benchmark | history span: {bench_days} calendar days.")
    if bench_days < 1000:
        logger.error(f"[Lookback Validation Failed] Benchmark index has only {bench_days} days of history.")
        return {
            "status": "error",
            "stage": "lookback_validation",
            "reason": f"benchmark index has insufficient history: {bench_days} days"
        }

    # 4. Generate compounded Equity Curves (100,000 Initial Capital)
    port_equity = compute_equity_curve(port_returns, 100000.0)
    if port_equity is not None and not port_equity.empty:
        port_equity.index = normalize_index(port_equity.index)
    
    # 5. Calculate daily Drawdown series
    port_drawdown = compute_drawdown_series(port_equity)
    if port_drawdown is not None and not port_drawdown.empty:
        port_drawdown.index = normalize_index(port_drawdown.index)
    
    # 6. Generate compounded Benchmark Equity Curve aligned to portfolio dates
    aligned_bench_returns = bench_returns.reindex(port_returns.index).ffill().bfill()
    if aligned_bench_returns is not None and not aligned_bench_returns.empty:
        aligned_bench_returns.index = normalize_index(aligned_bench_returns.index)
        
    bench_equity = compute_equity_curve(aligned_bench_returns, 100000.0)
    if bench_equity is not None and not bench_equity.empty:
        bench_equity.index = normalize_index(bench_equity.index)
    
    # 7. Compute Ratios & Metrics
    metrics = calculate_metrics(port_returns, aligned_bench_returns, port_drawdown, port_equity)
    
    # Guard 2: Insufficient data or calculation failure yielding empty metrics
    if not metrics or port_equity.empty or aligned_bench_returns.empty:
        logger.warning("[Analytics Orchestrator] Insufficient overlap or computation failure.")
        return {
            "status": "error",
            "message": "Insufficient historical data"
        }
    
    # Format timeseries curves for JSON serialization
    equity_curve = [{"date": str(d.date()), "value": float(v)} for d, v in port_equity.items()]
    drawdown_curve = [{"date": str(d.date()), "drawdown": float(v)} for d, v in port_drawdown.items()]
    benchmark_curve = []
    
    # Align curves chronologically
    for d in port_equity.index:
        date_str = str(d.date())
        benchmark_curve.append({
            "date": date_str,
            "portfolio": float(port_equity[d]),
            "benchmark": float(bench_equity[d]) if d in bench_equity.index else 100000.0
        })
        
    metadata = {
        "lookback_period": period,
        "benchmark_symbol": benchmark_symbol,
        "calculation_timestamp": datetime.now(timezone.utc).isoformat(),
        "asset_count": len(tickers)
    }
    
    return {
        "metadata": metadata,
        "metrics": metrics,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "benchmark_curve": benchmark_curve
    }

def compute_portfolio_analytics(weights: dict[str, float], period: str = "3y", benchmark_symbol: str = "^NSEI") -> dict:
    """
    Computes analytics at the aggregated portfolio level.
    """
    return compute_strategy_analytics(weights, period, benchmark_symbol)

def compute_momentum_agent_analytics(weights: dict[str, float], period: str = "3y", benchmark_symbol: str = "^NSEI") -> dict:
    """
    Computes analytics for the Momentum agent strategy.
    Designed for future agent-level backtesting.
    """
    return compute_strategy_analytics(weights, period, benchmark_symbol)

def compute_mean_reversion_agent_analytics(weights: dict[str, float], period: str = "3y", benchmark_symbol: str = "^NSEI") -> dict:
    """
    Computes analytics for the Mean Reversion agent strategy.
    Designed for future agent-level backtesting.
    """
    return compute_strategy_analytics(weights, period, benchmark_symbol)

def compute_sentiment_agent_analytics(weights: dict[str, float], period: str = "3y", benchmark_symbol: str = "^NSEI") -> dict:
    """
    Computes analytics for the Sentiment agent strategy.
    Designed for future agent-level backtesting.
    """
    return compute_strategy_analytics(weights, period, benchmark_symbol)
