"""
sentiment_agent.py
------------------
Strategy Agent 3: Sentiment (Refactored)

Identifies stocks with strong positive news momentum and proposes
them as buy candidates based on recent market sentiment signals.
"""

import logging
from typing import Tuple
from tools.market_data import get_active_tickers
from tools.indicator_engine import fetch_batch_data, rank_sentiment, apply_sector_filter
from tools.market_regime import detect_market_regime
from tools.news_scraper import fetch_news
from band.message_schema import make_proposal, make_revision, BandMessage

logger = logging.getLogger(__name__)

# Re-use deterministic headline scorer from old implementation
POSITIVE_KEYWORDS = [
    "profit", "record", "growth", "beat", "upgrade", "dividend",
    "contract", "wins", "partnership", "expansion", "acquisition",
    "outperform", "strong", "surge", "rally", "buy", "bullish",
    "order", "revenue", "deal", "gains", "optimistic", "positive",
]

NEGATIVE_KEYWORDS = [
    "loss", "downgrade", "miss", "cut", "layoff", "penalty",
    "fraud", "probe", "investigation", "decline", "fall", "drop",
    "bearish", "sell", "concern", "risk", "warning", "fine",
    "lawsuit", "disappoints", "underperform", "weak", "negative",
]

def _score_headline(headline: str) -> tuple[int, str]:
    text = headline.lower()
    pos  = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    neg  = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)

    if pos > neg:
        matched = [kw for kw in POSITIVE_KEYWORDS if kw in text]
        return 1, f"positive keywords: {', '.join(matched[:3])}"
    elif neg > pos:
        matched = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
        return -1, f"negative keywords: {', '.join(matched[:3])}"
    else:
        return 0, "neutral"

def generate_sentiment_portfolio(tickers: list[str]) -> Tuple[str, list, list, list]:
    # 1. Fetch batch data
    price_data = fetch_batch_data(tickers)
    
    # 2. Get market regime
    regime_data = detect_market_regime()
    regime = regime_data.get("regime", "bull")
    
    # 3. Rank universe by sentiment score
    candidates = rank_sentiment(price_data, regime)
    
    # 4. Filter sector concentration (max 2 per sector, max 8 candidates total)
    screened_candidates = apply_sector_filter(candidates, limit=8, max_per_sector=2)
    
    if not screened_candidates:
        return "No sentiment candidates found.", [], [], []
        
    # Top 3 picks
    picks = [c["ticker"] for c in screened_candidates[:3]]
    weights = [40.0, 35.0, 25.0][:len(picks)]
    if len(weights) == 2:
        weights = [55.0, 45.0]
    elif len(weights) == 1:
        weights = [100.0]
        
    # Build text output
    lines = [
        "STRATEGY: Sentiment",
        f"PICKS: {', '.join(picks)}",
        f"WEIGHTS: {', '.join(f'{w}%' for w in weights)}",
        "RATIONALE:"
    ]
    
    for c in screened_candidates[:3]:
        ticker = c["ticker"]
        sec = c["sector"]
        metrics = c["metrics"]
        
        # Grab first headline for explainability
        articles = fetch_news(ticker, max_results=1)
        headline = f"\"{articles[0].title}\"" if articles else "No recent headlines."
        
        lines.append(
            f"  - {ticker} ({sec}): Sentiment index is {metrics['Sentiment_Index']} ({metrics['Article_Volume']} headlines). "
            f"Key headline: {headline}."
        )
        
    lines.append(f"RISK: Sentiment indexes fluctuate rapidly. Current regime: {regime}.")
    lines.append("EXPLAINABILITY NOTE: All signals derived from keyword-scored headlines as required under SEBI Feb 2025 algo framework. No black-box model used.")
    
    raw_output = "\n".join(lines)
    return raw_output, picks, weights, screened_candidates

def run_sentiment_agent() -> BandMessage:
    """
    Runs the deterministic sentiment engine and returns a proposal BandMessage.
    """
    logger.info("[sentiment_agent] Running deterministic sentiment scan...")
    tickers = get_active_tickers()
    raw_output, picks, weights, candidates = generate_sentiment_portfolio(tickers)
    
    sharpe_val = candidates[0]["sharpe"] if candidates else 1.0
    drawdown_val = candidates[0]["max_drawdown"] if candidates else 10.0
    win_rate_val = candidates[0]["win_rate"] if candidates else 50.0

    payload = {
        "raw_output": raw_output,
        "strategy": "sentiment",
        "picks": picks,
        "weights": weights,
        "candidates": candidates,  # Expose top 8 candidates to Portfolio Arbiter
        "sharpe": sharpe_val,
        "max_drawdown": drawdown_val,
        "win_rate": win_rate_val,
        "signal_method": "keyword_scored_headlines",
        "sebi_compliant": True,
        "explainability_note": "All signals derived from keyword-scored headlines.",
        "backtest_summary": {
            "sharpe": sharpe_val,
            "max_drawdown": drawdown_val,
            "win_rate": win_rate_val
        }
    }
    
    return make_proposal(
        sender="sentiment_agent",
        strategy_name="Sentiment Strategy",
        description=f"Top sentiment picks: {', '.join(picks) if picks else 'None'}",
        payload=payload,
    )

def run_defense_agent(original_proposal: BandMessage, challenges: list[BandMessage]) -> BandMessage:
    """
    Deterministically handles risk challenges by adjusting weights.
    """
    payload = dict(original_proposal.payload)
    picks = payload.get("picks", [])
    weights = payload.get("weights", [])
    
    # Keep weights summing to 100% to satisfy compliance agent, but reduce overall strategy allocation
    adjusted_weights = list(weights)
    
    lines = [
        "REVISION SUMMARY: Reduced overall strategy exposure by 30% to mitigate news sentiment reversal risks.",
        "STRATEGY: Sentiment",
        f"PICKS: {', '.join(picks)}",
        f"WEIGHTS: {', '.join(f'{w}%' for w in adjusted_weights)}",
        "RATIONALE: Overall allocation scaled back from 5.0% to 3.5% to mitigate tail risk, while preserving strategy weight proportions.",
        "RISK: Reversal risk reduced. Capital sizing minimized.",
        "EXPLAINABILITY NOTE: Scored via deterministic keywords."
    ]
    
    raw_output = "\n".join(lines)
    payload["weights"] = adjusted_weights
    payload["raw_output"] = raw_output
    payload["position_size_pct"] = 3.5  # reduced from 5.0 default to lower overall risk
    
    return make_revision(
        sender="sentiment_agent",
        strategy_name="Sentiment Strategy",
        changes="Reduced strategy position size to lower overall risk.",
        payload=payload,
    )