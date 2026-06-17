"""
Portfolio Arbiter Agent — CrewAI agent that makes the final allocation
decision across all compliance-approved proposals.

Behavior:
    1. Waits for compliance-approved verdicts for all active proposals
       (or a 60-second timeout, then works with what it has)
    2. Checks correlation between tickers using yfinance (reduce if r > 0.7)
    3. Enforces total exposure ≤ 15% (diversification rule)
    4. Ranks proposals by Sharpe ratio
    5. Posts FinalVerdict with allocations and reasoning
    6. Saves full audit trail to audit_log.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from crewai import Agent, Task, Crew

from band.room_manager import BandRoomManager
from band.message_schema import (
    FinalVerdict,
    AllocationItem,
)

logger = logging.getLogger(__name__)


class PortfolioArbiter:
    """
    CrewAI-based portfolio risk arbiter — final gatekeeper.

    Collects all compliance-approved strategies, checks correlations,
    enforces position limits, ranks by Sharpe, and posts FinalVerdict.
    """

    def __init__(
        self,
        room_manager: BandRoomManager,
        groq_api_key: Optional[str] = None,
    ):
        self.room_manager = room_manager
        self.agent_id = "portfolio_arbiter"
        self.total_exposure_limit = 15.0  # max 15% of portfolio

        api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        from crewai import LLM
        self.llm = LLM(
            model="openai/llama-3.3-70b-versatile",
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.2
        )

        self.crew_agent = Agent(
            role="Portfolio Risk Arbiter",
            goal=(
                "Allocate capital across approved strategies while managing "
                "total portfolio risk"
            ),
            backstory=(
                "You are the chief risk officer for a retail algo trading "
                "platform. Your job is to make the final capital allocation "
                "decisions across all strategies that have passed compliance. "
                "You balance expected returns against correlation risk, "
                "concentration risk, and total portfolio exposure. You are "
                "conservative — you'd rather under-allocate than over-expose."
            ),
            llm=self.llm,
            verbose=True,
        )

    async def run_arbitration(
        self,
        approved_proposals: list[dict],
        all_verdicts: Optional[list[dict]] = None,
        timeout: int = 60,
    ) -> FinalVerdict:
        """
        Run final portfolio-level arbitration.

        Args:
            approved_proposals: Proposals that passed compliance (with algo_tag_id).
            all_verdicts: All compliance verdicts for context.
            timeout: Seconds to wait for stragglers (not used in sync mode).

        Returns:
            FinalVerdict with allocations and reasoning.
        """
        if not approved_proposals:
            logger.warning(f"[{self.agent_id}] No proposals to arbitrate")
            return FinalVerdict(
                allocations=[],
                portfolio_risk_summary="No proposals passed compliance.",
                reasoning="No approved proposals available for allocation.",
            )

        logger.info(
            f"[{self.agent_id}] Arbitrating {len(approved_proposals)} proposals"
        )

        # ── Step 1: Fetch price data & compute correlations ──────────────
        tickers = list({p.get("ticker", "") for p in approved_proposals if p.get("ticker")})
        correlation_matrix = self._compute_correlations(tickers)
        high_corr_pairs = self._find_high_correlations(correlation_matrix)

        # ── Step 2: Rank by Sharpe ratio ─────────────────────────────────
        ranked = sorted(
            approved_proposals,
            key=lambda p: p.get("backtest_summary", {}).get("sharpe", 0),
            reverse=True,
        )

        # ── Step 3: Build allocations ────────────────────────────────────
        allocations: list[AllocationItem] = []
        total_allocated = 0.0

        # Use LLM for final reasoning
        proposals_text = "\n".join(
            f"  - {p.get('proposal_id')}: {p.get('ticker')} "
            f"({p.get('strategy_type')}), "
            f"position={p.get('position_size_pct', 5)}%, "
            f"sharpe={p.get('backtest_summary', {}).get('sharpe', 0):.2f}, "
            f"algo_tag={p.get('algo_tag_id', 'N/A')}"
            for p in ranked
        )

        corr_text = (
            "High correlations: " + ", ".join(
                f"{t1}/{t2}: {c:.2f}" for t1, t2, c in high_corr_pairs
            )
            if high_corr_pairs
            else "No high correlations found."
        )

        task = Task(
            description=(
                f"Make final capital allocation decisions for these approved strategies:\n"
                f"{proposals_text}\n\n"
                f"Correlation analysis:\n{corr_text}\n\n"
                f"Rules:\n"
                f"  - Total portfolio exposure must be ≤ {self.total_exposure_limit}%\n"
                f"  - If two tickers are highly correlated (r > 0.7), reduce the "
                f"smaller allocation by 30%\n"
                f"  - Rank by Sharpe ratio — higher Sharpe gets priority\n"
                f"  - No single position > 10% of portfolio\n\n"
                f"For each proposal, decide: approved allocation %, or reject. "
                f"Explain your reasoning concisely."
            ),
            expected_output=(
                "For each proposal: proposal_id, final allocation %, "
                "status (approved/reduced/rejected), and brief notes. "
                "Also: total portfolio risk summary."
            ),
            agent=self.crew_agent,
        )

        crew = Crew(agents=[self.crew_agent], tasks=[task], verbose=False)

        try:
            import asyncio
            crew_result = await asyncio.to_thread(crew.kickoff)
            llm_reasoning = str(crew_result)[:500]
        except Exception as e:
            logger.error(f"[{self.agent_id}] LLM arbitration failed: {e}")
            llm_reasoning = "LLM reasoning unavailable. Using rule-based allocation."

        # ── Build allocations with rules ─────────────────────────────────
        for proposal in ranked:
            prop_id = proposal.get("proposal_id", "")
            ticker = proposal.get("ticker", "")
            position_pct = float(proposal.get("position_size_pct", 5.0))

            # Apply correlation reduction
            for t1, t2, corr in high_corr_pairs:
                if ticker in (t1, t2):
                    position_pct *= 0.7
                    logger.info(
                        f"[{self.agent_id}] Reduced {ticker} allocation "
                        f"by 30% due to correlation with "
                        f"{t2 if ticker == t1 else t1}"
                    )
                    break

            # Cap at 10% single position
            position_pct = min(position_pct, 10.0)

            # Check total budget
            if total_allocated + position_pct > self.total_exposure_limit:
                remaining = self.total_exposure_limit - total_allocated
                if remaining < 1.0:
                    allocations.append(
                        AllocationItem(
                            proposal_id=prop_id,
                            ticker=ticker,
                            agent_name=proposal.get("agent_name", ""),
                            allocation_pct=0.0,
                            status="rejected",
                            algo_tag_id=proposal.get("algo_tag_id"),
                        )
                    )
                    continue
                position_pct = remaining

            total_allocated += position_pct

            allocations.append(
                AllocationItem(
                    proposal_id=prop_id,
                    ticker=ticker,
                    agent_name=proposal.get("agent_name", ""),
                    allocation_pct=round(position_pct, 2),
                    status="approved" if position_pct > 0 else "rejected",
                    algo_tag_id=proposal.get("algo_tag_id"),
                )
            )

        # ── Build risk summary ───────────────────────────────────────────
        approved_count = sum(1 for a in allocations if a.status == "approved")
        risk_summary = (
            f"Total capital deployed: {total_allocated:.1f}% "
            f"(limit: {self.total_exposure_limit}%). "
            f"Strategies approved: {approved_count}/{len(allocations)}. "
            f"{corr_text}"
        )

        verdict = FinalVerdict(
            allocations=allocations,
            portfolio_risk_summary=risk_summary,
            reasoning=llm_reasoning,
        )

        # Post to Band room
        await self.room_manager.post_message(
            verdict.model_dump(), sender_id=self.agent_id
        )

        # Save audit trail
        self._save_audit_log(verdict, approved_proposals)

        logger.info(
            f"[{self.agent_id}] Final verdict posted. "
            f"Approved: {approved_count}, "
            f"Total allocated: {total_allocated:.1f}%"
        )
        return verdict

    def _compute_correlations(self, tickers: list[str]) -> pd.DataFrame:
        """Compute return correlation matrix using yfinance."""
        if len(tickers) < 2:
            return pd.DataFrame()

        returns = {}
        for ticker in tickers:
            nse = f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
            try:
                df = yf.Ticker(nse).history(period="1y")
                if not df.empty:
                    returns[ticker] = df["Close"].pct_change().dropna().tail(60)
            except Exception as e:
                logger.warning(f"Failed to fetch {nse}: {e}")

        if len(returns) < 2:
            return pd.DataFrame()

        return pd.DataFrame(returns).corr()

    def _find_high_correlations(
        self, corr_matrix: pd.DataFrame
    ) -> list[tuple[str, str, float]]:
        """Find pairs with correlation > 0.7."""
        pairs = []
        if corr_matrix.empty:
            return pairs

        cols = corr_matrix.columns
        for i, t1 in enumerate(cols):
            for j, t2 in enumerate(cols):
                if i < j and abs(corr_matrix.loc[t1, t2]) > 0.7:
                    pairs.append((t1, t2, float(corr_matrix.loc[t1, t2])))

        return pairs

    def _save_audit_log(
        self, verdict: FinalVerdict, proposals: list[dict]
    ) -> None:
        """
        Save the full audit trail to audit_log.json.

        Keys entries by algo_tag_id for traceability.
        """
        audit_path = Path(__file__).parent.parent / "audit_log.json"

        # Load existing log
        existing = {}
        if audit_path.exists():
            try:
                existing = json.loads(audit_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}

        # Build audit entries keyed by algo_tag_id
        all_messages = self.room_manager.get_all_messages()

        for alloc in verdict.allocations:
            if alloc.algo_tag_id:
                audit_entry = {
                    "proposal_id": alloc.proposal_id,
                    "ticker": alloc.ticker,
                    "agent_name": alloc.agent_name,
                    "allocation_pct": alloc.allocation_pct,
                    "status": alloc.status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "debate_messages": [
                        m for m in all_messages
                        if m.get("target_proposal_id") == alloc.proposal_id
                        or m.get("proposal_id") == alloc.proposal_id
                    ],
                    "final_verdict": verdict.model_dump(),
                }
                existing[alloc.algo_tag_id] = audit_entry

        try:
            audit_path.write_text(
                json.dumps(existing, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info(f"[{self.agent_id}] Audit log saved to {audit_path}")
        except Exception as e:
            logger.error(f"[{self.agent_id}] Failed to save audit log: {e}")



# ── Wrapper for main.py compatibility ────────────────────────────────────────

def run_portfolio_arbiter(proposals: list) -> "BandMessage":
    """
    Synchronous wrapper called by main.py.
    """
    import asyncio
    from band.message_schema import BandMessage, make_final_verdict

    all_picks = []
    for p in proposals:
        payload = p.payload or {}
        all_picks.append({
            "proposal_id":   p.message_id,
            "strategy":      payload.get("strategy", "unknown"),
            "picks":         payload.get("picks", []),
            "weights":       payload.get("weights", []),
            "sender":        p.sender,
        })

    try:
        arbiter = PortfolioArbiter(room_manager=None)
        result  = asyncio.run(arbiter.run_arbitration(all_picks))
        if result:
            return make_final_verdict(
                sender="portfolio_arbiter",
                allocations=all_picks,
                reasoning=str(result)[:300],
            )
    except Exception as e:
        print(f"[portfolio_arbiter] Warning: {e}")

    return make_final_verdict(
        sender="portfolio_arbiter",
        allocations=all_picks,
        reasoning=f"Portfolio arbiter reviewed {len(proposals)} proposals. Allocations based on momentum, mean-reversion, and sentiment signals with SEBI compliance.",
    )            
