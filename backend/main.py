from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .database import init_db
from .event_bus import event_bus
from .llm_client import LLMClient
from .models import AgentLearning
from .pipeline import pipeline_orchestrator
from .schemas import DeployRequest, DeployResponse
from .session_store import SessionNotFoundError, session_store


app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_tasks: dict[str, asyncio.Task[None]] = {}


def _model_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.on_event("startup")
async def on_startup() -> None:
    settings.local_workspace.mkdir(parents=True, exist_ok=True)
    await init_db()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "ollama_host": settings.ollama_host,
        "model": settings.deepseek_model,
    }


@app.get("/api/agents/health")
async def agent_health() -> dict[str, Any]:
    return {
        "multi_agent": settings.use_multi_agent,
        "validation_enabled": settings.agent_validation_enabled,
        "llm": await LLMClient().health(),
    }


@app.get("/api/agents/learnings")
async def agent_learnings(limit: int = 50) -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AgentLearning)
            .order_by(AgentLearning.updated_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        return [
            {
                "provider": row.provider,
                "error_signature": row.error_signature,
                "successes": row.successes,
                "failures": row.failures,
                "last_error": row.last_error,
                "last_fix": row.last_fix,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in result.scalars()
        ]


@app.post("/api/deploy", response_model=DeployResponse)
async def deploy(request: DeployRequest) -> DeployResponse:
    try:
        inputs = request.to_inputs()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session_id = str(uuid.uuid4())
    await session_store.create(session_id, _model_dict(inputs))
    task = asyncio.create_task(pipeline_orchestrator.execute_pipeline(session_id, inputs))
    _tasks[session_id] = task
    task.add_done_callback(lambda _task: _tasks.pop(session_id, None))
    return DeployResponse(session_id=session_id)


@app.get("/api/status/{session_id}")
async def status(session_id: str) -> JSONResponse:
    try:
        payload = await session_store.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session_id") from exc
    payload["session_id"] = payload["id"]
    return JSONResponse(content=_jsonable(payload))


@app.get("/api/credentials/{session_id}")
async def credentials(session_id: str) -> dict[str, Any]:
    try:
        payload = await session_store.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Unknown session_id") from exc
    if payload["status"] not in {"completed", "failed"} and not payload.get("outputs"):
        return {"ready": False, "status": payload["status"]}
    return {"ready": bool(payload.get("outputs")), "status": payload["status"], **payload.get("outputs", {})}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    try:
        snapshot = await session_store.get(session_id)
    except SessionNotFoundError:
        await websocket.send_json({"type": "error", "data": {"message": "Unknown session_id"}})
        await websocket.close(code=1008)
        return

    await websocket.send_json(
        {
            "type": "status",
            "data": _jsonable(snapshot),
            "timestamp": snapshot["created_at"].isoformat(),
        }
    )
    try:
        async for event in event_bus.subscribe(session_id):
            await websocket.send_json(event.to_dict())
    except WebSocketDisconnect:
        return


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


if settings.frontend_build_dir.exists():
    app.mount("/", StaticFiles(directory=settings.frontend_build_dir, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
