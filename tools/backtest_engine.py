"""
backtest_engine.py
------------------
Shared backtest utility for AlgoDesk.

Given a list of tickers + weights, simulates how that portfolio
would have performed over a historical period using daily close prices.

Returns key stats:
  - Total return %
  - Max drawdown %
  - Sharpe ratio (annualised, risk-free rate = 6.5% for India)
  - Win rate (% of days portfolio was positive)
  - Volatility (annualised std of daily returns)
  - Best day / Worst day

Used by:
  - stress_test_agent  → runs portfolio through crash/stress windows
  - portfolio_arbiter  → compares surviving strategies before allocating
  - Any strategy agent → can self-validate before posting a proposal

No external dependencies beyond pandas and numpy (already needed by market_data).
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from tools.market_data import get_multi_close


# ── India risk-free rate (RBI repo rate approx) ───────────────────────────────
RISK_FREE_RATE_ANNUAL = 0.065   # 6.5%
RISK_FREE_RATE_DAILY  = RISK_FREE_RATE_ANNUAL / 252


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    """
    All performance stats for one backtest run.
    Passed between agents as part of a BandMessage payload.
    """
    tickers:          list[str]
    weights:          list[float]          # must sum to 100
    period:           str

    # Core stats
    total_return_pct: float = 0.0          # e.g. 12.4  means +12.4%
    max_drawdown_pct: float = 0.0          # e.g. -8.3  means -8.3% peak-to-trough
    sharpe_ratio:     float = 0.0          # annualised, India risk-free adjusted
    win_rate_pct:     float = 0.0          # % of trading days with positive return
    volatility_pct:   float = 0.0          # annualised std of daily returns
    best_day_pct:     float = 0.0          # single best day return
    worst_day_pct:    float = 0.0          # single worst day return
    n_days:           int   = 0            # number of trading days in the window

    # Stress window results (populated by stress_test_agent)
    stress_results:   dict  = field(default_factory=dict)

    # Human-readable summary
    summary:          str   = ""

    def to_payload(self) -> dict:
        """Convert to dict for inclusion in a BandMessage payload."""
        return {
            "tickers":          self.tickers,
            "weights":          self.weights,
            "period":           self.period,
            "total_return_pct": self.total_return_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio":     self.sharpe_ratio,
            "win_rate_pct":     self.win_rate_pct,
            "volatility_pct":   self.volatility_pct,
            "best_day_pct":     self.best_day_pct,
            "worst_day_pct":    self.worst_day_pct,
            "n_days":           self.n_days,
            "stress_results":   self.stress_results,
            "summary":          self.summary,
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "BacktestResult":
        """Reconstruct from a BandMessage payload dict."""
        return cls(
            tickers          = payload["tickers"],
            weights          = payload["weights"],
            period           = payload["period"],
            total_return_pct = payload.get("total_return_pct", 0.0),
            max_drawdown_pct = payload.get("max_drawdown_pct", 0.0),
            sharpe_ratio     = payload.get("sharpe_ratio", 0.0),
            win_rate_pct     = payload.get("win_rate_pct", 0.0),
            volatility_pct   = payload.get("volatility_pct", 0.0),
            best_day_pct     = payload.get("best_day_pct", 0.0),
            worst_day_pct    = payload.get("worst_day_pct", 0.0),
            n_days           = payload.get("n_days", 0),
            stress_results   = payload.get("stress_results", {}),
            summary          = payload.get("summary", ""),
        )


# ── Core backtest function ────────────────────────────────────────────────────

def run_backtest(
    tickers: list[str],
    weights: list[float],
    period:  str = "6mo",
) -> BacktestResult:
    """
    Simulate a buy-and-hold portfolio over the given period.

    Args:
        tickers : list of NSE ticker strings e.g. ["RELIANCE.NS", "INFY.NS"]
        weights : list of floats that sum to 100 e.g. [60.0, 40.0]
        period  : yfinance-style period string e.g. "6mo", "1y", "3mo"

    Returns:
        BacktestResult with all performance stats filled in.
    """
    # ── Validate inputs ───────────────────────────────────────────────────────
    if len(tickers) != len(weights):
        raise ValueError(f"tickers ({len(tickers)}) and weights ({len(weights)}) must match")

    weight_sum = sum(weights)
    if abs(weight_sum - 100.0) > 0.5:
        raise ValueError(f"Weights must sum to 100, got {weight_sum}")

    # Normalise weights to fractions
    w = np.array(weights) / 100.0

    # ── Fetch close prices ────────────────────────────────────────────────────
    close_df = get_multi_close(tickers, period)       # DataFrame: dates × tickers

    # Drop any tickers that failed to load
    valid_tickers = [t for t in tickers if t in close_df.columns]
    if not valid_tickers:
        raise ValueError("No valid price data returned for any ticker.")

    if len(valid_tickers) < len(tickers):
        missing = set(tickers) - set(valid_tickers)
        print(f"[backtest_engine] Warning: no data for {missing}, skipping.")
        # Re-normalise weights for valid tickers only
        valid_idx = [tickers.index(t) for t in valid_tickers]
        w = w[valid_idx]
        w = w / w.sum()
        tickers = valid_tickers

    close_df = close_df[tickers].dropna()

    # ── Daily returns ─────────────────────────────────────────────────────────
    daily_returns = close_df.pct_change().dropna()     # DataFrame

    if daily_returns.empty:
        raise ValueError("Not enough price history to compute returns.")

    # ── Portfolio daily return = weighted sum of individual returns ───────────
    portfolio_returns = daily_returns.values @ w       # numpy array, shape (n_days,)

    # ── Cumulative return ─────────────────────────────────────────────────────
    cumulative       = np.cumprod(1 + portfolio_returns)
    total_return_pct = round((cumulative[-1] - 1) * 100, 2)

    # ── Max drawdown ──────────────────────────────────────────────────────────
    peak        = np.maximum.accumulate(cumulative)
    drawdown    = (cumulative - peak) / peak
    max_dd_pct  = round(float(drawdown.min()) * 100, 2)   # negative number

    # ── Sharpe ratio (annualised, India risk-free = 6.5%) ────────────────────
    excess_returns  = portfolio_returns - RISK_FREE_RATE_DAILY
    mean_excess     = np.mean(excess_returns)
    std_returns     = np.std(portfolio_returns, ddof=1)

    if std_returns > 0:
        sharpe = round(float((mean_excess / std_returns) * np.sqrt(252)), 3)
    else:
        sharpe = 0.0

    # ── Win rate ──────────────────────────────────────────────────────────────
    win_rate_pct = round(float(np.mean(portfolio_returns > 0) * 100), 2)

    # ── Annualised volatility ─────────────────────────────────────────────────
    volatility_pct = round(float(std_returns * np.sqrt(252) * 100), 2)

    # ── Best / worst day ─────────────────────────────────────────────────────
    best_day_pct  = round(float(portfolio_returns.max() * 100), 2)
    worst_day_pct = round(float(portfolio_returns.min() * 100), 2)

    n_days = len(portfolio_returns)

    # ── Human-readable summary ────────────────────────────────────────────────
    summary = (
        f"Portfolio [{', '.join(tickers)}] over {period}: "
        f"Return={total_return_pct:+.1f}% | "
        f"MaxDD={max_dd_pct:.1f}% | "
        f"Sharpe={sharpe:.2f} | "
        f"WinRate={win_rate_pct:.1f}% | "
        f"Vol={volatility_pct:.1f}%"
    )

    return BacktestResult(
        tickers          = tickers,
        weights          = weights,
        period           = period,
        total_return_pct = total_return_pct,
        max_drawdown_pct = max_dd_pct,
        sharpe_ratio     = sharpe,
        win_rate_pct     = win_rate_pct,
        volatility_pct   = volatility_pct,
        best_day_pct     = best_day_pct,
        worst_day_pct    = worst_day_pct,
        n_days           = n_days,
        summary          = summary,
    )


# ── Stress window backtest ────────────────────────────────────────────────────

# Pre-defined stress scenarios relevant to Indian markets.
# These are approximate date ranges — mock mode will simulate them
# using the deterministic random walk from market_data.py.
STRESS_WINDOWS = {
    "covid_crash_2020": {
        "label":       "COVID Crash (Feb–Mar 2020)",
        "description": "NIFTY fell ~38% in 40 days. Tests extreme drawdown resilience.",
        "period":      "1y",     # fetch 1y then slice — mock is deterministic
        "slice_pct":   (0.10, 0.25),   # use middle 15% of the period as stress window
    },
    "russia_ukraine_2022": {
        "label":       "Russia-Ukraine Shock (Feb 2022)",
        "description": "Global risk-off event. Commodity and energy spike. INR weakness.",
        "period":      "1y",
        "slice_pct":   (0.25, 0.40),
    },
    "adani_selloff_2023": {
        "label":       "Adani Group Selloff (Jan 2023)",
        "description": "Hindenburg report triggered broader Indian market contagion.",
        "period":      "1y",
        "slice_pct":   (0.40, 0.55),
    },
}


def run_stress_backtest(
    tickers: list[str],
    weights: list[float],
) -> dict[str, BacktestResult]:
    """
    Run the portfolio through all predefined stress windows.
    Returns a dict of {scenario_name: BacktestResult}.

    Used by stress_test_agent to challenge proposals.
    """
    stress_results = {}

    for scenario_name, config in STRESS_WINDOWS.items():
        try:
            # Fetch full period close prices
            close_df = get_multi_close(tickers, config["period"])
            valid    = [t for t in tickers if t in close_df.columns]
            close_df = close_df[valid].dropna()

            # Slice to stress window
            n        = len(close_df)
            start_i  = int(n * config["slice_pct"][0])
            end_i    = int(n * config["slice_pct"][1])
            sliced   = close_df.iloc[start_i:end_i]

            if len(sliced) < 5:
                continue

            # Re-normalise weights for valid tickers
            valid_idx = [tickers.index(t) for t in valid]
            w_arr     = np.array(weights)[valid_idx] / 100.0
            w_arr     = w_arr / w_arr.sum()

            daily_ret  = sliced.pct_change().dropna().values @ w_arr
            cumulative = np.cumprod(1 + daily_ret)
            peak       = np.maximum.accumulate(cumulative)
            drawdown   = (cumulative - peak) / peak

            result = BacktestResult(
                tickers          = valid,
                weights          = [round(x * 100, 1) for x in w_arr],
                period           = config["label"],
                total_return_pct = round((cumulative[-1] - 1) * 100, 2),
                max_drawdown_pct = round(float(drawdown.min()) * 100, 2),
                sharpe_ratio     = 0.0,    # not meaningful for short stress windows
                win_rate_pct     = round(float(np.mean(daily_ret > 0) * 100), 2),
                volatility_pct   = round(float(np.std(daily_ret, ddof=1) * np.sqrt(252) * 100), 2),
                best_day_pct     = round(float(daily_ret.max() * 100), 2),
                worst_day_pct    = round(float(daily_ret.min() * 100), 2),
                n_days           = len(daily_ret),
                summary          = (
                    f"{config['label']}: "
                    f"Return={round((cumulative[-1]-1)*100,2):+.1f}% | "
                    f"MaxDD={round(float(drawdown.min())*100,2):.1f}%"
                ),
            )
            stress_results[scenario_name] = result

        except Exception as e:
            print(f"[backtest_engine] Stress test '{scenario_name}' failed: {e}")

    return stress_results


# ── Correlation helper ────────────────────────────────────────────────────────

def compute_correlation(
    tickers_a: list[str],
    tickers_b: list[str],
    period: str = "6mo",
) -> float:
    """
    Compute the average pairwise return correlation between two
    sets of tickers. Used by portfolio_arbiter to check strategy overlap.

    Returns a float between -1 and 1.
    """
    all_tickers = list(set(tickers_a + tickers_b))
    close_df    = get_multi_close(all_tickers, period)
    returns_df  = close_df.pct_change().dropna()

    correlations = []
    for ta in tickers_a:
        for tb in tickers_b:
            if ta in returns_df.columns and tb in returns_df.columns and ta != tb:
                corr = returns_df[ta].corr(returns_df[tb])
                if not np.isnan(corr):
                    correlations.append(corr)

    if not correlations:
        return 0.0

    return round(float(np.mean(correlations)), 4)


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== run_backtest smoke test ===\n")

    result = run_backtest(
        tickers = ["RELIANCE.NS", "INFY.NS", "TCS.NS"],
        weights = [40.0, 35.0, 25.0],
        period  = "6mo",
    )
    print(result.summary)
    print(f"  Total return : {result.total_return_pct:+.2f}%")
    print(f"  Max drawdown : {result.max_drawdown_pct:.2f}%")
    print(f"  Sharpe ratio : {result.sharpe_ratio:.3f}")
    print(f"  Win rate     : {result.win_rate_pct:.1f}%")
    print(f"  Volatility   : {result.volatility_pct:.1f}%")
    print(f"  Best day     : {result.best_day_pct:+.2f}%")
    print(f"  Worst day    : {result.worst_day_pct:+.2f}%")
    print(f"  Trading days : {result.n_days}")

    print("\n=== run_stress_backtest smoke test ===\n")
    stress = run_stress_backtest(
        tickers = ["RELIANCE.NS", "INFY.NS", "TCS.NS"],
        weights = [40.0, 35.0, 25.0],
    )
    for name, r in stress.items():
        print(f"  {name}: {r.summary}")

    print("\n=== compute_correlation smoke test ===\n")
    corr = compute_correlation(
        tickers_a = ["RELIANCE.NS", "INFY.NS"],
        tickers_b = ["TCS.NS", "WIPRO.NS"],
        period    = "6mo",
    )
    print(f"  Avg correlation between strategy A and B: {corr:.4f}")

    print("\n=== to_payload / from_payload round-trip ===\n")
    payload  = result.to_payload()
    restored = BacktestResult.from_payload(payload)
    print(f"  Round-trip OK: {restored.summary}")