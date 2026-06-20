"""
sentiment_agent.py
------------------
Strategy Agent 3: Sentiment

Identifies stocks with strong positive news momentum and proposes
them as buy candidates based on recent market sentiment signals.

Logic:
  - Fetches recent headlines for each DEMO_TICKER via news_scraper.py
    (Google News + Economic Times + Moneycontrol RSS — no API key needed)
  - Scores each headline using keyword matching (+1 / 0 / -1)
  - Computes a sentiment score per ticker = average score across all headlines
  - Also considers headline VOLUME (more coverage = more market attention)
  - Final score = (avg_sentiment * 0.7) + (normalised_volume * 0.3)
  - Picks top 3 tickers by final score as the proposal

Explainability rule (SEBI compliance-ready):
  - Every proposal states the EXACT headlines that drove the signal
  - No opaque LLM scoring — the reasoning is fully auditable
  - This avoids "black box" classification under the SEBI Feb 2025 circular
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from crewai import Agent, Task, Crew, LLM
from crewai.tools import tool

from tools.market_data import DEMO_TICKERS
from tools.news_scraper import fetch_news, articles_to_payload
from band.message_schema import make_proposal, BandMessage


# ── Ticker → company name map (for readable display) ─────────────────────────
from crewai import LLM
import os
import litellm

litellm.drop_params = True
api_key = os.getenv("GROQ_API_KEY_SENTIMENT") or os.getenv("GROQ_API_KEY", "")
llm = LLM(
    model=os.getenv("MODEL_SENTIMENT") or os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile"),
    api_key=api_key,
    temperature=0.3
)

TICKER_TO_COMPANY = {
    "RELIANCE.NS":  "Reliance Industries",
    "INFY.NS":      "Infosys",
    "TCS.NS":       "TCS Tata Consultancy",
    "HDFCBANK.NS":  "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "WIPRO.NS":     "Wipro",
    "AXISBANK.NS":  "Axis Bank",
    "SBIN.NS":      "State Bank of India SBI",
}


# ── Positive / negative keyword lists for rule-based scoring ─────────────────

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


# ── Keyword-based headline scorer ────────────────────────────────────────────

def _score_headline(headline: str) -> tuple[int, str]:
    """
    Score a single headline using keyword matching.
    Returns (score, reason) where score is -1, 0, or +1.
    Fully deterministic — no LLM involved here (explainability for SEBI).
    """
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


# ── CrewAI Tool ───────────────────────────────────────────────────────────────

@tool("SentimentScanner")
def sentiment_scanner(period: str = "recent") -> str:
    """
    Scans all demo tickers by fetching recent news headlines from
    Google News, Economic Times, and Moneycontrol, then scores sentiment
    using keyword analysis. Returns a ranked list of tickers with their
    sentiment scores and the specific headlines that drove each score —
    making the reasoning fully auditable and SEBI-compliant.
    Input: period string (ignored for news — always fetches latest headlines)
    Output: ranked ticker list with scores and headline evidence.
    """
    results = {}

    for ticker in DEMO_TICKERS:
        company  = TICKER_TO_COMPANY.get(ticker, ticker)

        # ── Fetch structured articles from news_scraper ───────────────────────
        articles  = fetch_news(ticker, max_results=8)
        headlines = [a.title for a in articles]

        if not headlines:
            continue

        # ── Score each headline ───────────────────────────────────────────────
        scored = []
        for h in headlines:
            score, reason = _score_headline(h)
            scored.append({"headline": h, "score": score, "reason": reason})

        avg_score    = sum(s["score"] for s in scored) / len(scored)
        volume_score = min(len(headlines) / 8.0, 1.0)
        final_score  = round((avg_score * 0.7) + (volume_score * 0.3), 4)

        # Keep only headlines that moved the score (non-neutral), top 3
        key_headlines = [s for s in scored if s["score"] != 0][:3]

        results[ticker] = {
            "company":          company,
            "final_score":      final_score,
            "avg_sentiment":    round(avg_score, 4),
            "headline_count":   len(headlines),
            "key_headlines":    key_headlines,
            "articles_payload": articles_to_payload(articles),
        }

    # ── Sort by final_score descending ────────────────────────────────────────
    ranked = sorted(results.items(), key=lambda x: x[1]["final_score"], reverse=True)

    lines = ["SENTIMENT SCAN RESULTS (most positive → least positive):\n"]

    for rank, (ticker, data) in enumerate(ranked, 1):
        signal = (
            "🟢 POSITIVE" if data["final_score"] >  0.2 else
            "🔴 NEGATIVE" if data["final_score"] < -0.2 else
            "🟡 NEUTRAL"
        )
        lines.append(
            f"{rank}. {ticker} ({data['company']}) | Score: {data['final_score']} | {signal}\n"
            f"   Headlines analysed: {data['headline_count']} | "
            f"Avg sentiment: {data['avg_sentiment']}"
        )
        for h in data["key_headlines"]:
            direction = "✅" if h["score"] > 0 else "❌"
            lines.append(f"   {direction} \"{h['headline'][:80]}\"")
            lines.append(f"      → {h['reason']}")
        lines.append("")

    return "\n".join(lines)


# ── Agent definition ──────────────────────────────────────────────────────────

def build_sentiment_agent(with_tools: bool = True) -> Agent:
    return Agent(
        role="Sentiment Strategy Analyst",
        llm=llm,
        goal=(
            "Identify the top 3 Indian equities with the strongest positive news sentiment "
            "and propose them as portfolio candidates backed by specific, auditable headline evidence."
        ),
        backstory=(
            "You are a market analyst who specialises in news-driven trading strategies "
            "for Indian equity markets. You believe that sustained positive news flow "
            "creates buying pressure before price charts reflect it. "
            "Critically, you follow SEBI's explainability guidelines strictly: "
            "every trade signal you propose must cite the exact headlines and keywords "
            "that triggered it — no black-box reasoning, no opaque scores. "
            "You are transparent, rigorous, and always show your evidence."
        ),
        tools=[sentiment_scanner] if with_tools else [],
        verbose=True,
        allow_delegation=False,
    )


# ── Task definition ───────────────────────────────────────────────────────────

def build_sentiment_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Use the SentimentScanner tool to scan all tickers. "
            "Focus on stocks with a positive final score (above 0.2). "
            "Pick the top 3 by sentiment score. "
            "For each pick:\n"
            "  1. State the sentiment score and number of headlines analysed\n"
            "  2. Quote at least 2 specific headlines that drove the positive signal\n"
            "  3. Explain in plain English what the news implies for the stock\n\n"
            "Then produce a final proposal in this exact format:\n\n"
            "STRATEGY: Sentiment\n"
            "PICKS: <TICKER1>, <TICKER2>, <TICKER3>\n"
            "WEIGHTS: <w1>%, <w2>%, <w3>%  (must sum to 100, weight more to higher scores)\n"
            "RATIONALE: <per pick: score + 2 quoted headlines + 1-sentence market implication>\n"
            "RISK: <one sentence — e.g. sentiment can reverse rapidly on macro news>\n"
            "EXPLAINABILITY NOTE: All signals derived from keyword-scored headlines "
            "as required under SEBI Feb 2025 algo framework. No black-box model used.\n"
        ),
        expected_output=(
            "A structured proposal with STRATEGY, PICKS, WEIGHTS, RATIONALE, RISK, "
            "and EXPLAINABILITY NOTE sections."
        ),
        agent=agent,
    )


# ── Band message builder ──────────────────────────────────────────────────────

def proposal_to_band_message(crew_output: str) -> BandMessage:
    """
    Parse crew output and wrap in a BandMessage proposal.
    """
    payload = {"raw_output": crew_output, "strategy": "sentiment"}

    picks, weights      = [], []
    explainability_note = ""

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
        if line.startswith("EXPLAINABILITY NOTE:"):
            explainability_note = line.replace("EXPLAINABILITY NOTE:", "").strip()

    if picks:
        payload["picks"]   = picks
    if weights:
        payload["weights"] = weights
    if explainability_note:
        payload["explainability_note"] = explainability_note

    payload["signal_method"]  = "keyword_scored_headlines"
    payload["sebi_compliant"] = True

    return make_proposal(
        sender="sentiment_agent",
        strategy_name="Sentiment Strategy",
        description=f"Top sentiment picks: {', '.join(picks) if picks else 'see raw output'}",
        payload=payload,
    )


# ── Defense ───────────────────────────────────────────────────────────────────

def build_defense_task(agent: Agent, original_proposal: BandMessage, challenges: list[BandMessage]) -> Task:
    challenges_text = "\n".join([c.content for c in challenges])
    return Task(
        description=(
            f"You are defending your original Sentiment proposal against challenges from review agents.\n\n"
            f"ORIGINAL PROPOSAL:\n{original_proposal.payload.get('raw_output', original_proposal.content)}\n\n"
            f"CHALLENGES:\n{challenges_text}\n\n"
            "Analyze the challenges. If they highlight valid risks, modify your picks or weights to reduce risk. "
            "If you disagree with the challenge, defend your original picks.\n\n"
            "CRITICAL: Do not attempt to use any tools or call functions. You do not have access to any external tools for this task. "
            "Respond only with the text in the exact format requested below.\n\n"
            "You must output your final defense/revision in this exact format:\n\n"
            "REVISION SUMMARY: <1-2 sentences explaining how you addressed the challenges>\n"
            "STRATEGY: Sentiment\n"
            "PICKS: <TICKER1>, <TICKER2>, <TICKER3>\n"
            "WEIGHTS: <w1>%, <w2>%, <w3>%  (must sum to 100)\n"
            "RATIONALE: <per pick: score + 2 quoted headlines + 1-sentence market implication>\n"
            "RISK: <one sentence — e.g. sentiment can reverse rapidly on macro news>\n"
            "EXPLAINABILITY NOTE: All signals derived from keyword-scored headlines "
            "as required under SEBI Feb 2025 algo framework. No black-box model used.\n"
        ),
        expected_output="A structured defense and revised proposal.",
        agent=agent,
    )

def defense_to_band_message(crew_output: str) -> BandMessage:
    from band.message_schema import make_revision
    payload = {"raw_output": crew_output, "strategy": "sentiment"}
    
    summary = "Defended proposal"
    picks, weights = [], []
    explainability_note = ""
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
        if line.startswith("EXPLAINABILITY NOTE:"):
            explainability_note = line.replace("EXPLAINABILITY NOTE:", "").strip()
                
    if picks:
        payload["picks"] = picks
    if weights:
        payload["weights"] = weights
    if explainability_note:
        payload["explainability_note"] = explainability_note
        
    return make_revision(
        sender="sentiment_agent",
        strategy_name="Sentiment Strategy",
        changes=summary,
        payload=payload,
    )

def run_defense_agent(original_proposal: BandMessage, challenges: list[BandMessage]) -> BandMessage:
    agent = build_sentiment_agent(with_tools=False)
    task = build_defense_task(agent, original_proposal, challenges)
    crew = Crew(agents=[agent], tasks=[task], verbose=True)
    
    print("[sentiment_agent] Starting defense crew run...")
    result = crew.kickoff()
    
    output_text = str(result)
    band_msg = defense_to_band_message(output_text)
    
    print(f"[sentiment_agent] Defense ready → {band_msg.content}")
    return band_msg

# ── Runner ────────────────────────────────────────────────────────────────────

def run_sentiment_agent() -> BandMessage:
    """
    Runs the sentiment agent crew and returns a BandMessage ready to post.
    Call this from main.py or room_manager.py.
    """
    agent = build_sentiment_agent()
    task  = build_sentiment_task(agent)
    crew  = Crew(agents=[agent], tasks=[task], verbose=True)

    print("[sentiment_agent] Starting crew run...")
    result = crew.kickoff()

    output_text = str(result)
    band_msg    = proposal_to_band_message(output_text)

    print(f"[sentiment_agent] Proposal ready → {band_msg.content}")
    return band_msg


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== SentimentScanner direct test (no CrewAI) ===\n")
    print(sentiment_scanner.func("recent"))

    print("\n=== Band message shape ===\n")
    msg = make_proposal(
        sender="sentiment_agent",
        strategy_name="Sentiment Strategy",
        description="Test proposal",
        payload={
            "picks":               ["INFY.NS", "TCS.NS", "HDFCBANK.NS"],
            "weights":             [40, 35, 25],
            "signal_method":       "keyword_scored_headlines",
            "sebi_compliant":      True,
            "explainability_note": "All signals derived from keyword-scored headlines.",
        },
    )
    print(msg.model_dump_json(indent=2))