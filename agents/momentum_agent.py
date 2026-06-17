"""
momentum_agent.py
-----------------
Strategy Agent 1: Momentum

Identifies stocks with strong recent price trends and proposes
buying high-momentum equities for the portfolio.

Logic:
  - Computes 20-day and 60-day momentum (% return over window)
  - Ranks DEMO_TICKERS by momentum score
  - Picks top 3 as the proposal
  - Posts a BandMessage of type "proposal" to the room
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

from tools.market_data import get_returns, get_ohlcv, DEMO_TICKERS
from band.message_schema import make_proposal, make_status_update, BandMessage


# ── CrewAI Tool ───────────────────────────────────────────────────────────────
llm = LLM(model="groq/llama-3.3-70b-versatile")

@tool("MomentumScanner")
def momentum_scanner(period: str = "6mo") -> str:
    """
    Scans all demo tickers and returns a ranked list by momentum score.
    Momentum score = average of 20-day return and 60-day return.
    Input: period string like '6mo' or '1y'
    Output: ranked ticker list as a formatted string.
    """
    scores = {}

    for ticker in DEMO_TICKERS:
        try:
            returns = get_returns(ticker, period)

            mom_20  = returns.tail(20).sum()   # ~1-month momentum
            mom_60  = returns.tail(60).sum()   # ~3-month momentum
            score   = (mom_20 + mom_60) / 2

            latest_price = get_ohlcv(ticker, "1mo").latest_price
            scores[ticker] = {
                "score":        round(score * 100, 2),   # as percentage
                "mom_20d":      round(mom_20 * 100, 2),
                "mom_60d":      round(mom_60 * 100, 2),
                "latest_price": latest_price,
            }
        except Exception as e:
            scores[ticker] = {"error": str(e)}

    # Sort by score descending
    ranked = sorted(
        [(t, d) for t, d in scores.items() if "score" in d],
        key=lambda x: x[1]["score"],
        reverse=True,
    )

    lines = ["MOMENTUM SCAN RESULTS (ranked best → worst):\n"]
    for rank, (ticker, data) in enumerate(ranked, 1):
        lines.append(
            f"{rank}. {ticker} | Score: {data['score']}% | "
            f"20d: {data['mom_20d']}% | 60d: {data['mom_60d']}% | "
            f"Price: ₹{data['latest_price']}"
        )

    return "\n".join(lines)


# ── Agent definition ──────────────────────────────────────────────────────────

def build_momentum_agent() -> Agent:
    return Agent(
        role="Momentum Strategy Analyst",
        llm=llm,
        goal=(
            "Identify the top 3 high-momentum Indian equities from the universe "
            "and propose them as a portfolio strategy with clear justification."
        ),
        backstory=(
            "You are a quantitative analyst specialising in price momentum strategies "
            "for Indian equity markets. You believe that stocks which have performed "
            "well over the past 1-3 months tend to continue outperforming in the "
            "near term. You back every recommendation with momentum scores and "
            "return data. You are concise, data-driven, and confident."
        ),
        tools=[momentum_scanner],
        verbose=True,
        allow_delegation=False,
    )


# ── Task definition ───────────────────────────────────────────────────────────

def build_momentum_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Use the MomentumScanner tool to scan all available tickers over a 6-month period. "
            "Pick the top 3 by momentum score. "
            "For each pick, explain WHY it qualifies (cite its 20d and 60d momentum). "
            "Then produce a final proposal in this exact format:\n\n"
            "STRATEGY: Momentum\n"
            "PICKS: <TICKER1>, <TICKER2>, <TICKER3>\n"
            "WEIGHTS: <w1>%, <w2>%, <w3>%  (must sum to 100)\n"
            "RATIONALE: <2-3 sentences per pick>\n"
            "RISK: <one sentence on the main risk of this strategy>\n"
        ),
        expected_output=(
            "A structured proposal with STRATEGY, PICKS, WEIGHTS, RATIONALE, and RISK sections."
        ),
        agent=agent,
    )


# ── Band message builder ──────────────────────────────────────────────────────

def proposal_to_band_message(crew_output: str) -> BandMessage:
    """
    Parse the crew output text and wrap it in a BandMessage proposal.
    The raw text goes into content; we also extract tickers/weights for payload.
    """
    payload = {"raw_output": crew_output, "strategy": "momentum"}

    # Best-effort extraction of tickers and weights
    picks, weights = [], []
    for line in crew_output.splitlines():
        if line.startswith("PICKS:"):
            picks = [t.strip() for t in line.replace("PICKS:", "").split(",")]
        if line.startswith("WEIGHTS:"):
            raw_w = line.replace("WEIGHTS:", "").replace("%", "").split(",")
            try:
                weights = [float(w.strip()) for w in raw_w]
            except ValueError:
                weights = []

    if picks:
        payload["picks"]   = picks
    if weights:
        payload["weights"] = weights

    return make_proposal(
        sender="momentum_agent",
        strategy_name="Momentum Strategy",
        description=f"Top momentum picks: {', '.join(picks) if picks else 'see raw output'}",
        payload=payload,
    )


# ── Runner ────────────────────────────────────────────────────────────────────

def run_momentum_agent() -> BandMessage:
    """
    Runs the momentum agent crew and returns a BandMessage ready to post.
    Call this from main.py or room_manager.py.
    """
    agent = build_momentum_agent()
    task  = build_momentum_task(agent)
    crew  = Crew(agents=[agent], tasks=[task], verbose=True)

    print("[momentum_agent] Starting crew run...")
    result = crew.kickoff()

    output_text = str(result)
    band_msg    = proposal_to_band_message(output_text)

    print(f"[momentum_agent] Proposal ready → {band_msg.content}")
    return band_msg


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test the scanner tool directly without spinning up CrewAI
    print("=== MomentumScanner direct test ===\n")
    print(momentum_scanner("6mo"))

    print("\n=== Band message shape ===\n")
    msg = make_proposal(
        sender="momentum_agent",
        strategy_name="Momentum Strategy",
        description="Test proposal",
        payload={"picks": ["RELIANCE.NS", "TCS.NS", "INFY.NS"], "weights": [40, 35, 25]},
    )
    print(msg.model_dump_json(indent=2))