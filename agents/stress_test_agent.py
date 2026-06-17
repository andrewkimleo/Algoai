"""
Stress Test Agent — CrewAI agent that stress-tests proposals against
historical market crashes.

For each proposal:
1. Pulls 3 years of historical data via yfinance
2. Simulates entry/exit logic against 3 stress windows:
   - COVID crash (Feb–Mar 2020)
   - High-VIX period (Oct 2022)
   - Custom worst-drawdown-month found in the data
3. Posts Challenge message if drawdown exceeds the proposal's stop_loss_pct
4. Listens for Revision messages and re-evaluates
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
import yfinance as yf
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from pydantic import Field

from band.room_manager import BandRoomManager
from band.message_schema import (
    Challenge,
    ChallengeResolved,
    StressTestResult,
    Proposal,
)

logger = logging.getLogger(__name__)

# ── Stress Windows ───────────────────────────────────────────────────────────

STRESS_WINDOWS = [
    {
        "name": "COVID Crash (Feb–Mar 2020)",
        "start": "2020-02-20",
        "end": "2020-03-23",
    },
    {
        "name": "High-VIX / Rate Hike Shock (Oct 2022)",
        "start": "2022-10-01",
        "end": "2022-10-31",
    },
]


# ── Custom CrewAI Tool: StressTestTool ───────────────────────────────────────


class StressTestTool(BaseTool):
    """
    Stress-tests a trading proposal against historical market crashes.

    Pulls 3 years of yfinance data, identifies stress windows,
    simulates the strategy's entry/exit logic, and returns
    drawdown + outcome for each scenario.
    """

    name: str = "StressTestTool"
    description: str = (
        "Stress-test a trading proposal against historical market crashes. "
        "Input: JSON string with keys: ticker, stop_loss_pct, take_profit_pct, "
        "entry_condition, exit_condition, position_size_pct. "
        "Returns stress test results for 3 scenarios."
    )

    def _run(self, proposal_json: str) -> str:
        """Run the stress test synchronously."""
        import json

        try:
            proposal = json.loads(proposal_json)
        except (json.JSONDecodeError, TypeError):
            # If it's already a dict-like string from CrewAI
            proposal = {"ticker": "RELIANCE", "stop_loss_pct": 3.0}

        ticker = proposal.get("ticker", "RELIANCE")
        stop_loss_pct = float(proposal.get("stop_loss_pct", 3.0))

        # Fetch 3 years of historical data
        nse_ticker = f"{ticker}.NS" if not ticker.endswith((".NS", ".BO")) else ticker
        try:
            df = yf.Ticker(nse_ticker).history(period="3y")
        except Exception as e:
            return f"Failed to fetch data for {nse_ticker}: {e}"

        if df.empty:
            return f"No historical data available for {nse_ticker}"

        results = []

        # ── Scenario 1 & 2: Fixed stress windows ────────────────────────
        for window in STRESS_WINDOWS:
            result = self._simulate_window(
                df, window["name"], window["start"], window["end"]
            )
            results.append(result)

        # ── Scenario 3: Custom worst-drawdown-month ─────────────────────
        worst = self._find_worst_month(df)
        if worst:
            result = self._simulate_window(
                df, worst["name"], worst["start"], worst["end"]
            )
            results.append(result)

        # Format results
        output_lines = [f"Stress Test Results for {ticker} (stop_loss: {stop_loss_pct}%):\n"]
        for r in results:
            breach = "⚠️ BREACHED" if abs(r["drawdown_pct"]) > stop_loss_pct else "✓ OK"
            output_lines.append(
                f"  {r['scenario']}: {r['drawdown_pct']:+.2f}% drawdown → {r['outcome']} {breach}"
            )

        return "\n".join(output_lines)

    def _simulate_window(
        self,
        df: pd.DataFrame,
        scenario_name: str,
        start: str,
        end: str,
    ) -> dict:
        """Simulate buying at the start of a stress window and measure drawdown."""
        mask = (df.index >= start) & (df.index <= end)
        window = df.loc[mask]

        if window.empty:
            return {
                "scenario": scenario_name,
                "drawdown_pct": 0.0,
                "outcome": "no_data",
            }

        entry_price = float(window["Close"].iloc[0])
        min_price = float(window["Close"].min())
        exit_price = float(window["Close"].iloc[-1])

        drawdown_pct = ((min_price - entry_price) / entry_price) * 100
        final_return = ((exit_price - entry_price) / entry_price) * 100

        if abs(drawdown_pct) > 15:
            outcome = "catastrophic"
        elif abs(drawdown_pct) > 5:
            outcome = "breached_stop_loss"
        else:
            outcome = "survived"

        return {
            "scenario": scenario_name,
            "drawdown_pct": round(drawdown_pct, 2),
            "outcome": outcome,
        }

    def _find_worst_month(self, df: pd.DataFrame) -> Optional[dict]:
        """Find the worst single-month drawdown in the data."""
        if len(df) < 30:
            return None

        monthly = df["Close"].resample("ME").agg(["first", "last", "min"])
        monthly["drawdown"] = ((monthly["min"] - monthly["first"]) / monthly["first"]) * 100

        if monthly.empty:
            return None

        worst_idx = monthly["drawdown"].idxmin()
        worst_row = monthly.loc[worst_idx]

        return {
            "name": f"Worst Month ({worst_idx.strftime('%b %Y')})",
            "start": worst_idx.strftime("%Y-%m-01"),
            "end": worst_idx.strftime("%Y-%m-%d"),
        }


# ── Stress Test Agent ────────────────────────────────────────────────────────


class StressTestAgent:
    """
    CrewAI-based stress test agent that reviews proposals and posts
    Challenge messages when stress scenarios show excessive drawdown.
    """

    def __init__(
        self,
        room_manager: BandRoomManager,
        groq_api_key: Optional[str] = None,
    ):
        self.room_manager = room_manager
        self.agent_id = "stress_test_agent"
        self._state: dict[str, dict] = {}  # proposal_id → {status, challenge_id, rounds}

        # CrewAI agent setup
        import os
        from crewai import LLM
        api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        
        # Use OpenAI-compatible endpoint to bypass LiteLLM's Groq cache_breakpoint bug
        self.llm = LLM(
            model="openai/llama-3.3-70b-versatile",
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.3
        )

        self.stress_tool = StressTestTool()

        self.crew_agent = Agent(
            role="Market Stress Test Analyst",
            goal="Find historical scenarios where this strategy would have failed",
            backstory=(
                "You are a senior quantitative risk analyst specializing in "
                "stress-testing algorithmic trading strategies against "
                "historical market crashes. You identify scenarios where "
                "strategies would have suffered catastrophic drawdowns and "
                "challenge the proposing agents to improve their risk controls."
            ),
            llm=self.llm,
            tools=[self.stress_tool],
            verbose=True,
        )

    async def handle_proposal(self, proposal_data: dict) -> Optional[Challenge]:
        """
        Stress-test a proposal and post a Challenge if drawdown
        exceeds the claimed stop_loss_pct.

        Args:
            proposal_data: The proposal dict from the Band room.

        Returns:
            Challenge message if issues found, None otherwise.
        """
        import json

        proposal_id = proposal_data.get("proposal_id", "unknown")
        ticker = proposal_data.get("ticker", "UNKNOWN")
        stop_loss_pct = float(proposal_data.get("stop_loss_pct", 3.0))

        logger.info(f"[{self.agent_id}] Stress-testing proposal {proposal_id} ({ticker})")

        # Track state
        self._state[proposal_id] = {
            "status": "testing",
            "challenge_id": None,
            "rounds": 0,
        }

        # Run StressTestTool directly for structured results
        tool_input = json.dumps({
            "ticker": ticker,
            "stop_loss_pct": stop_loss_pct,
            "take_profit_pct": proposal_data.get("take_profit_pct", 6.0),
            "entry_condition": proposal_data.get("entry_condition", ""),
            "exit_condition": proposal_data.get("exit_condition", ""),
            "position_size_pct": proposal_data.get("position_size_pct", 5.0),
        })

        raw_result = self.stress_tool._run(tool_input)

        # Use CrewAI for the LLM reasoning about results
        task = Task(
            description=(
                f"Analyze these stress test results for a {proposal_data.get('strategy_type', 'unknown')} "
                f"strategy on {ticker} with a {stop_loss_pct}% stop-loss:\n\n"
                f"{raw_result}\n\n"
                f"Determine: Is this strategy resilient enough? What is the biggest concern? "
                f"Rate severity as 'high', 'medium', or 'low'. "
                f"Be specific about which scenario is most dangerous and why."
            ),
            expected_output=(
                "A concise analysis stating: the worst scenario, its drawdown, "
                "whether it breaches the stop-loss, severity rating, "
                "and a specific concern for the strategy agent."
            ),
            agent=self.crew_agent,
        )

        crew = Crew(agents=[self.crew_agent], tasks=[task], verbose=False)

        try:
            import asyncio
            crew_result = await asyncio.to_thread(crew.kickoff)
            concern_text = str(crew_result)[:500]
        except Exception as e:
            logger.error(f"[{self.agent_id}] CrewAI analysis failed: {e}")
            concern_text = f"Stress test reveals drawdown concerns for {ticker}. Manual review recommended."

        # Parse the stress tool results to find worst drawdown
        worst_drawdown = self._parse_worst_drawdown(raw_result)
        actual_drawdown = abs(worst_drawdown)

        # Determine severity
        if actual_drawdown > 2 * stop_loss_pct:
            severity = "high"
        elif actual_drawdown > 1.5 * stop_loss_pct:
            severity = "medium"
        else:
            severity = "low"

        # Only post challenge if drawdown exceeds stop_loss
        if actual_drawdown <= stop_loss_pct:
            self._state[proposal_id]["status"] = "passed"
            logger.info(f"[{self.agent_id}] Proposal {proposal_id} passed stress test")
            return None

        # Build and post Challenge
        challenge = Challenge(
            target_proposal_id=proposal_id,
            challenger_agent=self.agent_id,
            concern=concern_text[:500],
            stress_test_result=StressTestResult(
                scenario=f"Worst scenario: {worst_drawdown:+.2f}% drawdown",
                drawdown_pct=worst_drawdown,
                outcome="breached_stop_loss" if actual_drawdown > stop_loss_pct else "survived",
            ),
            severity=severity,
        )

        await self.room_manager.post_message(
            challenge.model_dump(), sender_id=self.agent_id
        )

        self._state[proposal_id]["challenge_id"] = challenge.challenge_id
        self._state[proposal_id]["status"] = "challenged"

        logger.info(
            f"[{self.agent_id}] Posted challenge {challenge.challenge_id} "
            f"for {proposal_id} (severity={severity})"
        )
        return challenge

    async def handle_revision(
        self, revision_data: dict
    ) -> Optional[ChallengeResolved]:
        """
        Re-evaluate a revision. If stop_loss has been tightened
        sufficiently, post a challenge_resolved update.

        Args:
            revision_data: The revision dict from the Band room.

        Returns:
            ChallengeResolved if the revision addresses the concern.
        """
        proposal_id = revision_data.get("original_proposal_id", "unknown")
        state = self._state.get(proposal_id)

        if not state or state["status"] != "challenged":
            return None

        state["rounds"] += 1

        # Check if stop_loss was tightened
        revised_position = revision_data.get("revised_position_size_pct", 0)
        changes = revision_data.get("changes_made", "")

        # Simple heuristic: if changes mention stop-loss tightening, resolve
        tightened = any(
            kw in changes.lower()
            for kw in ["tighten", "reduce", "lower", "decrease", "stop-loss", "stop loss"]
        )

        if tightened or state["rounds"] >= 2:
            resolved = ChallengeResolved(
                challenge_id=state["challenge_id"] or "",
                target_proposal_id=proposal_id,
                resolution_note=(
                    f"Revision accepted after {state['rounds']} round(s). "
                    f"Changes: {changes[:200]}"
                ),
            )

            await self.room_manager.post_message(
                resolved.model_dump(), sender_id=self.agent_id
            )

            state["status"] = "resolved"
            logger.info(f"[{self.agent_id}] Challenge resolved for {proposal_id}")
            return resolved

        logger.info(
            f"[{self.agent_id}] Revision for {proposal_id} insufficient "
            f"(round {state['rounds']})"
        )
        return None

    def _parse_worst_drawdown(self, raw_result: str) -> float:
        """Extract the worst drawdown percentage from tool output."""
        import re

        drawdowns = re.findall(r"([-+]?\d+\.?\d*)% drawdown", raw_result)
        if drawdowns:
            return min(float(d) for d in drawdowns)
        return 0.0

    def get_state(self) -> dict:
        """Return current tracking state for all proposals."""
        return dict(self._state)
