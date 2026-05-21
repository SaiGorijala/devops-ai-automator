from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select

from .database import AsyncSessionLocal
from .event_bus import event_bus
from .models import PipelineSession
from .security import redact, secret_box


STAGES = {
    "init": "Server Init",
    "sonar": "SonarQube",
    "jenkins": "Jenkins CI",
    "scan": "Code Scan",
    "docker": "Docker Build",
    "push": "Hub Push",
    "deploy": "Deploy",
}


class SessionNotFoundError(KeyError):
    pass


class SessionStore:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def create(self, session_id: str, inputs: dict[str, Any]) -> None:
        encrypted_inputs = secret_box.encrypt_json(inputs)
        stages = {stage: "pending" for stage in STAGES}
        async with AsyncSessionLocal() as db:
            db.add(
                PipelineSession(
                    id=session_id,
                    status="running",
                    progress=0,
                    current_stage=None,
                    inputs=encrypted_inputs,
                    outputs={},
                    ai_interventions=[],
                    logs=[],
                    stages=stages,
                )
            )
            await db.commit()
        await event_bus.publish(
            session_id,
            "status",
            {"status": "running", "progress": 0, "stages": stages},
        )

    async def get(self, session_id: str) -> dict[str, Any]:
        async with AsyncSessionLocal() as db:
            session = await db.get(PipelineSession, session_id)
            if not session:
                raise SessionNotFoundError(session_id)
            return self._to_dict(session)

    async def append_log(
        self,
        session_id: str,
        text: str,
        log_type: str = "info",
        stage: str | None = None,
        **extra: Any,
    ) -> None:
        entry = {
            "text": text,
            "type": log_type,
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        await self._mutate(session_id, lambda session: self._append(session, "logs", entry))
        await event_bus.publish(session_id, "log", entry)

    async def add_ai_intervention(
        self,
        session_id: str,
        text: str,
        intervention_type: str = "action",
        stage: str | None = None,
        **extra: Any,
    ) -> None:
        entry = {
            "text": text,
            "type": intervention_type,
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        await self._mutate(
            session_id, lambda session: self._append(session, "ai_interventions", entry)
        )
        await event_bus.publish(session_id, "ai_action", entry)

    async def set_stage(
        self,
        session_id: str,
        stage: str,
        status: str,
        progress: int | None = None,
    ) -> None:
        async def mutator(session: PipelineSession) -> None:
            stages = dict(session.stages or {})
            stages[stage] = status
            session.stages = stages
            if status == "running":
                session.current_stage = stage
            elif session.current_stage == stage:
                session.current_stage = None
            if progress is not None:
                session.progress = progress

        await self._mutate(session_id, mutator)
        await event_bus.publish(session_id, "stage_update", {"stage": stage, "status": status})
        if progress is not None:
            await event_bus.publish(session_id, "progress", {"progress": progress})

    async def set_progress(self, session_id: str, progress: int) -> None:
        await self._mutate(session_id, lambda session: setattr(session, "progress", progress))
        await event_bus.publish(session_id, "progress", {"progress": progress})

    async def set_outputs(self, session_id: str, outputs: dict[str, Any]) -> None:
        await self._mutate(session_id, lambda session: setattr(session, "outputs", outputs))
        await event_bus.publish(session_id, "credentials", outputs)

    async def complete(self, session_id: str, outputs: dict[str, Any]) -> None:
        async def mutator(session: PipelineSession) -> None:
            stages = dict(session.stages or {})
            for stage in stages:
                stages[stage] = "done"
            session.stages = stages
            session.outputs = outputs
            session.status = "completed"
            session.progress = 100
            session.current_stage = None
            session.completed_at = datetime.now(timezone.utc)

        await self._mutate(session_id, mutator)
        await event_bus.publish(session_id, "credentials", outputs)
        await event_bus.publish(session_id, "progress", {"progress": 100})
        await event_bus.publish(session_id, "status", {"status": "completed", "progress": 100})

    async def fail(self, session_id: str, error: str) -> None:
        async def mutator(session: PipelineSession) -> None:
            session.status = "failed"
            session.error = error
            session.completed_at = datetime.now(timezone.utc)
            stages = dict(session.stages or {})
            if session.current_stage and stages.get(session.current_stage) == "running":
                stages[session.current_stage] = "failed"
            session.stages = stages

        await self._mutate(session_id, mutator)
        await event_bus.publish(session_id, "error", {"message": error})
        await event_bus.publish(session_id, "status", {"status": "failed", "error": error})

    async def _mutate(
        self, session_id: str, mutator: Callable[[PipelineSession], Any]
    ) -> None:
        async with self._locks[session_id]:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PipelineSession).where(PipelineSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if not session:
                    raise SessionNotFoundError(session_id)
                maybe_awaitable = mutator(session)
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
                await db.commit()

    @staticmethod
    def _append(session: PipelineSession, field: str, entry: dict[str, Any]) -> None:
        values = list(getattr(session, field) or [])
        values.append(entry)
        setattr(session, field, values[-2000:])

    @staticmethod
    def _to_dict(session: PipelineSession) -> dict[str, Any]:
        return {
            "id": session.id,
            "status": session.status,
            "created_at": session.created_at,
            "completed_at": session.completed_at,
            "progress": session.progress,
            "current_stage": session.current_stage,
            "inputs": redact(secret_box.decrypt_json(session.inputs or {})),
            "outputs": session.outputs or {},
            "ai_interventions": session.ai_interventions or [],
            "logs": session.logs or [],
            "stages": session.stages or {},
            "error": session.error,
        }


session_store = SessionStore()
