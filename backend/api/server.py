"""
AlgoDesk FastAPI Server — bridges Band room messages to Next.js frontend via SSE.

Endpoints:
    POST /api/start-session     → Create a session, start agent pipeline
    GET  /api/session/{id}/stream → SSE stream of all agent messages
    GET  /api/session/{id}/messages → Full message history (polling fallback)
    GET  /api/session/{id}/state → Current proposal lifecycle state
    GET  /api/sessions          → List all active sessions
    GET  /api/health            → Health check
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticBaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["AlgoDesk"])


# ── Request / Response Models ────────────────────────────────────────────────


class StartSessionRequest(PydanticBaseModel):
    tickers: Optional[list[str]] = None


class StartSessionResponse(PydanticBaseModel):
    session_id: str
    room_id: str
    status: str
    tickers: list[str]


# ── In-memory session state ─────────────────────────────────────────────────

# This gets populated by main.py on startup
_sessions: dict[str, dict] = {}


def register_session(session_id: str, session_data: dict) -> None:
    """Register a session for the API to serve."""
    _sessions[session_id] = session_data


def get_session_data(session_id: str) -> Optional[dict]:
    """Retrieve session data."""
    return _sessions.get(session_id)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/start-session", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create a new AlgoDesk debate session.

    1. Creates a Band room (or mock room)
    2. Generates session_id
    3. Triggers the full agent pipeline as a background task

    Body: { "tickers": ["RELIANCE", "TATAMOTORS", "INFY"] }
    """
    from main import create_and_run_session

    tickers = request.tickers or ["RELIANCE", "TATAMOTORS", "INFY"]
    session_id = f"session_{uuid.uuid4().hex[:12]}"

    # This sets up the room_manager and registers the session
    room_manager = await create_and_run_session(
        session_id, tickers, background_tasks
    )

    room_id = room_manager.room_id or "unknown"

    return StartSessionResponse(
        session_id=session_id,
        room_id=room_id,
        status="agents_starting",
        tickers=tickers,
    )


@router.get("/session/{session_id}/stream")
async def stream_session(session_id: str):
    """
    SSE (Server-Sent Events) stream of agent messages.

    The frontend connects to this endpoint and receives each agent
    message as it's posted during the debate pipeline.

    Event format:
        event: {message_type}
        data: {json_payload}

    A heartbeat ping is sent every 15 seconds to keep the connection alive.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    room_manager = session.get("room_manager")
    if not room_manager:
        raise HTTPException(status_code=500, detail="Room manager not available")

    async def event_generator():
        """Generate SSE events from the room message queue."""
        queue = room_manager.subscribe_queue()

        try:
            # First, send all existing messages as a catchup burst
            existing = room_manager.get_all_messages()
            for msg in existing:
                event_type = msg.get("type", "message")
                data = json.dumps(msg, default=str)
                yield f"event: {event_type}\ndata: {data}\n\n"

            # Then stream new messages as they arrive
            while True:
                try:
                    # Wait for a new message, with a 15s timeout for heartbeat
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = msg.get("type", "message")
                    data = json.dumps(msg, default=str)
                    yield f"event: {event_type}\ndata: {data}\n\n"

                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"event: heartbeat\ndata: {{}}\n\n"

                except asyncio.CancelledError:
                    break

        finally:
            room_manager.unsubscribe_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@router.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str):
    """
    Get all messages in this session, ordered by timestamp.
    Polling fallback for frontends that can't use SSE.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    room_manager = session.get("room_manager")
    if not room_manager:
        return {"session_id": session_id, "messages": [], "count": 0}

    messages = room_manager.get_all_messages()
    messages.sort(key=lambda m: m.get("timestamp", m.get("posted_at", "")))

    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }


@router.get("/session/{session_id}/state")
async def get_session_state(session_id: str):
    """
    Get the current state of all proposals in a session.
    Shows lifecycle status, challenge tracking, and compliance results.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    room_manager = session.get("room_manager")
    messages = room_manager.get_all_messages() if room_manager else []

    # Build state from messages
    proposals = {}
    challenges = {}
    verdicts = {}

    for msg in messages:
        msg_type = msg.get("type")

        if msg_type == "proposal":
            pid = msg.get("proposal_id", "")
            proposals[pid] = {
                "proposal_id": pid,
                "ticker": msg.get("ticker"),
                "strategy_type": msg.get("strategy_type"),
                "agent_name": msg.get("agent_name"),
                "status": "open",
            }

        elif msg_type == "challenge":
            pid = msg.get("target_proposal_id", "")
            if pid in proposals:
                proposals[pid]["status"] = "challenged"
                challenges[pid] = msg.get("severity", "medium")

        elif msg_type == "challenge_resolved":
            pid = msg.get("target_proposal_id", "")
            if pid in proposals:
                proposals[pid]["status"] = "challenge_resolved"

        elif msg_type == "compliance_verdict":
            pid = msg.get("target_proposal_id", "")
            if pid in proposals:
                proposals[pid]["status"] = f"compliance_{msg.get('status', 'unknown')}"
                proposals[pid]["algo_tag_id"] = msg.get("algo_tag_id")

        elif msg_type == "final_verdict":
            for alloc in msg.get("allocations", []):
                pid = alloc.get("proposal_id", "")
                if pid in proposals:
                    proposals[pid]["status"] = f"final_{alloc.get('status', 'unknown')}"
                    proposals[pid]["allocation_pct"] = alloc.get("allocation_pct")

    return {
        "session_id": session_id,
        "proposals": proposals,
        "total_messages": len(messages),
        "summary": {
            "total_proposals": len(proposals),
            "challenged": sum(1 for p in proposals.values() if "challeng" in p.get("status", "")),
            "approved": sum(1 for p in proposals.values() if "approved" in p.get("status", "")),
            "rejected": sum(1 for p in proposals.values() if "rejected" in p.get("status", "")),
        },
    }


@router.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {
        "sessions": [
            {
                "session_id": sid,
                "room_id": data.get("room_manager", {}).room_id
                if hasattr(data.get("room_manager"), "room_id")
                else "unknown",
                "tickers": data.get("tickers", []),
                "message_count": len(
                    data.get("room_manager").get_all_messages()
                    if data.get("room_manager")
                    else []
                ),
            }
            for sid, data in _sessions.items()
        ]
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "algodesk-backend"}
