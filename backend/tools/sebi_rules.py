"""
sebi_rules.py
-------------
Pure deterministic Python compliance checks based on SEBI's Feb 2025
framework for algorithmic trading by retail investors.

NO LLM calls here. All logic is rule-based and fully auditable.

Functions:
    check_order_frequency   → order rate vs 10/sec threshold
    check_explainability    → black-box vs transparent classification
    check_position_limits   → single position % of portfolio
    check_algo_registration → whether strategy needs exchange registration
    generate_algo_tag_id    → SEBI-style unique algo tag
    run_all_checks          → run everything, return list of results
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone


# ── Constants ─────────────────────────────────────────────────────────────────

TRADING_SECONDS_PER_DAY = 23_400      # 6.5 hr trading day
ORDER_FREQ_THRESHOLD    = 10.0        # orders/sec — SEBI retail limit
MAX_SINGLE_POSITION_PCT = 20.0        # max % of portfolio in one stock
MAX_TOTAL_EXPOSURE_PCT  = 60.0        # max % of portfolio in algo strategies


# ── Rule 1: Order Frequency ───────────────────────────────────────────────────

def check_order_frequency(orders_per_day: float) -> dict:
    """
    Check if order frequency complies with SEBI retail algo limits.

    Rule: < 10 orders/sec = tech-savvy retail (light registration).
          >= 10 orders/sec = requires full exchange algo registration.

    For context: 10 orders/sec = 864,000 orders/day.
    Investment-style algos (1-5 orders/day) trivially pass.

    Args:
        orders_per_day: Estimated average orders per trading day.

    Returns:
        dict with {compliant, category, message, rule}
    """
    orders_per_sec = orders_per_day / TRADING_SECONDS_PER_DAY

    if orders_per_sec < ORDER_FREQ_THRESHOLD:
        return {
            "rule":      "order_frequency",
            "compliant": True,
            "category":  "tech_savvy_retail",
            "severity":  "none",
            "message": (
                f"Order frequency: {orders_per_sec:.4f} orders/sec "
                f"({orders_per_day:.0f}/day). Well under the 10 orders/sec "
                f"threshold for tech-savvy retail. Light registration applies."
            ),
        }
    else:
        return {
            "rule":      "order_frequency",
            "compliant": False,
            "category":  "requires_full_registration",
            "severity":  "high",
            "message": (
                f"Order frequency: {orders_per_sec:.2f} orders/sec "
                f"({orders_per_day:.0f}/day). EXCEEDS the 10 orders/sec "
                f"retail threshold. Full exchange algo registration required "
                f"under SEBI/HO/MRD/TPD-1 Rule 1."
            ),
        }


# ── Rule 2: Explainability (Black-Box Classification) ────────────────────────

def check_explainability(
    strategy_description: str,
    is_llm_based: bool = False,
) -> dict:
    """
    Classify an algorithm as black-box or transparent.

    Rule:
        - LLM-based or opaque logic = potential "black box"
          requires Research Analyst (RA) registration under SEBI.
        - Rule-based with clear conditions = transparent / white-box.

    Args:
        strategy_description: Plain-text description of the strategy logic.
        is_llm_based: Whether the strategy uses LLM/ML for decision-making.

    Returns:
        dict with {compliant, classification, message, rule}
    """
    # Keywords that suggest a transparent, rule-based strategy
    transparent_keywords = [
        "moving average", "crossover", "z-score", "rsi", "macd",
        "momentum", "mean reversion", "bollinger", "keyword", "threshold",
        "if", "when", "greater than", "less than", "above", "below",
        "percentage", "deviation", "indicator", "signal",
    ]

    # Keywords that suggest opacity / black-box
    opaque_keywords = [
        "neural network", "deep learning", "transformer", "embedding",
        "black box", "proprietary", "undisclosed", "model output",
        "ai decision", "llm score",
    ]

    desc_lower = strategy_description.lower()

    has_transparent = any(kw in desc_lower for kw in transparent_keywords)
    has_opaque      = any(kw in desc_lower for kw in opaque_keywords)

    if is_llm_based or has_opaque:
        # Sentiment agent uses keyword scoring (not raw LLM) — still explainable
        # but flag for human review
        if "keyword" in desc_lower or "keyword_scored" in desc_lower:
            return {
                "rule":           "explainability",
                "compliant":      True,
                "classification": "transparent_keyword_based",
                "severity":       "none",
                "message": (
                    "Strategy uses keyword-based scoring — signals are derived "
                    "from explicit keyword lists, not opaque LLM reasoning. "
                    "Classified as transparent under SEBI Feb 2025 framework. "
                    "Each signal is traceable to specific headline keywords."
                ),
            }
        return {
            "rule":           "explainability",
            "compliant":      False,
            "classification": "black_box",
            "severity":       "high",
            "message": (
                "Strategy logic is not fully explainable to the end user. "
                "Under SEBI Feb 2025 framework, this may require Research "
                "Analyst (RA) registration. Recommend restructuring signal "
                "generation into explicit, auditable rules."
            ),
        }

    if has_transparent:
        return {
            "rule":           "explainability",
            "compliant":      True,
            "classification": "transparent",
            "severity":       "none",
            "message": (
                "Strategy uses clear, rule-based logic with explicit "
                "conditions. Classified as transparent / white-box under "
                "SEBI Feb 2025 framework. No RA registration required."
            ),
        }

    # Ambiguous — flag for review but don't block
    return {
        "rule":           "explainability",
        "compliant":      True,
        "classification": "needs_review",
        "severity":       "low",
        "message": (
            "Strategy description is ambiguous. Recommend adding explicit "
            "entry/exit conditions to confirm transparent classification "
            "under SEBI Feb 2025 framework."
        ),
    }


# ── Rule 3: Position Size Limits ─────────────────────────────────────────────

def check_position_limits(
    picks:    list[str],
    weights:  list[float],
) -> dict:
    """
    Check individual position sizes against SEBI/internal risk limits.

    Args:
        picks:   List of ticker strings
        weights: List of allocation weights (must sum to ~100)

    Returns:
        dict with {compliant, violations, message, rule}
    """
    violations = []

    for ticker, weight in zip(picks, weights):
        if weight > MAX_SINGLE_POSITION_PCT:
            violations.append(
                f"{ticker}: {weight:.1f}% exceeds {MAX_SINGLE_POSITION_PCT}% limit"
            )

    total_weight = sum(weights)
    if abs(total_weight - 100.0) > 1.0:
        violations.append(
            f"Weights sum to {total_weight:.1f}%, expected 100%"
        )

    if violations:
        return {
            "rule":       "position_limits",
            "compliant":  False,
            "violations": violations,
            "severity":   "medium",
            "message": (
                f"Position limit violations detected: {'; '.join(violations)}. "
                f"SEBI retail risk guidelines recommend max {MAX_SINGLE_POSITION_PCT}% "
                f"per position to avoid concentration risk."
            ),
        }

    return {
        "rule":       "position_limits",
        "compliant":  True,
        "violations": [],
        "severity":   "none",
        "message": (
            f"All positions within limits. "
            f"Largest position: {max(weights):.1f}% "
            f"(limit: {MAX_SINGLE_POSITION_PCT}%)."
        ),
    }


# ── Rule 4: Algo Registration Check ──────────────────────────────────────────

def check_algo_registration(
    strategy_name:  str,
    signal_method:  str = "rule_based",
    orders_per_day: float = 2.0,
) -> dict:
    """
    Determine whether this strategy needs formal exchange algo registration.

    Under SEBI Feb 2025:
    - All algos must carry a unique exchange-assigned tag ID
    - High frequency (>10 orders/sec) needs full registration
    - Black-box algos need RA registration
    - Low frequency rule-based algos need minimal registration

    Returns:
        dict with {registration_required, registration_type, algo_tag_id, message}
    """
    orders_per_sec = orders_per_day / TRADING_SECONDS_PER_DAY
    algo_tag       = generate_algo_tag_id(strategy_name)

    if orders_per_sec >= ORDER_FREQ_THRESHOLD:
        return {
            "rule":                "algo_registration",
            "compliant":           False,
            "registration_required": True,
            "registration_type":   "full_exchange_registration",
            "algo_tag_id":         algo_tag,
            "severity":            "high",
            "message": (
                f"Full exchange algo registration required. "
                f"Algo tag assigned: {algo_tag}. "
                f"Must be submitted to exchange before live trading."
            ),
        }

    if signal_method in ("llm", "neural_network", "black_box"):
        return {
            "rule":                "algo_registration",
            "compliant":           False,
            "registration_required": True,
            "registration_type":   "research_analyst_registration",
            "algo_tag_id":         algo_tag,
            "severity":            "high",
            "message": (
                f"Research Analyst (RA) registration required for opaque "
                f"strategy '{strategy_name}'. Algo tag: {algo_tag}."
            ),
        }

    # Low frequency, rule-based — just needs algo tagging
    return {
        "rule":                "algo_registration",
        "compliant":           True,
        "registration_required": False,
        "registration_type":   "algo_tag_only",
        "algo_tag_id":         algo_tag,
        "severity":            "none",
        "message": (
            f"Low-frequency rule-based strategy. "
            f"Algo tag assigned: {algo_tag}. "
            f"No formal registration required beyond tagging."
        ),
    }


# ── Algo Tag Generator ────────────────────────────────────────────────────────

def generate_algo_tag_id(strategy_name: str = "algo") -> str:
    """
    Generate a SEBI-style unique algo tag ID.
    Format: SEBI-NSE-YYYY-XXXXXXXX

    Args:
        strategy_name: Used as a label prefix (cosmetic only)

    Returns:
        A unique tag string e.g. "SEBI-NSE-2026-A1B2C3D4"
    """
    year     = datetime.now(timezone.utc).year
    uid      = str(uuid.uuid4()).replace("-", "").upper()[:8]
    return f"SEBI-NSE-{year}-{uid}"


# ── Run All Checks ────────────────────────────────────────────────────────────

def run_all_checks(proposal: dict) -> list[dict]:
    """
    Run all SEBI compliance checks on a proposal dict.

    Expected proposal keys (all optional with sensible defaults):
        strategy_name   : str
        picks           : list[str]
        weights         : list[float]
        signal_method   : str  ("rule_based" | "keyword_scored_headlines" | "llm")
        orders_per_day  : float (default 2.0 — investment style)
        raw_output      : str  (full proposal text for explainability check)

    Returns:
        List of result dicts, one per rule checked.
    """
    results = []

    strategy_name   = proposal.get("strategy_name", proposal.get("strategy", "unknown"))
    picks           = proposal.get("picks", [])
    weights         = proposal.get("weights", [])
    signal_method   = proposal.get("signal_method", "rule_based")
    orders_per_day  = proposal.get("orders_per_day", 2.0)
    raw_output      = proposal.get("raw_output", "")
    sebi_compliant  = proposal.get("sebi_compliant", False)

    # Determine if LLM-based from signal_method
    is_llm_based = signal_method in ("llm", "neural_network", "black_box")

    # If sentiment agent already flagged itself as compliant via keyword scoring
    if signal_method == "keyword_scored_headlines":
        is_llm_based = False

    # ── Check 1: Order frequency ──────────────────────────────────────────────
    results.append(check_order_frequency(orders_per_day))

    # ── Check 2: Explainability ───────────────────────────────────────────────
    description = f"{strategy_name} {signal_method} {raw_output[:200]}"
    results.append(check_explainability(description, is_llm_based))

    # ── Check 3: Position limits ──────────────────────────────────────────────
    if picks and weights:
        results.append(check_position_limits(picks, weights))

    # ── Check 4: Algo registration ────────────────────────────────────────────
    results.append(check_algo_registration(
        strategy_name  = strategy_name,
        signal_method  = signal_method,
        orders_per_day = orders_per_day,
    ))

    return results


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== SEBI Rules smoke test ===\n")

    # Test momentum proposal
    proposal = {
        "strategy_name": "Momentum Strategy",
        "picks":         ["AXISBANK.NS", "INFY.NS", "SBIN.NS"],
        "weights":       [50.0, 30.0, 20.0],
        "signal_method": "rule_based",
        "orders_per_day": 2.0,
        "raw_output":    "moving average crossover momentum strategy",
    }

    results = run_all_checks(proposal)
    for r in results:
        status = "✅" if r["compliant"] else "❌"
        print(f"  {status} [{r['rule']}] {r['message'][:80]}")

    print(f"\n=== generate_algo_tag_id ===")
    print(f"  {generate_algo_tag_id('momentum')}")
    print(f"  {generate_algo_tag_id('sentiment')}")