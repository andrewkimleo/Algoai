"""
drawdown.py
-----------
Computes daily drawdown percentages and tracks running peaks.
"""

import pandas as pd

def compute_drawdown_series(equity: pd.Series) -> pd.Series:
    """
    Computes daily drawdown percentages.
    Formula:
        drawdown[t] = (equity[t] - peak[t]) / peak[t]
    """
    if equity.empty:
        return pd.Series(dtype='float64')

    running_peak = equity.cummax()
    drawdown = (equity - running_peak) / running_peak
    return drawdown
