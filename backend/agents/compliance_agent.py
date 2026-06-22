"""
compliance_agent.py
-------------------
Compliance Agent (Refactored)

Checks strategy proposals against deterministic SEBI algorithmic circular guidelines,
returning structured ComplianceVerdict messages without LLM calls.
"""

import logging
from typing import Optional

from band.room_manager import BandRoomManager
from band.message_schema import (
    ComplianceVerdict,
    ComplianceCheckResult,
    BandMessage,
)
from tools.sebi_rules import run_all_checks, generate_algo_tag_id

logger = logging.getLogger(__name__)

class ComplianceAgent:
    def __init__(self, room_manager: Optional[BandRoomManager] = None):
        self.room_manager = room_manager
        self.agent_id = "compliance_agent"
        self._revision_tracker = {}
        self.max_revision_rounds = 2

    async def check_proposal(self, proposal_data: dict) -> ComplianceVerdict:
        proposal_id = proposal_data.get("proposal_id", "unknown")
        ticker = proposal_data.get("ticker", "UNKNOWN")

        logger.info(f"[compliance_agent] Running SEBI validation on {proposal_id} ({ticker})")

        # Step 1: Run deterministic SEBI rules validation
        deterministic_results = run_all_checks(proposal_data)

        # Log check details for diagnostics
        logger.info(f"[compliance_agent] Diagnosis for {proposal_data.get('strategy')}: "
                    f"picks={proposal_data.get('picks')}, "
                    f"weights={proposal_data.get('weights')}, "
                    f"results={[{c['check_name']: c['passed'] for c in deterministic_results}]}")

        checks_run = []
        has_failure = False

        for check in deterministic_results:
            passed = check["passed"]
            if not passed:
                has_failure = True

            checks_run.append(
                ComplianceCheckResult(
                    check_name=check["check_name"],
                    passed=passed,
                    message=check["message"],
                )
            )

        # Step 2: Determine verdict
        if not has_failure:
            status = "approved"
            algo_tag = generate_algo_tag_id(f"{proposal_id}-{ticker}")
            reasoning = f"All compliance validation steps successfully passed under SEBI retail guidelines. Tag: {algo_tag}"
            required_action = None
        else:
            # We flag for revision so strategy agent defense updates weights
            status = "flagged"
            algo_tag = None
            reasoning = "Deterministic audit flagged position sizing or parameter constraints. Revision required."
            required_action = "; ".join(c["message"] for c in deterministic_results if not c["passed"])

        verdict = ComplianceVerdict(
            target_proposal_id=proposal_id,
            status=status,
            checks_run=checks_run,
            reasoning=reasoning,
            required_action=required_action,
            algo_tag_id=algo_tag,
        )

        if self.room_manager:
            await self.room_manager.post_message(
                verdict.model_dump(), sender_id=self.agent_id
            )

        return verdict

    async def handle_revision(self, revision_data: dict, original_proposal: dict) -> ComplianceVerdict:
        proposal_id = revision_data.get("original_proposal_id", "unknown")
        current_round = self._revision_tracker.get(proposal_id, 0) + 1
        self._revision_tracker[proposal_id] = current_round

        if current_round > self.max_revision_rounds:
            verdict = ComplianceVerdict(
                target_proposal_id=proposal_id,
                status="rejected",
                checks_run=[],
                reasoning=f"Proposal rejected. Maximum compliance revision rounds ({self.max_revision_rounds}) exceeded.",
                required_action="Fundamental strategy redesign required.",
            )
            if self.room_manager:
                await self.room_manager.post_message(
                    verdict.model_dump(), sender_id=self.agent_id
                )
            return verdict

        # Merge changes
        updated_proposal = dict(original_proposal)
        if revision_data.get("payload", {}).get("weights"):
            updated_proposal["weights"] = revision_data["payload"]["weights"]
        if revision_data.get("payload", {}).get("position_size_pct"):
            updated_proposal["position_size_pct"] = revision_data["payload"]["position_size_pct"]

        # Recheck
        return await self.check_proposal(updated_proposal)

def run_compliance_agent(all_messages: list) -> BandMessage:
    """
    Synchronous entry point called by main.py.
    """
    import asyncio
    from band.message_schema import make_compliance_verdict

    latest_per_strategy = {}
    for msg in all_messages:
        if msg.message_type in ["proposal", "revision"]:
            strategy = msg.payload.get("strategy", msg.sender)
            latest_per_strategy[strategy] = msg

    verdicts = []
    for strategy, proposal in latest_per_strategy.items():
        payload = proposal.payload or {}
        picks = payload.get("picks", ["UNKNOWN"])
        ticker = picks[0] if picks else "UNKNOWN"

        proposal_data = {
            "proposal_id": proposal.message_id,
            "strategy": payload.get("strategy", "unknown"),
            "ticker": ticker,
            "picks": picks,
            "weights": payload.get("weights", []),
            "signal_method": payload.get("signal_method", "rule_based"),
            "sebi_compliant": payload.get("sebi_compliant", False),
            "position_size_pct": float(payload.get("position_size_pct", 5.0)),
        }

        agent = ComplianceAgent()
        result = asyncio.run(agent.check_proposal(proposal_data))
        if result:
            verdicts.append(result)

    approved = len([v for v in verdicts if v.status == "approved"])
    total = len(latest_per_strategy)

    return make_compliance_verdict(
        sender="compliance_agent",
        target_strategy="all_proposals",
        status="approved" if approved == total else "flagged",
        reasoning=f"{approved}/{total} proposals passed SEBI compliance checks.",
    )
