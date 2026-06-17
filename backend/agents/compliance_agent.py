"""
Compliance Agent — CrewAI agent that checks proposals against SEBI rules.

Uses BOTH:
    1. Deterministic checks (sebi_rules.py) — hard pass/fail
    2. RAG-grounded LLM reasoning (rag_retriever.py) — for borderline cases

Behavior:
    - Waits for proposals where challenges are resolved
    - Runs all deterministic checks via SEBIRulesTool
    - For flagged/borderline checks, queries RAG for rule text → LLM reasons
    - Posts ComplianceVerdict: approved → generates algo_tag_id
    - Tracks revision rounds per proposal (max 2 before rejecting)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

from crewai import Agent, Task, Crew
from crewai.tools import BaseTool

from band.room_manager import BandRoomManager
from band.message_schema import (
    ComplianceVerdict,
    ComplianceCheckResult,
)
from tools.sebi_rules import run_all_checks, generate_algo_tag_id
from knowledge_base.rag_retriever import get_knowledge_base

logger = logging.getLogger(__name__)


# ── CrewAI Tools ─────────────────────────────────────────────────────────────


class SEBIRulesTool(BaseTool):
    """
    Wraps sebi_rules.run_all_checks for CrewAI.
    Runs all deterministic SEBI compliance checks on a proposal.
    """

    name: str = "SEBIRulesTool"
    description: str = (
        "Run all SEBI compliance checks on a trading proposal. "
        "Input: JSON string with keys: ticker, strategy_type, "
        "entry_condition, exit_condition, stop_loss_pct, "
        "position_size_pct, reasoning. "
        "Returns a list of check results (pass/fail)."
    )

    def _run(self, proposal_json: str) -> str:
        try:
            proposal = json.loads(proposal_json)
        except (json.JSONDecodeError, TypeError):
            proposal = {}

        results = run_all_checks(proposal)
        return json.dumps(results, indent=2)


class SEBIKnowledgeTool(BaseTool):
    """
    Wraps rag_retriever.query for CrewAI.
    Retrieves relevant SEBI rule text for a given question.
    """

    name: str = "SEBIKnowledgeTool"
    description: str = (
        "Query the SEBI regulatory knowledge base. "
        "Input: a natural language question about SEBI algo trading rules. "
        "Returns relevant sections from the SEBI circular."
    )

    def _run(self, question: str) -> str:
        try:
            kb = get_knowledge_base()
            return kb.query(question, n_results=3)
        except Exception as e:
            return f"RAG query failed: {e}"


# ── Compliance Agent ─────────────────────────────────────────────────────────


class ComplianceAgent:
    """
    CrewAI-based SEBI compliance agent.

    Runs deterministic checks AND RAG-grounded LLM reasoning to
    produce ComplianceVerdict messages for each proposal.
    """

    def __init__(
        self,
        room_manager: BandRoomManager,
        groq_api_key: Optional[str] = None,
    ):
        self.room_manager = room_manager
        self.agent_id = "compliance_agent"
        self._revision_tracker: dict[str, int] = {}  # proposal_id → revision count
        self.max_revision_rounds = 2

        api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        from crewai import LLM
        self.llm = LLM(
            model="openai/llama-3.3-70b-versatile",
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.2
        )

        self.rules_tool = SEBIRulesTool()
        self.knowledge_tool = SEBIKnowledgeTool()

        self.crew_agent = Agent(
            role="SEBI Compliance Officer",
            goal=(
                "Ensure every trading strategy complies with SEBI's 2025 "
                "algorithmic trading framework for retail investors"
            ),
            backstory=(
                "You are a senior compliance officer at a leading Indian "
                "brokerage. You have deep expertise in SEBI's February 2025 "
                "circular on algorithmic trading for retail investors. You "
                "use both rule-based checks and your regulatory knowledge to "
                "evaluate strategies for compliance. You are thorough but "
                "fair — you approve compliant strategies and provide clear "
                "guidance for those that need modifications."
            ),
            llm=self.llm,
            tools=[self.rules_tool, self.knowledge_tool],
            verbose=True,
        )

    async def check_proposal(
        self, proposal_data: dict
    ) -> ComplianceVerdict:
        """
        Run full compliance check on a proposal.

        1. Run deterministic checks (sebi_rules.py)
        2. For flagged/borderline checks, query RAG → LLM reasoning
        3. Post ComplianceVerdict

        Args:
            proposal_data: The proposal dict.

        Returns:
            ComplianceVerdict message.
        """
        proposal_id = proposal_data.get("proposal_id", "unknown")
        ticker = proposal_data.get("ticker", "UNKNOWN")

        logger.info(
            f"[{self.agent_id}] Running compliance checks on {proposal_id} ({ticker})"
        )

        # ── Step 1: Deterministic checks ─────────────────────────────────
        deterministic_results = run_all_checks(proposal_data)

        checks_run = []
        has_failure = False
        flagged_checks = []

        for check in deterministic_results:
            passed = check["passed"]
            if not passed:
                has_failure = True
                flagged_checks.append(check)

            checks_run.append(
                ComplianceCheckResult(
                    check_name=check["check_name"],
                    passed=passed,
                    message=check["message"],
                )
            )

        # ── Step 2: RAG-grounded LLM reasoning for flagged checks ────────
        rag_reasoning = ""

        if flagged_checks:
            # Query RAG for relevant SEBI rules
            for fc in flagged_checks:
                question = f"SEBI rules about {fc['check_name'].replace('_', ' ')}"
                try:
                    rule_text = self.knowledge_tool._run(question)
                except Exception:
                    rule_text = "Could not retrieve relevant rules."

                # Use CrewAI for LLM reasoning
                task = Task(
                    description=(
                        f"A trading strategy has FAILED the '{fc['check_name']}' "
                        f"compliance check.\n\n"
                        f"Check result: {fc['message']}\n\n"
                        f"Relevant SEBI rules:\n{rule_text[:1000]}\n\n"
                        f"Strategy details: {json.dumps(proposal_data, indent=2, default=str)[:500]}\n\n"
                        f"Determine: Is this a hard rejection or can the strategy be "
                        f"modified to comply? What specific changes are required? "
                        f"Be concise and actionable."
                    ),
                    expected_output=(
                        "A concise compliance assessment stating: "
                        "the specific rule violated, whether it's fixable, "
                        "and exact changes the strategy agent must make."
                    ),
                    agent=self.crew_agent,
                )

                crew = Crew(
                    agents=[self.crew_agent], tasks=[task], verbose=False
                )

                try:
                    import asyncio
                    result = await asyncio.to_thread(crew.kickoff)
                    rag_reasoning += f"\n{fc['check_name']}: {str(result)[:300]}"
                except Exception as e:
                    logger.error(f"[{self.agent_id}] LLM reasoning failed: {e}")
                    rag_reasoning += f"\n{fc['check_name']}: Manual review required."

        # ── Step 3: Determine verdict ────────────────────────────────────
        fail_count = sum(1 for c in checks_run if not c.passed)

        if fail_count == 0:
            # All checks passed → APPROVED
            status = "approved"
            algo_tag = generate_algo_tag_id(proposal_id, ticker)
            reasoning = (
                f"All {len(checks_run)} SEBI compliance checks passed. "
                f"Strategy approved for registration. Algo Tag: {algo_tag}"
            )
            required_action = None

        elif any(
            "rejected" in c.message.lower() or "exceeds" in c.message.lower()
            for c in checks_run
            if not c.passed
        ):
            # Hard rejection (e.g., position > 20%)
            status = "rejected"
            algo_tag = None
            reasoning = (
                f"{fail_count} check(s) failed with hard violations. "
                f"Strategy rejected under SEBI framework. {rag_reasoning}"
            )
            required_action = "; ".join(
                c.message for c in checks_run if not c.passed
            )

        else:
            # Soft failures → FLAGGED (can be revised)
            status = "flagged"
            algo_tag = None
            reasoning = (
                f"{fail_count} check(s) require attention. "
                f"Strategy flagged for revision. {rag_reasoning}"
            )
            required_action = "; ".join(
                c.message for c in checks_run if not c.passed
            )

        verdict = ComplianceVerdict(
            target_proposal_id=proposal_id,
            status=status,
            checks_run=checks_run,
            reasoning=reasoning[:500],
            required_action=required_action,
            algo_tag_id=algo_tag,
        )

        await self.room_manager.post_message(
            verdict.model_dump(), sender_id=self.agent_id
        )

        logger.info(
            f"[{self.agent_id}] Verdict for {proposal_id}: {status} "
            f"(algo_tag={algo_tag})"
        )
        return verdict

    async def handle_revision(
        self, revision_data: dict, original_proposal: dict
    ) -> ComplianceVerdict:
        """
        Handle a revision from a strategy agent after a compliance flag.

        Re-runs compliance checks on the revised proposal.
        Tracks revision rounds — auto-rejects after max_revision_rounds.

        Args:
            revision_data: The revision message dict.
            original_proposal: The original proposal, updated with revisions.

        Returns:
            Updated ComplianceVerdict.
        """
        proposal_id = revision_data.get("original_proposal_id", "unknown")

        # Track revision rounds
        current_round = self._revision_tracker.get(proposal_id, 0) + 1
        self._revision_tracker[proposal_id] = current_round

        if current_round > self.max_revision_rounds:
            # Auto-reject after too many rounds
            verdict = ComplianceVerdict(
                target_proposal_id=proposal_id,
                status="rejected",
                checks_run=[],
                reasoning=(
                    f"Proposal rejected after {current_round} revision rounds. "
                    f"Maximum of {self.max_revision_rounds} revision rounds exceeded. "
                    f"Strategy does not meet SEBI compliance requirements."
                ),
                required_action="Fundamental strategy redesign required.",
            )

            await self.room_manager.post_message(
                verdict.model_dump(), sender_id=self.agent_id
            )

            logger.warning(
                f"[{self.agent_id}] Proposal {proposal_id} auto-rejected "
                f"after {current_round} revisions"
            )
            return verdict

        # Merge revision changes into proposal
        updated_proposal = dict(original_proposal)
        if revision_data.get("revised_entry_condition"):
            updated_proposal["entry_condition"] = revision_data["revised_entry_condition"]
        if revision_data.get("revised_exit_condition"):
            updated_proposal["exit_condition"] = revision_data["revised_exit_condition"]
        if revision_data.get("revised_position_size_pct"):
            updated_proposal["position_size_pct"] = revision_data["revised_position_size_pct"]

        # Re-run compliance
        return await self.check_proposal(updated_proposal)
