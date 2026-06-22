"""
momentum_agent.py
-----------------
Strategy Agent 1: Momentum (Refactored)

Identifies stocks with strong recent price trends and proposes
buying high-momentum equities for the portfolio.
"""

import logging
from typing import Tuple
from tools.market_data import get_active_tickers
from tools.indicator_engine import fetch_batch_data, rank_momentum, apply_sector_filter
from tools.market_regime import detect_market_regime
from band.message_schema import make_proposal, make_revision, BandMessage

logger = logging.getLogger(__name__)

def generate_momentum_portfolio(tickers: list[str]) -> Tuple[str, list, list, list]:
    # 1. Fetch batch price data
    price_data = fetch_batch_data(tickers)
    
    # 2. Get market regime
    regime_data = detect_market_regime()
    regime = regime_data.get("regime", "bull")
    
    # 3. Rank universe by momentum
    candidates = rank_momentum(price_data, regime)
    
    # 4. Apply sector exposure limit (max 2 per sector, max 8 candidates total)
    screened_candidates = apply_sector_filter(candidates, limit=8, max_per_sector=2)
    
    if not screened_candidates:
        return "No momentum candidates found.", [], [], []
        
    # Top 3 for the active proposal
    picks = [c["ticker"] for c in screened_candidates[:3]]
    weights = [40.0, 35.0, 25.0][:len(picks)]
    if len(weights) == 2:
        weights = [55.0, 45.0]
    elif len(weights) == 1:
        weights = [100.0]
        
    # Build text output matching original layout with factor breakdowns
    lines = [
        "STRATEGY: Momentum",
        f"PICKS: {', '.join(picks)}",
        f"WEIGHTS: {', '.join(f'{w}%' for w in weights)}",
        "RATIONALE:"
    ]
    
    for c in screened_candidates[:3]:
        ticker = c["ticker"]
        sec = c["sector"]
        metrics = c["metrics"]
        lines.append(
            f"  - {ticker} ({sec}): RSI is {metrics['RSI']}, 20d return is {metrics['20d_Return']}, "
            f"60d return is {metrics['60d_Return']}, Volatility is {metrics['Volatility']}. Strong trend strength."
        )
        
    lines.append(f"RISK: Momentum strategies carry reversal risk in volatile or sideways markets. Current regime: {regime}.")
    
    raw_output = "\n".join(lines)
    return raw_output, picks, weights, screened_candidates

def run_momentum_agent() -> BandMessage:
    """
    Runs the deterministic momentum engine and returns a proposal BandMessage.
    """
    logger.info("[momentum_agent] Running deterministic momentum scan...")
    tickers = get_active_tickers()
    raw_output, picks, weights, candidates = generate_momentum_portfolio(tickers)
    
    sharpe_val = candidates[0]["sharpe"] if candidates else 1.0
    drawdown_val = candidates[0]["max_drawdown"] if candidates else 10.0
    win_rate_val = candidates[0]["win_rate"] if candidates else 50.0

    payload = {
        "raw_output": raw_output,
        "strategy": "momentum",
        "picks": picks,
        "weights": weights,
        "candidates": candidates,  # Expose top 8 candidates to Portfolio Arbiter
        "sharpe": sharpe_val,
        "max_drawdown": drawdown_val,
        "win_rate": win_rate_val,
        "backtest_summary": {
            "sharpe": sharpe_val,
            "max_drawdown": drawdown_val,
            "win_rate": win_rate_val
        }
    }
    
    return make_proposal(
        sender="momentum_agent",
        strategy_name="Momentum Strategy",
        description=f"Top momentum picks: {', '.join(picks) if picks else 'None'}",
        payload=payload,
    )

def run_defense_agent(original_proposal: BandMessage, challenges: list[BandMessage]) -> BandMessage:
    """
    Deterministically handles risk challenges by adjusting weights or stop loss.
    """
    payload = dict(original_proposal.payload)
    picks = payload.get("picks", [])
    weights = payload.get("weights", [])
    
    # Keep weights summing to 100% to satisfy compliance agent, but reduce overall strategy allocation
    adjusted_weights = list(weights)
    
    lines = [
        "REVISION SUMMARY: Reduced overall strategy exposure by 30% to enhance capital defense against extreme drawdowns.",
        "STRATEGY: Momentum",
        f"PICKS: {', '.join(picks)}",
        f"WEIGHTS: {', '.join(f'{w}%' for w in adjusted_weights)}",
        "RATIONALE: Overall allocation scaled back from 5.0% to 3.5% to mitigate tail risk, while preserving strategy weight proportions.",
        "RISK: Scaled back allocation reduces absolute upside but mitigates drawdowns."
    ]
    
    raw_output = "\n".join(lines)
    payload["weights"] = adjusted_weights
    payload["raw_output"] = raw_output
    payload["position_size_pct"] = 3.5  # reduced from 5.0 default to lower overall risk
    
    return make_revision(
        sender="momentum_agent",
        strategy_name="Momentum Strategy",
        changes="Reduced strategy position size to lower overall risk.",
        payload=payload,
    )
