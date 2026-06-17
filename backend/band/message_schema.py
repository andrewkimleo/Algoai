"""
AlgoDesk Message Schemas — Pydantic v2 models for all Band room messages.

Every message posted to the Band room is one of these types, serialized as JSON.
The Band room chat history IS the audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ── Shared Sub-Models ────────────────────────────────────────────────────────


class BacktestSummary(BaseModel):
    """Summary statistics from a backtest run."""
    win_rate: float
    max_drawdown: float
    sharpe: float


class StressTestResult(BaseModel):
    """Result of a single stress-test scenario."""
    scenario: str
    drawdown_pct: float
    outcome: Literal["survived", "breached_stop_loss", "catastrophic"]


class ComplianceCheckResult(BaseModel):
    """Result of a single compliance check."""
    check_name: str
    passed: bool
    message: str


class AllocationItem(BaseModel):
    """A single strategy allocation in the final portfolio verdict."""
    proposal_id: str
    ticker: str
    agent_name: str
    allocation_pct: float
    status: Literal["approved", "reduced", "rejected"]
    algo_tag_id: Optional[str] = None


# ── Message Type: Proposal ───────────────────────────────────────────────────


class Proposal(BaseModel):
    """A strategy agent proposes a trade for debate."""
    type: Literal["proposal"] = "proposal"
    proposal_id: str = Field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:8]}")
    agent_name: str
    strategy_type: Literal["momentum", "mean_reversion", "sentiment"]
    ticker: str
    entry_condition: str
    exit_condition: str
    stop_loss_pct: float
    take_profit_pct: float
    position_size_pct: float
    backtest_summary: BacktestSummary
    reasoning: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Message Type: Challenge ──────────────────────────────────────────────────


class Challenge(BaseModel):
    """Stress-test agent challenges a proposal."""
    type: Literal["challenge"] = "challenge"
    challenge_id: str = Field(default_factory=lambda: f"chal_{uuid.uuid4().hex[:8]}")
    target_proposal_id: str
    challenger_agent: str
    concern: str
    stress_test_result: StressTestResult
    severity: Literal["high", "medium", "low"]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Message Type: Revision ───────────────────────────────────────────────────


class Revision(BaseModel):
    """Strategy agent revises a proposal to address a challenge."""
    type: Literal["revision"] = "revision"
    revision_id: str = Field(default_factory=lambda: f"rev_{uuid.uuid4().hex[:8]}")
    original_proposal_id: str
    agent_name: str
    changes_made: str
    revised_entry_condition: str
    revised_exit_condition: str
    revised_position_size_pct: float
    revision_reasoning: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Message Type: ComplianceVerdict ──────────────────────────────────────────


class ComplianceVerdict(BaseModel):
    """SEBI compliance agent's verdict on a proposal."""
    type: Literal["compliance_verdict"] = "compliance_verdict"
    verdict_id: str = Field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:8]}")
    target_proposal_id: str
    status: Literal["approved", "flagged", "rejected"]
    checks_run: List[ComplianceCheckResult]
    reasoning: str
    required_action: Optional[str] = None
    algo_tag_id: Optional[str] = None  # UUID assigned if approved
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Message Type: FinalVerdict ───────────────────────────────────────────────


class FinalVerdict(BaseModel):
    """Portfolio arbiter's final allocation verdict."""
    type: Literal["final_verdict"] = "final_verdict"
    allocations: List[AllocationItem]
    portfolio_risk_summary: str
    reasoning: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Message Type: ChallengeResolved ──────────────────────────────────────────


class ChallengeResolved(BaseModel):
    """Stress-test agent acknowledges a revision resolved the concern."""
    type: Literal["challenge_resolved"] = "challenge_resolved"
    challenge_id: str
    target_proposal_id: str
    resolution_note: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Union Wrapper ────────────────────────────────────────────────────────────

# All possible message types
MessagePayload = Union[
    Proposal,
    Challenge,
    Revision,
    ComplianceVerdict,
    FinalVerdict,
    ChallengeResolved,
]

# Map type string → model class
MESSAGE_TYPE_MAP: dict[str, type[BaseModel]] = {
    "proposal": Proposal,
    "challenge": Challenge,
    "revision": Revision,
    "compliance_verdict": ComplianceVerdict,
    "final_verdict": FinalVerdict,
    "challenge_resolved": ChallengeResolved,
}


class RoomMessage(BaseModel):
    """
    Wrapper that can hold any message type posted to the Band room.

    Use RoomMessage.from_dict(data) to deserialize any raw dict
    into the appropriate typed model.
    """
    sender_id: str
    payload: MessagePayload

    @classmethod
    def from_dict(cls, data: dict) -> "RoomMessage":
        """
        Deserialize a raw dict into a RoomMessage with the correct
        payload type based on the 'type' field.

        Args:
            data: Raw dict with at minimum 'sender_id' and the payload
                  fields including 'type'.

        Returns:
            RoomMessage with strongly-typed payload.

        Raises:
            ValueError: If the message type is unknown.
        """
        sender_id = data.get("sender_id", "unknown")

        # The payload might be nested under 'payload' or at top level
        payload_data = data.get("payload", data)
        msg_type = payload_data.get("type")

        if msg_type not in MESSAGE_TYPE_MAP:
            raise ValueError(
                f"Unknown message type: {msg_type}. "
                f"Known types: {list(MESSAGE_TYPE_MAP.keys())}"
            )

        model_cls = MESSAGE_TYPE_MAP[msg_type]
        payload = model_cls.model_validate(payload_data)

        return cls(sender_id=sender_id, payload=payload)
