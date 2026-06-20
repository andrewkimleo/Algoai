"""
mean_reversion_agent.py
-----------------------
Strategy Agent 2: Mean Reversion

Identifies stocks that have deviated significantly below their
historical mean and proposes them as buy candidates expecting
a price correction back toward the mean.

Logic:
  - Computes rolling 60-day mean and standard deviation of close prices
  - Calculates Z-score: (current_price - mean) / std
  - Stocks with Z-score < -1.5 are considered oversold / undervalued
  - Picks top 3 most oversold tickers as the proposal
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

from tools.market_data import get_ohlcv, DEMO_TICKERS
from band.message_schema import make_proposal, BandMessage


# ── CrewAI Tool ───────────────────────────────────────────────────────────────
from crewai import LLM
import os
import litellm

litellm.drop_params = True
api_key = os.getenv("GROQ_API_KEY_MEAN_REVERSION") or os.getenv("GROQ_API_KEY", "")
llm = LLM(
    model=os.getenv("MODEL_MEAN_REVERSION") or os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile"),
    api_key=api_key,
    temperature=0.3
)

@tool("MeanReversionScanner")
def mean_reversion_scanner(period: str = "6mo") -> str:
    """
    Scans all demo tickers and computes the Z-score of the current price
    relative to its 60-day rolling mean and standard deviation.
    A Z-score below -1.5 signals the stock is oversold and likely to revert.
    Input: period string like '6mo' or '1y'
    Output: ranked ticker list sorted by Z-score (most oversold first).
    """
    scores = {}

    for ticker in DEMO_TICKERS:
        try:
            result = get_ohlcv(ticker, period)
            close  = result.df["close"]

            rolling_mean = close.rolling(window=60).mean()
            rolling_std  = close.rolling(window=60).std()

            current_price = close.iloc[-1]
            mean_60       = rolling_mean.iloc[-1]
            std_60        = rolling_std.iloc[-1]

            if std_60 == 0 or pd.isna(std_60):
                continue

            z_score = (current_price - mean_60) / std_60

            # Distance from mean as a percentage
            pct_from_mean = ((current_price - mean_60) / mean_60) * 100

            scores[ticker] = {
                "z_score":       round(float(z_score), 3),
                "current_price": round(float(current_price), 2),
                "mean_60d":      round(float(mean_60), 2),
                "std_60d":       round(float(std_60), 2),
                "pct_from_mean": round(float(pct_from_mean), 2),
            }

        except Exception as e:
            scores[ticker] = {"error": str(e)}

    # Sort by Z-score ascending (most negative = most oversold = best opportunity)
    ranked = sorted(
        [(t, d) for t, d in scores.items() if "z_score" in d],
        key=lambda x: x[1]["z_score"],
    )

    lines = ["MEAN REVERSION SCAN RESULTS (most oversold → least oversold):\n"]
    for rank, (ticker, data) in enumerate(ranked, 1):
        signal = "🔴 OVERSOLD" if data["z_score"] < -1.5 else (
                 "🟡 SLIGHTLY LOW" if data["z_score"] < -0.5 else "⚪ NEUTRAL/HIGH"
        )
        lines.append(
            f"{rank}. {ticker} | Z-Score: {data['z_score']} | {signal}\n"
            f"   Price: ₹{data['current_price']} | 60d Mean: ₹{data['mean_60d']} | "
            f"Deviation: {data['pct_from_mean']}%"
        )

    return "\n".join(lines)


# Pandas import needed inside the tool
import pandas as pd


# ── Agent definition ──────────────────────────────────────────────────────────

def build_mean_reversion_agent(with_tools: bool = True) -> Agent:
    return Agent(
        role="Mean Reversion Strategy Analyst",
        llm=llm,
        goal=(
            "Identify the top 3 oversold Indian equities using statistical Z-score analysis "
            "and propose them as portfolio candidates expecting a price recovery."
        ),
        backstory=(
            "You are a quantitative analyst who specialises in statistical arbitrage "
            "and mean reversion strategies for Indian equity markets. You believe that "
            "stock prices tend to revert to their historical averages after extreme "
            "deviations. You use Z-scores and rolling statistics to identify stocks "
            "that are statistically oversold — not just subjectively cheap. "
            "You are methodical, precise, and always anchor your arguments in numbers."
        ),
        tools=[mean_reversion_scanner] if with_tools else [],
        verbose=True,
        allow_delegation=False,
    )


# ── Task definition ───────────────────────────────────────────────────────────

def build_mean_reversion_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Use the MeanReversionScanner tool to scan all tickers over a 6-month period. "
            "Focus on stocks with a Z-score below -1.0 as your candidates. "
            "Pick the top 3 most oversold stocks. "
            "For each pick, explain the statistical case for reversion "
            "(cite Z-score, current price vs 60d mean, % deviation). "
            "Then produce a final proposal in this exact format:\n\n"
            "STRATEGY: Mean Reversion\n"
            "PICKS: <TICKER1>, <TICKER2>, <TICKER3>\n"
            "WEIGHTS: <w1>%, <w2>%, <w3>%  (must sum to 100, weight more to deeper Z-scores)\n"
            "RATIONALE: <2-3 sentences per pick citing Z-score and deviation>\n"
            "RISK: <one sentence on the main risk — e.g. value trap / prolonged deviation>\n"
        ),
        expected_output=(
            "A structured proposal with STRATEGY, PICKS, WEIGHTS, RATIONALE, and RISK sections."
        ),
        agent=agent,
    )


# ── Band message builder ──────────────────────────────────────────────────────

def proposal_to_band_message(crew_output: str) -> BandMessage:
    """
    Wrap the crew output in a BandMessage proposal.
    """
    payload = {"raw_output": crew_output, "strategy": "mean_reversion"}

    picks, weights = [], []
    for line in crew_output.splitlines():
        if line.startswith("PICKS:"):
            picks = [t.strip() for t in line.replace("PICKS:", "").split(",")]
        if line.startswith("WEIGHTS:"):
            import re
            raw_w = line.replace("WEIGHTS:", "")
            raw_w = re.sub(r'[^0-9.,]', '', raw_w).split(",")
            try:
                weights = [float(w.strip()) for w in raw_w if w.strip()]
            except ValueError:
                weights = []

    if picks:
        payload["picks"]   = picks
    if weights:
        payload["weights"] = weights

    return make_proposal(
        sender="mean_reversion_agent",
        strategy_name="Mean Reversion Strategy",
        description=f"Top oversold picks: {', '.join(picks) if picks else 'see raw output'}",
        payload=payload,
    )


# ── Defense ───────────────────────────────────────────────────────────────────

def build_defense_task(agent: Agent, original_proposal: BandMessage, challenges: list[BandMessage]) -> Task:
    challenges_text = "\n".join([c.content for c in challenges])
    return Task(
        description=(
            f"You are defending your original Mean Reversion proposal against challenges from review agents.\n\n"
            f"ORIGINAL PROPOSAL:\n{original_proposal.payload.get('raw_output', original_proposal.content)}\n\n"
            f"CHALLENGES:\n{challenges_text}\n\n"
            "Analyze the challenges. If they highlight valid risks, modify your picks or weights to reduce risk. "
            "If you disagree with the challenge, defend your original picks.\n\n"
            "CRITICAL: Do not attempt to use any tools or call functions. You do not have access to any external tools for this task. "
            "Respond only with the text in the exact format requested below.\n\n"
            "You must output your final defense/revision in this exact format:\n\n"
            "REVISION SUMMARY: <1-2 sentences explaining how you addressed the challenges>\n"
            "STRATEGY: Mean Reversion\n"
            "PICKS: <TICKER1>, <TICKER2>, <TICKER3>\n"
            "WEIGHTS: <w1>%, <w2>%, <w3>%  (must sum to 100)\n"
            "RATIONALE: <2-3 sentences per pick>\n"
            "RISK: <one sentence on the main risk of this strategy>\n"
        ),
        expected_output="A structured defense and revised proposal.",
        agent=agent,
    )

def defense_to_band_message(crew_output: str) -> BandMessage:
    from band.message_schema import make_revision
    payload = {"raw_output": crew_output, "strategy": "mean_reversion"}
    
    summary = "Defended proposal"
    picks, weights = [], []
    for line in crew_output.splitlines():
        if line.startswith("REVISION SUMMARY:"):
            summary = line.replace("REVISION SUMMARY:", "").strip()
        if line.startswith("PICKS:"):
            picks = [t.strip() for t in line.replace("PICKS:", "").split(",")]
        if line.startswith("WEIGHTS:"):
            import re
            raw_w = line.replace("WEIGHTS:", "")
            raw_w = re.sub(r'[^0-9.,]', '', raw_w).split(",")
            try:
                weights = [float(w.strip()) for w in raw_w if w.strip()]
            except ValueError:
                weights = []
                
    if picks:
        payload["picks"] = picks
    if weights:
        payload["weights"] = weights
        
    return make_revision(
        sender="mean_reversion_agent",
        strategy_name="Mean Reversion Strategy",
        changes=summary,
        payload=payload,
    )

def run_defense_agent(original_proposal: BandMessage, challenges: list[BandMessage]) -> BandMessage:
    agent = build_mean_reversion_agent(with_tools=False)
    task = build_defense_task(agent, original_proposal, challenges)
    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    
    print("[mean_reversion_agent] Starting defense crew run...")
    result = crew.kickoff()
    
    output_text = str(result)
    band_msg = defense_to_band_message(output_text)
    
    print(f"[mean_reversion_agent] Defense ready → {band_msg.content}")
    return band_msg

# ── Runner ────────────────────────────────────────────────────────────────────

def run_mean_reversion_agent() -> BandMessage:
    """
    Runs the mean reversion agent crew and returns a BandMessage ready to post.
    Call this from main.py or room_manager.py.
    """
    agent = build_mean_reversion_agent()
    task  = build_mean_reversion_task(agent)
    crew  = Crew(agents=[agent], tasks=[task], verbose=True)

    print("[mean_reversion_agent] Starting crew run...")
    result = crew.kickoff()

    output_text = str(result)
    band_msg    = proposal_to_band_message(output_text)

    print(f"[mean_reversion_agent] Proposal ready → {band_msg.content}")
    return band_msg


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== MeanReversionScanner direct test ===\n")
    print(mean_reversion_scanner("6mo"))

    print("\n=== Band message shape ===\n")
    msg = make_proposal(
        sender="mean_reversion_agent",
        strategy_name="Mean Reversion Strategy",
        description="Test proposal",
        payload={"picks": ["SBIN.NS", "WIPRO.NS", "AXISBANK.NS"], "weights": [40, 35, 25]},
    )
    print(msg.model_dump_json(indent=2))