"""
SEBI Rules Tool — Pure deterministic Python compliance checks.

NO LLM calls here. All logic is based on SEBI's Feb 2025 framework
for algorithmic trading by retail investors.

Functions:
    check_order_frequency   — order rate vs 10/sec threshold
    check_explainability    — black-box vs transparent classification
    generate_algo_tag_id    — SEBI-style unique algo tag
    check_position_limits   — single position % of portfolio
    run_all_checks          — run everything, return list of results
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


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
        dict with {compliant: bool, category: str, message: str}
    """
    # Convert to orders/sec (6.5 hr trading day = 23,400 seconds)
    TRADING_SECONDS_PER_DAY = 23_400
    orders_per_sec = orders_per_day / TRADING_SECONDS_PER_DAY
    THRESHOLD = 10.0  # orders per second

    if orders_per_sec < THRESHOLD:
        return {
            "compliant": True,
            "category": "tech_savvy_retail",
            "message": (
                f"Order frequency: {orders_per_sec:.4f} orders/sec "
                f"({orders_per_day:.0f}/day). Well under the 10 orders/sec "
                f"threshold for tech-savvy retail. Light registration applies."
            ),
        }
    else:
        return {
            "compliant": False,
            "category": "requires_full_registration",
            "message": (
                f"Order frequency: {orders_per_sec:.2f} orders/sec "
                f"({orders_per_day:.0f}/day). EXCEEDS the 10 orders/sec "
                f"retail threshold. Full exchange algo registration required "
                f"under SEBI/HO/MRD/TPD-1 Rule 1."
            ),
        }


def check_explainability(
    strategy_description: str,
    is_llm_based: bool,
) -> dict:
    """
    Classify an algorithm as black-box or transparent.

    Rule:
        - LLM-based or opaque logic = potential "black box" →
          requires Research Analyst (RA) registration under SEBI.
        - Rule-based with clear conditions = transparent / white-box.

    Args:
        strategy_description: Plain-text description of the strategy logic.
        is_llm_based: Whether the strategy uses LLM/ML for decision-making.

    Returns:
        dict with {compliant: bool, classification: str, message: str}
    """
    # Black-box indicators
    BLACK_BOX_KEYWORDS = [
        "neural network", "deep learning", "machine learning",
        "language model", "llm", "gpt", "claude", "transformer",
        "model predicts", "model-dependent", "ai-driven",
        "black box", "opaque", "proprietary model",
    ]

    description_lower = strategy_description.lower()
    found_keywords = [
        kw for kw in BLACK_BOX_KEYWORDS if kw in description_lower
    ]

    is_black_box = is_llm_based or bool(found_keywords)

    if is_black_box:
        reasons = []
        if is_llm_based:
            reasons.append("Strategy is flagged as LLM-based")
        if found_keywords:
            reasons.append(
                f"Description contains black-box indicators: {found_keywords}"
            )

        return {
            "compliant": False,
            "classification": "black_box",
            "message": (
                f"Strategy classified as BLACK-BOX. {'; '.join(reasons)}. "
                f"Under SEBI/HO/MRD/TPD-1 Rule 2, the algo provider must "
                f"register as a Research Analyst (RA) with SEBI. "
                f"Alternatively, convert to a white-box strategy with "
                f"explicit, auditable entry/exit rules."
            ),
        }
    else:
        return {
            "compliant": True,
            "classification": "transparent",
            "message": (
                f"Strategy classified as TRANSPARENT (white-box). "
                f"Rule-based logic with auditable conditions. "
                f"No RA registration required."
            ),
        }


def generate_algo_tag_id(proposal_id: str, ticker: str) -> str:
    """
    Generate a SEBI-style unique algo tag ID for audit trail.

    Format: NSE-ALGO-{year}-{uuid[:8].upper()}

    Args:
        proposal_id: The proposal being approved.
        ticker: The stock ticker.

    Returns:
        A unique algo tag string (e.g., "NSE-ALGO-2026-A1B2C3D4").
    """
    year = datetime.now(timezone.utc).year
    unique_part = uuid.uuid4().hex[:8].upper()
    return f"NSE-ALGO-{year}-{unique_part}"


def check_position_limits(position_size_pct: float) -> dict:
    """
    Check position sizing against SEBI portfolio concentration limits.

    Rule:
        - Single position > 10% of portfolio = FLAGGED (warning)
        - Single position > 20% of portfolio = REJECTED (hard limit)
        - Otherwise = compliant

    Args:
        position_size_pct: Proposed position size as % of total portfolio.

    Returns:
        dict with {compliant: bool, severity: str, message: str}
    """
    if position_size_pct > 20.0:
        return {
            "compliant": False,
            "severity": "rejected",
            "message": (
                f"Position size {position_size_pct}% EXCEEDS the 20% hard "
                f"limit for a single algorithmic strategy. Under SEBI "
                f"guidelines, no single algo strategy should deploy more "
                f"than 20% of total portfolio value. This proposal is "
                f"REJECTED — reduce position size below 20%."
            ),
        }
    elif position_size_pct > 10.0:
        return {
            "compliant": True,  # not rejected, but flagged
            "severity": "flagged",
            "message": (
                f"Position size {position_size_pct}% exceeds the recommended "
                f"10% limit for a single position. While not a hard rejection, "
                f"SEBI guidelines recommend no single algo strategy deploy "
                f"more than 10% of portfolio. Consider reducing position size."
            ),
        }
    else:
        return {
            "compliant": True,
            "severity": "ok",
            "message": (
                f"Position size {position_size_pct}% is within the "
                f"recommended 10% single-position limit. Compliant."
            ),
        }


def run_all_checks(proposal: dict) -> list[dict]:
    """
    Run all SEBI compliance checks on a proposal.

    Args:
        proposal: A proposal dict containing at minimum:
            - strategy_type (str)
            - ticker (str)
            - position_size_pct (float)
            - entry_condition (str)
            - exit_condition (str)
            - reasoning (str)
            - stop_loss_pct (float)

    Returns:
        List of dicts, each with {check_name, passed, message}.
    """
    results = []

    # ── Check 1: Order Frequency ─────────────────────────────────────────
    # Investment-style algos typically do 1-5 orders/day
    # We estimate based on strategy type
    strategy_type = proposal.get("strategy_type", "unknown")
    if strategy_type == "momentum":
        estimated_orders = 2.0  # momentum = low frequency
    elif strategy_type == "mean_reversion":
        estimated_orders = 5.0  # slightly more active
    elif strategy_type == "sentiment":
        estimated_orders = 3.0  # event-driven
    else:
        estimated_orders = 5.0  # conservative estimate

    freq_check = check_order_frequency(estimated_orders)
    results.append({
        "check_name": "order_frequency",
        "passed": freq_check["compliant"],
        "message": freq_check["message"],
    })

    # ── Check 2: Explainability / Black-Box ──────────────────────────────
    # Build the strategy description from available fields
    description_parts = [
        proposal.get("entry_condition", ""),
        proposal.get("exit_condition", ""),
        proposal.get("reasoning", ""),
    ]
    full_description = " ".join(filter(None, description_parts))

    # Heuristic: sentiment strategies mentioning AI/LLM are LLM-based
    is_llm = strategy_type == "sentiment" and any(
        kw in full_description.lower()
        for kw in ["llm", "language model", "ai", "gpt", "claude", "model"]
    )

    explain_check = check_explainability(full_description, is_llm)
    results.append({
        "check_name": "explainability",
        "passed": explain_check["compliant"],
        "message": explain_check["message"],
    })

    # ── Check 3: Position Limits ─────────────────────────────────────────
    position_pct = proposal.get("position_size_pct", 5.0)
    pos_check = check_position_limits(position_pct)
    results.append({
        "check_name": "position_limits",
        "passed": pos_check["compliant"],
        "message": pos_check["message"],
    })

    # ── Check 4: Audit Trail Readiness ───────────────────────────────────
    # Verify proposal has all fields needed for exchange registration
    required_fields = [
        "ticker", "entry_condition", "exit_condition",
        "stop_loss_pct", "strategy_type",
    ]
    missing = [f for f in required_fields if not proposal.get(f)]

    if missing:
        results.append({
            "check_name": "audit_trail_readiness",
            "passed": False,
            "message": (
                f"Missing required fields for exchange registration and "
                f"audit trail: {missing}. Under SEBI/HO/MRD/TPD-1 Rules 3&4, "
                f"all algo strategies must have complete documentation."
            ),
        })
    else:
        results.append({
            "check_name": "audit_trail_readiness",
            "passed": True,
            "message": (
                "All required fields present for exchange registration "
                "and order tagging. Algo Tag ID can be assigned upon approval."
            ),
        })

    return results
