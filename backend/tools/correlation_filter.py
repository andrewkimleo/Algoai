"""
correlation_filter.py
---------------------
Prunes highly correlated stocks from strategy candidate pools before
submitting them to the final Portfolio Arbiter, ensuring true diversification.
"""

import logging
import pandas as pd
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def prune_correlated_candidates(
    candidates: List[Dict[str, Any]],
    price_data: Dict[str, pd.DataFrame],
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Computes returns correlation for candidates. If correlation between two stocks
    exceeds threshold, prunes the lower-ranked stock.
    
    Candidates list should be already sorted by strategy score descending.
    """
    if len(candidates) <= 1:
        return candidates

    tickers = [c["ticker"] for c in candidates]
    
    # Extract returns
    returns_df = pd.DataFrame()
    for t in tickers:
        if t in price_data:
            close = price_data[t]["close"]
            if len(close) > 20:
                returns_df[t] = close.pct_change().dropna().tail(60) # use 60-day return window

    if returns_df.empty or len(returns_df.columns) < 2:
        return candidates

    # Compute correlation matrix
    corr_matrix = returns_df.corr()
    
    pruned_tickers = set()
    pruned_candidates = []

    # Sort candidates by score descending (already assumed sorted, but enforce it)
    sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)

    for i, c1 in enumerate(sorted_candidates):
        t1 = c1["ticker"]
        if t1 in pruned_tickers:
            continue
            
        pruned_candidates.append(c1)
        
        # Check against all remaining lower-ranked candidates
        for c2 in sorted_candidates[i+1:]:
            t2 = c2["ticker"]
            if t2 in pruned_tickers:
                continue
                
            # If correlation exceeds threshold, prune the lower-ranked ticker (t2)
            if t1 in corr_matrix.columns and t2 in corr_matrix.columns:
                corr_val = corr_matrix.loc[t1, t2]
                if pd.notna(corr_val) and abs(corr_val) > threshold:
                    logger.info(
                        f"[CorrelationFilter] Pruning {t2} (corr with {t1} is {corr_val:.2f} > {threshold})"
                    )
                    pruned_tickers.add(t2)

    return pruned_candidates
