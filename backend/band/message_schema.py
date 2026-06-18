from pydantic import BaseModel, Field
from typing import Literal, Optional, Any
from datetime import datetime
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
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
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


# Add these to message_schema.py

def make_compliance_verdict(sender: AgentName, target_strategy: str, status: str, reasoning: str, algo_tag_id: str = None) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="compliance_verdict",
        content=f"[COMPLIANCE] {target_strategy}: {status} — {reasoning}",
        payload={
            "target_strategy": target_strategy,
            "status": status,
            "reasoning": reasoning,
            "algo_tag_id": algo_tag_id or str(uuid.uuid4()),
        },
    )

def make_final_verdict(sender: AgentName, allocations: list, reasoning: str) -> BandMessage:
    return BandMessage(
        sender=sender,
        message_type="final_verdict",
        content=f"[FINAL VERDICT] Portfolio allocation decided — {reasoning[:60]}",
        payload={
            "allocations": allocations,
            "reasoning": reasoning,
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

def make_compliance_verdict(sender, target_strategy, status, reasoning, algo_tag_id=None):
    import uuid
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

def make_final_verdict(sender, allocations, reasoning):
    return BandMessage(
        sender=sender,
        message_type="final_verdict",
        content=f"[FINAL VERDICT] {reasoning[:80]}",
        payload={
            "allocations": allocations,
            "reasoning":   reasoning,
        },
    )

# ── Typed message classes for teammate's review agents ───────────────────────
# These provide structured Pydantic models that compliance/stress agents use
# internally before converting to BandMessage for posting to Band.

class Proposal(BaseModel):
    proposal_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender:        str
    strategy_name:   str = "unknown"
    picks:         list[str]    = []
    weights:       list[float]  = []
    rationale:     str          = ""
    risk:          str          = ""
    raw_output:    str          = ""
    payload:       dict         = {}

class Challenge(BaseModel):
    challenge_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_proposal_id: str
    challenger_id:  str = "stress_test_agent"
    concern:        str
    stress_result:  Optional[dict] = None
    severity:       str = "medium"   # "high" | "medium" | "low"
    timestamp:      str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ChallengeResolved(BaseModel):
    challenge_id:     str
    proposal_id:      str
    resolution_note:  str
    resolved_by:      str = "stress_test_agent"
    timestamp:        str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class StressTestResult(BaseModel):
    scenario:      str
    drawdown_pct:  float
    outcome:       str    # "catastrophic" | "breached_stop_loss" | "survived"
    summary:       str    = ""

class ComplianceVerdict(BaseModel):
    verdict_id:       str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id:      str
    status:           str    # "approved" | "flagged" | "rejected"
    reasoning:        str
    required_action:  str    = "none"
    algo_tag_id:      str    = Field(default_factory=lambda: f"SEBI-NSE-2026-{str(uuid.uuid4())[:8].upper()}")
    timestamp:        str    = Field(default_factory=lambda: datetime.utcnow().isoformat())

class FinalVerdict(BaseModel):
    verdict_id:   str = Field(default_factory=lambda: str(uuid.uuid4()))
    allocations:  list[Any]
    reasoning:    str
    timestamp:    str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ComplianceCheckResult(BaseModel):
    check_id:        str = Field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id:     str
    rule:            str   # which SEBI rule was checked
    passed:          bool
    finding:         str   # what was found
    severity:        str = "low"   # "high" | "medium" | "low"
    timestamp:       str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class AllocationItem(BaseModel):
    proposal_id:     str
    strategy_name:   str = "unknown"
    picks:           list[str]  = []
    weights:         list[float] = []
    allocation_pct:  float       # % of total portfolio allocated
    status:          str         # "approved" | "rejected" | "reduced"
    reason:          str         = ""    