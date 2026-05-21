from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PipelineEvent:
    type: str
    data: dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class EventBus:
    def __init__(self, history_size: int = 500) -> None:
        self._history_size = history_size
        self._history: dict[str, deque[PipelineEvent]] = defaultdict(
            lambda: deque(maxlen=self._history_size)
        )
        self._subscribers: dict[str, set[asyncio.Queue[PipelineEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        event = PipelineEvent(
            type=event_type,
            data=data,
            timestamp=datetime.now(timezone.utc),
        )
        async with self._lock:
            self._history[session_id].append(event)
            subscribers = list(self._subscribers.get(session_id, set()))
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                _ = queue.get_nowait()
                queue.put_nowait(event)

    async def subscribe(self, session_id: str) -> AsyncGenerator[PipelineEvent, None]:
        queue: asyncio.Queue[PipelineEvent] = asyncio.Queue(maxsize=1000)
        async with self._lock:
            for event in self._history.get(session_id, []):
                queue.put_nowait(event)
            self._subscribers[session_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[session_id].discard(queue)


event_bus = EventBus()

