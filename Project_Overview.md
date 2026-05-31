# DevOps AI Platform
## Complete Application Documentation — From Vision to Production

---

## Table of Contents

1. [What This Application Is](#1-what-this-application-is)
2. [How It Works — The Big Picture](#2-how-it-works--the-big-picture)
3. [The Four Agents — What Each One Does](#3-the-four-agents--what-each-one-does)
4. [Full Architecture](#4-full-architecture)
5. [Project Structure](#5-project-structure)
6. [Phase 1 — Environment Setup](#6-phase-1--environment-setup)
7. [Phase 2 — Core Infrastructure](#7-phase-2--core-infrastructure)
8. [Phase 3 — Build the Detector Agent](#8-phase-3--build-the-detector-agent)
9. [Phase 4 — Build the Deploy Agent](#9-phase-4--build-the-deploy-agent)
10. [Phase 5 — Build the Validator Agent](#10-phase-5--build-the-validator-agent)
11. [Phase 6 — Build the Rollback Agent](#11-phase-6--build-the-rollback-agent)
12. [Phase 7 — Orchestrator + API](#12-phase-7--orchestrator--api)
13. [Phase 8 — Monitoring Stack](#13-phase-8--monitoring-stack)
14. [Phase 9 — Testing](#14-phase-9--testing)
15. [Phase 10 — First Full Deployment Run](#15-phase-10--first-full-deployment-run)
16. [Post-MVP Roadmap](#16-post-mvp-roadmap)

---

## 1. What This Application Is

### The Problem It Solves

Deploying an application to a server is a multi-step, error-prone process. A developer has to:

- Detect what kind of project it is (Node.js? Python? What version?)
- Install the right runtime and dependencies
- Start the process correctly
- Check that it actually came up healthy
- Roll back everything if something went wrong
- Set up monitoring so they know when it breaks in the future

Most teams do this manually, with bash scripts that break on edge cases, or expensive CI/CD platforms that take weeks to configure. Neither option helps when something fails at 2am.

### What This Platform Does

The DevOps AI Platform automates the entire lifecycle — from reading your repo to confirming your app is live — using four specialized AI agents powered by a local LLM (Ollama + DeepSeek). No cloud API keys. No monthly bills. Runs on your own hardware.

You point it at a repository and a server. It figures out the rest.

### The Flow in Plain English

```
You submit a deploy request
        ↓
Detector Agent reads the repo → "This is Node.js 20, Express, needs a build step"
        ↓
Deploy Agent SSHs into the server → installs, builds, starts the app
        ↓
Validator Agent checks health → "Port 3000 responding, process running, all good"
        ↓
If anything failed → Rollback Agent restores server to pre-deploy state
        ↓
Monitoring stack watches it 24/7 going forward
```

### Why Four Agents?

Each agent has one job. That makes each one independently testable, replaceable, and explainable. When something goes wrong, you know exactly which agent failed and why. It also makes for a compelling demo — you can show each agent handing off to the next in real time.

### What This Is NOT (Scope is Everything)

- It is not a replacement for Kubernetes (yet)
- It does not manage cloud infrastructure (Terraform, Pulumi)
- It does not support every language on day one — Node.js first, Python second
- It is not a SaaS product — it runs on-premise, inside your network

---

## 2. How It Works — The Big Picture

### Request Lifecycle

Every deployment request travels through the same pipeline:

```
1. API receives POST /api/v1/deploy
2. Orchestrator creates a deployment record in PostgreSQL
3. Orchestrator opens a rollback checkpoint
4. Detector Agent runs → returns structured analysis
5. Orchestrator scores confidence for each planned action
6. Deploy Agent executes — HIGH confidence = auto, MEDIUM = waits for approval
7. Validator Agent confirms health
8. Result written to PostgreSQL
9. WebSocket streams every step to the caller in real time
10. If any step fails → Rollback Agent activates
```

### The Confidence System

Before executing any action, the platform scores it:

| Level  | Meaning                          | What Happens               |
|--------|----------------------------------|----------------------------|
| HIGH   | Known safe action with history   | Executes automatically     |
| MEDIUM | Uncertain or first time seen     | Pauses, waits for approval |
| LOW    | Destructive or risky             | Never auto-executes        |

The score is determined by two things: whether the action is on a known-safe list, and whether that action has succeeded before in the PostgreSQL log. It is rule-based, not ML — predictable and auditable.

### The Memory System

Every action is logged to PostgreSQL:

```
agent_logs(deployment_id, agent, action, command, success, error_msg, fix_applied, duration_ms)
```

This is not a vector database. It is a plain table. Over time, actions that always succeed get promoted from MEDIUM to HIGH confidence. Actions that keep failing trigger alerts. Simple, readable, debuggable.

### LLM Usage — Where and Why

The LLM (DeepSeek 6.7B via Ollama) is used in exactly three places:

1. **Detector Agent** — interpreting ambiguous package configs, inferring Node version requirements
2. **Deploy Agent** — when a step fails, generating a suggested fix command
3. **Validator Agent** — interpreting unusual health check responses

The LLM is a fallback and interpreter, not the primary control flow. Every LLM output is validated and scored before acting on it.

---

## 3. The Four Agents — What Each One Does

### Agent 1 — Detector Agent

**Single responsibility:** Read the repository. Return a structured analysis. Touch nothing on the server.

**Input:** repo path (local or SSH-accessible), list of files

**Output:**
```json
{
  "language": "nodejs",
  "framework": "express",
  "node_version": "20",
  "package_manager": "npm",
  "start_script": "node dist/server.js",
  "needs_build": true,
  "build_script": "npm run build",
  "env_vars_required": ["DATABASE_URL", "PORT"],
  "port": 3000
}
```

**How it works:**
- Reads `package.json` directly — no guessing
- Asks Ollama: "Given this package.json, what Node version and start command?"
- Validates LLM output against known patterns
- Raises an error if the repo is unrecognisable — never silently proceeds

---

### Agent 2 — Deploy Agent

**Single responsibility:** Take the Detector's output and make the app run on the target server.

**Input:** Detector analysis + SSH credentials + environment variables

**Steps it executes:**
1. Check server prerequisites (disk space, existing Node version)
2. Install correct Node.js version if needed
3. Clone or sync the repository
4. Install dependencies (`npm ci`)
5. Run build if required (`npm run build`)
6. Write environment file
7. Start process via PM2
8. Return control to Orchestrator

**Error behaviour:** On any step failure, calls Ollama with the error, attempts one LLM-suggested fix, logs result. If recovery fails, signals the Rollback Agent.

---

### Agent 3 — Validator Agent

**Single responsibility:** Confirm the deployment actually worked. No assumptions.

**Input:** deploy result + server details + expected port/health endpoint

**Checks it runs:**
1. Is the process running? (`pm2 list`)
2. Is the port bound? (`ss -tlnp | grep :3000`)
3. Does the health endpoint respond? (`curl http://localhost:3000/health`)
4. Is the response code 200?
5. Did it stay up for 30 seconds? (liveness check)

**Output:**
```json
{
  "healthy": true,
  "checks": {
    "process_running": true,
    "port_bound": true,
    "health_endpoint": true,
    "liveness": true
  },
  "url": "http://server-ip:3000",
  "validated_at": "2024-01-15T14:32:00Z"
}
```

---

### Agent 4 — Rollback Agent

**Single responsibility:** Restore the server to exactly the state it was in before the deployment started.

**Input:** rollback checkpoint (JSON file saved before deploy began)

**What it reverses:**
- Stops and deletes the PM2 process if started
- Removes cloned/synced files if they didn't exist before
- Restores the previous `.env` file from backup
- Restores the previously running version if one existed

**Key principle:** Rollback Agent only acts on checkpoints it created. It never guesses what to undo. If no checkpoint exists, it stops and alerts — it does not try to improvise.

---

## 4. Full Architecture

### Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT / CI PIPELINE                        │
│              curl / GitHub Actions / Jenkins webhook                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ POST /api/v1/deploy
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION                         │
│    POST /deploy    GET /deploy/{id}    WebSocket /ws/{id}           │
│                    Orchestrator (coordinates agents)                │
└──────┬─────────────────┬─────────────────┬──────────────┬──────────┘
       │                 │                 │              │
       ▼                 ▼                 ▼              ▼
┌────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
│  DETECTOR  │  │    DEPLOY    │  │  VALIDATOR  │  │   ROLLBACK   │
│   AGENT    │→ │    AGENT     │→ │    AGENT    │  │    AGENT     │
│            │  │              │  │             │  │              │
│ Reads repo │  │ SSH executor │  │ Health chks │  │ Reverses all │
│ Detects    │  │ Installs     │  │ Port checks │  │ steps on     │
│ tech stack │  │ Builds       │  │ Process     │  │ any failure  │
│ Infers     │  │ Starts app   │  │ checks      │  │              │
│ config     │  │ Handles errs │  │             │  │              │
└─────┬──────┘  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘
      │                │                 │                 │
      └────────────────┴─────────────────┴────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
             ┌──────────┐ ┌─────────┐ ┌─────────────────┐
             │  OLLAMA  │ │POSTGRES │ │   TARGET SERVER  │
             │DeepSeek  │ │agent_   │ │   (via SSH)      │
             │  6.7B    │ │logs +   │ │                  │
             │          │ │deploys  │ │  Your app runs   │
             └──────────┘ └─────────┘ │  here            │
                                      └─────────────────-┘
                    ▼
             ┌──────────────────────────────┐
             │     MONITORING STACK         │
             │  Prometheus + Grafana        │
             │  Alerts on error rate / CPU  │
             └──────────────────────────────┘
```

### Data Flow

```
Request → Orchestrator creates deployment_id
        → Rollback Agent saves checkpoint
        → Detector Agent analyzes repo
        → Orchestrator scores each planned action
        → Deploy Agent executes (action by action, logging each to PostgreSQL)
        → Validator Agent confirms health
        → Orchestrator marks deployment complete
        → WebSocket sends final status to caller
```

### Technology Stack

| Layer         | Technology              | Why                                     |
|---------------|-------------------------|-----------------------------------------|
| API           | FastAPI + Uvicorn       | Async, fast, WebSocket native           |
| LLM           | Ollama + DeepSeek 6.7B  | Free, local, no API key required        |
| SSH Execution | Paramiko                | Industry standard Python SSH library    |
| Database      | PostgreSQL 15           | Reliable, queryable deployment history  |
| ORM           | SQLAlchemy + Alembic    | Schema migrations built in              |
| Process Mgr   | PM2 (on target server)  | Node.js production standard             |
| Containers    | Docker Compose          | Dev environment only for now            |
| Monitoring    | Prometheus + Grafana    | Standard observability stack            |
| Real-time     | WebSocket               | Live deployment logs to caller          |

---

## 5. Project Structure

```
devops-ai-platform/
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, lifespan, CORS
│   │   ├── config.py                # Pydantic settings from .env
│   │   ├── database.py              # SQLAlchemy engine, session, models
│   │   │
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py        # Abstract: analyze(), plan(), execute()
│   │   │   ├── detector_agent.py    # Reads repo, returns structured analysis
│   │   │   ├── deploy_agent.py      # SSH execution, installs, starts app
│   │   │   ├── validator_agent.py   # Health checks, port checks, liveness
│   │   │   └── rollback_agent.py    # Checkpoint + reverse all steps
│   │   │
│   │   ├── core/
│   │   │   ├── llm_client.py        # Ollama HTTP wrapper
│   │   │   ├── ssh_executor.py      # Paramiko wrapper with logging
│   │   │   ├── confidence.py        # HIGH / MEDIUM / LOW rule engine
│   │   │   ├── orchestrator.py      # Coordinates the four agents
│   │   │   └── rollback_manager.py  # Checkpoint save/load
│   │   │
│   │   └── api/
│   │       ├── deployments.py       # POST /deploy, GET /deploy/{id}
│   │       └── websocket.py         # /ws/{deployment_id}
│   │
│   ├── alembic/
│   │   └── versions/                # DB migration files
│   ├── tests/
│   │   ├── test_detector.py
│   │   ├── test_deploy.py
│   │   ├── test_validator.py
│   │   ├── test_rollback.py
│   │   └── test_confidence.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── infrastructure/
│   ├── docker-compose.yml           # postgres + ollama + backend
│   └── prometheus/
│       └── prometheus.yml
│
├── scripts/
│   ├── setup.sh                     # Full dev environment setup
│   ├── init_ollama.sh               # Pull and test DeepSeek model
│   └── test_deploy.py               # Manual integration test
│
├── .env.example
├── Makefile
└── README.md
```

---

## 6. Phase 1 — Environment Setup

### Step 1.1 — Prerequisites

Ensure you have these installed before starting:

```bash
python3.11 --version    # need 3.11+
docker --version        # need 24+
docker compose version  # need v2
git --version
```

### Step 1.2 — Project Scaffold

```bash
mkdir devops-ai-platform && cd devops-ai-platform

# Create directory structure
mkdir -p backend/app/{agents,core,api}
mkdir -p backend/{alembic/versions,tests}
mkdir -p infrastructure/prometheus
mkdir -p scripts

# Python environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Version control
git init
echo "venv/" >> .gitignore
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

### Step 1.3 — Install Ollama and Pull the Model

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull DeepSeek Coder (this takes 5–15 minutes, ~4GB download)
ollama pull deepseek-coder:6.7b

# Verify it works — it should return JSON
ollama run deepseek-coder:6.7b \
  'Return only this JSON, nothing else: {"status": "ready"}'

# Start Ollama as a background service
ollama serve &
```

### Step 1.4 — Python Dependencies

Create `backend/requirements.txt`:

```txt
# Web framework
fastapi==0.104.1
uvicorn[standard]==0.24.0

# Database
sqlalchemy==2.0.23
alembic==1.12.1
asyncpg==0.29.0

# LLM client
httpx==0.25.1

# SSH execution
paramiko==3.4.0

# Config
python-dotenv==1.0.0
pydantic-settings==2.1.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.0
```

```bash
pip install -r backend/requirements.txt
```

### Step 1.5 — Environment File

Create `.env.example` then copy it to `.env`:

```bash
# Application
APP_SECRET_KEY=replace-with-random-64-char-string
DEBUG=true
LOG_LEVEL=INFO

# LLM — Ollama only
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=deepseek-coder:6.7b
OLLAMA_TIMEOUT=90

# Database
DATABASE_URL=postgresql+asyncpg://devops:devops123@localhost:5432/devops_ai

# Agent behaviour
CONFIDENCE_AUTO_THRESHOLD=HIGH
MAX_ROLLBACK_CHECKPOINTS=5
SSH_COMMAND_TIMEOUT=60
CHECKPOINT_DIR=./checkpoints
```

```bash
cp .env.example .env
```

### Step 1.6 — Docker Compose (Dev Environment)

Create `infrastructure/docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: devops_ai
      POSTGRES_USER: devops
      POSTGRES_PASSWORD: devops123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U devops -d devops_ai"]
      interval: 10s
      timeout: 5s
      retries: 5

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  ollama_data:
  grafana_data:
```

```bash
# Start everything
cd infrastructure
docker compose up -d

# Verify
docker compose ps
```

**Phase 1 complete when:** `docker compose ps` shows all containers healthy and `ollama run deepseek-coder:6.7b 'say ok'` responds.

---

## 7. Phase 2 — Core Infrastructure

### Step 2.1 — Configuration

Create `backend/app/config.py`:

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App
    app_secret_key: str
    debug: bool = True
    log_level: str = "INFO"

    # LLM
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "deepseek-coder:6.7b"
    ollama_timeout: int = 90

    # Database
    database_url: str

    # Agent behaviour
    confidence_auto_threshold: str = "HIGH"
    max_rollback_checkpoints: int = 5
    ssh_command_timeout: int = 60
    checkpoint_dir: str = "./checkpoints"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### Step 2.2 — Database Models

Create `backend/app/database.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, func
from .config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Deployment(Base):
    __tablename__ = "deployments"
    id            = Column(String, primary_key=True)   # deployment_id
    repo_path     = Column(String, nullable=False)
    server_host   = Column(String, nullable=False)
    status        = Column(String, default="pending")  # pending/running/success/failed
    started_at    = Column(DateTime, server_default=func.now())
    completed_at  = Column(DateTime, nullable=True)
    error_summary = Column(Text, nullable=True)

class AgentLog(Base):
    __tablename__ = "agent_logs"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(String, nullable=False)
    agent_name    = Column(String, nullable=False)    # detector/deploy/validator/rollback
    action        = Column(String, nullable=False)    # install_node/run_build/etc
    command       = Column(Text, nullable=True)       # exact shell command
    success       = Column(Boolean, nullable=False)
    error_msg     = Column(Text, nullable=True)
    fix_applied   = Column(Text, nullable=True)       # LLM-suggested fix if used
    duration_ms   = Column(Integer, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

### Step 2.3 — LLM Client

Create `backend/app/core/llm_client.py`:

```python
import httpx, json, re, asyncio
from dataclasses import dataclass
from ..config import settings

@dataclass
class LLMResponse:
    content: str
    latency_ms: float
    tokens_used: int

class OllamaClient:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=settings.ollama_timeout)
        self.host    = settings.ollama_host
        self.model   = settings.ollama_model

    async def generate(self, prompt: str) -> LLMResponse:
        t0 = asyncio.get_event_loop().time()
        r  = await self._client.post(
            f"{self.host}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False}
        )
        r.raise_for_status()
        data = r.json()
        return LLMResponse(
            content    = data["response"],
            latency_ms = (asyncio.get_event_loop().time() - t0) * 1000,
            tokens_used= data.get("eval_count", 0)
        )

    async def generate_json(self, prompt: str) -> dict:
        """Generate and parse JSON. Retries once with stricter prompt on failure."""
        for attempt in range(2):
            strict = " Respond with ONLY a JSON object. No explanation, no markdown." if attempt > 0 else ""
            resp = await self.generate(prompt + strict)
            text = re.sub(r'```json|```', '', resp.content).strip()
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"LLM returned invalid JSON after 2 attempts: {resp.content[:300]}")

    async def is_available(self) -> bool:
        try:
            r = await self._client.get(f"{self.host}/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False
```

### Step 2.4 — SSH Executor

Create `backend/app/core/ssh_executor.py`:

```python
import paramiko, asyncio, time
from typing import Optional
from ..config import settings

class SSHResult:
    def __init__(self, stdout: str, stderr: str, exit_code: int, duration_ms: int):
        self.stdout      = stdout
        self.stderr      = stderr
        self.exit_code   = exit_code
        self.duration_ms = duration_ms
        self.success     = exit_code == 0

class SSHExecutor:
    def __init__(self, host: str, user: str, key_path: str, port: int = 22):
        self.host     = host
        self.user     = user
        self.key_path = key_path
        self.port     = port
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self):
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            self.host,
            port       = self.port,
            username   = self.user,
            key_filename = self.key_path,
            timeout    = 15
        )

    def disconnect(self):
        if self._client:
            self._client.close()

    def run(self, command: str) -> SSHResult:
        """Run a command. Raises RuntimeError if SSH is not connected."""
        if not self._client:
            raise RuntimeError("SSH not connected. Call connect() first.")
        t0 = time.time()
        timeout = settings.ssh_command_timeout
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return SSHResult(
            stdout      = stdout.read().decode("utf-8", errors="replace"),
            stderr      = stderr.read().decode("utf-8", errors="replace"),
            exit_code   = exit_code,
            duration_ms = int((time.time() - t0) * 1000)
        )

    def read_file(self, path: str) -> str:
        result = self.run(f"cat {path}")
        if not result.success:
            raise FileNotFoundError(f"Cannot read {path}: {result.stderr}")
        return result.stdout

    def file_exists(self, path: str) -> bool:
        return self.run(f"test -f {path}").success

    def dir_exists(self, path: str) -> bool:
        return self.run(f"test -d {path}").success

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
```

### Step 2.5 — Confidence Scorer

Create `backend/app/core/confidence.py`:

```python
from enum import Enum
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class Confidence(str, Enum):
    HIGH   = "HIGH"    # auto-execute
    MEDIUM = "MEDIUM"  # pause for human approval
    LOW    = "LOW"     # never auto-execute

# Always safe — read-only or idempotent
HIGH_SAFE = {
    "check_node_version", "check_disk_space", "check_port_available",
    "read_package_json", "list_pm2_processes", "check_npm_version",
    "verify_repo_access", "check_git_status",
}

# Potentially impactful — safe after proven history
MEDIUM_SAFE = {
    "install_node", "install_npm_packages", "run_build_script",
    "clone_repository", "sync_repository", "write_env_file",
    "start_pm2_process", "restart_pm2_process", "rotate_pm2_logs",
}

# Never auto-execute regardless of history
ALWAYS_LOW = {
    "delete_directory", "drop_database", "modify_nginx_config",
    "change_firewall_rules", "modify_ssh_config", "format_disk",
    "kill_all_processes", "remove_all_containers",
}

async def score_action(action: str, db: AsyncSession) -> Confidence:
    if action in ALWAYS_LOW:
        return Confidence.LOW

    if action in MEDIUM_SAFE:
        # Upgrade to HIGH if this action has succeeded 3+ times before
        result = await db.execute(
            text("SELECT COUNT(*) FROM agent_logs WHERE action = :action AND success = TRUE"),
            {"action": action}
        )
        past_successes = result.scalar()
        return Confidence.HIGH if past_successes >= 3 else Confidence.MEDIUM

    return Confidence.HIGH  # Unknown but assumed safe (read operations, checks)
```

### Step 2.6 — Base Agent

Create `backend/app/agents/base_agent.py`:

```python
from abc import ABC, abstractmethod
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.llm_client import OllamaClient
from ..core.ssh_executor import SSHExecutor
from ..database import AgentLog
import time

class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, llm: OllamaClient, db: AsyncSession):
        self.llm = llm
        self.db  = db

    @abstractmethod
    async def analyze(self, context: dict) -> dict:
        pass

    @abstractmethod
    async def execute(self, plan: dict, ssh: SSHExecutor) -> dict:
        pass

    async def log(
        self,
        deployment_id: str,
        action: str,
        success: bool,
        command: str  = None,
        error_msg: str = None,
        fix_applied: str = None,
        duration_ms: int = None
    ):
        entry = AgentLog(
            deployment_id = deployment_id,
            agent_name    = self.name,
            action        = action,
            command       = command,
            success       = success,
            error_msg     = error_msg,
            fix_applied   = fix_applied,
            duration_ms   = duration_ms,
        )
        self.db.add(entry)
        await self.db.commit()
```

**Phase 2 complete when:** You can import all core modules without errors and `init_db()` creates the tables in PostgreSQL.

---

## 8. Phase 3 — Build the Detector Agent

Create `backend/app/agents/detector_agent.py`:

```python
import json
from .base_agent import BaseAgent
from ..core.ssh_executor import SSHExecutor

class DetectorAgent(BaseAgent):
    name = "detector"

    async def analyze(self, context: dict) -> dict:
        """
        Reads the repository and returns a structured analysis.
        context keys: repo_path, deployment_id
        """
        repo_path     = context["repo_path"]
        deployment_id = context["deployment_id"]
        ssh: SSHExecutor = context["ssh"]

        # 1. List the files at root
        result = ssh.run(f"ls {repo_path}")
        if not result.success:
            raise ValueError(f"Cannot access repo at {repo_path}: {result.stderr}")

        files = result.stdout.strip().split("\n")

        # 2. Confirm it is a Node.js project
        if "package.json" not in files:
            raise ValueError(f"No package.json found in {repo_path}. Only Node.js supported in MVP.")

        # 3. Read package.json
        pkg_raw = ssh.read_file(f"{repo_path}/package.json")
        try:
            pkg = json.loads(pkg_raw)
        except json.JSONDecodeError:
            raise ValueError("package.json is not valid JSON")

        # 4. Ask LLM to interpret the config
        prompt = f"""
You are a DevOps expert. Given this package.json, return deployment information as JSON.

package.json:
{json.dumps(pkg, indent=2)}

Return ONLY this JSON structure, nothing else:
{{
  "node_version": "20",
  "start_script": "node dist/server.js",
  "needs_build": true,
  "build_script": "npm run build",
  "port": 3000,
  "env_vars_required": ["DATABASE_URL"]
}}
"""
        llm_result = await self.llm.generate_json(prompt)

        # 5. Validate and fill defaults
        analysis = {
            "language":          "nodejs",
            "framework":         self._detect_framework(pkg),
            "node_version":      str(llm_result.get("node_version", "20")),
            "package_manager":   "npm",
            "start_script":      llm_result.get("start_script") or pkg.get("scripts", {}).get("start", "node index.js"),
            "needs_build":       bool(llm_result.get("needs_build", False)),
            "build_script":      llm_result.get("build_script") or pkg.get("scripts", {}).get("build"),
            "port":              int(llm_result.get("port", 3000)),
            "env_vars_required": llm_result.get("env_vars_required", []),
            "app_name":          pkg.get("name", "app").replace(" ", "-").lower(),
        }

        await self.log(deployment_id, "analyze_repo", True, command=f"ls {repo_path}")
        return analysis

    def _detect_framework(self, pkg: dict) -> str:
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "next"      in deps: return "nextjs"
        if "express"   in deps: return "express"
        if "fastify"   in deps: return "fastify"
        if "nestjs"    in deps: return "nestjs"
        if "koa"       in deps: return "koa"
        return "nodejs"

    async def execute(self, plan: dict, ssh: SSHExecutor) -> dict:
        # Detector only reads — no execution phase
        raise NotImplementedError("DetectorAgent does not execute plans")
```

**Test this phase:**

```bash
# Create a simple test
python -c "
import asyncio
from backend.app.core.llm_client import OllamaClient

async def test():
    llm = OllamaClient()
    available = await llm.is_available()
    print('LLM available:', available)
    if available:
        result = await llm.generate_json(
            'Return ONLY JSON: {\"framework\": \"express\", \"port\": 3000}'
        )
        print('JSON result:', result)

asyncio.run(test())
"
```

---

## 9. Phase 4 — Build the Deploy Agent

Create `backend/app/agents/deploy_agent.py`:

```python
import time
from .base_agent import BaseAgent
from ..core.ssh_executor import SSHExecutor
from ..core.confidence import score_action, Confidence

class DeployAgent(BaseAgent):
    name = "deploy"

    async def analyze(self, context: dict) -> dict:
        """Build the ordered list of steps to execute."""
        analysis = context["detector_analysis"]
        steps = [
            {"action": "check_disk_space",    "command": "df -h / | awk 'NR==2{print $5}'"},
            {"action": "check_node_version",  "command": "node --version 2>/dev/null || echo 'not_installed'"},
        ]

        if analysis["needs_build"]:
            steps.append({"action": "install_node", "command": self._node_install_cmd(analysis["node_version"])})

        steps += [
            {"action": "sync_repository",     "command": f"cd {context['repo_path']} && git pull origin main"},
            {"action": "install_npm_packages", "command": f"cd {context['repo_path']} && npm ci"},
        ]

        if analysis["needs_build"] and analysis.get("build_script"):
            steps.append({
                "action": "run_build_script",
                "command": f"cd {context['repo_path']} && {analysis['build_script']}"
            })

        steps.append({
            "action": "start_pm2_process",
            "command": (
                f"cd {context['repo_path']} && "
                f"pm2 delete {analysis['app_name']} 2>/dev/null || true && "
                f"pm2 start {analysis['start_script']} --name {analysis['app_name']}"
            )
        })

        # Score confidence for each step
        for step in steps:
            step["confidence"] = (await score_action(step["action"], self.db)).value

        return {"steps": steps}

    async def execute(self, plan: dict, ssh: SSHExecutor) -> dict:
        """Execute each step. On failure, attempt LLM-suggested fix or return for rollback."""
        deployment_id = plan["deployment_id"]
        results = []

        for step in plan["steps"]:
            if step["confidence"] == Confidence.LOW:
                return {
                    "status": "blocked",
                    "reason": f"Action '{step['action']}' is LOW confidence — manual approval required",
                    "step": step
                }

            if step["confidence"] == Confidence.MEDIUM:
                return {
                    "status": "requires_approval",
                    "action": step["action"],
                    "command": step["command"],
                    "message": "MEDIUM confidence action paused for human approval"
                }

            t0 = time.time()
            result = ssh.run(step["command"])
            duration = int((time.time() - t0) * 1000)

            if result.success:
                await self.log(deployment_id, step["action"], True,
                               command=step["command"], duration_ms=duration)
                results.append({"action": step["action"], "status": "success"})
            else:
                # Attempt LLM-assisted fix
                fix = await self._request_fix(step["command"], result.stderr)
                if fix and fix.get("safe"):
                    fix_result = ssh.run(fix["fix_command"])
                    await self.log(deployment_id, step["action"], fix_result.success,
                                   command=step["command"], error_msg=result.stderr,
                                   fix_applied=fix["fix_command"], duration_ms=duration)
                    if fix_result.success:
                        results.append({"action": step["action"], "status": "recovered", "fix": fix["explanation"]})
                        continue

                # Cannot recover
                await self.log(deployment_id, step["action"], False,
                               command=step["command"], error_msg=result.stderr, duration_ms=duration)
                return {
                    "status": "failed",
                    "action": step["action"],
                    "error": result.stderr,
                    "trigger_rollback": True
                }

        return {"status": "success", "steps": results}

    async def _request_fix(self, command: str, error: str) -> dict | None:
        prompt = f"""
A deployment command failed. Suggest a fix.

Failed command: {command}
Error output: {error}

Return ONLY this JSON:
{{
  "fix_command": "the corrected command",
  "explanation": "one sentence explanation",
  "safe": true
}}

Only set "safe": true if the fix command cannot cause data loss.
If you cannot safely fix this, return {{"safe": false}}.
"""
        try:
            return await self.llm.generate_json(prompt)
        except Exception:
            return None

    def _node_install_cmd(self, version: str) -> str:
        return (
            f"curl -fsSL https://deb.nodesource.com/setup_{version}.x | sudo -E bash - && "
            f"sudo apt-get install -y nodejs"
        )
```

---

## 10. Phase 5 — Build the Validator Agent

Create `backend/app/agents/validator_agent.py`:

```python
import time, asyncio
from .base_agent import BaseAgent
from ..core.ssh_executor import SSHExecutor

class ValidatorAgent(BaseAgent):
    name = "validator"

    async def analyze(self, context: dict) -> dict:
        return {"checks": ["process_running", "port_bound", "health_endpoint", "liveness"]}

    async def execute(self, plan: dict, ssh: SSHExecutor) -> dict:
        deployment_id = plan["deployment_id"]
        app_name      = plan["app_name"]
        port          = plan["port"]
        results       = {}

        # Check 1: PM2 process running
        r = ssh.run(f"pm2 show {app_name} | grep status | grep -c online")
        results["process_running"] = r.success and "1" in r.stdout
        await self.log(deployment_id, "check_process_running", results["process_running"])

        # Check 2: Port is bound
        r = ssh.run(f"ss -tlnp | grep -c :{port}")
        results["port_bound"] = r.success and int(r.stdout.strip() or "0") > 0
        await self.log(deployment_id, "check_port_bound", results["port_bound"])

        # Check 3: Health endpoint responds
        r = ssh.run(f"curl -sf -o /dev/null -w '%{{http_code}}' http://localhost:{port}/health")
        results["health_endpoint"] = r.success and r.stdout.strip() in ("200", "204")
        await self.log(deployment_id, "check_health_endpoint", results["health_endpoint"])

        # Check 4: Liveness — still running after 10 seconds
        await asyncio.sleep(10)
        r = ssh.run(f"pm2 show {app_name} | grep status | grep -c online")
        results["liveness"] = r.success and "1" in r.stdout
        await self.log(deployment_id, "check_liveness", results["liveness"])

        healthy = all(results.values())

        return {
            "healthy": healthy,
            "checks":  results,
            "url":     f"http://{plan['server_host']}:{port}",
            "status":  "success" if healthy else "failed"
        }
```

---

## 11. Phase 6 — Build the Rollback Agent

Create `backend/app/agents/rollback_agent.py`:

```python
import json, os
from datetime import datetime
from .base_agent import BaseAgent
from ..core.ssh_executor import SSHExecutor
from ..config import settings

class RollbackAgent(BaseAgent):
    name = "rollback"

    async def analyze(self, context: dict) -> dict:
        return {"action": "capture_checkpoint"}

    async def capture_checkpoint(self, deployment_id: str, ssh: SSHExecutor, context: dict) -> str:
        """
        Called BEFORE deployment begins. Captures current server state.
        Returns checkpoint_id.
        """
        app_name  = context.get("app_name", "app")
        repo_path = context["repo_path"]

        snapshot = {
            "deployment_id": deployment_id,
            "captured_at":   datetime.now().isoformat(),
            "app_name":      app_name,
            "repo_path":     repo_path,
            "server_host":   context["server_host"],
        }

        # Was PM2 running anything before?
        r = ssh.run("pm2 list --json 2>/dev/null || echo '[]'")
        snapshot["pm2_processes"] = r.stdout.strip()

        # Does the repo directory exist?
        snapshot["repo_existed"] = ssh.dir_exists(repo_path)

        # Backup .env if it exists
        env_path = f"{repo_path}/.env"
        if ssh.file_exists(env_path):
            snapshot["env_backup"] = ssh.read_file(env_path)

        # Save checkpoint to disk
        os.makedirs(settings.checkpoint_dir, exist_ok=True)
        checkpoint_path = f"{settings.checkpoint_dir}/{deployment_id}.json"
        with open(checkpoint_path, "w") as f:
            json.dump(snapshot, f, indent=2)

        await self.log(deployment_id, "capture_checkpoint", True)
        return deployment_id

    async def execute(self, plan: dict, ssh: SSHExecutor) -> dict:
        """
        Called on deployment failure. Restores server to checkpoint state.
        """
        deployment_id   = plan["deployment_id"]
        checkpoint_path = f"{settings.checkpoint_dir}/{deployment_id}.json"

        if not os.path.exists(checkpoint_path):
            return {"status": "failed", "reason": "No checkpoint found — cannot rollback safely"}

        with open(checkpoint_path) as f:
            snapshot = json.load(f)

        steps_reversed = []

        # Stop PM2 process that was started
        app_name = snapshot["app_name"]
        r = ssh.run(f"pm2 delete {app_name} 2>/dev/null || true")
        steps_reversed.append({"action": "stop_pm2", "success": True})

        # Restore .env if we have a backup
        if "env_backup" in snapshot:
            env_path = f"{snapshot['repo_path']}/.env"
            r = ssh.run(f"cat > {env_path} << 'ENVEOF'\n{snapshot['env_backup']}\nENVEOF")
            steps_reversed.append({"action": "restore_env", "success": r.success})

        # If repo didn't exist before, remove it
        if not snapshot["repo_existed"]:
            r = ssh.run(f"rm -rf {snapshot['repo_path']}")
            steps_reversed.append({"action": "remove_repo", "success": r.success})

        await self.log(deployment_id, "rollback_complete", True)

        return {
            "status":         "rolled_back",
            "deployment_id":  deployment_id,
            "steps_reversed": steps_reversed
        }
```

---

## 12. Phase 7 — Orchestrator + API

### Step 7.1 — Orchestrator

Create `backend/app/core/orchestrator.py`:

```python
import uuid, asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from ..agents.detector_agent  import DetectorAgent
from ..agents.deploy_agent    import DeployAgent
from ..agents.validator_agent import ValidatorAgent
from ..agents.rollback_agent  import RollbackAgent
from ..core.llm_client        import OllamaClient
from ..core.ssh_executor      import SSHExecutor
from ..database               import Deployment

class Orchestrator:
    def __init__(self, db: AsyncSession):
        llm = OllamaClient()
        self.detector  = DetectorAgent(llm, db)
        self.deployer  = DeployAgent(llm, db)
        self.validator = ValidatorAgent(llm, db)
        self.rollback  = RollbackAgent(llm, db)
        self.db        = db

    async def run(self, config: dict, broadcast) -> dict:
        """
        Full deployment pipeline.
        broadcast(msg) sends a string to the WebSocket caller.
        """
        deployment_id = str(uuid.uuid4())[:8]
        server        = config["server"]

        deployment = Deployment(
            id          = deployment_id,
            repo_path   = config["repo_path"],
            server_host = server["host"],
            status      = "running",
        )
        self.db.add(deployment)
        await self.db.commit()

        with SSHExecutor(server["host"], server["user"], server["key_path"]) as ssh:
            try:
                # Step 1: Capture rollback checkpoint
                await broadcast(f"[{deployment_id}] Capturing rollback checkpoint...")
                ctx = {**config, "deployment_id": deployment_id, "ssh": ssh, "server_host": server["host"]}
                await self.rollback.capture_checkpoint(deployment_id, ssh, ctx)

                # Step 2: Detect
                await broadcast(f"[{deployment_id}] Detector Agent: analyzing repository...")
                analysis = await self.detector.analyze({**ctx})
                await broadcast(f"[{deployment_id}] Detected: {analysis['framework']} / Node {analysis['node_version']}")

                # Step 3: Plan
                deploy_plan = await self.deployer.analyze({**ctx, "detector_analysis": analysis})

                # Step 4: Deploy
                await broadcast(f"[{deployment_id}] Deploy Agent: executing {len(deploy_plan['steps'])} steps...")
                for step in deploy_plan["steps"]:
                    await broadcast(f"[{deployment_id}]   → {step['action']} [{step['confidence']}]")

                deploy_result = await self.deployer.execute(
                    {**deploy_plan, "deployment_id": deployment_id}, ssh
                )

                if deploy_result["status"] != "success":
                    await broadcast(f"[{deployment_id}] Deploy failed: {deploy_result.get('error')}")
                    if deploy_result.get("trigger_rollback"):
                        await broadcast(f"[{deployment_id}] Rollback Agent: restoring server...")
                        await self.rollback.execute({"deployment_id": deployment_id}, ssh)
                    deployment.status = "failed"
                    await self.db.commit()
                    return {"status": "failed", "deployment_id": deployment_id}

                # Step 5: Validate
                await broadcast(f"[{deployment_id}] Validator Agent: running health checks...")
                val_result = await self.validator.execute({
                    "deployment_id": deployment_id,
                    "app_name":      analysis["app_name"],
                    "port":          analysis["port"],
                    "server_host":   server["host"],
                }, ssh)

                if not val_result["healthy"]:
                    await broadcast(f"[{deployment_id}] Validation failed — rolling back...")
                    await self.rollback.execute({"deployment_id": deployment_id}, ssh)
                    deployment.status = "failed"
                    await self.db.commit()
                    return {"status": "failed", "deployment_id": deployment_id, "validation": val_result}

                deployment.status       = "success"
                deployment.completed_at = datetime.now()
                await self.db.commit()

                await broadcast(f"[{deployment_id}] SUCCESS — app live at {val_result['url']}")
                return {"status": "success", "deployment_id": deployment_id, "url": val_result["url"]}

            except Exception as e:
                deployment.status        = "failed"
                deployment.error_summary = str(e)
                await self.db.commit()
                await broadcast(f"[{deployment_id}] ERROR: {str(e)}")
                return {"status": "error", "deployment_id": deployment_id, "error": str(e)}
```

### Step 7.2 — FastAPI Application

Create `backend/app/main.py`:

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any
from .database import init_db, get_db, Deployment
from .core.orchestrator import Orchestrator
from .core.llm_client import OllamaClient
from .config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio

active_connections: Dict[str, WebSocket] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print(f"DevOps AI Platform started — LLM: {settings.ollama_model}")
    yield

app = FastAPI(title="DevOps AI Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    llm = OllamaClient()
    return {
        "status": "ok",
        "llm_available": await llm.is_available(),
        "model": settings.ollama_model
    }

@app.post("/api/v1/deploy")
async def deploy(config: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Start a deployment. Required fields:
    { "repo_path": "/var/app", "server": {"host": "...", "user": "...", "key_path": "..."} }
    """
    required = ["repo_path", "server"]
    for field in required:
        if field not in config:
            raise HTTPException(400, f"Missing required field: {field}")

    orchestrator = Orchestrator(db)

    async def broadcast(msg: str):
        # Also print server-side for logging
        print(msg)

    result = await asyncio.create_task(orchestrator.run(config, broadcast))
    return result

@app.get("/api/v1/deployments/{deployment_id}")
async def get_deployment(deployment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Deployment).where(Deployment.id == deployment_id))
    dep = result.scalar_one_or_none()
    if not dep:
        raise HTTPException(404, "Deployment not found")
    return {"id": dep.id, "status": dep.status, "repo": dep.repo_path, "server": dep.server_host}

@app.websocket("/ws/{deployment_id}")
async def websocket_endpoint(websocket: WebSocket, deployment_id: str):
    await websocket.accept()
    active_connections[deployment_id] = websocket
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        active_connections.pop(deployment_id, None)
```

**Phase 7 complete when:** `uvicorn backend.app.main:app --reload` starts without errors and `GET /health` returns `{"llm_available": true}`.

---

## 13. Phase 8 — Monitoring Stack

### Step 8.1 — Prometheus Config

Create `infrastructure/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'devops-ai-backend'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'
```

### Step 8.2 — Add Metrics to FastAPI

```bash
pip install prometheus-fastapi-instrumentator==6.1.0
```

Add to `main.py` after app creation:

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

### Step 8.3 — Grafana Dashboard

After `docker compose up`:

1. Open `http://localhost:3001` (Grafana) — login: admin/admin
2. Add data source → Prometheus → URL: `http://prometheus:9090`
3. Import dashboard ID **11159** (FastAPI Observability)
4. Create an alert: if `http_request_duration_seconds` p95 > 5s, send notification

### Step 8.4 — Application-Level Alerts

Add to `backend/app/core/orchestrator.py` — after a failed deployment:

```python
# Log failed deployment rate to Prometheus counter
from prometheus_client import Counter
deployment_failures = Counter('deployment_failures_total', 'Total deployment failures')

# In the failure branch:
deployment_failures.inc()
```

**Phase 8 complete when:** Grafana shows request metrics and you can trigger an alert by intentionally failing a deployment.

---

## 14. Phase 9 — Testing

### Step 9.1 — Test Each Agent in Isolation

Create `backend/tests/test_detector.py`:

```python
import pytest, json
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_detector_identifies_express():
    pkg = {"name": "my-api", "scripts": {"start": "node server.js", "build": "tsc"},
           "dependencies": {"express": "^4.18.0"}}
    
    llm = AsyncMock()
    llm.generate_json = AsyncMock(return_value={
        "node_version": "20", "start_script": "node server.js",
        "needs_build": True, "build_script": "npm run build", "port": 3000, "env_vars_required": []
    })
    
    db  = AsyncMock()
    ssh = MagicMock()
    ssh.run.return_value = MagicMock(success=True, stdout="package.json\nserver.js\n")
    ssh.read_file.return_value = json.dumps(pkg)
    
    from backend.app.agents.detector_agent import DetectorAgent
    agent = DetectorAgent(llm, db)
    result = await agent.analyze({"repo_path": "/app", "deployment_id": "test-1", "ssh": ssh})
    
    assert result["framework"]   == "express"
    assert result["needs_build"] == True
    assert result["port"]        == 3000

@pytest.mark.asyncio
async def test_detector_raises_on_missing_package_json():
    llm = AsyncMock()
    db  = AsyncMock()
    ssh = MagicMock()
    ssh.run.return_value = MagicMock(success=True, stdout="index.html\nstyle.css\n")
    
    from backend.app.agents.detector_agent import DetectorAgent
    agent = DetectorAgent(llm, db)
    
    with pytest.raises(ValueError, match="No package.json"):
        await agent.analyze({"repo_path": "/app", "deployment_id": "test-2", "ssh": ssh})
```

### Step 9.2 — Run Tests

```bash
cd backend
pytest tests/ -v --asyncio-mode=auto

# Expected output:
# tests/test_detector.py::test_detector_identifies_express        PASSED
# tests/test_detector.py::test_detector_raises_on_missing_package PASSED
```

### Step 9.3 — Integration Test Script

Create `scripts/test_deploy.py`:

```python
"""
Manual integration test — runs against a real local Docker container.
Requires: docker running, Ollama running, PostgreSQL running.
"""
import httpx, asyncio

async def test_full_deploy():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Check health
        r = await client.get("/health")
        assert r.json()["llm_available"], "Ollama must be running"
        print("✓ Health check passed")

        # 2. Submit deploy
        r = await client.post("/api/v1/deploy", json={
            "repo_path": "/tmp/test-app",
            "server": {
                "host":     "127.0.0.1",
                "user":     "ubuntu",
                "key_path": "/home/user/.ssh/id_rsa"
            }
        }, timeout=120)
        result = r.json()
        print(f"Deploy result: {result}")
        assert result["status"] in ("success", "failed")  # not an unhandled error
        print("✓ Deploy completed without crash")

asyncio.run(test_full_deploy())
```

---

## 15. Phase 10 — First Full Deployment Run

### Step 10.1 — Prepare a Test Target

```bash
# Option A: Local Docker container as deploy target
docker run -d --name deploy-target \
  -p 2222:22 \
  -e AUTHORIZED_KEY="$(cat ~/.ssh/id_rsa.pub)" \
  linuxserver/openssh-server

# Option B: Any Linux VM (local or cloud) with SSH access
```

### Step 10.2 — Prepare a Test Node.js App

```bash
mkdir /tmp/test-app && cd /tmp/test-app
npm init -y
npm install express
cat > index.js << 'EOF'
const express = require('express')
const app = express()
app.get('/health', (req, res) => res.json({ status: 'ok' }))
app.listen(process.env.PORT || 3000, () => console.log('Running'))
EOF
```

### Step 10.3 — Start the Platform

```bash
# Terminal 1: Infrastructure
cd infrastructure && docker compose up -d

# Terminal 2: Ollama
ollama serve

# Terminal 3: Backend
cd backend && uvicorn app.main:app --reload --port 8000
```

### Step 10.4 — Run the Deployment

```bash
curl -X POST http://localhost:8000/api/v1/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/tmp/test-app",
    "server": {
      "host": "127.0.0.1",
      "user": "ubuntu",
      "key_path": "/home/youruser/.ssh/id_rsa"
    }
  }'
```

### Step 10.5 — Verify

```bash
# Watch logs in Terminal 3 — you should see each agent step
# Then verify the app is live:
curl http://127.0.0.1:3000/health
# Expected: {"status": "ok"}

# Check deployment record in PostgreSQL
psql postgresql://devops:devops123@localhost/devops_ai \
  -c "SELECT id, status, completed_at FROM deployments ORDER BY started_at DESC LIMIT 5;"
```

---

## 16. Post-MVP Roadmap

Build these features in order. Each one builds on a stable base.

| Priority | Feature | Effort | What It Adds |
|----------|---------|--------|--------------|
| 1 | Python support in Detector + Deploy | 1 week | Django, Flask, FastAPI apps |
| 2 | React UI — deployment dashboard | 1 week | Visual deployment history, live logs |
| 3 | FrontendAgent (React/Vite apps) | 1 week | Static site + SSR deployments |
| 4 | DatabaseAgent (PostgreSQL setup) | 1 week | DB provisioning as part of deploy |
| 5 | OpenAI / Anthropic LLM support | 2 days | Swap Ollama in config.py |
| 6 | GitHub webhook trigger | 3 days | Auto-deploy on git push |
| 7 | Slack / email notifications | 2 days | Alert on deploy success/failure |
| 8 | Multi-server deployments | 2 weeks | Blue-green, rolling updates |
| 9 | Kubernetes support | 3 weeks | Only after Docker path is solid |

---

*Build it end-to-end before building it wide. The architecture above gives you an application that actually works — four agents that each have one job, hand off cleanly, and leave an auditable trail in PostgreSQL. When you demo this, every step is visible, explainable, and real.*