from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .database import init_db
from .event_bus import event_bus
from .llm_client import LLMClient
from .models import AgentLearning
from .multi_agent import RemediationAgent, ValidatorAgent
from .pipeline import pipeline_orchestrator
from .schemas import DeployRequest, DeployResponse
from .session_store import SessionNotFoundError, session_store
from .ssh_manager import SSHManager


app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_tasks: dict[str, asyncio.Task[None]] = {}


class DebugSSHRequest(BaseModel):
    server_ip: str
    pem_content: str
    username: str | None = None
    port: int | None = None
    timeout: int | None = None


def _model_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.on_event("startup")
async def on_startup() -> None:
    settings.local_workspace.mkdir(parents=True, exist_ok=True)
    await init_db()


@app.get("/", response_model=None)
async def root() -> Response:
    """Root endpoint - serves frontend index.html"""
    frontend_dir = settings.frontend_build_dir
    index_file = frontend_dir / "index.html"
    
    # If frontend is built, serve it
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    
    # Fallback when frontend not built
    return JSONResponse({
        "status": "ok",
        "message": "DevOps AI Platform API (frontend not built)",
        "api_endpoints": {
            "health": "/api/health",
            "agents_health": "/api/agents/health",
            "deploy": "POST /api/deploy",
            "status": "GET /api/status/{session_id}",
            "credentials": "GET /api/credentials/{session_id}",
            "websocket": "WS /ws/{session_id}"
        }
    })


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


@app.get("/api/debug/ollama")
async def debug_ollama() -> dict[str, Any]:
    client = LLMClient()
    return await client.test_ollama_generation()


@app.get("/api/debug/ollama-fix-test")
async def debug_ollama_fix_test() -> dict[str, Any]:
    """Test if Ollama actually returns fix commands"""
    client = LLMClient()

    test_error = "Timeout opening channel"
    test_context = {
        "command": "ssh connection",
        "exit_code": 1,
        "stdout": "",
        "stderr": test_error,
        "attempt": 1,
        "max_attempts": 3,
        "operation": "ssh_connect",
        "stage": "test",
        "context": {},
        "system": {"location": "local"},
    }

    result = {
        "ollama_available": await client.health(),
        "test_error": test_error,
        "candidates": {},
    }

    try:
        candidates = await client.query_fix_candidates(test_context)
        for provider, fix in candidates.items():
            result["candidates"][provider] = {
                "has_commands": len(fix.get("commands", [])) > 0,
                "command_count": len(fix.get("commands", [])),
                "commands": fix.get("commands", [])[:5],
                "analysis": fix.get("analysis", "")[:200],
                "confidence": fix.get("confidence", 0),
                "provider": fix.get("provider", "unknown"),
            }
    except Exception as exc:
        result["error"] = str(exc)

    return result


@app.post("/api/debug/ssh-test")
async def debug_ssh_connection(request: DebugSSHRequest) -> dict[str, Any]:
    target = request.server_ip
    if request.port and ":" not in target:
        target = f"{target}:{request.port}"
    session_id = f"debug-{uuid.uuid4()}"
    await session_store.create(
        session_id,
        {
            "server_ip": request.server_ip,
            "username": request.username or settings.ssh_user,
            "port": request.port or 22,
            "pem_content": "provided",
            "debug": True,
        },
    )
    llm = LLMClient()
    validator = ValidatorAgent(session_id=session_id, llm=llm)
    ai = RemediationAgent(session_id=session_id, llm=llm, validator=validator)
    await ai.ensure_llm_available()
    try:
        ssh = await ai.monitor_and_fix(
            SSHManager.connect,
            target,
            request.pem_content,
            request.username,
            request.timeout or settings.ssh_timeout,
            stage="init",
            fix_location="local",
            context={
                "server_ip": target,
                "ssh_user": request.username or settings.ssh_user,
                "error_type": "SSH_connection_failure",
            },
        )
        ssh.close()
        await session_store.complete(
            session_id,
            {"debug": {"ssh": "connected"}, "ai_fix_history": ai.fix_history},
        )
        return {
            "success": True,
            "session_id": session_id,
            "ai_fixes_applied": len(ai.fix_history),
            "ai_fix_history": ai.fix_history,
        }
    except Exception as exc:  # noqa: BLE001
        await session_store.fail(session_id, str(exc))
        return {
            "success": False,
            "session_id": session_id,
            "error": str(exc),
            "ai_fixes_applied": len(ai.fix_history),
            "ai_fix_history": ai.fix_history,
        }


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


# Mount static files (assets, CSS, JS) for frontend
frontend_build_dir = settings.frontend_build_dir
assets_dir = frontend_build_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


# Catchall for SPA - serves index.html for unmatched routes
@app.get("/{full_path:path}", response_model=None)
async def serve_spa(full_path: str) -> Response:
    """Serve SPA index.html for frontend routes, or 404 for unknown API routes"""
    # Don't intercept API routes
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    
    frontend_build_dir = settings.frontend_build_dir
    index_file = frontend_build_dir / "index.html"
    
    if index_file.exists():
        return FileResponse(index_file)
    
    return JSONResponse({"detail": "Not Found"}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
