import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def calculate_metrics(portfolio_returns: pd.Series, benchmark_returns: pd.Series, portfolio_drawdown: pd.Series, portfolio_equity: pd.Series) -> dict:
    """
    Computes annualized portfolio performance metrics relative to a benchmark index.
    Assumes standard 252 trading days per year.
    Defensively checks dates, timezone alignment, empty datasets, division by zero, NaNs, and infs.
    """
    # Defensive timezone localization stripping & index normalization to align DatetimeIndex joining
    for s in [portfolio_returns, benchmark_returns, portfolio_drawdown, portfolio_equity]:
        if s is not None and not s.empty:
            if not isinstance(s.index, pd.DatetimeIndex):
                s.index = pd.to_datetime(s.index)
            if getattr(s.index, "tz", None) is not None:
                s.index = s.index.tz_localize(None)
            if hasattr(s.index, "normalize"):
                s.index = s.index.normalize()

    # Log/Print original dataframe shapes after download/processing
    logger.info(
        f"[Metrics Calculation] Dataframe Shapes:\n"
        f"  - portfolio_returns: {portfolio_returns.shape if portfolio_returns is not None else 'None'}\n"
        f"  - benchmark_returns: {benchmark_returns.shape if benchmark_returns is not None else 'None'}\n"
        f"  - portfolio_drawdown: {portfolio_drawdown.shape if portfolio_drawdown is not None else 'None'}\n"
        f"  - portfolio_equity: {portfolio_equity.shape if portfolio_equity is not None else 'None'}"
    )
    print(f"portfolio_returns.shape: {portfolio_returns.shape if portfolio_returns is not None else 'None'}")
    print(f"benchmark_returns.shape: {benchmark_returns.shape if benchmark_returns is not None else 'None'}")

    if portfolio_returns is None or portfolio_returns.empty or benchmark_returns is None or benchmark_returns.empty or portfolio_equity is None or portfolio_equity.empty:
        logger.warning("[Metrics Calculation] One or more input return series is empty. Returning empty metrics.")
        return {}

    # Clean returns of any invalid/infinite/null values
    portfolio_returns = portfolio_returns.replace([np.inf, -np.inf], np.nan).dropna()
    benchmark_returns = benchmark_returns.replace([np.inf, -np.inf], np.nan).dropna()

    if portfolio_returns.empty or benchmark_returns.empty:
        logger.warning("[Metrics Calculation] Cleaned returns series are empty.")
        return {}

    # Join returns on common dates to handle correlation metrics (covariance, beta, alpha)
    aligned = pd.concat([portfolio_returns, benchmark_returns], axis=1, join="inner")
    aligned.columns = ["port", "bench"]
    
    logger.info(f"[Metrics Calculation] Aligned returns shape (merged): {aligned.shape}")
    print(f"merged.shape: {aligned.shape}")
    
    if aligned.empty or len(aligned) < 2:
        logger.warning("[Metrics Calculation] Aligned dataframe is empty or has insufficient overlap. Trading date indices do not overlap.")
        return {}

    port_ret = aligned["port"]
    bench_ret = aligned["bench"]
    n_days = len(port_ret)

    # Log/Print row counts and first/last 5 returns
    logger.info(f"[Metrics Calculation] Row Count: {n_days}")
    logger.info(f"[Metrics Calculation] First 5 Portfolio Returns:\n{port_ret.head(5)}")
    logger.info(f"[Metrics Calculation] Last 5 Portfolio Returns:\n{port_ret.tail(5)}")
    logger.info(f"[Metrics Calculation] First 5 Benchmark Returns:\n{bench_ret.head(5)}")
    logger.info(f"[Metrics Calculation] Last 5 Benchmark Returns:\n{bench_ret.tail(5)}")
    print(f"Number of rows in portfolio returns: {n_days}")
    print(f"First 5 returns:\n{port_ret.head(5)}")
    print(f"Last 5 returns:\n{port_ret.tail(5)}")

    # ──────────────────────────────────────────────────────────
    # Defensive Metrics Calculation
    # ──────────────────────────────────────────────────────────

    # 1. CAGR
    cagr = 0.0
    eq_clean = portfolio_equity.replace([np.inf, -np.inf], np.nan).dropna()
    if eq_clean.empty or len(eq_clean) < 2:
        logger.warning("[Metrics Calculation] portfolio_equity is empty or insufficient for CAGR.")
    else:
        total_days = (eq_clean.index[-1] - eq_clean.index[0]).days
        years = total_days / 365.25
        final_val = float(eq_clean.iloc[-1])
        init_val = float(eq_clean.iloc[0])
        
        if init_val <= 0:
            logger.warning("[Metrics Calculation] CAGR init_val is non-positive (division by zero).")
        elif final_val <= 0:
            logger.warning("[Metrics Calculation] CAGR final_val is non-positive.")
        elif years <= 0:
            logger.warning("[Metrics Calculation] CAGR years duration is zero or negative.")
        else:
            cagr = (final_val / init_val) ** (1.0 / years) - 1.0

    # 2. Volatility (Annualized)
    annualized_vol = 0.0
    daily_vol = port_ret.std()
    if np.isnan(daily_vol) or np.isinf(daily_vol):
        logger.warning("[Metrics Calculation] daily_vol std is NaN/Inf.")
    elif daily_vol <= 0:
        logger.warning("[Metrics Calculation] daily_vol std is zero or negative.")
    else:
        annualized_vol = daily_vol * np.sqrt(252)

    # 3. Sharpe Ratio (annualized, risk free rate = 0.0)
    sharpe_ratio = 0.0
    if np.isnan(daily_vol) or np.isinf(daily_vol) or daily_vol <= 0:
        logger.warning("[Metrics Calculation] standard deviation is zero, NaN, or Inf. Sharpe Ratio set to 0.0")
    else:
        sharpe_ratio = (port_ret.mean() / daily_vol) * np.sqrt(252)

    # 4. Sortino Ratio (annualized, risk free rate = 0.0)
    sortino_ratio = 0.0
    downside_returns = port_ret[port_ret < 0]
    if downside_returns.empty or len(downside_returns) < 2:
        logger.warning("[Metrics Calculation] Downside returns series has insufficient values.")
    else:
        downside_std = downside_returns.std()
        if np.isnan(downside_std) or np.isinf(downside_std) or downside_std <= 0:
            logger.warning("[Metrics Calculation] downside std is zero, NaN, or Inf. Sortino Ratio set to 0.0")
        else:
            sortino_ratio = (port_ret.mean() / downside_std) * np.sqrt(252)

    # 5. Max Drawdown
    max_dd = 0.0
    if portfolio_drawdown is not None and not portfolio_drawdown.empty:
        dd_clean = portfolio_drawdown.replace([np.inf, -np.inf], np.nan).dropna()
        if not dd_clean.empty:
            max_dd = float(dd_clean.min())

    # 6. Calmar Ratio
    calmar_ratio = 0.0
    if np.isnan(cagr) or np.isinf(cagr):
        logger.warning("[Metrics Calculation] CAGR is invalid for Calmar calculation.")
    elif np.isnan(max_dd) or np.isinf(max_dd):
        logger.warning("[Metrics Calculation] Max DD is invalid for Calmar calculation.")
    elif abs(max_dd) <= 1e-6:
        logger.warning("[Metrics Calculation] Max DD is zero/near-zero (division by zero). Calmar set to 0.0")
    else:
        calmar_ratio = cagr / abs(max_dd)

    # 7. Annualized Return
    annualized_return = port_ret.mean() * 252

    # 8. Benchmark CAGR for excess comparisons
    benchmark_cagr = 0.0
    bench_clean = bench_ret.replace([np.inf, -np.inf], np.nan).dropna()
    if bench_clean.empty:
        logger.warning("[Metrics Calculation] bench_clean is empty.")
    else:
        bench_cum = (1 + bench_clean).prod()
        if np.isnan(bench_cum) or np.isinf(bench_cum) or bench_cum <= 0:
            logger.warning("[Metrics Calculation] bench_cum is invalid or non-positive.")
        elif years <= 0:
            logger.warning("[Metrics Calculation] Years duration is invalid for Benchmark CAGR.")
        else:
            benchmark_cagr = (bench_cum) ** (1.0 / years) - 1.0

    # 9. Excess Return (CAGR difference)
    excess_return = 0.0
    if not np.isnan(cagr) and not np.isnan(benchmark_cagr):
        excess_return = cagr - benchmark_cagr

    # 10. Covariance for Beta & Alpha
    beta = 1.0
    alpha = 0.0
    try:
        cov = np.cov(port_ret, bench_ret)
        if cov.shape == (2, 2):
            bench_var = cov[1, 1]
            if np.isnan(bench_var) or np.isinf(bench_var) or bench_var <= 0:
                logger.warning("[Metrics Calculation] Benchmark variance is zero, NaN, or Inf. Beta set to 1.0")
            else:
                beta = cov[0, 1] / bench_var
                bench_mean = bench_ret.mean() * 252
                if not np.isnan(annualized_return) and not np.isnan(bench_mean):
                    alpha = annualized_return - beta * bench_mean
        else:
            logger.warning(f"[Metrics Calculation] Covariance matrix has unexpected shape: {cov.shape}")
    except Exception as e:
        logger.error(f"[Metrics Calculation] Beta/Covariance calculation error: {e}")

    # 11. Information Ratio (Tracking difference / tracking error)
    tracking_difference = port_ret - bench_ret
    tracking_error = tracking_difference.std()
    information_ratio = 0.0
    if np.isnan(tracking_error) or np.isinf(tracking_error) or tracking_error <= 0:
        logger.warning("[Metrics Calculation] Tracking error is zero, NaN, or Inf. Information Ratio set to 0.0")
    else:
        information_ratio = (tracking_difference.mean() / tracking_error) * np.sqrt(252)

    metrics = {
        "sharpe_ratio": float(sharpe_ratio),
        "sortino_ratio": float(sortino_ratio),
        "volatility": float(annualized_vol),
        "max_drawdown": float(max_dd),
        "calmar_ratio": float(calmar_ratio),
        "cagr": float(cagr),
        "annualized_return": float(annualized_return),
        "annualized_volatility": float(annualized_vol),
        "information_ratio": float(information_ratio),
        "beta": float(beta),
        "alpha": float(alpha),
        "excess_return": float(excess_return),
        "benchmark_cagr": float(benchmark_cagr)
    }

    # Clean all output values from NaN or Inf to guarantee JSON compatibility
    for k, v in metrics.items():
        if np.isnan(v) or np.isinf(v):
            logger.warning(f"[Metrics Calculation] Metric {k} was {v}. Replacing with 0.0")
            metrics[k] = 0.0

    # Log/Print intermediate values
    logger.info(
        f"[Metrics Calculation] Intermediate Values:\n"
        f"  - CAGR: {metrics['cagr']:.4f}\n"
        f"  - Volatility: {metrics['volatility']:.4f}\n"
        f"  - Sharpe: {metrics['sharpe_ratio']:.4f}\n"
        f"  - Sortino: {metrics['sortino_ratio']:.4f}\n"
        f"  - Alpha: {metrics['alpha']:.4f}\n"
        f"  - Beta: {metrics['beta']:.4f}\n"
        f"  - Information Ratio: {metrics['information_ratio']:.4f}"
    )
    print(f"CAGR: {metrics['cagr']:.4f}")
    print(f"Volatility: {metrics['volatility']:.4f}")
    print(f"Sharpe: {metrics['sharpe_ratio']:.4f}")
    print(f"Sortino: {metrics['sortino_ratio']:.4f}")
    print(f"Alpha: {metrics['alpha']:.4f}")
    print(f"Beta: {metrics['beta']:.4f}")
    print(f"Information Ratio: {metrics['information_ratio']:.4f}")

    return metrics
