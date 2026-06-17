"""
Band Room Manager — handles the Band room lifecycle for agent communication.

Uses the band-sdk Python package for real Band integration.
Falls back to "mock mode" (console logging) when BAND_API_KEY is not set,
so the system works for local dev/demo without a real Band account.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class BandRoomManager:
    """
    Manages a Band room for AlgoDesk agent communication.

    In mock mode (no BAND_API_KEY), messages are stored in-memory
    and printed to console — the full pipeline still works.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        room_name: str = "algodesk-debate-room",
    ):
        self.api_key = api_key or os.getenv("BAND_API_KEY", "")
        self.room_name = room_name
        self.room_id: Optional[str] = None
        self.mock_mode = not bool(self.api_key)
        self._client: Any = None
        self._participants: dict[str, str] = {}  # agent_name → agent_id
        self._messages: list[dict] = []  # in-memory message store
        self._listeners: list[Callable] = []
        self._message_queues: list[asyncio.Queue] = []  # for SSE streaming

        if self.mock_mode:
            logger.warning(
                "BAND_API_KEY not set — running in MOCK MODE. "
                "Messages will be stored locally and printed to console."
            )
        else:
            logger.info(f"Band configured with room: {room_name}")

    # ── Room Lifecycle ───────────────────────────────────────────────────────

    async def create_room(self) -> str:
        """
        Create the Band room and store the room_id.

        Returns:
            The room_id (or a mock ID in mock mode).
        """
        if self.mock_mode:
            self.room_id = f"mock_room_{self.room_name}"
            logger.info(f"[MOCK] Created room: {self.room_id}")
            return self.room_id

        try:
            # TODO: Replace with actual band-sdk API call:
            #   from band import BandClient
            #   self._client = BandClient(api_key=self.api_key)
            #   room = await self._client.create_room(name=self.room_name)
            #   self.room_id = room.id
            import httpx

            async with httpx.AsyncClient(
                base_url="https://app.band.ai",
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as client:
                resp = await client.post(
                    "/api/v1/agent/chats",
                    json={"chat": {"title": self.room_name}},
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                self.room_id = data.get("id", f"room_{self.room_name}")

            logger.info(f"Created Band room: {self.room_id}")
            return self.room_id

        except Exception as e:
            logger.error(f"Failed to create Band room: {e}. Falling back to mock mode.")
            self.mock_mode = True
            self.room_id = f"mock_room_{self.room_name}"
            return self.room_id

    async def add_agent(self, agent_name: str, agent_id: str) -> None:
        """
        Add an agent as a participant in the Band room.

        Args:
            agent_name: Human-readable agent name (e.g., "stress_test_agent").
            agent_id: The Band agent UUID.
        """
        self._participants[agent_name] = agent_id

        if self.mock_mode:
            logger.info(f"[MOCK] Added agent: {agent_name} ({agent_id})")
            return

        try:
            # TODO: Replace with actual band-sdk API call:
            #   await self._client.add_participant(self.room_id, agent_id)
            import httpx

            async with httpx.AsyncClient(
                base_url="https://app.band.ai",
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as client:
                await client.post(
                    f"/api/v1/agent/chats/{self.room_id}/participants",
                    json={"participant": {"id": agent_id}},
                )

            logger.info(f"Added {agent_name} to Band room {self.room_id}")

        except Exception as e:
            logger.warning(f"Failed to add {agent_name} to Band room: {e}")

    # ── Messaging ────────────────────────────────────────────────────────────

    async def post_message(self, message: dict, sender_id: str) -> None:
        """
        Post a structured JSON message to the Band room.

        Args:
            message: The message dict (serialized Pydantic model).
            sender_id: ID of the sending agent.
        """
        timestamped = {
            **message,
            "sender_id": sender_id,
            "posted_at": datetime.now(timezone.utc).isoformat(),
        }

        # Always store locally
        self._messages.append(timestamped)

        # Push to all SSE queues
        for queue in self._message_queues:
            await queue.put(timestamped)

        # Notify listeners
        for callback in self._listeners:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(timestamped)
                else:
                    callback(timestamped)
            except Exception as e:
                logger.error(f"Listener callback failed: {e}")

        if self.mock_mode:
            msg_type = message.get("type", "unknown")
            sender = sender_id or "unknown"
            logger.info(
                f"[MOCK] [{sender}] → {msg_type}: "
                f"{json.dumps(message, indent=2, default=str)[:300]}"
            )
            return

        try:
            # TODO: Replace with actual band-sdk API call:
            #   await self._client.post_message(
            #       room_id=self.room_id,
            #       content=json.dumps(message),
            #   )
            import httpx

            async with httpx.AsyncClient(
                base_url="https://app.band.ai",
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            ) as client:
                await client.post(
                    f"/api/v1/agent/chats/{self.room_id}/messages",
                    json={
                        "message": {
                            "content": f"[AlgoDesk] {json.dumps(message, default=str)}",
                            "mentions": [],
                        }
                    },
                )

            logger.debug(f"Posted {message.get('type')} to Band room")

        except Exception as e:
            logger.warning(
                f"Failed to post to Band room: {e}. Message cached locally."
            )

    async def get_messages(
        self, since_timestamp: Optional[str] = None
    ) -> list[dict]:
        """
        Fetch room message history.

        Args:
            since_timestamp: ISO timestamp — only return messages after this time.

        Returns:
            List of message dicts, ordered by timestamp.
        """
        if since_timestamp:
            return [
                m
                for m in self._messages
                if m.get("posted_at", "") > since_timestamp
            ]
        return list(self._messages)

    async def listen(self, callback: Callable) -> None:
        """
        Register a callback that fires on each new message.

        In mock mode, this registers an in-memory listener.
        In live mode, this would open a websocket to Band.

        Args:
            callback: Async or sync callable that receives a message dict.
        """
        self._listeners.append(callback)

        if self.mock_mode:
            logger.info("[MOCK] Registered message listener")
            return

        # TODO: Replace with actual band-sdk websocket listener:
        #   async for message in self._client.listen(self.room_id):
        #       await callback(message)
        logger.info(f"Registered listener on Band room {self.room_id}")

    def subscribe_queue(self) -> asyncio.Queue:
        """
        Create and return an asyncio.Queue that receives all new messages.
        Used by SSE endpoints to stream messages to the frontend.

        Returns:
            An asyncio.Queue that will receive message dicts.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._message_queues.append(queue)
        return queue

    def unsubscribe_queue(self, queue: asyncio.Queue) -> None:
        """Remove a queue from the subscriber list."""
        if queue in self._message_queues:
            self._message_queues.remove(queue)

    def get_all_messages(self) -> list[dict]:
        """Get all cached messages (synchronous access)."""
        return list(self._messages)

    @property
    def is_mock(self) -> bool:
        """Whether the manager is running in mock mode."""
        return self.mock_mode
