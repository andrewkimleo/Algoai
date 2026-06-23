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
            "reason": f"ticker data download exception: {str(e)}"
        }

    # Determine valid and failed tickers
    valid_tickers = []
    failed_tickers = []
    
    # We import TICKER_ALIASES to match exactly
    from .portfolio_returns import TICKER_ALIASES
    
    # Check each ticker from the weights keys
    for ticker in tickers:
        t_norm = ticker.upper().strip()
        if t_norm in TICKER_ALIASES:
            t_norm = TICKER_ALIASES[t_norm]
        if not t_norm.endswith(".NS") and not t_norm.endswith(".BO") and not t_norm.startswith("^"):
            t_norm += ".NS"
        if t_norm in TICKER_ALIASES:
            t_norm = TICKER_ALIASES[t_norm]
            
        if prices_df is not None and t_norm in prices_df.columns:
            series = prices_df[t_norm].dropna()
            # MIN_POINTS is 30
            if len(series) >= 30:
                valid_tickers.append(t_norm)
                logger.info(f"[Market Download Details] Ticker: {t_norm} | Rows: {len(series)} | First Date: {series.index[0].date()} | Last Date: {series.index[-1].date()}")
                continue
        failed_tickers.append(t_norm)
        logger.warning(f"[Market Download Failed] Ticker: {t_norm} has missing/all-NaN/insufficient price data.")

    # Calculate threshold
    MIN_VALID_TICKERS = max(5, int(len(tickers) * 0.25))
    
    logger.info(f"[Analytics Orchestrator] Requested: {len(tickers)} | Valid: {len(valid_tickers)} | Failed: {len(failed_tickers)} | Required: {MIN_VALID_TICKERS}")
    
    if len(valid_tickers) < MIN_VALID_TICKERS:
        logger.error(f"[Market Download Failed] Insufficient valid tickers. Valid: {len(valid_tickers)} | Required: {MIN_VALID_TICKERS}")
        return {
            "status": "error",
            "stage": "market_download",
            "reason": "insufficient valid tickers",
            "valid_count": len(valid_tickers),
            "required_count": MIN_VALID_TICKERS
        }

    # STEP 4: CHECK COLUMN MATCHING AND WEIGHT RE-NORMALIZATION
    # Filter the original weights dictionary to only keep valid tickers
    filtered_weights = {}
    for ticker, wt in weights.items():
        t_upper = ticker.upper().strip()
        if t_upper in TICKER_ALIASES:
            t_upper = TICKER_ALIASES[t_upper]
        if not t_upper.endswith(".NS") and not t_upper.endswith(".BO") and not t_upper.startswith("^"):
            t_upper += ".NS"
        if t_upper in TICKER_ALIASES:
            t_upper = TICKER_ALIASES[t_upper]
            
        if t_upper in valid_tickers:
            filtered_weights[t_upper] = wt

    remaining_sum = sum(filtered_weights.values())
    if remaining_sum > 0:
        normalized_weights = {k: v / remaining_sum for k, v in filtered_weights.items()}
        logger.info(f"[Validation] Re-normalized weights (sum=1.0): {normalized_weights}")
    else:
        logger.error("[Validation Failed] Aggregate weight of valid tickers is zero.")
        return {
            "status": "error",
            "stage": "market_download",
            "reason": "aggregate weight of valid tickers is zero",
            "valid_count": len(valid_tickers),
            "required_count": MIN_VALID_TICKERS
        }

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
    
    # Calculate success rate
    success_rate = round(len(valid_tickers) / len(tickers), 2) if tickers else 0.0
    diagnostics = {
        "valid_tickers": valid_tickers,
        "failed_tickers": failed_tickers,
        "failed_count": len(failed_tickers),
        "success_rate": success_rate
    }
    logger.info(f"[Analytics Orchestrator] Completed: Requested={len(tickers)}, Valid={len(valid_tickers)}, Failed={len(failed_tickers)}, SuccessRate={success_rate}")
    
    return {
        "metadata": metadata,
        "metrics": metrics,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "benchmark_curve": benchmark_curve,
        "diagnostics": diagnostics
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
