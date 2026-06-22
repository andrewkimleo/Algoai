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
    if not weights:
        raise ValueError("Portfolio weights dictionary is empty.")

    tickers = list(weights.keys())
    
    # 1. Fetch Tickers Adjusted Close Prices (utilizes cache_manager internally)
    prices_df = fetch_historical_prices(tickers, period=period)
    
    # 2. Fetch Benchmark index returns
    bench_returns = fetch_benchmark_returns(benchmark_symbol, period=period)
    
    # Normalize index helper
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

    # Apply index normalization immediately after retrieval
    if prices_df is not None and not prices_df.empty:
        prices_df.index = normalize_index(prices_df.index)
    if bench_returns is not None and not bench_returns.empty:
        bench_returns.index = normalize_index(bench_returns.index)

    # Log/Print shapes after download
    prices_shape = prices_df.shape if prices_df is not None else (0, 0)
    bench_shape = bench_returns.shape if bench_returns is not None else (0,)
    logger.info(f"[Analytics Orchestrator] prices.shape: {prices_shape}")
    logger.info(f"[Analytics Orchestrator] benchmark.shape: {bench_shape}")
    print(f"prices.shape: {prices_shape}")
    print(f"benchmark.shape: {bench_shape}")

    # Guard 1: Empty downloaded prices or benchmark returns
    try:
        import os
        diag_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diagnostics.log")
        with open(diag_path, "w") as f:
            f.write(f"--- Diagnostics Log {datetime.now().isoformat()} ---\n")
            f.write(f"Weights: {weights}\n")
            f.write(f"Tickers list: {tickers}\n")
            f.write(f"Prices empty: {prices_df.empty if prices_df is not None else 'None'}\n")
            if prices_df is not None and not prices_df.empty:
                f.write(f"Prices shape: {prices_df.shape}\n")
                f.write(f"Prices columns: {list(prices_df.columns)}\n")
                f.write(f"Prices index type: {type(prices_df.index)}\n")
                f.write(f"Prices index tz: {getattr(prices_df.index, 'tz', None)}\n")
                f.write(f"Prices head 3 index: {[str(d) for d in prices_df.index[:3]]}\n")
                f.write(f"Prices tail 3 index: {[str(d) for d in prices_df.index[-3:]]}\n")
            
            f.write(f"Benchmark empty: {bench_returns.empty if bench_returns is not None else 'None'}\n")
            if bench_returns is not None and not bench_returns.empty:
                f.write(f"Benchmark shape: {bench_returns.shape}\n")
                f.write(f"Benchmark index type: {type(bench_returns.index)}\n")
                f.write(f"Benchmark index tz: {getattr(bench_returns.index, 'tz', None)}\n")
                f.write(f"Benchmark head 3 index: {[str(d) for d in bench_returns.index[:3]]}\n")
                f.write(f"Benchmark tail 3 index: {[str(d) for d in bench_returns.index[-3:]]}\n")
    except Exception as diag_err:
        logger.error(f"Diagnostics logger failed: {diag_err}")

    if prices_df is None or prices_df.empty or bench_returns is None or bench_returns.empty:
        logger.warning("[Analytics Orchestrator] Insufficient data: prices or benchmark returns empty.")
        return {
            "status": "error",
            "message": "Insufficient historical data"
        }
    
    # 3. Calculate portfolio weighted return series
    port_returns = compute_weighted_returns(prices_df, weights)
    if port_returns is not None and not port_returns.empty:
        port_returns.index = normalize_index(port_returns.index)

    # Verify and log portfolio return series
    logger.info(f"[Analytics Orchestrator] portfolio return series empty: {port_returns.empty}, len: {len(port_returns)}")
    print(f"Portfolio returns count: {len(port_returns)}")
    if not port_returns.empty:
        logger.info(f"[Analytics Orchestrator] First 5 returns:\n{port_returns.head(5)}")
        logger.info(f"[Analytics Orchestrator] Last 5 returns:\n{port_returns.tail(5)}")
        print(f"First 5 returns:\n{port_returns.head(5)}")
        print(f"Last 5 returns:\n{port_returns.tail(5)}")
    else:
        logger.warning("[Analytics Orchestrator] portfolio returns are empty.")
        return {
            "status": "error",
            "message": "Insufficient historical data"
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
