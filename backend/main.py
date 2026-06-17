"""
AlgoDesk Backend — Main Entry Point.

Initializes FastAPI, sets up the Band room, and orchestrates the
full agent pipeline: proposals → stress test → compliance → arbitration.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Fix CrewAI 1.14+ bug where it injects Anthropic's 'cache_breakpoint' into Groq/OpenAI messages
import litellm
_original_completion = litellm.completion

def _patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        for msg in kwargs["messages"]:
            if isinstance(msg, dict) and "cache_breakpoint" in msg:
                del msg["cache_breakpoint"]
    return _original_completion(*args, **kwargs)

litellm.completion = _patched_completion

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Load .env from the backend directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Ensure the backend directory is on the path for imports
sys.path.insert(0, str(Path(__file__).parent))

from api.server import router as api_router, register_session
from band.room_manager import BandRoomManager
from agents.stress_test_agent import StressTestAgent
from agents.compliance_agent import ComplianceAgent
from agents.portfolio_arbiter import PortfolioArbiter

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("AlgoDesk Backend starting up...")
    logger.info("=" * 60)

    # Check config
    groq_key = os.getenv("GROQ_API_KEY", "")
    band_key = os.getenv("BAND_API_KEY", "")

    if not groq_key or groq_key.startswith("your_"):
        logger.warning(
            "GROQ_API_KEY not configured. LLM calls will fail until set in .env"
        )
    else:
        logger.info("✓ GROQ_API_KEY configured")

    if not band_key or band_key.startswith("your_"):
        logger.warning(
            "BAND_API_KEY not configured. Running in mock mode (local only)."
        )
    else:
        logger.info("✓ BAND_API_KEY configured")

    logger.info("AlgoDesk Backend ready!")
    logger.info("=" * 60)

    yield

    logger.info("Shutting down AlgoDesk Backend...")
    logger.info("Cleanup complete.")


# ── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="AlgoDesk",
    description=(
        "Multi-agent trading strategy governance system. "
        "AI agents collaborate through Band to review, stress-test, "
        "and approve algorithmic trading strategies under SEBI's framework."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


# ── Session Orchestration ────────────────────────────────────────────────────


async def create_and_run_session(
    session_id: str,
    tickers: list[str],
    background_tasks: BackgroundTasks,
) -> BandRoomManager:
    """
    Create a Band room and register the session.
    Kicks off the agent pipeline as a background task.

    Args:
        session_id: Unique session identifier.
        tickers: Stock tickers for strategy proposals.
        background_tasks: FastAPI background tasks.

    Returns:
        The BandRoomManager for this session.
    """
    band_key = os.getenv("BAND_API_KEY", "")
    room_manager = BandRoomManager(
        api_key=band_key,
        room_name=f"algodesk-{session_id}",
    )

    # Create the Band room
    await room_manager.create_room()

    # Register agents in the room
    agents = [
        ("stress_test_agent", os.getenv("STRESS_TEST_AGENT_ID", "stress_test")),
        ("compliance_agent", os.getenv("COMPLIANCE_AGENT_ID", "compliance")),
        ("portfolio_arbiter", os.getenv("PORTFOLIO_ARBITER_ID", "arbiter")),
    ]
    for name, agent_id in agents:
        await room_manager.add_agent(name, agent_id)

    # Register session for API
    register_session(session_id, {
        "room_manager": room_manager,
        "tickers": tickers,
        "status": "running",
    })

    # Run the pipeline in the background
    background_tasks.add_task(
        _run_full_pipeline, session_id, tickers, room_manager
    )

    return room_manager


async def _run_full_pipeline(
    session_id: str,
    tickers: list[str],
    room_manager: BandRoomManager,
) -> None:
    """
    Background task: run the full agent pipeline.

    Phase 1: Wait for proposals (from Sujan's strategy agents via Band)
    Phase 2: Stress-test each proposal
    Phase 3: Compliance check proposals that survive stress testing
    Phase 4: Portfolio arbiter makes final allocation

    For demo/hackathon: we simulate receiving proposals if none arrive
    within 30 seconds.
    """
    groq_key = os.getenv("GROQ_API_KEY", "")

    stress_agent = StressTestAgent(room_manager, groq_api_key=groq_key)
    compliance_agent = ComplianceAgent(room_manager, groq_api_key=groq_key)
    arbiter = PortfolioArbiter(room_manager, groq_api_key=groq_key)

    try:
        # ── Phase 1: Collect proposals ───────────────────────────────────
        logger.info(f"[{session_id}] Phase 1: Waiting for proposals...")

        # In a real setup, we'd listen via room_manager.listen().
        # For hackathon demo, we wait a bit then use whatever proposals
        # have arrived in the room. If none arrive, we simulate dummy ones.
        await asyncio.sleep(5)  # Give strategy agents time to post

        all_messages = room_manager.get_all_messages()
        proposals = [m for m in all_messages if m.get("type") == "proposal"]

        if not proposals:
            logger.info(f"[{session_id}] No proposals received. Generating demo proposals...")
            proposals = _generate_demo_proposals(session_id, tickers)
            for p in proposals:
                await room_manager.post_message(p, sender_id=p.get("agent_name", "demo"))

        logger.info(f"[{session_id}] Received {len(proposals)} proposals")

        # ── Phase 2: Stress test ─────────────────────────────────────────
        logger.info(f"[{session_id}] Phase 2: Stress testing...")

        challenges = {}
        for proposal in proposals:
            try:
                challenge = await stress_agent.handle_proposal(proposal)
                if challenge:
                    challenges[proposal.get("proposal_id", "")] = challenge
                    logger.info(
                        f"  ✓ Challenge {challenge.challenge_id} → "
                        f"{proposal.get('ticker')} ({challenge.severity})"
                    )
                else:
                    logger.info(f"  ✓ {proposal.get('ticker')} passed stress test")
            except Exception as e:
                logger.error(f"  ✗ Stress test failed for {proposal.get('ticker')}: {e}")

        # ── Phase 3: Compliance ──────────────────────────────────────────
        logger.info(f"[{session_id}] Phase 3: Compliance checks...")

        # Check proposals that either had no challenges or low severity
        proposals_for_compliance = []
        for proposal in proposals:
            pid = proposal.get("proposal_id", "")
            challenge = challenges.get(pid)

            if challenge is None or challenge.severity != "high":
                proposals_for_compliance.append(proposal)
            else:
                logger.info(f"  ⊘ {pid} blocked by high-severity challenge")

        approved_proposals = []
        for proposal in proposals_for_compliance:
            try:
                verdict = await compliance_agent.check_proposal(proposal)

                if verdict.status == "approved":
                    # Enrich proposal with algo_tag_id for arbiter
                    proposal["algo_tag_id"] = verdict.algo_tag_id
                    approved_proposals.append(proposal)
                    logger.info(
                        f"  ✓ {proposal.get('ticker')}: APPROVED "
                        f"(tag={verdict.algo_tag_id})"
                    )
                elif verdict.status == "flagged":
                    logger.info(
                        f"  ⚠ {proposal.get('ticker')}: FLAGGED — "
                        f"{verdict.required_action}"
                    )
                else:
                    logger.info(
                        f"  ✗ {proposal.get('ticker')}: REJECTED"
                    )
            except Exception as e:
                logger.error(f"  ✗ Compliance failed for {proposal.get('ticker')}: {e}")

        # ── Phase 4: Arbitration ─────────────────────────────────────────
        logger.info(f"[{session_id}] Phase 4: Portfolio arbitration...")

        if approved_proposals:
            try:
                verdict = await arbiter.run_arbitration(approved_proposals)
                logger.info(f"  ✓ Final verdict posted")
            except Exception as e:
                logger.error(f"  ✗ Arbitration failed: {e}")
        else:
            logger.warning(f"[{session_id}] No proposals passed for arbitration")

        # ── Done ─────────────────────────────────────────────────────────
        total_messages = len(room_manager.get_all_messages())
        logger.info(
            f"[{session_id}] Pipeline complete! "
            f"Total messages: {total_messages}"
        )

    except Exception as e:
        logger.error(f"[{session_id}] Pipeline failed: {e}", exc_info=True)


def _generate_demo_proposals(
    session_id: str, tickers: list[str]
) -> list[dict]:
    """
    Generate demo proposals for hackathon when no strategy agents
    are connected. These simulate what Sujan's agents would post.
    """
    from band.message_schema import Proposal, BacktestSummary

    demo_strategies = [
        {
            "strategy_type": "momentum",
            "entry_condition": "50-day SMA crosses above 200-day SMA (golden cross)",
            "exit_condition": "50-day SMA crosses below 200-day SMA or stop-loss hit",
            "stop_loss_pct": 3.0,
            "take_profit_pct": 6.0,
            "position_size_pct": 5.0,
            "reasoning": "Momentum strategy based on SMA crossover. Entry signal is purely mathematical.",
            "backtest_summary": {"win_rate": 62.5, "max_drawdown": 8.2, "sharpe": 1.45},
        },
        {
            "strategy_type": "mean_reversion",
            "entry_condition": "Z-score of 20-day rolling price drops below -2.0",
            "exit_condition": "Z-score reverts to 0 or stop-loss hit",
            "stop_loss_pct": 4.0,
            "take_profit_pct": 5.0,
            "position_size_pct": 4.0,
            "reasoning": "Mean reversion on oversold conditions using z-score. Purely statistical signal.",
            "backtest_summary": {"win_rate": 58.0, "max_drawdown": 6.5, "sharpe": 1.2},
        },
        {
            "strategy_type": "sentiment",
            "entry_condition": "Positive news sentiment score > 0.7 from verified financial sources",
            "exit_condition": "Sentiment drops below 0.3 or holding period exceeds 15 days",
            "stop_loss_pct": 5.0,
            "take_profit_pct": 8.0,
            "position_size_pct": 3.0,
            "reasoning": "Sentiment-driven strategy using news analysis from Reuters and Bloomberg feeds.",
            "backtest_summary": {"win_rate": 55.0, "max_drawdown": 10.0, "sharpe": 0.95},
        },
    ]

    proposals = []
    for i, ticker in enumerate(tickers[:3]):
        strategy = demo_strategies[i % len(demo_strategies)].copy()
        bt_summary = strategy.pop("backtest_summary")
        p = Proposal(
            agent_name=f"{'momentum' if i==0 else 'mean_reversion' if i==1 else 'sentiment'}_agent",
            ticker=ticker,
            **strategy,
            backtest_summary=BacktestSummary(**bt_summary),
        )
        proposals.append(p.model_dump())

    return proposals


# ── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
