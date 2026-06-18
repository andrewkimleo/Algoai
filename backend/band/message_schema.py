from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from datetime import datetime, timezone
import uuid



MessageType = Literal[
    "proposal",
    "challenge",
    "revision",
    "compliance_verdict",
    "final_verdict",
    "stress_result",
    "status_update",
]

AgentName = Literal[
    "momentum_agent",
    "mean_reversion_agent",
    "sentiment_agent",
    "stress_test_agent",
    "compliance_agent",
    "portfolio_arbiter",
]


class BandMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sender: AgentName
    message_type: MessageType
    content: str                        # Human-readable text shown in the debate timeline
    payload: Optional[dict] = None      # Structured data (strategy details, scores, etc.)

    def to_band_text(self) -> str:
        """Serialize to a plain string for posting into a Band room."""
        import json
        return json.dumps(self.model_dump())

    @classmethod
    def from_band_text(cls, raw: str) -> "BandMessage":
        """Deserialize a Band room message back into a BandMessage."""
        import json
        return cls(**json.loads(raw))


# ── Convenience constructors ──────────────────────────────────────────────────

def make_proposal(sender: AgentName, strategy_name: str, description: str, payload: dict) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="proposal",
        content=f"[PROPOSAL] {strategy_name}: {description}",
        payload=payload,
    )

def make_challenge(sender: AgentName, target_strategy: str, reason: str) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="challenge",
        content=f"[CHALLENGE] Challenging '{target_strategy}': {reason}",
        payload={"target_strategy": target_strategy, "reason": reason},
    )

def make_revision(sender: AgentName, strategy_name: str, changes: str, payload: dict) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="revision",
        content=f"[REVISION] Updated '{strategy_name}': {changes}",
        payload=payload,
    )

def make_status_update(sender: AgentName, message: str) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="status_update",
        content=f"[STATUS] {message}",
    )

def make_compliance_verdict(sender: AgentName, target_strategy: str, status: str, reasoning: str, algo_tag_id: str = None) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="compliance_verdict",
        content=f"[COMPLIANCE] {target_strategy}: {status} — {reasoning[:80]}",
        payload={
            "target_strategy": target_strategy,
            "status":          status,
            "reasoning":       reasoning,
            "algo_tag_id":     algo_tag_id or f"SEBI-NSE-2026-{str(uuid.uuid4())[:8].upper()}",
        },
    )

def make_final_verdict(sender: AgentName, allocations: list, reasoning: str) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="final_verdict",
        content=f"[FINAL VERDICT] {reasoning[:80]}",
        payload={
            "allocations": allocations,
            "reasoning":   reasoning,
        },
    )

def make_stress_result(sender: AgentName, target_strategy: str, scenario: str, result: dict) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="stress_result",
        content=f"[STRESS TEST] {target_strategy} under {scenario}: {result.get('summary', '')}",
        payload={
            "target_strategy": target_strategy,
            "scenario": scenario,
            "result": result,
        },
    )


# ── Typed message classes for agent internals ────────────────────────────────
# These provide structured Pydantic models that compliance/stress/arbiter agents
# use internally before converting to BandMessage for posting to Band.


class BacktestSummary(BaseModel):
    """Backtest performance summary embedded in demo proposals."""
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    sharpe: float = 0.0


class Proposal(BaseModel):
    """
    Typed proposal used by main.py's demo pipeline.
    Fields match what compliance/stress agents expect to receive.
    """
    proposal_id:       str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name:        str = ""
    ticker:            str = ""
    strategy_type:     str = "unknown"
    entry_condition:   str = ""
    exit_condition:    str = ""
    stop_loss_pct:     float = 3.0
    take_profit_pct:   float = 6.0
    position_size_pct: float = 5.0
    reasoning:         str = ""
    backtest_summary:  Optional[BacktestSummary] = None

    # Legacy fields used by strategy agent wrappers
    sender:            str = ""
    strategy_name:     str = "unknown"
    picks:             list[str] = []
    weights:           list[float] = []
    rationale:         str = ""
    risk:              str = ""
    raw_output:        str = ""
    payload:           Optional[dict] = None


class StressTestResult(BaseModel):
    """Result from a single stress-test scenario."""
    scenario:      str
    drawdown_pct:  float
    outcome:       str    # "catastrophic" | "breached_stop_loss" | "survived"
    summary:       str = ""


class Challenge(BaseModel):
    """Stress-test challenge posted against a proposal."""
    challenge_id:        str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_proposal_id:  str
    challenger_agent:    str = "stress_test_agent"
    concern:             str
    stress_test_result:  Optional[StressTestResult] = None
    severity:            str = "medium"   # "high" | "medium" | "low"
    timestamp:           str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ChallengeResolved(BaseModel):
    """Posted when a challenged proposal's revision is accepted."""
    challenge_id:        str
    target_proposal_id:  str
    resolution_note:     str
    resolved_by:         str = "stress_test_agent"
    timestamp:           str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ComplianceCheckResult(BaseModel):
    """Result of a single SEBI compliance check."""
    check_name:  str
    passed:      bool
    message:     str


class ComplianceVerdict(BaseModel):
    """Compliance agent's verdict on a proposal."""
    verdict_id:          str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_proposal_id:  str = ""
    status:              str = ""    # "approved" | "flagged" | "rejected"
    checks_run:          list[ComplianceCheckResult] = []
    reasoning:           str = ""
    required_action:     Optional[str] = None
    algo_tag_id:         Optional[str] = None
    timestamp:           str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AllocationItem(BaseModel):
    """One allocation decision within the final portfolio verdict."""
    proposal_id:     str
    ticker:          str = ""
    agent_name:      str = ""
    allocation_pct:  float = 0.0
    status:          str = "approved"   # "approved" | "rejected" | "reduced"
    algo_tag_id:     Optional[str] = None


class FinalVerdict(BaseModel):
    """Portfolio arbiter's final allocation verdict."""
    verdict_id:             str = Field(default_factory=lambda: str(uuid.uuid4()))
    allocations:            list[AllocationItem] = []
    portfolio_risk_summary: str = ""
    reasoning:              str = ""
    timestamp:              str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())