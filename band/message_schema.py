from pydantic import BaseModel, Field
from typing import Literal, Optional
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