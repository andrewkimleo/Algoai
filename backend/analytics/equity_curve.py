"""
equity_curve.py
---------------
Computes the daily equity values compounded from portfolio daily returns series.
"""

import pandas as pd

def compute_equity_curve(returns: pd.Series, initial_capital: float = 100000.0) -> pd.Series:
    """
    Computes equity curve compounded from daily returns.
    Formula:
        equity[t] = equity[t-1] * (1 + return[t])
    """
    if returns.empty:
        return pd.Series(dtype='float64')

    # Compounded returns
    cumulative_returns = (1 + returns).cumprod()
    equity = initial_capital * cumulative_returns

    # Prepend the starting capital at t-1 (one day before returns start)
    first_date = returns.index[0] - pd.Timedelta(days=1)
    initial_series = pd.Series([initial_capital], index=[first_date])
    
    return pd.concat([initial_series, equity])
