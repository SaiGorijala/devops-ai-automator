from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from .credentials_manager import CredentialsManager
from .websocket_manager import WebSocketManager
from .agents import RepositoryAnalyzer, PipelineCommander, ExecutionSolver, ValidatorSelector


app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_tasks: dict[str, asyncio.Task[None]] = {}

# Initialize global managers for multi-agent orchestration
_llm_client = LLMClient()
_credentials_manager = CredentialsManager()
_ws_manager = WebSocketManager()
_session_agents: dict[str, dict[str, Any]] = {}  # Track agents per session


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


# ============================================================================
# MULTI-AGENT ORCHESTRATION ENDPOINTS
# ============================================================================

@app.post("/api/multi-agent/deploy")
async def multi_agent_deploy(request: DeployRequest) -> dict[str, Any]:
    """Start multi-agent deployment pipeline with full observability.
    
    1. Generate credentials automatically
    2. Initialize 4 agents
    3. Execute pipeline with LLM integration
    4. Stream all activity via WebSocket
    """
    session_id = str(uuid.uuid4())
    
    try:
        # Generate all credentials first (never ask user)
        credentials = _credentials_manager.generate_all_credentials(request.server_ip)
        
        # Broadcast credentials generation
        await _ws_manager.broadcast_credentials_generated(
            request.server_ip,
            list(credentials.keys())
        )
        
        # Initialize agents for this session
        agent1 = RepositoryAnalyzer(_llm_client)
        agent2 = PipelineCommander(_llm_client)
        agent3 = ExecutionSolver(None, _llm_client, _credentials_manager)  # SSH manager set later
        agent4 = ValidatorSelector(_llm_client)
        
        _session_agents[session_id] = {
            "agent1": agent1,
            "agent2": agent2,
            "agent3": agent3,
            "agent4": agent4,
            "credentials": credentials,
        }
        
        # Start async pipeline execution
        asyncio.create_task(
            _run_multi_agent_pipeline(
                session_id, request, credentials, agent1, agent2, agent3, agent4
            )
        )
        
        return {
            "session_id": session_id,
            "status": "started",
            "credentials_generated": len(credentials),
            "agents_initialized": 4,
        }
    except Exception as e:
        await _ws_manager.broadcast_error("deployment_init", str(e))
        return {"error": str(e), "session_id": session_id}


@app.get("/api/multi-agent/credentials/{session_id}")
async def get_agent_credentials(session_id: str) -> dict[str, Any]:
    """Get auto-generated credentials for the session."""
    if session_id not in _session_agents:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return _session_agents[session_id]["credentials"]


@app.post("/api/multi-agent/credentials/regenerate/{session_id}/{service}")
async def regenerate_service_credentials(
    session_id: str, service: str
) -> dict[str, Any]:
    """Regenerate credentials for a specific service."""
    if session_id not in _session_agents:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        session_data = _session_agents[session_id]
        server_ip = list(session_data["credentials"].values())[0].get("url", "").split("//")[1].split(":")[0]
        
        new_creds = _credentials_manager.regenerate_service(service, server_ip)
        session_data["credentials"][service] = new_creds
        
        return {"success": True, "service": service, "credentials": new_creds}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/multi-agent/llm-conversations/{session_id}")
async def get_llm_conversations(session_id: str) -> dict[str, Any]:
    """Get all LLM conversations for observability."""
    if session_id not in _session_agents:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agent3 = _session_agents[session_id]["agent3"]
    return {
        "total_interactions": len(agent3.llm_conversations),
        "conversations": agent3.get_llm_conversations(),
    }


@app.get("/api/multi-agent/agent-history/{session_id}")
async def get_agent_history(session_id: str) -> dict[str, Any]:
    """Get execution history for all agents."""
    if session_id not in _session_agents:
        raise HTTPException(status_code=404, detail="Session not found")
    
    agents = _session_agents[session_id]
    
    return {
        "execution_log": agents["agent3"].get_execution_log(),
        "fix_history": agents["agent3"].get_fix_history(),
        "validation_history": agents["agent4"].get_validation_history(),
        "learned_patterns": agents["agent4"].get_agent_score_report(),
    }


@app.websocket("/ws/agent-activity/{session_id}")
async def websocket_agent_activity(websocket: WebSocket, session_id: str) -> None:
    """WebSocket for real-time agent activity streaming."""
    await _ws_manager.connect(websocket)
    
    # Send message history
    for msg in _ws_manager.get_message_history(50):
        try:
            await websocket.send_json(msg)
        except Exception:
            pass
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Could handle client commands here if needed
    except WebSocketDisconnect:
        _ws_manager.disconnect(websocket)


# ============================================================================
# HELPER FUNCTIONS FOR MULTI-AGENT PIPELINE
# ============================================================================

async def _run_multi_agent_pipeline(
    session_id: str,
    request: DeployRequest,
    credentials: dict[str, Any],
    agent1: RepositoryAnalyzer,
    agent2: PipelineCommander,
    agent3: ExecutionSolver,
    agent4: ValidatorSelector,
) -> None:
    """Execute the complete multi-agent pipeline."""
    try:
        await _ws_manager.broadcast_status("started", {"session_id": session_id})
        
        # AGENT 1: Analyze repository
        await _ws_manager.broadcast_agent_message(
            "RepositoryAnalyzer", "started", {"repo": request.repo_url}
        )
        
        repo_analysis = await agent1.analyze(request.repo_url, request.github_token)
        
        await _ws_manager.broadcast_agent_message(
            "RepositoryAnalyzer", "completed", repo_analysis
        )
        
        # AGENT 2: Create plan
        await _ws_manager.broadcast_agent_message(
            "PipelineCommander", "started", {"analysis": repo_analysis.get("project_type")}
        )
        
        plan = await agent2.create_plan(repo_analysis, request.server_ip, request.repo_url)
        
        await _ws_manager.broadcast_agent_message(
            "PipelineCommander", "completed", {"stages": len(plan.get("stages", []))}
        )
        
        # AGENT 3: Execute with error recovery
        ssh_manager = SSHManager()
        agent3.ssh = ssh_manager
        
        await _ws_manager.broadcast_agent_message(
            "ExecutionSolver", "ssh_connecting", {"server": request.server_ip}
        )
        
        try:
            ssh_manager.connect(request.server_ip, request.pem_content)
        except Exception as e:
            await _ws_manager.broadcast_error(
                "ssh_connection", f"Failed to connect: {str(e)}"
            )
            await _ws_manager.broadcast_status("failed", {"error": str(e)})
            return
        
        for stage in plan.get("stages", []):
            await _ws_manager.broadcast_agent_message(
                "ExecutionSolver", f"stage_executing", {"stage_id": stage.get("id"), "stage_name": stage.get("name")}
            )
            
            success, result = await agent3.execute_with_ai_fix(
                stage, {"repo_analysis": repo_analysis}
            )
            
            if success:
                await _ws_manager.broadcast_agent_message(
                    "ExecutionSolver",
                    f"stage_success_{stage.get('id')}",
                    result,
                )
            else:
                await _ws_manager.broadcast_agent_message(
                    "ExecutionSolver",
                    f"stage_failed_{stage.get('id')}",
                    result,
                )
                # Continue with other stages or stop
                if stage.get("critical"):
                    break
        
        # AGENT 4: Validate
        await _ws_manager.broadcast_agent_message(
            "ValidatorSelector", "validating", {}
        )
        
        validation = await agent4.validate_deployment(ssh_manager, request.server_ip)
        
        await _ws_manager.broadcast_agent_message(
            "ValidatorSelector", "validation_complete", validation
        )
        
        # Report learning
        score_report = agent4.get_agent_score_report()
        await _ws_manager.broadcast_agent_message(
            "ValidatorSelector", "learning_report", score_report
        )
        
        await _ws_manager.broadcast_status(
            "completed",
            {
                "success": validation.get("success"),
                "validation_score": validation.get("score"),
            },
        )
        
    except Exception as e:
        print(f"[Pipeline Error] {str(e)}")
        await _ws_manager.broadcast_error("pipeline_execution", str(e))
        await _ws_manager.broadcast_status("failed", {"error": str(e)})


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
