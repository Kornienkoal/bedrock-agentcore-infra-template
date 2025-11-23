"""
Memory utilities for AgentCore Memory.

Exposes MemoryHooks: a Strands HookProvider that records agent conversations into
Amazon Bedrock AgentCore Memory using bedrock_agentcore.memory.MemoryClient.
"""

from __future__ import annotations

import logging

from bedrock_agentcore.memory import MemoryClient as AcMemoryClient
from strands.hooks.events import AfterInvocationEvent, MessageAddedEvent
from strands.hooks.registry import HookProvider, HookRegistry


class MemoryHooks(HookProvider):
    """Strands hooks that capture messages and persist them to AgentCore Memory.

    The hook collects user/assistant text blocks from MessageAddedEvent and, after the
    agent invocation completes, writes a single memory event containing all messages.
    """

    def __init__(
        self,
        memory_client: AcMemoryClient,
        memory_id: str,
        actor_id: str,
        session_id: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self._client = memory_client
        self._memory_id = memory_id
        self._actor_id = actor_id
        self._session_id = session_id
        self._logger = logger or logging.getLogger(__name__)
        self._messages: list[tuple[str, str]] = []  # (text, ROLE)

    def register_hooks(self, registry: HookRegistry, **_kwargs) -> None:
        # Collect messages as they are added to the agent conversation
        registry.add_callback(MessageAddedEvent, self._on_message)
        # When invocation completes, persist the collected messages as a single event
        registry.add_callback(AfterInvocationEvent, self._on_after_invocation)

    def _on_message(self, event: MessageAddedEvent) -> None:
        # Extract plain text from the message content blocks
        blocks = event.message.get("content", [])
        if not isinstance(blocks, list):
            return
        texts: list[str] = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            text = b.get("text")
            if isinstance(text, str) and text:
                texts.append(text)
        if not texts:
            return

        role_literal = event.message.get("role", "user")  # "user" | "assistant"
        role = "USER" if role_literal == "user" else "ASSISTANT"

        # Join multiple text blocks conservatively
        joined = "\n".join(texts)
        self._messages.append((joined, role))

    def _on_after_invocation(self, _event: AfterInvocationEvent) -> None:
        if not self._messages:
            return
        # Create one memory event with all collected messages
        try:
            # Pass a copy so subsequent buffer clear doesn't mutate the event payload
            to_persist = list(self._messages)
            self._client.create_event(
                memory_id=self._memory_id,
                actor_id=self._actor_id,
                session_id=self._session_id,
                messages=to_persist,
            )
            self._logger.info(
                f"AgentCore Memory: stored event with {len(self._messages)} messages for actor={self._actor_id} session={self._session_id}"
            )
        except Exception as e:  # pragma: no cover - defensive, non-fatal
            self._logger.warning(f"AgentCore Memory write failed (non-fatal): {e}")
        # Reset buffer for next invocation regardless
        self._messages.clear()
