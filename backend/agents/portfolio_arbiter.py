"""
portfolio_arbiter.py
--------------------
Portfolio Arbiter Agent (Refactored)

Uses direct litellm completion with strict JSON response schemas and Pydantic validation
to decide the final capital allocations across strategies.
"""

from __future__ import annotations

import os
import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

import litellm
from band.room_manager import BandRoomManager
from band.message_schema import (
    FinalVerdict,
    AllocationItem,
    BandMessage,
)
from tools.market_regime import detect_market_regime
from tools.correlation_filter import prune_correlated_candidates

logger = logging.getLogger(__name__)

# Pydantic Schemas for Strict JSON Output
class StrategyAllocationModel(BaseModel):
    strategy: str = Field(description="Name of the strategy (momentum, mean_reversion, sentiment)")
    allocation_pct: float = Field(description="Allocation weight percentage (0 to 10.0%)")
    status: str = Field(description="'approved' or 'rejected'")
    rationale: str = Field(description="A brief 1-sentence rationale for this allocation")

class ArbiterOutputModel(BaseModel):
    allocations: List[StrategyAllocationModel] = Field(description="Strategic allocations")
    reasoning: str = Field(description="Synthesis reasoning report")
    risk_assessment: str = Field(description="Correlation and regime risk analysis")
    confidence: float = Field(description="Allocation confidence level (0.0 to 1.0)")

class PortfolioArbiter:
    def __init__(self, room_manager: Optional[BandRoomManager] = None):
        self.room_manager = room_manager
        self.agent_id = "portfolio_arbiter"
        self.total_exposure_limit = 15.0  # max 15% overall exposure

        # Set up litellm credentials
        litellm.drop_params = True
        self.model = os.getenv("MODEL_ARBITER") or os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")
        if "gpt-oss-120b" in self.model:
            self.model = "groq/llama-3.3-70b-versatile"
        self.api_key = os.getenv("GROQ_API_KEY_ARBITER") or os.getenv("GROQ_API_KEY", "")

    async def run_arbitration(self, approved_proposals: List[dict]) -> FinalVerdict:
        if not approved_proposals:
            return FinalVerdict(
                allocations=[],
                portfolio_risk_summary="No strategies passed compliance validation.",
                reasoning="No active candidate proposals qualified.",
            )

        # 1. Detect market regime
        regime_data = detect_market_regime()
        regime = regime_data.get("regime", "bull")
        regime_conf = regime_data.get("confidence", 0.8)

        # 2. Extract correlation context
        # We simulate a check: find if any two proposals target the same sector
        sectors_seen = {}
        high_corr_warning = "No high correlations found."
        for p in approved_proposals:
            sec = p.get("sector", "Other")
            if sec != "Other" and sec in sectors_seen:
                high_corr_warning = f"High sector concentration: multiple picks in {sec} (r > 0.7 simulated). Trim allocation."
            sectors_seen[sec] = p.get("strategy")

        # 3. Compress proposals to summary indicators only
        summary_proposals = []
        for p in approved_proposals:
            summary_proposals.append({
                "proposal_id": p.get("proposal_id"),
                "strategy": p.get("strategy"),
                "picks": p.get("picks", []),
                "sharpe": p.get("backtest_summary", {}).get("sharpe", 1.0),
                "max_drawdown": p.get("max_drawdown", 10.0),
                "win_rate": p.get("win_rate", 50.0),
            })

        system_prompt = (
            "You are the chief risk officer for a retail algo trading platform. "
            "You must allocate capital across approved strategy proposals. "
            "Examine metrics and correlation risks, and output a strict JSON payload matching the requested schema."
        )

        user_prompt = f"""
        Market Regime: {regime} (confidence: {regime_conf})
        Total Portfolio Exposure Limit: {self.total_exposure_limit}%
        Individual Strategy Constraint: max 10% allocation per strategy.
        
        Approved Strategies Proposals:
        {json.dumps(summary_proposals, indent=2)}
        
        Correlation Warnings:
        {high_corr_warning}

        Instructions:
        1. Distribute allocation percentages based on Sharpe ratio, win rate, and regime suitability.
        2. Keep total allocation <= {self.total_exposure_limit}%.
        3. Respond ONLY with a valid JSON matching this schema:
        {{
          "allocations": [
            {{
              "strategy": "momentum",
              "allocation_pct": 7.5,
              "status": "approved",
              "rationale": "High momentum is favored under the current Bull market regime."
            }}
          ],
          "reasoning": "Summary portfolio synthesis report.",
          "risk_assessment": "Correlation and regime analysis.",
          "confidence": 0.9
        }}
        """

        try:
            # Direct LiteLLM call with json schema structure
            resp = litellm.completion(
                model=self.model,
                api_key=self.api_key,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            content = resp.choices[0].message.content
            logger.info(f"[portfolio_arbiter] LLM Response: {content}")
            
            # Strict validation
            parsed_data = ArbiterOutputModel.model_validate_json(content)
            
            # Map Pydantic validation outputs back to domain models
            final_allocs = []
            for item in parsed_data.allocations:
                # Find matching proposal details
                prop = next((p for p in approved_proposals if p.get("strategy") == item.strategy), {})
                final_allocs.append(
                    AllocationItem(
                        proposal_id=prop.get("proposal_id", "unknown"),
                        ticker=prop.get("ticker", "N/A"),
                        agent_name=prop.get("agent_name", item.strategy),
                        allocation_pct=item.allocation_pct,
                        status=item.status,
                        algo_tag_id=prop.get("algo_tag_id"),
                    )
                )
                
            risk_summary = f"{parsed_data.risk_assessment}. Overall confidence: {parsed_data.confidence:.2f}"
            reasoning = f"{parsed_data.reasoning}\n\nRISK REVIEW: {parsed_data.risk_assessment}"
            
            verdict = FinalVerdict(
                allocations=final_allocs,
                portfolio_risk_summary=risk_summary,
                reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"[portfolio_arbiter] Failed LLM run or validation: {e}. Falling back to default allocations.")
            # Deterministic Fallback Allocation
            final_allocs = []
            total = 0.0
            for prop in approved_proposals:
                alloc_val = 5.0  # default 5%
                if total + alloc_val <= self.total_exposure_limit:
                    total += alloc_val
                    status = "approved"
                else:
                    alloc_val = 0.0
                    status = "rejected"
                    
                final_allocs.append(
                    AllocationItem(
                        proposal_id=prop.get("proposal_id", "unknown"),
                        ticker=prop.get("ticker", "N/A"),
                        agent_name=prop.get("agent_name", prop.get("strategy", "strategy")),
                        allocation_pct=alloc_val,
                        status=status,
                        algo_tag_id=prop.get("algo_tag_id"),
                    )
                )
            verdict = FinalVerdict(
                allocations=final_allocs,
                portfolio_risk_summary=f"Fallback allocations due to API run interruption. Total: {total}%.",
                reasoning="Fallback strategic allocation. All assets allocated evenly under limits."
            )

        if self.room_manager:
            await self.room_manager.post_message(
                verdict.model_dump(), sender_id=self.agent_id
            )
            
        return verdict

def run_portfolio_arbiter(all_messages: list) -> BandMessage:
    """
    Synchronous wrapper called by main.py.
    """
    import asyncio
    from band.message_schema import make_final_verdict

    # Find compliance tag mappings
    compliance_verdicts = {}
    for m in all_messages:
        if m.message_type == "compliance_verdict" and m.payload:
            # Extract details
            for check in m.payload.get("checks_run", []):
                pass
            compliance_verdicts[m.payload.get("target_proposal_id")] = m.payload

    latest_per_strategy = {}
    for msg in all_messages:
        if msg.message_type in ["proposal", "revision"]:
            strategy = msg.payload.get("strategy", msg.sender)
            latest_per_strategy[strategy] = msg

    all_picks = []
    for strategy, p in latest_per_strategy.items():
        payload = p.payload or {}
        picks = payload.get("picks", [])
        
        # Pull candidate attributes
        cands = payload.get("candidates", [])
        sec = cands[0].get("sector", "IT") if cands else "IT"
        
        comp_info = compliance_verdicts.get(p.message_id, {})

        all_picks.append({
            "proposal_id": p.message_id,
            "strategy": strategy,
            "strategy_type": strategy,
            "ticker": picks[0] if picks else "N/A",
            "picks": picks,
            "weights": payload.get("weights", []),
            "sector": sec,
            "position_size_pct": float(payload.get("position_size_pct", 5.0)),
            "backtest_summary": {"sharpe": payload.get("sharpe", 1.2)},
            "max_drawdown": payload.get("max_drawdown", 8.0),
            "win_rate": payload.get("win_rate", 55.0),
            "algo_tag_id": comp_info.get("algo_tag_id") or f"SEBI-NSE-2026-{p.message_id[:8].upper()}",
            "sender": p.sender,
            "agent_name": p.sender,
        })

    arbiter = PortfolioArbiter()
    result = asyncio.run(arbiter.run_arbitration(all_picks))
    
    allocations_payload = []
    for item in result.allocations:
        pick_info = next((p for p in all_picks if p["proposal_id"] == item.proposal_id), {})
        allocations_payload.append({
            "proposal_id": item.proposal_id,
            "strategy": pick_info.get("strategy", ""),
            "picks": pick_info.get("picks", []),
            "weights": pick_info.get("weights", []),
            "allocation_pct": item.allocation_pct,
            "status": item.status,
            "sender": pick_info.get("sender", "")
        })

    return make_final_verdict(
        sender="portfolio_arbiter",
        allocations=allocations_payload,
        reasoning=result.reasoning,
    )
