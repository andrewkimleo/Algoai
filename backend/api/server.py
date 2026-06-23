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
    try:
        from main import create_and_run_session
    except ImportError:
        import sys
        import os
        backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
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
                event_type = msg.get("message_type", "message")
                data = json.dumps(msg, default=str)
                yield f"event: {event_type}\ndata: {data}\n\n"

            # Then stream new messages as they arrive
            while True:
                try:
                    # Wait for a new message, with a 15s timeout for heartbeat
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = msg.get("message_type", "message")
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
        msg_type = msg.get("message_type")
        payload = msg.get("payload") or {}

        if msg_type == "proposal":
            pid = msg.get("message_id", "")
            proposals[pid] = {
                "proposal_id": pid,
                "ticker": payload.get("ticker"),
                "strategy_type": payload.get("strategy"),
                "agent_name": msg.get("sender"),
                "status": "open",
            }

        elif msg_type == "challenge":
            pid = payload.get("target_proposal_id", "")
            if pid in proposals:
                proposals[pid]["status"] = "challenged"
                challenges[pid] = payload.get("severity", "medium")

        elif msg_type == "challenge_resolved":
            pid = payload.get("target_proposal_id", "")
            if pid in proposals:
                proposals[pid]["status"] = "challenge_resolved"

        elif msg_type == "compliance_verdict":
            pid = payload.get("target_proposal_id", "")
            if pid in proposals:
                proposals[pid]["status"] = f"compliance_{payload.get('status', 'unknown')}"
                proposals[pid]["algo_tag_id"] = payload.get("algo_tag_id")

        elif msg_type == "final_verdict":
            for alloc in payload.get("allocations", []):
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



@router.get("/portfolio/analytics")
async def get_portfolio_analytics(session_id: Optional[str] = None):
    """
    Calculates historical performance analytics (returns, equity curve,
    drawdown curve, and Nifty benchmark comparisons) for a completed session.
    """
    session = None
    if session_id:
        session = _sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=404, 
                detail="The specified portfolio session was not found."
            )
    else:
        # Resolve the latest completed session
        completed_sessions = [
            (sid, sdata) for sid, sdata in _sessions.items() 
            if sdata.get("status") == "completed"
        ]
        if completed_sessions:
            session_id, session = completed_sessions[-1]
            logger.info(f"[Analytics API] Auto-selected latest completed session: {session_id}")
        else:
            raise HTTPException(
                status_code=404, 
                detail="No completed portfolio sessions exist yet. Run a live simulation first."
            )

    room_manager = session.get("room_manager")
    if not room_manager:
        raise HTTPException(
            status_code=500, 
            detail="Session internal room manager not found."
        )

    # Get final verdict message containing capital allocations
    messages = room_manager.get_all_messages()
    final_verdict_msg = next(
        (m for m in messages if m.get("message_type") == "final_verdict"), 
        None
    )
    
    if not final_verdict_msg:
        raise HTTPException(
            status_code=400, 
            detail="Portfolio capital decisions have not been finalized yet for this session."
        )

    allocations = final_verdict_msg.get("payload", {}).get("allocations", [])
    if not allocations:
        raise HTTPException(
            status_code=400, 
            detail="No strategy allocations found in the final verdict message."
        )

    # Forensic logging before calculation
    import os
    log_dir = "d:\\Algoai\\backend"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "diagnostics_forensic.log")
    for alloc in allocations:
        proposal_id = alloc.get("proposal_id")
        picks = alloc.get("picks", [])
        wt_list = alloc.get("weights", [])
        log_msg = f"[FORENSIC] Analytics Endpoint: strategy='{alloc.get('strategy')}', proposal_id='{proposal_id}', picks={picks}, weights={wt_list}\n"
        logger.info(log_msg)
        with open(log_file, "a") as df_log:
            df_log.write(log_msg)
        if proposal_id == "unknown" or not picks or not wt_list:
            warn_msg = f"[FORENSIC WARNING] Empty picks/weights or unknown proposal_id detected for strategy '{alloc.get('strategy')}'!\n"
            logger.warning(warn_msg)
            with open(log_file, "a") as df_log:
                df_log.write(warn_msg)

    # Calculate net stock-level weights from strategy weights
    weights = {}
    for alloc in allocations:
        strat_weight = alloc.get("allocation_pct", 0.0) / 100.0
        picks = alloc.get("picks", [])
        wt_list = alloc.get("weights", [])
        for pick, wt in zip(picks, wt_list):
            t_upper = pick.upper().strip()
            if not t_upper.endswith(".NS") and not t_upper.endswith(".BO") and not t_upper.startswith("^"):
                t_upper += ".NS"
            weights[t_upper] = weights.get(t_upper, 0.0) + (strat_weight * (wt / 100.0))

    # STEP 2: Log portfolio inputs
    logger.info(f"[Validation] 1. Final portfolio allocations received: {allocations}")
    logger.info(f"[Validation] 6. Weight vector used (raw): {weights}")
    logger.info(f"[Validation] 2. Asset tickers received: {list(weights.keys())}")

    # Validate weight counts and total allocations
    if not allocations:
        return {
            "status": "error",
            "stage": "portfolio_input_validation",
            "reason": "No strategy allocations found in the final verdict message."
        }
    if not weights:
        return {
            "status": "error",
            "stage": "portfolio_input_validation",
            "reason": "Aggregate weight sum is zero. Cannot compute returns."
        }

    # Normalize weights to sum to 1.0 (eliminates rounding discrepancies)
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}
        logger.info(f"[Validation] Weight vector used (normalized): {weights}")
    else:
        return {
            "status": "error",
            "stage": "portfolio_input_validation",
            "reason": "Aggregate weight sum is zero. Cannot compute returns."
        }

    try:
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir.replace('\\', '/').endswith('/backend/api'):
            backend_path = os.path.dirname(current_dir)
        elif current_dir.replace('\\', '/').endswith('/api'):
            backend_path = os.path.join(os.path.dirname(current_dir), "backend")
        else:
            backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
        backend_path = os.path.abspath(backend_path)
        
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        else:
            sys.path.remove(backend_path)
            sys.path.insert(0, backend_path)

        backend_path_normalized = backend_path.replace('\\', '/')
        if 'analytics' in sys.modules:
            analytics_mod = sys.modules['analytics']
            is_our_analytics = False
            if hasattr(analytics_mod, '__file__') and analytics_mod.__file__:
                file_path = os.path.abspath(analytics_mod.__file__).replace('\\', '/')
                if file_path.startswith(backend_path_normalized) and 'analytics' in file_path:
                    is_our_analytics = True
            if not is_our_analytics:
                logger.info(f"[Analytics Import Guard] Removing non-local analytics module: {getattr(analytics_mod, '__file__', None)}")
                for mod_name in list(sys.modules.keys()):
                    if mod_name == 'analytics' or mod_name.startswith('analytics.'):
                        del sys.modules[mod_name]

        from analytics import compute_portfolio_analytics
        analytics_result = compute_portfolio_analytics(weights, period="3y", benchmark_symbol="^NSEI")
        
        # STEP 8: Structured Error Reporting
        if isinstance(analytics_result, dict) and analytics_result.get("status") == "error":
            logger.warning(f"[Analytics API] Analytics returned error response: {analytics_result}")
            return analytics_result
            
        # Guard against empty metrics or curves to return standard error message
        if (not analytics_result or 
            not analytics_result.get("metrics") or 
            not analytics_result.get("equity_curve")):
            
            logger.warning("[Analytics API] Analytics returned empty metrics or equity curve.")
            return {
                "status": "error",
                "stage": "metrics_generation",
                "reason": "Analytics generated empty metrics or equity curve series"
            }
            
        return analytics_result
    except Exception as e:
        logger.error(f"[Analytics API] Performance calculation failure: {e}")
        return {
            "status": "error",
            "stage": "metrics_calculation",
            "reason": str(e)
        }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "algodesk-backend"}

