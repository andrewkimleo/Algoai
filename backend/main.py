"""
main.py
-------
AlgoDesk entry point.

Orchestrates the full multi-agent debate:
  1. Reads agent_config.yaml
  2. Creates a Band chat room (via the orchestrator agent's API key)
  3. Runs strategy agents (momentum, mean_reversion, sentiment) in order
  4. Posts each proposal as a message to the Band room
  5. Passes all proposals to review agents (stress_test, compliance, arbiter)
  6. Each review agent reads proposals, posts challenges/verdicts to Band
  7. Saves the full audit trail to band/audit_log.json

Run from the backend/ folder:
    python main.py
    python main.py --mode mock        # forces mock market data + news
    python main.py --mode live        # forces live data
    python main.py --skip-review      # runs only strategy agents (faster testing)
"""

import os
import sys

# Ensure backend directory is in the import path and force local 'tools' precedence
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if 'tools' in sys.modules:
    tools_mod = sys.modules['tools']
    is_our_tools = False
    if hasattr(tools_mod, '__file__') and tools_mod.__file__:
        file_path = tools_mod.__file__.replace('\\', '/')
        if 'backend/tools' in file_path or file_path.endswith('tools/__init__.py'):
            is_our_tools = True
    if not is_our_tools:
        del sys.modules['tools']

# Force-import local tools package immediately to cache it in sys.modules
import tools

import json
import time
import argparse
import importlib
import requests
import yaml
from datetime import datetime
from dotenv import load_dotenv

import litellm

# --- MONKEY PATCH LITELLM TO FIX CREWAI CACHE_BREAKPOINT BUG ---
original_completion = litellm.completion
def patched_completion(*args, **kwargs):
    if "messages" in kwargs:
        for msg in kwargs["messages"]:
            if isinstance(msg, dict):
                msg.pop("cache_breakpoint", None)
    return original_completion(*args, **kwargs)
litellm.completion = patched_completion
# ---------------------------------------------------------------

# ── Load .env first, before anything else ────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from band.message_schema import BandMessage, make_status_update

# ── Constants ─────────────────────────────────────────────────────────────────
BAND_BASE_URL  = "https://app.band.ai"
CONFIG_PATH    = os.path.join(os.path.dirname(__file__), "agent_config.yaml")
AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "band", "audit_log.json")


# ── Config loader ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


# ── Band HTTP helpers ─────────────────────────────────────────────────────────

def band_headers(api_key: str) -> dict:
    return {
        "X-API-Key":    api_key,
        "Content-Type": "application/json",
    }


def create_band_room(orchestrator_api_key: str, room_name: str) -> str:
    """
    Create a new Band chat room.
    Returns the room's chat_id string.
    """
    url  = f"{BAND_BASE_URL}/api/v1/agent/chats"
    body = {"chat": {"title": room_name}}

    resp = requests.post(url, headers=band_headers(orchestrator_api_key), json=body)
    resp.raise_for_status()

    chat_id = resp.json()["data"]["id"]
    print(f"[main] ✅ Band room created → chat_id: {chat_id}")
    return chat_id


def add_participant(orchestrator_api_key: str, chat_id: str, agent_id: str, agent_name: str):
    """Add an agent as a participant to the Band room."""
    url  = f"{BAND_BASE_URL}/api/v1/agent/chats/{chat_id}/participants"
    body = {"participant": {"participant_id": agent_id}}

    resp = requests.post(url, headers=band_headers(orchestrator_api_key), json=body)
    if resp.status_code in (201, 200):
        print(f"[main]   + Added participant: {agent_name}")
    else:
        print(f"[main]   ⚠ Could not add {agent_name}: {resp.status_code} {resp.text}")


def post_to_band(api_key: str, chat_id: str, band_msg: BandMessage, mentions: list = None):
    url = f"{BAND_BASE_URL}/api/v1/agent/chats/{chat_id}/messages"

    full_content = (
        f"{band_msg.content}\n\n"
        f"```json\n{band_msg.model_dump_json(indent=2)}\n```"
    )

    body = {
        "message": {
            "content": full_content,
            "mentions": mentions if mentions else [{"id": "00000000-0000-0000-0000-000000000000"}]
        }
    }

    resp = requests.post(url, headers=band_headers(api_key), json=body)

    if resp.status_code in (200, 201):
        print(f"[main]   📨 Posted to Band: {band_msg.content[:80]}")
        return resp.json()
    else:
        print(f"[main]   ⚠ Band post failed ({resp.status_code}): {resp.text[:120]}")
        return None

# ── Audit logger ──────────────────────────────────────────────────────────────

def save_audit_log(messages: list[BandMessage], chat_id: str):
    """
    Save the full debate transcript to band/audit_log.json.
    This is the SEBI-style audit trail — every message, in order, with
    sender, type, timestamp, and full payload.
    """
    os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

    log = {
        "chat_id":    chat_id,
        "generated":  datetime.utcnow().isoformat(),
        "total_messages": len(messages),
        "messages":   [m.model_dump() for m in messages],
    }

    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    print(f"[main] 📋 Audit log saved → {AUDIT_LOG_PATH}")


# ── Agent runner ──────────────────────────────────────────────────────────────

def run_agent(agent_cfg: dict) -> BandMessage | None:
    """
    Dynamically import and run an agent's runner function.
    Returns a BandMessage or None if the agent fails.
    """
    module_path = agent_cfg["module"]
    runner_fn   = agent_cfg["runner_fn"]
    name        = agent_cfg["name"]

    try:
        print(f"\n[main] 🤖 Running {name}...")
        module = importlib.import_module(module_path)
        fn     = getattr(module, runner_fn)
        result = fn()
        print(f"[main] ✅ {name} completed.")
        return result

    except Exception as e:
        print(f"[main] ❌ {name} failed: {e}")
        return None

def run_defense(agent_cfg: dict, original_proposal: BandMessage, challenges: list[BandMessage]) -> BandMessage | None:
    module_path = agent_cfg["module"]
    name        = agent_cfg["name"]
    
    try:
        print(f"\n[main] 🛡️ Running defense for {name}...")
        module = importlib.import_module(module_path)
        fn     = getattr(module, "run_defense_agent")
        result = fn(original_proposal, challenges)
        print(f"[main] ✅ {name} defense completed.")
        return result

    except Exception as e:
        print(f"[main] ❌ {name} defense failed: {e}")
        return None


def run_review_agent(agent_cfg: dict, all_messages: list[BandMessage]) -> BandMessage | None:
    """
    Run a review agent, passing all collected messages as context.
    Review agents (stress_test, compliance, arbiter) take messages as input.
    """
    module_path = agent_cfg["module"]
    runner_fn   = agent_cfg["runner_fn"]
    name        = agent_cfg["name"]

    try:
        print(f"\n[main] 🔍 Running {name}...")
        module = importlib.import_module(module_path)
        fn     = getattr(module, runner_fn)
        result = fn(all_messages)          # review agents receive all_messages list
        print(f"[main] ✅ {name} completed.")
        return result

    except Exception as e:
        print(f"[main] ❌ {name} failed: {e}")
        return None


# ── Main orchestrator ─────────────────────────────────────────────────────────

def main():
    # ── Parse CLI args ────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="AlgoDesk Multi-Agent Debate")
    parser.add_argument("--mode",        choices=["mock", "live"], default=None,
                        help="Override MARKET_DATA_MODE and NEWS_SCRAPER_MODE")
    parser.add_argument("--skip-review", action="store_true",
                        help="Only run strategy agents (for faster testing)")
    parser.add_argument("--no-band",     action="store_true",
                        help="Skip Band posting (run agents locally only)")
    parser.add_argument("--tickers",     type=str, default=None,
                        help="Comma-separated list of tickers to run on")
    args = parser.parse_args()

    # ── Apply mode override ───────────────────────────────────────────────────
    if args.mode:
        os.environ["MARKET_DATA_MODE"]  = args.mode
        os.environ["NEWS_SCRAPER_MODE"] = args.mode
        print(f"[main] Mode override → {args.mode}")

    # ── Apply ticker universe override ────────────────────────────────────────
    if args.tickers:
        from tools.market_data import session_tickers, _normalize_ticker
        ticker_list = [t.strip() for t in args.tickers.split(",") if t.strip()]
        normalized_tickers = [_normalize_ticker(t) for t in ticker_list]
        session_tickers.set(normalized_tickers)
        print(f"[main] Ticker universe override → {normalized_tickers}")

    # ── Load config ───────────────────────────────────────────────────────────
    config     = load_config()
    all_agents = sorted(config["agents"], key=lambda a: a["run_order"])
    room_cfg   = config["room"]

    strategy_agents = [a for a in all_agents if a["role"] == "strategy" and a["enabled"]]
    review_agents   = [a for a in all_agents if a["role"] != "strategy" and a["enabled"]]

    print(f"\n{'='*60}")
    print(f"  AlgoDesk — Multi-Agent Quant Debate")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}")
    print(f"  Strategy agents : {[a['name'] for a in strategy_agents]}")
    print(f"  Review agents   : {[a['name'] for a in review_agents]}")
    print(f"  Band posting    : {'disabled (--no-band)' if args.no_band else 'enabled'}")
    print(f"{'='*60}\n")

    # ── Band setup ────────────────────────────────────────────────────────────
    chat_id             = None
    orchestrator_key    = os.getenv("BAND_ORCHESTRATOR_API_KEY") or os.getenv("BAND_API_KEY")
    agent_api_keys      = {}      # agent_name → api_key

    # Load per-agent API keys from env
    # Convention: BAND_API_KEY_MOMENTUM_AGENT, BAND_API_KEY_SENTIMENT_AGENT, etc.
    for agent in all_agents:
        env_key = f"BAND_API_KEY_{agent['name'].upper()}"
        key     = os.getenv(env_key) or orchestrator_key   # fallback to orchestrator key
        agent_api_keys[agent["name"]] = key

    if not args.no_band and orchestrator_key:
        try:
            chat_id = create_band_room(orchestrator_key, room_cfg["name"])
            time.sleep(0.5)
            
            # --- Integrate Band Agents ---
            # Add all configured agents to the Band room as participants
            for agent in all_agents:
                # Check for either <AGENT_NAME>_ID or BAND_<AGENT_NAME>_ID in .env
                agent_id_key1 = f"{agent['name'].upper()}_ID"
                agent_id_key2 = f"BAND_{agent['name'].upper()}_ID"
                agent_id = os.getenv(agent_id_key1) or os.getenv(agent_id_key2)
                
                if agent_id:
                    add_participant(orchestrator_key, chat_id, agent_id, agent["display_name"])
                    time.sleep(0.2)
            # -----------------------------
            
        except Exception as e:
            print(f"[main] ⚠ Could not create Band room: {e}")
            print(f"[main]   Continuing without Band posting.")
            chat_id = None
    elif not args.no_band:
        print("[main] ⚠ BAND_API_KEY not set in .env — skipping Band posting.")

    # ── Phase 1: Run strategy agents ─────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  PHASE 1 — Strategy Proposals")
    print(f"{'─'*60}")

    all_messages:   list[BandMessage] = []
    proposals:      list[BandMessage] = []

    for agent_cfg in strategy_agents:
        print(f"\n[main] ⏳ Waiting 20s for Groq API token bucket to refill...")
        time.sleep(20)
        
        band_msg = run_agent(agent_cfg)

        if band_msg is None:
            continue

        proposals.append(band_msg)
        all_messages.append(band_msg)

        # Post to Band room
        if chat_id and agent_api_keys.get(agent_cfg["name"]):
            # Find an ID to mention (Band requires 1-5 mentions). Pick another agent to avoid self-mention.
            mention_id = None
            for other_a in all_agents:
                if other_a["name"] != agent_cfg["name"]:
                    val = os.getenv(f"{other_a['name'].upper()}_ID") or os.getenv(f"BAND_{other_a['name'].upper()}_ID")
                    if val:
                        mention_id = val
                        break
            if not mention_id:
                mention_id = os.getenv("BAND_ORCHESTRATOR_AGENT_ID")

            mentions = [{"id": mention_id}] if mention_id else [{"id": "00000000-0000-0000-0000-000000000000"}]

            post_to_band(
                api_key  = agent_api_keys[agent_cfg["name"]],
                chat_id  = chat_id,
                band_msg = band_msg,
                mentions = mentions
            )
            time.sleep(1)   # small delay between posts

    print(f"\n[main] 📊 {len(proposals)} proposals collected from strategy agents.")

    if not proposals:
        print("[main] ❌ No proposals generated. Exiting.")
        return

    # ── Phase 2: Challenges (Stress Test) ─────────────────────────────────────
    if not args.skip_review:
        print(f"\n{'─'*60}")
        print(f"  PHASE 2 — Stress Test Challenges")
        print(f"{'─'*60}")

        stress_agent_cfg = next((a for a in review_agents if a["name"] == "stress_test_agent"), None)
        if stress_agent_cfg:
            print(f"\n[main] ⏳ Waiting 20s for Groq API token bucket to refill...")
            time.sleep(20)
            band_msg = run_review_agent(stress_agent_cfg, all_messages)
            if band_msg:
                all_messages.append(band_msg)
                
                # Post to Band room
                if chat_id and agent_api_keys.get(stress_agent_cfg["name"]):
                    mention_id = None
                    for other_a in all_agents:
                        if other_a["name"] != stress_agent_cfg["name"]:
                            val = os.getenv(f"{other_a['name'].upper()}_ID") or os.getenv(f"BAND_{other_a['name'].upper()}_ID")
                            if val:
                                mention_id = val
                                break
                    if not mention_id:
                        mention_id = os.getenv("BAND_ORCHESTRATOR_AGENT_ID")

                    mentions = [{"id": mention_id}] if mention_id else [{"id": "00000000-0000-0000-0000-000000000000"}]
                    post_to_band(
                        api_key=agent_api_keys[stress_agent_cfg["name"]],
                        chat_id=chat_id,
                        band_msg=band_msg,
                        mentions=mentions
                    )
                    time.sleep(1)

    # ── Phase 3: Defenses ─────────────────────────────────────────────────────
    if not args.skip_review:
        print(f"\n{'─'*60}")
        print(f"  PHASE 3 — Strategy Defenses")
        print(f"{'─'*60}")
        
        for agent_cfg in strategy_agents:
            # Find their original proposal
            orig_prop = next((p for p in proposals if p.sender == agent_cfg["name"]), None)
            if not orig_prop: continue
            
            # Find challenges targeting them
            strategy_name = orig_prop.payload.get("strategy") if orig_prop.payload else orig_prop.sender
            challenges = [m for m in all_messages if m.message_type == "challenge" and (m.payload or {}).get("target_strategy") == strategy_name]
            
            if challenges:
                # Add a 60-second sleep to avoid hitting Groq's Tokens-Per-Minute rate limit
                print(f"\n[main] ⏳ Waiting 60s to avoid API rate limits before running defense...")
                time.sleep(60)
                def_msg = run_defense(agent_cfg, orig_prop, challenges)
                if def_msg:
                    all_messages.append(def_msg)
                    
                    if chat_id and agent_api_keys.get(agent_cfg["name"]):
                        mention_id = None
                        for other_a in all_agents:
                            if other_a["name"] != agent_cfg["name"]:
                                val = os.getenv(f"{other_a['name'].upper()}_ID") or os.getenv(f"BAND_{other_a['name'].upper()}_ID")
                                if val:
                                    mention_id = val
                                    break
                        if not mention_id:
                            mention_id = os.getenv("BAND_ORCHESTRATOR_AGENT_ID")

                        mentions = [{"id": mention_id}] if mention_id else [{"id": "00000000-0000-0000-0000-000000000000"}]
                        post_to_band(
                            api_key=agent_api_keys[agent_cfg["name"]],
                            chat_id=chat_id,
                            band_msg=def_msg,
                            mentions=mentions
                        )
                        time.sleep(1)

    # ── Phase 4: Final Review (Compliance & Arbiter) ──────────────────────────
    if not args.skip_review:
        print(f"\n{'─'*60}")
        print(f"  PHASE 4 — Compliance & Portfolio Arbiter")
        print(f"{'─'*60}")

        final_agents = [a for a in review_agents if a["name"] in ["compliance_agent", "portfolio_arbiter"]]
        for agent_cfg in final_agents:
            band_msg = run_review_agent(agent_cfg, all_messages)

            if band_msg is None:
                continue

            all_messages.append(band_msg)

            # Post to Band room
            if chat_id and agent_api_keys.get(agent_cfg["name"]):
                mention_id = None
                for other_a in all_agents:
                    if other_a["name"] != agent_cfg["name"]:
                        val = os.getenv(f"{other_a['name'].upper()}_ID") or os.getenv(f"BAND_{other_a['name'].upper()}_ID")
                        if val:
                            mention_id = val
                            break
                if not mention_id:
                    mention_id = os.getenv("BAND_ORCHESTRATOR_AGENT_ID")

                mentions = [{"id": mention_id}] if mention_id else [{"id": "00000000-0000-0000-0000-000000000000"}]
                post_to_band(
                    api_key=agent_api_keys[agent_cfg["name"]],
                    chat_id=chat_id,
                    band_msg=band_msg,
                    mentions=mentions
                )
                time.sleep(1)

            if band_msg.message_type == "final_verdict":
                print(f"\n[main] 🏁 Final verdict received from {agent_cfg['name']}.")
                break

    # ── Phase 3: Save audit log ───────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  PHASE 3 — Audit Trail")
    print(f"{'─'*60}")

    save_audit_log(all_messages, chat_id or "local-run")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  DEBATE COMPLETE")
    print(f"{'='*60}")
    print(f"  Total messages : {len(all_messages)}")
    print(f"  Band room      : {f'https://app.band.ai/chat/{chat_id}' if chat_id else 'N/A'}")
    print(f"  Audit log      : {AUDIT_LOG_PATH}")
    print(f"{'='*60}\n")

    # Print final message summary
    for msg in all_messages:
        icon = {
            "proposal":           "📝",
            "challenge":          "⚔️ ",
            "revision":           "🔄",
            "compliance_verdict": "✅",
            "final_verdict":      "🏆",
            "stress_result":      "🔥",
            "status_update":      "ℹ️ ",
        }.get(msg.message_type, "💬")
        print(f"  {icon} [{msg.sender}] {msg.content[:70]}")


# ── FastAPI / SSE Session Helpers ─────────────────────────────────────────────

async def to_thread_with_context(func, *args, **kwargs):
    """Runs a function in a background thread, propagating context variables."""
    import contextvars
    import asyncio
    ctx = contextvars.copy_context()
    return await asyncio.to_thread(ctx.run, func, *args, **kwargs)


def pre_fetch_historical_data(tickers: list[str]):
    """
    Pre-fetch prices for tickers and benchmark in the background to warm the cache.
    """
    try:
        from analytics.portfolio_returns import fetch_historical_prices
        from analytics.benchmark import fetch_benchmark_returns
        print(f"[Analytics Pre-fetch] Starting background data download for: {tickers}")
        # Warm cache for tickers (3y lookback is default)
        fetch_historical_prices(tickers, period="3y")
        # Warm cache for benchmark
        fetch_benchmark_returns("^NSEI", period="3y")
        print("[Analytics Pre-fetch] Background cache warming complete.")
    except Exception as e:
        print(f"[Analytics Pre-fetch] Failed to pre-fetch historical data: {e}")


async def create_and_run_session(session_id: str, tickers: list[str], background_tasks):
    """
    Create a new AlgoDesk debate session asynchronously (FastAPI integration).
    """
    from band.room_manager import BandRoomManager
    from api.server import register_session
    
    # 1. Create a Band room manager
    room_manager = BandRoomManager(room_name=f"algodesk-{session_id}")
    await room_manager.create_room()
    
    # 2. Register session so server endpoints can resolve it
    register_session(session_id, {
        "room_manager": room_manager,
        "tickers": tickers,
        "status": "running"
    })
    
    # 3. Queue the background debate task
    background_tasks.add_task(run_debate_pipeline_async, session_id, tickers, room_manager)
    
    # 4. Queue the background pre-fetching task to warm the cache asynchronously
    background_tasks.add_task(pre_fetch_historical_data, tickers)
    
    return room_manager


async def run_debate_pipeline_async(session_id: str, tickers: list[str], room_manager):
    """
    Run the complete 4-phase debate pipeline in the background.
    Communicates live updates to the frontend via the BandRoomManager queue.
    """
    import asyncio
    from band.message_schema import make_status_update
    from api.server import get_session_data
    from tools.market_data import session_tickers, _normalize_ticker

    if tickers:
        normalized_tickers = [_normalize_ticker(t) for t in tickers]
        session_tickers.set(normalized_tickers)
        
    from tools.market_regime import detect_market_regime
    regime_info = detect_market_regime()
    print(f"[main] Detected Market Regime: {regime_info['regime'].upper()} (Confidence: {regime_info['confidence']})")
    
    # Load config and order agents
    config = load_config()
    all_agents = sorted(config["agents"], key=lambda a: a["run_order"])
    
    strategy_agents = [a for a in all_agents if a["role"] == "strategy" and a["enabled"]]
    review_agents = [a for a in all_agents if a["role"] != "strategy" and a["enabled"]]
    
    # Mode overrides
    mode = os.getenv("MARKET_DATA_MODE", "mock").lower()
    is_mock = (mode == "mock")
    
    scan_sleep = 2.0 if is_mock else 20.0
    defense_sleep = 3.0 if is_mock else 60.0
    
    all_messages = []
    proposals = []
    
    # ── Phase 1: Strategy Proposals ──────────────────────────────────────────
    for agent_cfg in strategy_agents:
        # Post active thinking status update
        status = make_status_update(
            sender=agent_cfg["name"],
            message=f"Momentum & returns scanner running for ticker universe..."
        )
        await room_manager.post_message(status.model_dump(), agent_cfg["name"])
        
        await asyncio.sleep(scan_sleep)
        
        # Execute agent runner in thread
        band_msg = await to_thread_with_context(run_agent, agent_cfg)
        if band_msg:
            proposals.append(band_msg)
            all_messages.append(band_msg)
            await room_manager.post_message(band_msg.model_dump(), agent_cfg["name"])
            
    if not proposals:
        status = make_status_update(
            sender="portfolio_arbiter",
            message="No proposals were generated. Debate pipeline terminating."
        )
        await room_manager.post_message(status.model_dump(), "portfolio_arbiter")
        sess = get_session_data(session_id)
        if sess:
            sess["status"] = "failed"
        return
        
    # ── Phase 2: Stress Test Challenges ───────────────────────────────────────
    stress_agent_cfg = next((a for a in review_agents if a["name"] == "stress_test_agent"), None)
    if stress_agent_cfg:
        status = make_status_update(
            sender=stress_agent_cfg["name"],
            message="Evaluating historical drawdown limit breaches and extreme market shocks..."
        )
        await room_manager.post_message(status.model_dump(), stress_agent_cfg["name"])
        
        await asyncio.sleep(scan_sleep)
        
        band_msg = await to_thread_with_context(run_review_agent, stress_agent_cfg, all_messages)
        if band_msg:
            all_messages.append(band_msg)
            await room_manager.post_message(band_msg.model_dump(), stress_agent_cfg["name"])
            
    # ── Phase 3: Strategy Defenses ───────────────────────────────────────────
    for agent_cfg in strategy_agents:
        orig_prop = next((p for p in proposals if p.sender == agent_cfg["name"]), None)
        if not orig_prop:
            continue
            
        strategy_name = orig_prop.payload.get("strategy") if orig_prop.payload else orig_prop.sender
        challenges = [
            m for m in all_messages 
            if m.message_type == "challenge" and (m.payload or {}).get("target_strategy") == strategy_name
        ]
        
        if challenges:
            status = make_status_update(
                sender=agent_cfg["name"],
                message=f"Drafting quantitative defense and parameter revision in response to stress tests..."
            )
            await room_manager.post_message(status.model_dump(), agent_cfg["name"])
            
            await asyncio.sleep(defense_sleep)
            
            def_msg = await to_thread_with_context(run_defense, agent_cfg, orig_prop, challenges)
            if def_msg:
                all_messages.append(def_msg)
                await room_manager.post_message(def_msg.model_dump(), agent_cfg["name"])
                
    # ── Phase 4: Final Review (Compliance & Portfolio Arbiter) ───────────────
    final_agents = [a for a in review_agents if a["name"] in ["compliance_agent", "portfolio_arbiter"]]
    for agent_cfg in final_agents:
        status = make_status_update(
            sender=agent_cfg["name"],
            message=f"Verifying regulatory standards and auditing allocations..." if agent_cfg["name"] == "compliance_agent" else "Synthesizing portfolio weights and checking correlation risk..."
        )
        await room_manager.post_message(status.model_dump(), agent_cfg["name"])
        
        await asyncio.sleep(scan_sleep)
        
        band_msg = await to_thread_with_context(run_review_agent, agent_cfg, all_messages)
        if band_msg:
            all_messages.append(band_msg)
            await room_manager.post_message(band_msg.model_dump(), agent_cfg["name"])
            
    # ── Save Audit Log & Complete ────────────────────────────────────────────
    await to_thread_with_context(save_audit_log, all_messages, session_id)
    
    sess = get_session_data(session_id)
    if sess:
        sess["status"] = "completed"


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()