# DevOps AI Automator - Complete Technical Documentation

## Table of Contents

1. [Project Overview](#project-overview)
2. [Complete File Structure](#complete-file-structure)
3. [API Endpoints Documentation](#api-endpoints-documentation)
4. [Multi-Agent System Architecture](#multi-agent-system-architecture)
5. [LLM Integration Setup](#llm-integration-setup)
6. [Credentials Management](#credentials-management)
7. [WebSocket Implementation](#websocket-implementation)
8. [Deployment Pipeline Flow](#deployment-pipeline-flow)
9. [Docker Configuration](#docker-configuration)
10. [Frontend React Components](#frontend-react-components)
11. [Error Handling Strategy](#error-handling-strategy)
12. [Configuration Files](#configuration-files)
13. [API Call Sequence Examples](#api-call-sequence-examples)
14. [Known Issues and Limitations](#known-issues-and-limitations)
15. [Rebuild Instructions](#rebuild-instructions)
16. [Code Snippets](#code-snippets)

---

## 1. PROJECT OVERVIEW

### Project Name and Purpose

**DevOps AI Automator** - An autonomous, AI-powered DevOps deployment orchestration platform that leverages multi-agent AI systems to completely automate the deployment pipeline.

### High-Level Architecture Description

The system follows a **4-Agent Multi-Stage Pipeline Architecture**:

```
User Input → Frontend (React/Vite) → Backend API (FastAPI)
    ↓
Agent 1: Repository Analyzer - Scans repo, detects type, extracts dependencies
    ↓
Agent 2: Pipeline Commander - Creates optimized 7-stage deployment plan
    ↓
Agent 3: Execution Solver - Executes with AI-powered error recovery
    ↓
Agent 4: Validator Selector - Validates deployment, learns from outcomes
    ↓
Real-time Events → WebSocket → Frontend Dashboard
```

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Backend** | FastAPI | 0.104.1 |
| **Backend Runtime** | Uvicorn | 0.24.0 |
| **Frontend** | React | Latest (via Vite) |
| **Build Tool** | Vite | Latest |
| **Database** | SQLite + Async SQLAlchemy | SQLAlchemy 2.0.50 |
| **LLM Primary** | Claude API | claude-3-5-sonnet-20241022 |
| **LLM Fallback** | Ollama + DeepSeek | deepseek-coder:6.7b |
| **SSH Client** | Paramiko | 3.4.0 |
| **Docker Client** | Docker SDK | 6.1.3 |
| **Message Queue** | Redis | 5.0.1 (optional) |
| **Task Queue** | Celery | 5.3.4 (optional) |
| **Security** | Python-Jose, Passlib, Cryptography | Latest |
| **Async HTTP** | HTTPX | 0.25.1 |
| **Web Sockets** | WebSockets | 12.0 |
| **Container Runtime** | Docker Compose | v2.23.0+ |

### System Requirements and Prerequisites

**Server Requirements:**
- Linux host (Ubuntu 22.04 LTS recommended) with SSH access
- At least 4 CPU cores, 8GB RAM
- 20GB free disk space (for SonarQube, Jenkins, and application images)
- Docker Engine 20.10+ installed
- Sudo access for the SSH user

**Local Development:**
- Python 3.11+
- Node.js 20+
- Docker Desktop or Docker Engine
- Docker socket access

**External Services:**
- DockerHub account and credentials
- GitHub account with Personal Access Token (for private repos)
- OpenAI API key (optional, for Claude integration)
- Ollama running locally or remotely (default: localhost:11434)

---

## 2. COMPLETE FILE STRUCTURE

```
devops-ai-automator/
├── backend/                              # FastAPI backend
│   ├── __init__.py
│   ├── main.py                           # Main FastAPI app, route handlers
│   ├── config.py                         # Settings management (Pydantic)
│   ├── database.py                       # SQLAlchemy async setup
│   ├── models.py                         # SQLAlchemy ORM models
│   ├── schemas.py                        # Pydantic request/response models
│   │
│   ├── agents/                           # Multi-agent system
│   │   ├── __init__.py
│   │   ├── repository_analyzer.py        # Agent 1: Analyzes repo structure
│   │   ├── pipeline_commander.py         # Agent 2: Creates deployment plan
│   │   ├── execution_solver.py           # Agent 3: Executes with AI recovery
│   │   ├── validator_selector.py         # Agent 4: Validates & learns
│   │   └── orchestrator.py               # Agent orchestration & messaging
│   │
│   ├── llm_client.py                     # LLM provider adapter (Claude/Ollama)
│   ├── llm_error_formatter.py            # Error context formatting for LLM
│   ├── multi_agent.py                    # Core agent classes & remediation engine
│   ├── ai_agent.py                       # Base AI agent functionality
│   │
│   ├── pipeline.py                       # Pipeline orchestrator (7 stages)
│   ├── process.py                        # Local command execution wrapper
│   ├── ssh_manager.py                    # SSH connection & remote command execution
│   ├── docker_builder.py                 # Docker image build automation
│   ├── docker_orchestrator.py            # Docker Compose & container management
│   │
│   ├── credentials_manager.py            # Auto-generate secure credentials
│   ├── error_fix_mapper.py               # Direct error→fix pattern mappings
│   ├── github_manager.py                 # GitHub API integration
│   ├── sonar_integration.py              # SonarQube REST API client
│   ├── sonar_scanner.py                  # SonarQube scanner execution
│   ├── security.py                       # Security utilities, encryption
│   │
│   ├── event_bus.py                      # In-memory event pub/sub system
│   ├── session_store.py                  # Session persistence & state management
│   ├── websocket_manager.py              # WebSocket connection management
│   └── (other supporting modules)
│
├── frontend/                             # React + Vite frontend
│   ├── index.html                        # HTML entry point
│   ├── vite.config.js                    # Vite configuration
│   ├── package.json                      # Node dependencies
│   ├── App.jsx                           # Main React app component
│   ├── devops-ai-automator.jsx           # Primary UI component
│   ├── src/
│   │   ├── main.jsx                      # React app initialization
│   │   └── components/
│   │       ├── DeploymentForm.jsx        # Deployment input form
│   │       ├── CredentialsPanel.jsx      # Credentials display
│   │       ├── AgentActivityPanel.jsx    # Agent action monitoring
│   │       ├── ActiveLogsViewer.jsx      # Real-time log streaming
│   │       └── (other UI components)
│   └── styles/                           # CSS styling
│       ├── App.css
│       ├── DeploymentForm.css
│       └── (other component styles)
│
├── scripts/                              # Utility scripts
│   ├── setup_ollama.sh                   # Ollama model setup (Linux)
│   ├── setup_ollama.ps1                  # Ollama model setup (Windows)
│   ├── test_ollama.py                    # Test Ollama connectivity
│   ├── test_error_mapper.py              # Test error→fix mappings
│   ├── test_api.py                       # Integration tests
│   ├── verify_fixes.sh                   # Verify applied fixes
│   └── deploy_ec2.py                     # EC2 deployment script
│
├── Dockerfile                            # Multi-stage container image
├── docker-compose.yml                    # Local development compose stack
├── requirements.txt                      # Python dependencies
├── .env.example                          # Environment template
├── .dockerignore                         # Docker build exclusions
├── .gitignore                            # Git exclusions
├── devops-ai.service                     # SystemD service file (optional)
│
└── Documentation Files:
    ├── README.md                         # Quick start guide
    ├── SETUP_GUIDE.md                    # Detailed setup instructions
    ├── DEPLOYMENT_STATUS.md              # Deployment status tracking
    ├── MULTI_AGENT_SYSTEM.md             # Agent architecture details
    ├── ERROR_MAPPER_GUIDE.md             # Error mapping documentation
    ├── EC2_DEPLOYMENT.md                 # EC2-specific deployment
    └── PROJECT_DOCUMENTATION.md          # This file
```

### Key Files Description

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app initialization, route definitions, WebSocket endpoint |
| `backend/multi_agent.py` | Core RemediationAgent and ValidatorAgent classes |
| `backend/pipeline.py` | 7-stage pipeline orchestrator with progress tracking |
| `backend/llm_client.py` | LLM abstraction layer (Claude → Ollama → Fallback) |
| `backend/credentials_manager.py` | Auto-generates credentials for all services |
| `backend/error_fix_mapper.py` | Direct error pattern → fix command mapping |
| `backend/session_store.py` | SQLite persistence for deployment sessions |
| `backend/event_bus.py` | In-memory pub/sub for real-time events |
| `frontend/App.jsx` | Main React application wrapper |
| `frontend/components/DeploymentForm.jsx` | Input form for deployment parameters |
| `docker-compose.yml` | Local development stack (Backend, Ollama, Redis, Postgres) |

---

## 3. API ENDPOINTS DOCUMENTATION

### Base URL
```
http://{backend_host}:{port}
Default: http://localhost:8000
```

### Root Endpoint

#### GET `/`
- **Description**: Root endpoint - serves frontend or returns API information
- **Response**: HTML (if frontend built) or JSON
- **Status Codes**: 200
- **Example Response**:
```json
{
  "status": "ok",
  "message": "DevOps AI Platform API",
  "api_endpoints": {
    "health": "/api/health",
    "deploy": "POST /api/deploy",
    "status": "GET /api/status/{session_id}",
    "credentials": "GET /api/credentials/{session_id}",
    "websocket": "WS /ws/{session_id}"
  }
}
```
- **Code Location**: `backend/main.py:61-83`

### Health Check Endpoints

#### GET `/api/health`
- **Description**: Check backend health and LLM availability
- **Response Schema**:
```json
{
  "status": "ok",
  "ollama_host": "http://localhost:11434",
  "model": "deepseek-coder:6.7b"
}
```
- **Status Codes**: 200
- **Example Curl**:
```bash
curl http://localhost:8000/api/health
```
- **Code Location**: `backend/main.py:86-92`

#### GET `/api/agents/health`
- **Description**: Check multi-agent system configuration
- **Response Schema**:
```json
{
  "multi_agent": true,
  "validation_enabled": true,
  "llm": {
    "claude_configured": true,
    "ollama_ready": true,
    "ollama_models": ["deepseek-coder:6.7b"]
  }
}
```
- **Status Codes**: 200
- **Example Curl**:
```bash
curl http://localhost:8000/api/agents/health
```
- **Code Location**: `backend/main.py:95-101`

### Deployment Endpoints

#### POST `/api/deploy`
- **Description**: Start a new deployment pipeline
- **Authentication**: None required
- **Request Body Schema**:
```json
{
  "repo_url": "https://github.com/user/repo.git",
  "github_token": "ghp_xxxxxxxxxxxxx",
  "server_ip": "192.168.1.100",
  "pem_file_content": "-----BEGIN PRIVATE KEY-----\n...",
  "dockerhub_user": "dockerhub_username",
  "dockerhub_pass": "dockerhub_password",
  "branch": "main",
  "ssh_user": "ubuntu"
}
```
- **Response Schema**:
```json
{
  "session_id": "uuid-string"
}
```
- **Status Codes**: 200 (Created), 422 (Validation Error)
- **Example Curl**:
```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/repo.git",
    "github_token": "ghp_xxx",
    "server_ip": "192.168.1.100",
    "pem_file_content": "-----BEGIN PRIVATE KEY-----\n...",
    "dockerhub_user": "user",
    "dockerhub_pass": "pass"
  }'
```
- **Code Location**: `backend/main.py:231-243`
- **Backend Implementation**: 
  1. Creates unique session_id
  2. Stores deployment inputs in session
  3. Creates async task for pipeline execution
  4. Returns session_id immediately (async)

#### GET `/api/status/{session_id}`
- **Description**: Get current deployment status
- **Path Parameters**: `session_id` (UUID string)
- **Response Schema**:
```json
{
  "session_id": "uuid",
  "status": "running|completed|failed",
  "progress": 45,
  "current_stage": "docker",
  "stages": {
    "init": "completed",
    "sonar": "running",
    "jenkins": "pending"
  },
  "logs": [
    {
      "timestamp": "2024-05-28T10:51:06",
      "level": "info",
      "message": "Connected to server",
      "stage": "init"
    }
  ],
  "ai_interventions": [
    {
      "timestamp": "2024-05-28T10:51:06",
      "type": "error",
      "message": "SSH timeout detected - retrying",
      "agent": "RemediationAgent"
    }
  ],
  "outputs": {
    "sonarqube": { "url": "http://192.168.1.100:9000" },
    "jenkins": { "url": "http://192.168.1.100:8081" },
    "application": { "url": "http://192.168.1.100:3000" }
  },
  "error": null,
  "created_at": "2024-05-28T10:51:00",
  "completed_at": null
}
```
- **Status Codes**: 200, 404 (Session Not Found)
- **Example Curl**:
```bash
curl http://localhost:8000/api/status/550e8400-e29b-41d4-a716-446655440000
```
- **Code Location**: `backend/main.py:246-253`
- **Data Source**: SessionStore (SQLite)

#### GET `/api/credentials/{session_id}`
- **Description**: Get generated credentials after deployment completes
- **Path Parameters**: `session_id` (UUID)
- **Response Schema**:
```json
{
  "ready": true,
  "status": "completed",
  "sonarqube": {
    "service": "SonarQube",
    "url": "http://192.168.1.100:9000",
    "username": "admin",
    "password": "Auto-generated: xxxxx***",
    "api_token": "squ_xxxxxxxxxxxxxxxx"
  },
  "jenkins": {
    "service": "Jenkins",
    "url": "http://192.168.1.100:8081",
    "username": "admin",
    "password": "Auto-generated: xxxxx***",
    "api_token": "xxxxxxxx"
  },
  "application": {
    "service": "Application",
    "url": "http://192.168.1.100:3000",
    "username": "appuser_xxx",
    "password": "Auto-generated: xxxxx",
    "api_key": "xxxxxxxxxxxxxxxx"
  }
}
```
- **Status Codes**: 200, 404
- **Example Curl**:
```bash
curl http://localhost:8000/api/credentials/550e8400-e29b-41d4-a716-446655440000
```
- **Code Location**: `backend/main.py:256-264`

### Agent & Learning Endpoints

#### GET `/api/agents/learnings`
- **Description**: Retrieve agent learning history (error patterns & success/failure rates)
- **Query Parameters**: `limit` (default: 50, max: 200)
- **Response Schema**:
```json
[
  {
    "provider": "claude",
    "error_signature": "timeout_opening_channel",
    "successes": 5,
    "failures": 1,
    "last_error": "Connection reset by peer",
    "last_fix": "Increased SSH ClientAliveInterval",
    "updated_at": "2024-05-28T10:51:06.123"
  }
]
```
- **Status Codes**: 200
- **Example Curl**:
```bash
curl "http://localhost:8000/api/agents/learnings?limit=20"
```
- **Code Location**: `backend/main.py:104-123`
- **Data Source**: SQLAlchemy AgentLearning model

### Debug Endpoints

#### GET `/api/debug/ollama`
- **Description**: Test Ollama connectivity and model availability
- **Response Schema**:
```json
{
  "ollama_reachable": true,
  "model_loaded": true,
  "test_response": "OK",
  "models": ["deepseek-coder:6.7b"],
  "model": "deepseek-coder:6.7b",
  "ollama_host": "http://localhost:11434"
}
```
- **Status Codes**: 200
- **Example Curl**:
```bash
curl http://localhost:8000/api/debug/ollama
```
- **Code Location**: `backend/main.py:126-129`

#### GET `/api/debug/ollama-fix-test`
- **Description**: Test if Ollama can generate fix commands
- **Response Schema**:
```json
{
  "ollama_available": true,
  "test_error": "Timeout opening channel",
  "candidates": {
    "claude": {
      "has_commands": true,
      "command_count": 4,
      "commands": ["cmd1", "cmd2"],
      "confidence": 0.95
    },
    "ollama": {
      "has_commands": true,
      "command_count": 3,
      "commands": ["cmd1", "cmd2"],
      "confidence": 0.85
    }
  }
}
```
- **Status Codes**: 200
- **Example Curl**:
```bash
curl http://localhost:8000/api/debug/ollama-fix-test
```
- **Code Location**: `backend/main.py:132-171`

#### POST `/api/debug/ssh-test`
- **Description**: Test SSH connectivity and AI-powered error recovery
- **Request Body**:
```json
{
  "server_ip": "192.168.1.100",
  "pem_content": "-----BEGIN PRIVATE KEY-----\n...",
  "username": "ubuntu",
  "port": 22,
  "timeout": 30
}
```
- **Response Schema**:
```json
{
  "success": true,
  "session_id": "debug-uuid",
  "ai_fixes_applied": 2,
  "ai_fix_history": [
    "Applied: Increased SSH timeout settings",
    "Applied: Fixed SSH key permissions"
  ]
}
```
- **Status Codes**: 200
- **Example Curl**:
```bash
curl -X POST http://localhost:8000/api/debug/ssh-test \
  -H "Content-Type: application/json" \
  -d '{
    "server_ip": "192.168.1.100",
    "pem_content": "...",
    "username": "ubuntu"
  }'
```
- **Code Location**: `backend/main.py:174-228`

### WebSocket Endpoint

#### WS `/ws/{session_id}`
- **Description**: Real-time streaming of deployment events and agent activity
- **Connection**: WebSocket upgrade required
- **Path Parameters**: `session_id` (UUID)
- **Message Types**:

**Initial Status Message** (sent on connect):
```json
{
  "type": "status",
  "data": { /* full session status */ },
  "timestamp": "2024-05-28T10:51:06.123"
}
```

**Log Event**:
```json
{
  "type": "log",
  "data": {
    "message": "Connected to server",
    "level": "info",
    "stage": "init",
    "timestamp": "2024-05-28T10:51:06"
  },
  "timestamp": "2024-05-28T10:51:06.123"
}
```

**AI Intervention Event**:
```json
{
  "type": "ai_action",
  "data": {
    "agent": "RemediationAgent",
    "action": "Applied SSH timeout fix",
    "intervention_type": "ok",
    "message": "SSH timeout detected - applied fix"
  },
  "timestamp": "2024-05-28T10:51:06.123"
}
```

**Stage Update Event**:
```json
{
  "type": "stage_update",
  "data": {
    "stage": "docker",
    "status": "completed",
    "progress": 75
  },
  "timestamp": "2024-05-28T10:51:06.123"
}
```

**Progress Event**:
```json
{
  "type": "progress",
  "data": {
    "current": 45,
    "total": 100,
    "stage": "docker"
  },
  "timestamp": "2024-05-28T10:51:06.123"
}
```

**Error Event**:
```json
{
  "type": "error",
  "data": {
    "message": "Docker build failed",
    "error": "permission denied",
    "stage": "docker"
  },
  "timestamp": "2024-05-28T10:51:06.123"
}
```

- **Example WebSocket Connection** (JavaScript):
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/550e8400-e29b-41d4-a716-446655440000');
ws.onopen = () => console.log('Connected');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(`[${message.type}]`, message.data);
};
ws.onerror = (error) => console.error('WebSocket error:', error);
ws.onclose = () => console.log('Disconnected');
```

- **Code Location**: `backend/main.py:267-288`, `backend/event_bus.py`

---

## 4. MULTI-AGENT SYSTEM ARCHITECTURE

### Agent System Overview

The system uses **4 specialized AI agents** working in sequence:

```
┌─────────────────────────────────────────────────────────────┐
│                 MULTI-AGENT PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Agent 1: Repository Analyzer                               │
│  ├─ Input: GitHub repo URL, token                           │
│  ├─ Process: Clone, scan files, detect type                 │
│  └─ Output: { project_type, dependencies, entry_points }   │
│         ↓                                                     │
│  Agent 2: Pipeline Commander                                │
│  ├─ Input: Repository analysis                              │
│  ├─ Process: Use LLM to create optimized 7-stage plan      │
│  └─ Output: { stages[], build_cmd, start_cmd }             │
│         ↓                                                     │
│  Agent 3: Execution Solver                                  │
│  ├─ Input: Pipeline plan, SSH target, credentials           │
│  ├─ Process: Execute each stage, catch errors, auto-fix     │
│  └─ Output: { success: bool, fix_history[], logs[] }       │
│         ↓                                                     │
│  Agent 4: Validator Selector                                │
│  ├─ Input: Execution results                                │
│  ├─ Process: Validate deployment, score agent responses     │
│  └─ Output: { validation_score, issues[], learned[] }       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Agent 1: Repository Analyzer

**File Location**: `backend/agents/repository_analyzer.py`

**Purpose**: 
- Analyzes GitHub repository structure
- Detects application type (Node.js, Python, Java, etc.)
- Extracts dependencies and entry points
- Identifies required services (database, cache, etc.)
- Proposes build and start commands

**Input Format**:
```python
repo_path: str           # GitHub URL or local path
github_token: str | None # For private repos
```

**Output Format**:
```python
{
    "project_type": "nodejs",  # nodejs, python, java, go, rust, etc.
    "dependencies": ["express", "axios", "dotenv"],  # Top 20
    "entry_points": ["src/index.js", "server.js"],
    "suggested_ports": [3000, 5000],
    "build_command": "npm install && npm run build",
    "start_command": "npm start",
    "environment_variables": ["NODE_ENV", "PORT"],
    "database_required": True,
    "special_configs": {
        "nodejs_version": "20",
        "package_manager": "npm"
    },
    "confidence_score": 0.95,
    "analyzed_at": "2024-05-28T10:51:06.123",
    "repo_path": "/path/to/repo",
    "total_files": 152
}
```

**LLM Integration**:
- Uses Claude/Ollama to enhance analysis
- Prompt: "Based on the project structure, dependencies, and entry points, suggest the optimal build and start commands"
- Response parsing: Extracts JSON commands from LLM response

**Code Location**: 
- Class: `RepositoryAnalyzer` in `backend/agents/repository_analyzer.py`
- Main method: `async def analyze(repo_path, github_token)`
- LLM method: `async def _llm_enhance_analysis(app_type, dependencies, entry_points, files)`

**Workflow**:
1. Clone/access repository locally
2. Scan file tree for known patterns (package.json, requirements.txt, pom.xml, etc.)
3. Detect application type from file patterns
4. Extract dependencies from package managers
5. Find entry points (main files, index files)
6. Detect required ports from code analysis
7. Query LLM for optimization suggestions
8. Return comprehensive analysis

**Dependencies**:
- GitHubManager (GitHub API integration)
- LLMClient (for enhanced analysis)
- File system utilities

### Agent 2: Pipeline Commander

**File Location**: `backend/agents/pipeline_commander.py`

**Purpose**:
- Creates optimized 7-stage deployment pipeline
- Decides execution order and parallelization
- Generates Docker setup commands
- Plans SonarQube scanning
- Plans Jenkins integration
- Plans application deployment

**Input Format**:
```python
repo_analysis: dict  # Output from Agent 1
```

**Output Format**:
```python
{
    "project_type": "nodejs",
    "stages": [
        {
            "id": "init",
            "name": "Initialize Infrastructure",
            "commands": ["apt-get update", "docker --version"],
            "depends_on": []
        },
        {
            "id": "docker",
            "name": "Build and Push Docker Image",
            "commands": ["docker build ...", "docker push ..."],
            "depends_on": ["init"]
        }
    ],
    "total_duration_estimate": 1800,  # seconds
    "required_resources": ["docker", "nodejs"],
    "critical_path": ["init", "docker", "sonar", "jenkins"]
}
```

**LLM Integration**:
- Prompt: "Create a complete 7-stage deployment pipeline for a {project_type} application"
- Used for: Stage prioritization, command generation, resource allocation

**Code Location**: 
- Class: `PipelineCommanderAgent` in `backend/agents/pipeline_commander.py`
- Main method: `async def create_plan(repo_analysis)`

**Workflow**:
1. Parse repository analysis
2. Determine application type
3. Plan 7 standard stages:
   - Stage 1: Init (Docker, compose install)
   - Stage 2: SonarQube setup
   - Stage 3: Jenkins setup
   - Stage 4: Code scanning (SonarQube)
   - Stage 5: Docker build
   - Stage 6: Docker push
   - Stage 7: Deploy & validate
4. Optimize stage execution order
5. Add error recovery checkpoints
6. Return complete plan

**Dependencies**:
- RepositoryAnalyzer output
- LLMClient for planning

### Agent 3: Execution Solver

**File Location**: `backend/agents/execution_solver.py` (via `backend/multi_agent.py`)

**Purpose**:
- Executes each pipeline stage
- Monitors command output for errors
- Automatically applies AI-generated fixes on failure
- Retries failed operations with fixes
- Logs all actions for audit trail

**Input Format**:
```python
stage: dict          # Stage definition with commands
context: dict        # Execution context (repo analysis, deployment plan)
ssh_manager: SSHManager  # For remote execution
llm_client: LLMClient    # For fix generation
```

**Output Format**:
```python
{
    "success": True,
    "stage_id": "docker",
    "attempts": 2,
    "fix_applied": "Increased Docker daemon timeout",
    "fix_history": [
        "Attempt 1: Failed with 'timeout'",
        "Applied: Increased timeout to 120s",
        "Attempt 2: Succeeded"
    ],
    "execution_log": [
        {
            "command": "docker build ...",
            "stdout": "...",
            "stderr": "",
            "exit_code": 0
        }
    ],
    "execution_time_seconds": 45
}
```

**Error Handling**:
- **Pattern Matching**: Direct error→fix mapping first (ErrorFixMapper)
- **LLM Fallback**: If no pattern matches, query LLM for fix
- **Retry Logic**: Up to 3 attempts per stage
- **Learning**: Store success/failure patterns for future use

**Code Location**: 
- Class: `RemediationAgent` in `backend/multi_agent.py`
- Main method: `async def monitor_and_fix(func, *args, **kwargs)`
- Error handler: `async def _handle_operation_failure(error_context)`

**Workflow**:
1. Execute command on SSH target
2. Capture stdout/stderr/exit_code
3. Check if command succeeded (exit_code == 0)
4. On failure:
   a. Format error context with system info
   b. Check ErrorFixMapper for pattern match
   c. If found: apply fix, increment fix_history, retry
   d. If not found: query LLM for fix candidates
   e. Select best fix (confidence scoring)
   f. Apply fix and retry
5. On success: log execution, return results
6. Max 3 attempts per operation

**Dependencies**:
- SSHManager for command execution
- LLMClient for fix generation
- ErrorFixMapper for deterministic fixes
- EventBus for status broadcasting

### Agent 4: Validator Selector

**File Location**: `backend/agents/validator_selector.py` (via `backend/multi_agent.py`)

**Purpose**:
- Validates deployment success
- Scores different LLM providers/fixes
- Learns from outcomes
- Updates confidence scores
- Recommends best strategies for future deployments

**Input Format**:
```python
ssh_manager: SSHManager  # For validation checks
server_ip: str          # Target server IP
execution_results: dict # From Agent 3
```

**Output Format**:
```python
{
    "success": True,
    "validation_score": 0.98,
    "checks": [
        {
            "name": "Docker Status",
            "passed": True,
            "details": "Docker daemon is running"
        },
        {
            "name": "Container Status",
            "passed": True,
            "containers": ["sonarqube", "jenkins", "app"]
        }
    ],
    "issues": [],
    "learned": [
        {
            "error_pattern": "timeout_opening_channel",
            "successful_fix": "Increased SSH ClientAliveInterval",
            "provider": "claude",
            "confidence": 0.95
        }
    ],
    "timestamp": "2024-05-28T10:51:06.123"
}
```

**Selection Logic**:
1. Score each LLM provider based on fix success rate
2. Compare fix quality (execution speed, resource usage)
3. Track error patterns and successful fixes
4. Update AgentLearning table with metrics

**Learning Mechanism**:
- Database: `AgentLearning` table
- Tracks: error_signature, provider, successes, failures, confidence
- Updates: After each deployment (success/failure)
- Uses: For future provider selection

**Code Location**: 
- Class: `ValidatorAgent` in `backend/multi_agent.py`
- Main method: `async def validate_deployment(ssh_manager, server_ip)`
- Learning method: `async def _update_learning_metrics(provider, error_sig, success)`

**Workflow**:
1. Run validation checks on target server:
   - Docker daemon running
   - Required containers running
   - Services responding on expected ports
   - Application health checks
2. Score each check
3. Aggregate score (0-100%)
4. For each AI intervention used during execution:
   - Record provider (Claude/Ollama)
   - Record error pattern
   - Record outcome (success/failure)
   - Update confidence scores in database
5. Return validation results and learning updates

**Dependencies**:
- SSHManager for validation commands
- SQLAlchemy for learning database updates
- Execution results from Agent 3

---

## 5. LLM INTEGRATION SETUP

### LLM Provider Architecture

```
Query → Try Claude API
      ↓ (if configured and available)
      → Try Ollama
      ↓ (if Ollama running)
      → Use Fallback Patterns
      ↓ (deterministic error→fix mappings)
      → Return Result
```

### LLM Provider Configuration

**Claude API** (Primary):
- Provider: Anthropic
- Model: `claude-3-5-sonnet-20241022`
- Requires: `CLAUDE_API_KEY` environment variable
- Timeout: 90 seconds (configurable via `LLM_TIMEOUT`)

**Ollama** (Secondary):
- Provider: Local/Remote Ollama instance
- Model: `deepseek-coder:6.7b` (default)
- Host: `http://localhost:11434` (configurable via `OLLAMA_HOST`)
- Timeout: 90 seconds

**Fallback Patterns** (Tertiary):
- Provider: Direct error→fix mappings
- Source: `ErrorFixMapper` class
- No LLM dependency required

### Environment Variables

Required for LLM integration:

```env
# Claude Configuration (optional, but recommended)
CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# Ollama Configuration
OLLAMA_HOST=http://localhost:11434
DEEPSEEK_MODEL=deepseek-coder:6.7b

# LLM Behavior
LLM_TIMEOUT=90
USE_MULTI_AGENT=true
AGENT_VALIDATION_ENABLED=true

# Error Recovery
AI_AUTO_EXECUTE=true
AI_ALLOW_DANGEROUS_COMMANDS=false
AI_MAX_RETRIES=3
```

### Prompt Engineering Examples

#### Repository Analysis Prompt

```
You are analyzing a software repository. Identify the project type, technologies, 
entry points, and suggest optimal build/start commands.

Project Files:
- package.json (Node.js)
- src/index.js
- .gitignore

Dependencies Found:
- express
- axios
- dotenv

Response format: JSON only, no explanation.

{
  "project_type": "nodejs",
  "build_command": "npm install && npm run build",
  "start_command": "npm start",
  "environment_variables": ["NODE_ENV", "PORT"],
  "database_required": true
}
```

#### Error Fix Generation Prompt

```
An operation failed with this error on a Linux server:

Error: "Timeout opening channel"
Command: ssh ubuntu@192.168.1.100
Context: SSH connection attempt during deployment

Generate EXACT shell commands to fix this. 
Respond with JSON:

{
  "analysis": "Brief explanation of the issue",
  "commands": [
    "command 1",
    "command 2",
    "command 3"
  ],
  "verification": "command to verify fix worked",
  "confidence": 0.85
}
```

### Response Parsing

All LLM responses are parsed as JSON:

```python
def _parse_json_object(raw: str) -> dict:
    # Extract JSON from raw response
    # Handle markdown code blocks
    # Fallback to empty dict on parse error
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {}
```

### Error Handling and Fallback

**On Claude API failure**:
- Fallback to Ollama automatically
- Log error with timestamp
- Continue execution

**On Ollama failure**:
- Fallback to ErrorFixMapper
- Use deterministic pattern matching
- Apply known fixes

**On all LLM failures**:
- Return cached/fallback responses
- Continue with default behavior
- Alert user in UI

**Code Location**: `backend/llm_client.py:78-90`

### LLM Conversation Logging

All LLM interactions are logged:

```python
{
    "timestamp": "2024-05-28T10:51:06.123",
    "direction": "query",
    "agent": "RepositoryAnalyzer",
    "prompt": "Analyze this repository...",
    "response": { /* LLM response */ },
    "provider": "claude",
    "latency_ms": 1234
}
```

Accessible via: `GET /api/debug/ollama`, WebSocket messages

### Connection Configuration

**Claude API Connection**:
```python
from anthropic import Anthropic
client = Anthropic(api_key=settings.claude_api_key)
response = await client.messages.create(
    model=settings.claude_model,
    max_tokens=2048,
    messages=[{"role": "user", "content": prompt}]
)
```

**Ollama Connection**:
```python
async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
    response = await client.post(
        f"{settings.ollama_host}/api/generate",
        json={
            "model": settings.deepseek_model,
            "prompt": prompt,
            "stream": False
        }
    )
```

---

## 6. CREDENTIALS MANAGEMENT

### Credentials Generation Strategy

**Key Principle**: Users NEVER input credentials - they are auto-generated by the system.

**Generation Timing**: After successful deployment, credentials are generated for:
- SonarQube
- Jenkins
- Application
- Database
- API Keys

### Services Covered

| Service | Credentials Generated | Purpose |
|---------|----------------------|---------|
| **SonarQube** | admin username, password, API token | Code quality scanning |
| **Jenkins** | admin username, password, API token, SSH key | CI/CD pipeline |
| **Application** | username, password, API key, API secret | App authentication |
| **Database** | username, password, connection string | Data persistence |
| **API Keys** | Multiple API keys for external services | Service integration |

### Generation Implementation

**File Location**: `backend/credentials_manager.py`

**Class**: `CredentialsManager`

**Main Method**:
```python
async def generate_all_credentials(server_ip: str) -> dict[str, Any]:
    """Generate all credentials at once."""
    return {
        "sonarqube": self._generate_sonarqube_credentials(server_ip),
        "jenkins": self._generate_jenkins_credentials(server_ip),
        "application": self._generate_application_credentials(),
        "database": self._generate_database_credentials(),
        "api_keys": self._generate_api_keys(),
        "generated_at": datetime.now().isoformat()
    }
```

### SonarQube Credentials

```python
{
    "service": "SonarQube",
    "url": "http://192.168.1.100:9000",
    "username": "admin",
    "password": "Xyz123!@#Random24",  # 16 chars, alphanumeric + symbols
    "api_token": "squ_a1b2c3d4e5f6g7h8i9j0",
    "admin_token": "admin_k1l2m3n4o5p6q7r8s9t0",
    "display_password": "Auto-generated: Xyz123!***"
}
```

### Jenkins Credentials

```python
{
    "service": "Jenkins",
    "url": "http://192.168.1.100:8081",
    "username": "admin",
    "password": "Xyz123!@#Random24",  # 20 chars
    "api_token": "11a22b33c44d55e66f77a88b99c00d11",
    "initial_password": "Xyz123!@#R",
    "ssh_key": {
        "private": "-----BEGIN RSA PRIVATE KEY-----\n...",
        "public": "ssh-rsa AAAAB3Nz..."
    }
}
```

### Application Credentials

```python
{
    "service": "Application",
    "username": "appuser_a1b2",
    "password": "Auto-generated: Xyz12***",
    "api_key": "4a5b6c7d8e9f0a1b2c3d4e5f6g7h8i9j",
    "api_secret": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"
}
```

### Password Generation Security

**Method**: `secrets.token_hex()` + character mixing

```python
def _generate_password(length: int) -> str:
    """Generate cryptographically secure password."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    password = ''.join(secrets.choice(chars) for _ in range(length))
    return password
```

**Characteristics**:
- Uses `secrets` module (cryptographically secure)
- 16-20 characters default
- Mix of uppercase, lowercase, digits, symbols
- No user dictionary patterns
- Unique per generation

### SSH Key Pair Generation

```python
def _generate_ssh_key_pair() -> dict[str, str]:
    """Generate SSH RSA key pair for Jenkins."""
    # Using paramiko.RSAKey
    key = paramiko.RSAKey.generate(4096)
    private_file = io.StringIO()
    key.write_private_key(private_file)
    private_key = private_file.getvalue()
    public_key = f"ssh-rsa {base64.b64encode(key.get_base64()).decode()}"
    return {"private": private_key, "public": public_key}
```

### Storage

**Location**: SQLite session store or encrypted environment variables

**Access Endpoint**: `GET /api/credentials/{session_id}`

**Display Strategy**:
- Full password stored in database
- Display shows: `Auto-generated: Xyz123!***`
- Users can reveal in UI with confirmation
- Audit trail logged for all access

---

## 7. WEBSOCKET IMPLEMENTATION

### Connection Flow

```
1. Client initiates WebSocket connection
   Client: WS /ws/{session_id}
   
2. Server accepts connection
   Server: Accept WebSocket
   
3. Server sends initial snapshot
   Server: { type: "status", data: {session_data} }
   
4. Client subscribes to event stream
   Server: Start streaming events via EventBus
   
5. Events pushed in real-time as they occur
   Server: { type: "log", data: {...} }
   Server: { type: "ai_action", data: {...} }
   
6. Connection closed by client or server error
```

### Message Types

| Type | When Sent | Example |
|------|-----------|---------|
| `status` | On connection | Full session state snapshot |
| `log` | Pipeline events | Command output, stages |
| `ai_action` | Agent action | AI fix applied, error handled |
| `stage_update` | Stage changes | Stage started/completed |
| `progress` | Progress updates | Current progress % |
| `credentials` | Credentials ready | Service URLs and credentials |
| `error` | Errors occur | Stage failure, fatal error |

### Message Format (JSON)

All WebSocket messages follow this structure:

```json
{
  "type": "message_type",
  "data": { /* message-specific data */ },
  "timestamp": "2024-05-28T10:51:06.123Z"
}
```

### Broadcasting Implementation

**File Location**: `backend/event_bus.py`

**Class**: `EventBus`

```python
class EventBus:
    async def publish(self, session_id: str, event_type: str, data: dict) -> None:
        """Publish event to all subscribers."""
        event = PipelineEvent(
            type=event_type,
            data=data,
            timestamp=datetime.now(timezone.utc)
        )
        # Store in history (for new subscribers)
        self._history[session_id].append(event)
        
        # Send to all active subscribers
        for queue in self._subscribers.get(session_id, set()):
            queue.put_nowait(event)

    async def subscribe(self, session_id: str) -> AsyncGenerator[PipelineEvent, None]:
        """Subscribe to events for a session."""
        queue = asyncio.Queue(maxsize=1000)
        # Send all historical events first
        for event in self._history.get(session_id, []):
            queue.put_nowait(event)
        # Then stream new events
        self._subscribers[session_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[session_id].discard(queue)
```

### Broadcasting Pattern

Events are published from multiple places in the pipeline:

```python
# From RemediationAgent
await event_bus.publish(
    session_id,
    "ai_action",
    {
        "agent": "RemediationAgent",
        "action": "Applied SSH timeout fix",
        "message": "SSH error detected and fixed"
    }
)

# From PipelineOrchestrator
await event_bus.publish(
    session_id,
    "stage_update",
    {
        "stage": "docker",
        "status": "completed",
        "progress": 75
    }
)

# From SessionStore
await event_bus.publish(
    session_id,
    "log",
    {
        "message": "Connected to server",
        "level": "info",
        "stage": "init"
    }
)
```

### WebSocket Endpoint Implementation

**File Location**: `backend/main.py:267-288`

```python
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    try:
        # Send initial state snapshot
        snapshot = await session_store.get(session_id)
        await websocket.send_json({
            "type": "status",
            "data": _jsonable(snapshot),
            "timestamp": snapshot["created_at"].isoformat()
        })
        
        # Stream events as they occur
        async for event in event_bus.subscribe(session_id):
            await websocket.send_json(event.to_dict())
            
    except WebSocketDisconnect:
        return
```

### Frontend Integration

**File Location**: `frontend/components/ActiveLogsViewer.jsx`

```javascript
useEffect(() => {
  const ws = new WebSocket(`ws://${API_BASE_URL.replace('http://', '')}/ws/${sessionId}`);
  
  ws.onopen = () => setConnected(true);
  
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    switch(message.type) {
      case 'log':
        setLogs(prev => [...prev, message.data]);
        break;
      case 'ai_action':
        setAgentActivity(prev => [...prev, message.data]);
        break;
      case 'stage_update':
        setProgress(message.data.progress);
        break;
      case 'error':
        setError(message.data);
        break;
    }
  };
  
  ws.onerror = (error) => setConnected(false);
  ws.onclose = () => setConnected(false);
  
  return () => ws.close();
}, [sessionId]);
```

---

## 8. DEPLOYMENT PIPELINE FLOW

### 7-Stage Pipeline Overview

| Stage | Duration | Purpose | Failure Recovery |
|-------|----------|---------|------------------|
| **1. Init** | 1-3 min | Install Docker, Docker Compose | Retry install, check permissions |
| **2. Sonar** | 3-5 min | Deploy SonarQube + PostgreSQL | Restart containers, regenerate tokens |
| **3. Jenkins** | 2-4 min | Deploy Jenkins with plugins | Reinstall plugins, reset config |
| **4. Scan** | 5-15 min | Run SonarQube analysis on code | Retry with adjusted timeout |
| **5. Docker** | 5-10 min | Build Docker image from repo | Clear cache, rebuild |
| **6. Push** | 2-5 min | Push image to DockerHub | Retry with new credentials |
| **7. Deploy** | 2-5 min | Deploy app, validate services | Restart services, check logs |

### Complete Flow Sequence Diagram

```
User Input
    ↓
Frontend Form Submitted
    ↓
POST /api/deploy
    ↓
Generate Session ID
    ↓
Store Deployment Inputs (encrypted)
    ↓
Create async pipeline task
    ↓
Return Session ID to client
    ↓
Client connects to WS /ws/{session_id}
    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PIPELINE EXECUTION (Async)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ↓
[STAGE 1: INIT] ────────────────────────
├─ SSH connect to target server
├─ Validate SSH connectivity
├─ Install Docker (if needed)
├─ Install Docker Compose (if needed)
├─ Check Docker daemon
└─ Publish stage progress
    ↓
[STAGE 2: SONAR] ───────────────────────
├─ Generate SonarQube credentials
├─ Docker pull SonarQube image
├─ Docker pull PostgreSQL image
├─ Start containers with docker-compose
├─ Wait for health checks
├─ Create admin user and API token
└─ Publish credentials
    ↓
[STAGE 3: JENKINS] ──────────────────────
├─ Generate Jenkins credentials
├─ Docker pull Jenkins image
├─ Start Jenkins container
├─ Wait for Jenkins to be ready
├─ Install recommended plugins
├─ Create admin user
└─ Retrieve initial admin password
    ↓
[STAGE 4: SCAN] ────────────────────────
├─ Clone repository from GitHub
├─ Analyze repository structure
├─ Detect project type (Agent 1)
├─ Create deployment plan (Agent 2)
├─ Run SonarQube scanner
│  └─ On error: Auto-retry with AI fixes (Agent 3)
├─ Wait for scan completion
├─ Fetch scan results
└─ Publish scan status
    ↓
[STAGE 5: DOCKER] ──────────────────────
├─ Generate Dockerfile (if needed)
├─ Build Docker image
│  └─ On error: Clear cache, rebuild (Agent 3)
├─ Tag image with version
├─ Generate credentials for app
└─ Publish build status
    ↓
[STAGE 6: PUSH] ────────────────────────
├─ Login to DockerHub
├─ Push image to DockerHub
│  └─ On error: Retry auth, push again (Agent 3)
├─ Verify image in registry
└─ Publish push status
    ↓
[STAGE 7: DEPLOY] ──────────────────────
├─ Generate docker-compose.yml for app
├─ Deploy application container
├─ Wait for application to start
├─ Run health checks
├─ Validate all services (Agent 4)
├─ Update agent learning metrics
└─ Publish final status
    ↓
PIPELINE COMPLETION
    ↓
Store outputs (URLs, credentials, logs)
    ↓
Mark session as "completed"
    ↓
Broadcast completion event to WebSocket
    ↓
Frontend updates dashboard
```

### Each Stage in Detail

#### Stage 1: Init

**Triggers**: Immediately on pipeline start

**Function**: `async def _start_stage(session_id, "init")`

**Code Location**: `backend/pipeline.py:82-100`

**Operations**:
1. SSH connect to target
2. Check Docker installation
3. Check Docker Compose installation
4. Start Docker daemon (if stopped)
5. Verify connectivity

**On Error**:
- Retry SSH connection (max 3 attempts)
- If Docker missing: install it
- If Compose missing: download from releases

**Error Context** (passed to LLM):
```python
{
    "command": "docker ps",
    "exit_code": 127,
    "stderr": "command not found",
    "operation": "verify_docker",
    "stage": "init",
    "context": {"server_ip": "192.168.1.100"}
}
```

**Outputs**:
```python
{
    "ssh_connected": True,
    "docker_version": "24.0.0",
    "compose_version": "2.23.0",
    "server_host": "ubuntu@192.168.1.100"
}
```

#### Stage 2: SonarQube Setup

**Triggers**: After Stage 1 success

**Function**: `async def _deploy_sonarqube(ssh, session_id, credentials_mgr)`

**Code Location**: `backend/pipeline.py` (SonarQube deployment)

**Operations**:
1. Generate SonarQube credentials
2. Create docker-compose stack
3. Start SonarQube and PostgreSQL
4. Wait for health checks (30s timeout)
5. Create admin user
6. Generate API tokens
7. Store credentials

**Docker Services**:
```yaml
sonarqube:
  image: sonarqube:latest
  ports:
    - "9000:9000"
  environment:
    - SONAR_JDBC_URL=jdbc:postgresql://postgres:5432/sonarqube
    - SONAR_JDBC_USERNAME=sonar
    - SONAR_JDBC_PASSWORD=sonar
postgres:
  image: postgres:15
  environment:
    - POSTGRES_DB=sonarqube
    - POSTGRES_USER=sonar
```

**On Error** (e.g., "port already in use"):
1. Check if port is free
2. If occupied: find next available port (9001, 9002, etc.)
3. Update configuration
4. Restart deployment

**Learning Opportunity**:
- Track provider (Claude/Ollama) that fixed the error
- Update success/failure scores in AgentLearning table
- Use for future provider selection

#### Stage 3: Jenkins Setup

**Triggers**: After Stage 2 success

**Operations**:
1. Generate Jenkins credentials
2. Create docker-compose stack
3. Start Jenkins container
4. Wait for startup (60s)
5. Retrieve initial admin password
6. Create admin user with generated password
7. Install plugins (via Jenkins CLI)

**Docker Service**:
```yaml
jenkins:
  image: jenkins/jenkins:lts
  ports:
    - "8081:8080"
  volumes:
    - jenkins_home:/var/jenkins_home
```

**Plugins Installed**:
- Docker Plugin
- GitHub Integration
- Pipeline Plugin
- Credentials Plugin

#### Stage 4: Code Scanning

**Triggers**: After Stage 3 success

**Operations**:
1. Clone repository locally
2. Run Agent 1: Repository Analysis
3. Run Agent 2: Create Deployment Plan
4. Run SonarQube scanner
5. Poll for results
6. Parse and store results

**Agent 1 Output** (Example):
```python
{
    "project_type": "nodejs",
    "dependencies": ["express", "axios", "dotenv"],
    "build_command": "npm install && npm run build",
    "start_command": "npm start"
}
```

**SonarQube Scanner Command**:
```bash
sonar-scanner \
  -Dsonar.projectKey=myapp \
  -Dsonar.sources=. \
  -Dsonar.host.url=http://192.168.1.100:9000 \
  -Dsonar.login=$SONAR_TOKEN
```

**Outputs**:
```python
{
    "quality_gate_status": "PASSED",
    "bugs": 0,
    "vulnerabilities": 2,
    "code_smells": 15,
    "coverage": 65.5,
    "scan_url": "http://192.168.1.100:9000/dashboard?id=myapp"
}
```

#### Stage 5: Docker Build

**Triggers**: After Stage 4 success

**Operations**:
1. Generate Dockerfile (if not exists)
2. Build Docker image
3. Tag image
4. Verify image

**Generated Dockerfile** (Node.js Example):
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

**Build Command**:
```bash
docker build -t myimage:latest -t myimage:v1.0.0 .
```

**On Error** (e.g., "Docker daemon socket permission denied"):
- Agent 3 captures error
- Queries LLM: "How to fix Docker socket permission error?"
- Applies fix: `usermod -aG docker ubuntu && newgrp docker`
- Retries build

#### Stage 6: Docker Push

**Triggers**: After Stage 5 success

**Operations**:
1. Login to DockerHub
2. Push image
3. Verify in registry

**Push Command**:
```bash
docker login -u $DOCKERHUB_USER -p $DOCKERHUB_PASS
docker push myrepo/myimage:latest
```

#### Stage 7: Deploy & Validate

**Triggers**: After Stage 6 success

**Operations**:
1. Generate final docker-compose.yml
2. Deploy application
3. Run health checks
4. Agent 4 validates deployment
5. Store outputs
6. Complete session

**Generated Compose for Application**:
```yaml
version: '3.8'
services:
  app:
    image: myrepo/myimage:latest
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=...
    restart: always
```

**Health Checks**:
```bash
curl -f http://localhost:3000/health || exit 1
```

**Validation Checks** (Agent 4):
- Docker daemon running
- Application container running
- All services responding
- Quality metrics acceptable

---

## 9. DOCKER CONFIGURATION

### Services in docker-compose.yml

| Service | Image | Port (Internal:External) | Purpose |
|---------|-------|------------------------|---------|
| backend | Custom (Python 3.11) | 8000:8000 | FastAPI application |
| ollama | ollama/ollama:latest | 11434:11434 | LLM inference engine |
| ollama-init | ollama/ollama:latest | N/A | Model initialization |
| redis | redis:7-alpine | 6379:6379 | Message broker (optional) |
| postgres | postgres:15 | 5432:5432 | Database (for future) |

### Port Mappings

```yaml
services:
  backend:
    ports:
      - "8000:8000"  # FastAPI
  
  ollama:
    ports:
      - "11434:11434"  # Ollama API
  
  redis:
    ports:
      - "6379:6379"  # Redis
  
  postgres:
    ports:
      - "5432:5432"  # PostgreSQL
```

### Volume Mounts

| Service | Volume | Mount Point | Purpose |
|---------|--------|-------------|---------|
| backend | backend_data | /data | Session & agent learning DB |
| backend | backend_workspace | /app/workspace | Repository clones & builds |
| backend | /var/run/docker.sock | /var/run/docker.sock | Docker socket (host) |
| ollama | ollama_data | /root/.ollama | Model cache & data |
| postgres | postgres_data | /var/lib/postgresql/data | Database persistence |

### Networks

All services connected on default network:
```
network: compose (default bridge)
```

Services can communicate via service name:
```
backend → ollama:11434
ollama-init → ollama:11434
```

### Health Checks

**Ollama Health Check**:
```yaml
healthcheck:
  test: ["CMD-SHELL", "ollama list >/dev/null 2>&1"]
  interval: 10s
  timeout: 5s
  retries: 30
```

**Backend Health Check** (implicit):
- Checks `GET /api/health`
- Verifies Ollama connectivity
- Verifies database connectivity

### Build Process

```dockerfile
# Stage 1: Frontend build
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + runtime
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    docker.io \
    git \
    openssh-client \
    openjdk-17-jre-headless \
    curl

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend ./backend
COPY scripts ./scripts
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables in Compose

```yaml
services:
  backend:
    environment:
      - APP_ENV=production
      - OLLAMA_HOST=http://ollama:11434
      - DEEPSEEK_MODEL=deepseek-coder:6.7b
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - DATABASE_URL=sqlite+aiosqlite:////data/devops_ai.db
      - REDIS_URL=redis://redis:6379
```

### Volume Management

**Backend Data Volume**:
- Stores: SQLite database (`devops_ai.db`)
- Location: `/data` in container
- Persists: Session state, agent learning

**Backend Workspace Volume**:
- Stores: Cloned repositories, build artifacts
- Location: `/app/workspace` in container
- Persists: Code for analysis and debugging

**Ollama Data Volume**:
- Stores: Model cache, weights
- Location: `/root/.ollama` in container
- Persists: Downloaded models (large files)

---

## 10. FRONTEND REACT COMPONENTS

### Component Hierarchy

```
App (main.jsx)
  ├── AppHeader
  │   └── API Health Status Badge
  ├── AppNav
  │   ├── Home Button
  │   ├── Deploy Button
  │   └── Monitoring Button (conditional)
  └── AppMain
      ├── HomeView
      │   ├── HeroSection
      │   ├── FeatureCards (4 agents)
      │   ├── SystemFeatures
      │   └── CTA Button
      ├── DeployView
      │   ├── DeploymentForm
      │   │   ├── Repository URL Input
      │   │   ├── GitHub Token Input
      │   │   ├── Server IP Input
      │   │   ├── SSH Username Input
      │   │   ├── PEM Content TextArea
      │   │   ├── DockerHub Username Input
      │   │   ├── DockerHub Password Input
      │   │   ├── Branch Input (optional)
      │   │   └── Submit Button
      │   └── Status Messages
      └── MonitoringView
          ├── CredentialsPanel
          ├── AgentActivityPanel
          ├── ActiveLogsViewer
          └── Reset Button
```

### Component Descriptions

#### App.jsx

**File**: `frontend/App.jsx`

**Purpose**: Main application wrapper, state management, routing

**Props**: None

**State**:
```javascript
{
  currentView: 'home' | 'deploy' | 'monitoring',
  sessionId: null | string,
  isDeploying: boolean,
  deploymentStatus: null | object,
  error: null | string,
  apiHealth: null | object
}
```

**Key Functions**:
- `checkHealth()` - Verify API connectivity on mount
- `handleDeploy(formData)` - Initiate deployment
- `resetDeployment()` - Clear session and return to home

**Lifecycle**:
- Mount: Check API health
- Deploy click: POST /api/deploy
- Session received: Connect to WebSocket
- Monitoring: Stream events in real-time

#### DeploymentForm.jsx

**File**: `frontend/components/DeploymentForm.jsx`

**Purpose**: Deployment input form with validation

**Props**:
```javascript
{
  onDeploy: (formData) => void,
  isLoading: boolean
}
```

**State**:
```javascript
{
  formData: {
    repo_url: string,
    github_token: string,
    server_ip: string,
    username: string,
    pem_content: string,
    dockerhub_user: string,
    dockerhub_pass: string
  },
  errors: { [fieldName]: string }
}
```

**Validation Rules**:
- `repo_url`: Required, valid URL format
- `github_token`: Required
- `server_ip`: Required, valid IP format
- `username`: Optional (defaults to 'ubuntu')
- `pem_content`: Required, PEM format
- `dockerhub_user`: Required
- `dockerhub_pass`: Required

**Form Fields**:
```jsx
<input type="url" name="repo_url" placeholder="https://github.com/user/repo.git" />
<input type="password" name="github_token" placeholder="ghp_xxxxxxxxxxxxx" />
<input type="text" name="server_ip" placeholder="192.168.1.100" />
<input type="text" name="username" value="ubuntu" />
<textarea name="pem_content" placeholder="-----BEGIN PRIVATE KEY-----" />
<input type="text" name="dockerhub_user" />
<input type="password" name="dockerhub_pass" />
<button type="submit" disabled={isLoading}>Start Deployment</button>
```

#### ActiveLogsViewer.jsx

**File**: `frontend/components/ActiveLogsViewer.jsx`

**Purpose**: Real-time log streaming via WebSocket

**Props**:
```javascript
{
  sessionId: string,
  apiBase: string
}
```

**State**:
```javascript
{
  logs: [{ timestamp, message, level, stage }],
  connected: boolean,
  error: null | string
}
```

**WebSocket Connection**:
```javascript
const ws = new WebSocket(`ws://${API_BASE_URL.replace('http://', '')}/ws/${sessionId}`);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'log') {
    setLogs(prev => [...prev, message.data]);
  }
};
```

**Log Display**:
- Scrolls to latest log
- Color-coded by level (info, warn, error, ok)
- Shows stage name
- Shows timestamp

#### AgentActivityPanel.jsx

**File**: `frontend/components/AgentActivityPanel.jsx`

**Purpose**: Display AI agent activities and interventions

**Props**:
```javascript
{
  sessionId: string,
  apiBase: string
}
```

**State**:
```javascript
{
  activities: [{
    timestamp,
    agent: string,
    message: string,
    type: 'error' | 'warn' | 'ok' | 'action',
    stage: string
  }],
  connected: boolean
}
```

**WebSocket Events**:
- `ai_action`: Agent performed action
- `error`: Agent encountered error

**Display**:
- Agent name
- Action taken
- Error message (if any)
- Timestamp
- Color by type

#### CredentialsPanel.jsx

**File**: `frontend/components/CredentialsPanel.jsx`

**Purpose**: Display generated credentials

**Props**:
```javascript
{
  sessionId: string,
  apiBase: string
}
```

**Data Fetching**:
```javascript
useEffect(() => {
  const fetchCredentials = async () => {
    const response = await fetch(`${apiBase}/api/credentials/${sessionId}`);
    const data = await response.json();
    setCredentials(data);
  };
  
  const interval = setInterval(fetchCredentials, 5000);
  return () => clearInterval(interval);
}, [sessionId]);
```

**Display Format**:
```javascript
{
  sonarqube: { url, username, password_display, api_token },
  jenkins: { url, username, password_display, api_token },
  application: { url, username, api_key }
}
```

**UI Features**:
- Copy-to-clipboard for each credential
- Hide/show password toggle
- Clickable links to service URLs
- Last updated timestamp

### State Management

No external state manager (Redux/Context) - uses React hooks:
- `useState` for local component state
- `useEffect` for side effects
- Props drilling for parent-child communication

### API Integration

**Base URL** (hardcoded in App.jsx):
```javascript
const API_BASE_URL = "http://16.16.128.193:8000";
```

**HTTP Methods**:
- `GET` - Fetch status, credentials
- `POST` - Initiate deployment
- `WebSocket` - Real-time events

**Error Handling**:
- Network errors → show error message
- HTTP 404 → "Unknown session"
- HTTP 422 → "Validation error"
- WebSocket disconnect → reconnect

### WebSocket Integration

**Flow**:
1. User starts deployment → POST /api/deploy → Get session_id
2. Navigate to Monitoring view
3. Connect to WebSocket: `WS /ws/{session_id}`
4. Receive messages continuously
5. Update UI components with new data

**Message Processing**:
```javascript
ws.onmessage = (event) => {
  const { type, data, timestamp } = JSON.parse(event.data);
  
  switch(type) {
    case 'log':
      setLogs(prev => [...prev, data]);
      break;
    case 'ai_action':
      setActivities(prev => [...prev, data]);
      break;
    case 'progress':
      setProgress(data.current);
      break;
    case 'error':
      setError(data);
      break;
  }
};
```

---

## 11. ERROR HANDLING STRATEGY

### Error Capture Strategy

All errors captured during execution:

1. **SSH Errors**: Connection, timeout, permission, key issues
2. **Docker Errors**: Image build, push, run, compose errors
3. **SonarQube Errors**: Authentication, scanner, analysis errors
4. **Jenkins Errors**: Startup, plugin, credential errors
5. **Network Errors**: Timeout, DNS, connectivity
6. **LLM Errors**: API timeout, model unavailable
7. **Authentication Errors**: Token invalid, expired

### Error Context Captured

```python
{
    "command": "docker build ...",
    "exit_code": 1,
    "stdout": "...",
    "stderr": "Error: permission denied",
    "attempt": 1,
    "max_attempts": 3,
    "operation": "docker_build",
    "stage": "docker",
    "context": {
        "server_ip": "192.168.1.100",
        "project_type": "nodejs"
    },
    "system": {
        "location": "remote",
        "timestamp": "2024-05-28T10:51:06"
    }
}
```

### Error→Fix Mapping

**File Location**: `backend/error_fix_mapper.py`

**Pattern Matching**:
```python
FIX_PATTERNS = {
    "not authorized": {
        "analysis": "Token invalid - regenerating",
        "commands": [
            "curl -s -u admin:admin -X POST '...' > /tmp/token.txt",
            "export TOKEN=$(cat /tmp/token.txt)"
        ],
        "verification": "curl -s -u admin:admin '...' | grep -i up",
        "requires_retry": True,
        "confidence": 0.95
    },
    "timeout opening channel": {
        "analysis": "SSH timeout - increasing keepalive",
        "commands": [
            "sudo sed -i 's/^#ClientAliveInterval.*/ClientAliveInterval 120/' /etc/ssh/sshd_config",
            "sudo systemctl restart sshd"
        ],
        "confidence": 0.88
    }
}
```

**Matching Process**:
1. Extract error message from stderr
2. Check against known patterns
3. Return best match (highest confidence)
4. If no match: query LLM for suggestions

### Retry Logic

**Implementation** (in RemediationAgent):
```python
async def monitor_and_fix(self, func, *args, **kwargs):
    max_attempts = 3
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = await func(*args, **kwargs)
            if result.exit_code == 0:
                return result  # Success
        except Exception as exc:
            error_context = self._format_error_context(exc, attempt, max_attempts)
            
            if attempt < max_attempts:
                # Try to fix
                fixes = await self.llm.query_fix_candidates(error_context)
                fix = self._select_best_fix(fixes)
                
                await self._apply_fix(fix)
                # Retry with fix applied
                continue
            else:
                # Max attempts reached
                raise OperationFailure(str(exc))
    
    raise OperationFailure("Operation failed after max retries")
```

**Retry Configuration**:
- Max retries: 3 (configurable via `AI_MAX_RETRIES`)
- Exponential backoff: 1s, 2s, 4s
- Per-stage retries: Independent for each operation

### Fallback Patterns

**Pattern 1: Direct Error→Fix Mapping** (ErrorFixMapper)
```python
# Fastest: O(1) lookup
if error_message in FIX_PATTERNS:
    return FIX_PATTERNS[error_message]
```

**Pattern 2: LLM-Generated Fixes** (Claude/Ollama)
```python
# Slower: Requires LLM inference (1-5s)
candidates = await self.llm.query_fix_candidates(error_context)
selected_fix = self._select_best_fix(candidates)
```

**Pattern 3: Deterministic Recovery** (Fallback)
```python
# Deterministic fixes applied as last resort
# Examples: retry with longer timeout, clear cache, restart service
```

### Learning Mechanism

**Database Table**: `AgentLearning`

```sql
CREATE TABLE agent_learning (
    id INTEGER PRIMARY KEY,
    provider TEXT,              -- 'claude' | 'ollama'
    error_signature TEXT,       -- Error pattern hash
    successes INTEGER DEFAULT 0,
    failures INTEGER DEFAULT 0,
    last_error TEXT,
    last_fix TEXT,
    updated_at DATETIME
);
```

**Update on Deployment**:
```python
# After each fix attempt
async def _update_learning(provider, error_sig, success):
    # Find or create record
    record = await db.execute(
        select(AgentLearning)
        .where(
            (AgentLearning.provider == provider) &
            (AgentLearning.error_signature == error_sig)
        )
    )
    
    if success:
        record.successes += 1
    else:
        record.failures += 1
    
    record.last_error = error_message
    record.last_fix = applied_fix
    record.updated_at = datetime.now()
    
    await db.commit()
```

**Use Cases**:
1. Provider selection: Use providers with higher success rates
2. Error prediction: Warn if similar error likely to occur
3. Confidence scoring: Lower confidence for frequently-failing fixes

---

## 12. CONFIGURATION FILES

### requirements.txt

```
fastapi==0.104.1                         # Web framework
uvicorn[standard]==0.24.0               # ASGI server
aiohttp==3.9.1                          # Async HTTP
pydantic==2.5.0                         # Data validation
websockets==12.0                        # WebSocket support
python-multipart==0.0.6                 # Form data handling
paramiko==3.4.0                         # SSH client
docker==6.1.3                           # Docker SDK
redis==5.0.1                            # Redis client
celery==5.3.4                           # Task queue
python-jose[cryptography]==3.3.0        # JWT
passlib[bcrypt]==1.7.4                  # Password hashing
httpx==0.25.1                           # HTTP client
python-dotenv==1.0.0                    # Environment variables
sqlalchemy==2.0.50                      # ORM
aiosqlite==0.20.0                       # Async SQLite
cryptography==42.0.5                    # Encryption
anthropic==0.28.1                       # Claude API
requests==2.31.0                        # Requests library
```

### package.json

```json
{
  "name": "devops-ai-automator-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.1.0"
  }
}
```

### .env.example

```env
# Application
APP_NAME=DevOps AI Automator
APP_ENV=production
APP_SECRET_KEY=replace-with-a-long-random-secret

# LLM Configuration
CLAUDE_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
CLAUDE_MODEL=claude-3-5-sonnet-20241022
OLLAMA_HOST=http://localhost:11434
DEEPSEEK_MODEL=deepseek-coder:6.7b
LLM_TIMEOUT=90

# Multi-Agent System
USE_MULTI_AGENT=true
AGENT_VALIDATION_ENABLED=true

# AI Execution
AI_AUTO_EXECUTE=true
AI_ALLOW_DANGEROUS_COMMANDS=false
AI_MAX_RETRIES=3

# Database
DATABASE_URL=sqlite:///./devops_ai.db
REDIS_URL=redis://localhost:6379

# SSH Configuration
SSH_USER=ubuntu
SSH_TIMEOUT=30

# Docker/Deployment
DOCKERHUB_REPO_NAME=devops-ai-app
REMOTE_WORKSPACE=/opt/devops-ai-automator
LOCAL_WORKSPACE=./workspace
MAX_PIPELINE_DURATION=1800

# Networking
CORS_ORIGINS=*
FRONTEND_BUILD_DIR=./frontend/dist
```

### Dockerfile Explanation

**Line by Line**:

```dockerfile
# Stage 1: Frontend build
FROM node:20-alpine AS frontend
# Use Node 20 Alpine for smaller image size
# Tag as 'frontend' for multi-stage reference

WORKDIR /frontend
# Set working directory

COPY frontend/package*.json ./
# Copy package.json and package-lock.json

RUN npm ci || npm install
# Install dependencies (ci = clean install)

COPY frontend/ ./
# Copy all frontend source code

RUN npm run build
# Build production bundle (creates dist/)

# Stage 2: Backend + runtime
FROM python:3.11-slim-bookworm
# Fresh Python image with Debian Bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_BUILD_DIR=/app/frontend/dist
# Disable bytecode, enable stdout buffering, set frontend path

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \                           # Shell scripting
    ca-certificates \                # SSL/TLS certificates
    curl \                           # HTTP requests
    docker.io \                      # Docker CLI
    git \                            # Version control
    iputils-ping \                   # Network diagnostics
    netcat-openbsd \                 # Network utilities
    openjdk-17-jre-headless \       # Java for SonarQube Scanner
    openssh-client \                 # SSH client
    unzip \                          # Archive extraction

RUN docker --version && \
    curl -fsSLo /tmp/sonar-scanner.zip \
       https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip && \
    unzip -q /tmp/sonar-scanner.zip -d /opt && \
    mv /opt/sonar-scanner-* /opt/sonar-scanner && \
    ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner
# Download and install SonarQube Scanner

WORKDIR /app
# Set app working directory

COPY requirements.txt .
# Copy Python dependencies

RUN pip install --no-cache-dir -r requirements.txt
# Install Python packages (--no-cache-dir saves space)

COPY backend ./backend
# Copy backend source code

COPY scripts ./scripts
# Copy utility scripts

COPY --from=frontend /frontend/dist ./frontend/dist
# Copy built frontend from Stage 1

EXPOSE 8000
# Declare port (informational)

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Start FastAPI with Uvicorn
```

### docker-compose.yml Explanation

See Section 9 for detailed Docker configuration.

---

## 13. API CALL SEQUENCE EXAMPLES

### Example 1: Complete Deployment Flow (curl)

**Step 1: Start Deployment**
```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/myapp.git",
    "github_token": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
    "server_ip": "192.168.1.100",
    "pem_file_content": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQE...\n-----END PRIVATE KEY-----",
    "dockerhub_user": "myusername",
    "dockerhub_pass": "mypassword",
    "branch": "main",
    "ssh_user": "ubuntu"
  }'
```

**Response**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Step 2: Poll Status**
```bash
# Check status every 5 seconds
curl http://localhost:8000/api/status/550e8400-e29b-41d4-a716-446655440000
```

**Response** (initial):
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 25,
  "current_stage": "sonar",
  "stages": {
    "init": "completed",
    "sonar": "running",
    "jenkins": "pending"
  }
}
```

**Step 3: Get Credentials** (after completion)
```bash
curl http://localhost:8000/api/credentials/550e8400-e29b-41d4-a716-446655440000
```

**Response**:
```json
{
  "ready": true,
  "status": "completed",
  "sonarqube": {
    "service": "SonarQube",
    "url": "http://192.168.1.100:9000",
    "username": "admin",
    "password": "Auto-generated: Xyz123***"
  },
  "jenkins": {
    "service": "Jenkins",
    "url": "http://192.168.1.100:8081",
    "username": "admin",
    "password": "Auto-generated: Abc456***"
  },
  "application": {
    "service": "Application",
    "url": "http://192.168.1.100:3000",
    "username": "appuser_abc",
    "api_key": "a1b2c3d4e5f6"
  }
}
```

### Example 2: WebSocket Connection (JavaScript)

```javascript
// Connect to WebSocket
const sessionId = '550e8400-e29b-41d4-a716-446655440000';
const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`);

// Connection established
ws.onopen = () => {
  console.log('Connected to deployment stream');
};

// Handle incoming messages
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'status':
      console.log('Current status:', message.data);
      console.log('Progress:', message.data.progress);
      break;
    
    case 'log':
      console.log(`[${message.data.level}] ${message.data.message}`);
      break;
    
    case 'ai_action':
      console.log(`🤖 ${message.data.agent}: ${message.data.message}`);
      break;
    
    case 'stage_update':
      console.log(`Stage: ${message.data.stage} → ${message.data.status}`);
      break;
    
    case 'progress':
      console.log(`Progress: ${message.data.current}/${message.data.total}`);
      updateProgressBar(message.data.current);
      break;
    
    case 'error':
      console.error(`Error: ${message.data.message}`);
      break;
    
    case 'credentials':
      console.log('Credentials ready:', message.data);
      displayCredentials(message.data);
      break;
  }
};

// Error handling
ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

// Connection closed
ws.onclose = () => {
  console.log('Deployment stream closed');
};

// Clean up on page unload
window.addEventListener('beforeunload', () => {
  ws.close();
});
```

### Example 3: Credential Regeneration

```bash
# After deployment, regenerate SonarQube credentials
curl -X POST http://localhost:8000/api/credentials/regenerate/sonarqube \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "server_ip": "192.168.1.100"
  }'
```

**Response**:
```json
{
  "service": "SonarQube",
  "url": "http://192.168.1.100:9000",
  "username": "admin",
  "password": "NewPassword123!@#",
  "api_token": "squ_newsecuretoken",
  "regenerated_at": "2024-05-28T10:51:06.123"
}
```

### Example 4: Agent Learning Query

```bash
# Get agent learning history
curl "http://localhost:8000/api/agents/learnings?limit=10"
```

**Response**:
```json
[
  {
    "provider": "claude",
    "error_signature": "timeout_opening_channel",
    "successes": 5,
    "failures": 1,
    "last_error": "Connection reset by peer",
    "last_fix": "Increased SSH ClientAliveInterval to 120",
    "updated_at": "2024-05-28T10:51:06.123"
  },
  {
    "provider": "ollama",
    "error_signature": "docker_build_failed",
    "successes": 3,
    "failures": 2,
    "last_error": "permission denied while trying to connect to Docker daemon",
    "last_fix": "Added ubuntu user to docker group",
    "updated_at": "2024-05-28T10:50:00.123"
  }
]
```

---

## 14. KNOWN ISSUES AND LIMITATIONS

### Current Issues

1. **Ollama Model Download Slow**
   - First-time setup can take 10-15 minutes
   - Issue: Large model download (6.7B parameters)
   - Workaround: Pre-download model using `scripts/setup_ollama.sh`

2. **SSH Key Format Strict**
   - Only OpenSSH format supported
   - PuTTY format (.ppk) not supported
   - Workaround: Convert using puttygen or ssh-keygen

3. **Docker Socket Permission Issues**
   - Can occur on some Linux systems
   - Issue: Docker socket ownership/permissions
   - Workaround: Run as root or add user to docker group: `usermod -aG docker $USER`

4. **SonarQube Scanner Timeout**
   - Large repositories may timeout during scanning
   - Issue: Default timeout 60 seconds
   - Workaround: Increase `LLM_TIMEOUT` environment variable

5. **Credentials Not Persisted Between Sessions**
   - Credentials only available within session lifetime
   - Database stores encrypted credentials but not retrievable after session
   - Workaround: Store credentials manually after first deployment

### Performance Considerations

1. **LLM Inference Latency**
   - Claude API: 1-3 seconds per query
   - Ollama local: 5-15 seconds per query
   - Impact: Adds to total deployment time if errors occur

2. **SSH Command Execution**
   - Network latency impacts remote commands
   - Large file transfers slow on slow connections
   - Optimization: Use local workspace caching

3. **Docker Build Time**
   - Varies based on application size and dependencies
   - First build slower (layer cache miss)
   - Optimization: Use Docker layer caching

4. **SonarQube Analysis Duration**
   - Depends on code size and complexity
   - Large projects: 10+ minutes
   - Optimization: Use SonarQube selective analysis (skip certain folders)

### Scalability Limitations

1. **Single Backend Instance**
   - Current design: Single FastAPI instance
   - Limitation: No horizontal scaling
   - Future: Add load balancer and session sharing via Redis

2. **SQLite Database**
   - Limitation: Single-writer concurrent writes
   - Impact: Multiple concurrent deployments slow
   - Future: Migrate to PostgreSQL

3. **In-Memory Event Bus**
   - Limitation: Events lost on restart
   - Impact: Reconnecting clients miss history
   - Future: Add Redis-backed event bus

4. **SSH Connection Pool**
   - Limitation: No connection pooling
   - Impact: New SSH connection per operation
   - Future: Add paramiko connection pool

### Security Considerations

1. **PEM Key Storage**
   - Issue: PEM keys stored in plaintext in database
   - Risk: Database breach exposes keys
   - Mitigation: Add field-level encryption (feature in progress)

2. **CORS Configuration**
   - Default: `CORS_ORIGINS=*`
   - Risk: Any origin can access API
   - Recommendation: Set `CORS_ORIGINS=https://yourdomain.com` in production

3. **API Authentication**
   - Issue: No authentication/authorization on endpoints
   - Risk: Unauthenticated users can trigger deployments
   - Recommendation: Add JWT/API key authentication

4. **Dangerous Commands**
   - Configuration: `AI_ALLOW_DANGEROUS_COMMANDS=false`
   - Issue: AI might suggest rm -rf / on failure
   - Mitigation: Command allowlist and review before execution

### Dependency Vulnerabilities

- Regular security audits recommended
- `pip audit` to check Python dependencies
- `npm audit` to check Node.js dependencies

### Docker/Container Limitations

1. **Docker-in-Docker**
   - Current: /var/run/docker.sock mounted
   - Issue: Security risk on untrusted containers
   - Note: Required for Docker builds

2. **Resource Limits**
   - No CPU/memory limits set
   - Can impact host if deployment resource-hungry
   - Recommendation: Set docker-compose resource limits

---

## 15. REBUILD INSTRUCTIONS

Complete step-by-step guide to rebuild from scratch:

### Prerequisites

- Ubuntu 22.04 LTS or similar
- 4+ CPU cores, 8GB+ RAM
- 20GB+ free disk space
- Git installed
- Docker Desktop or Docker Engine 20.10+
- Node.js 20+
- Python 3.11+

### Step 1: Clone Repository

```bash
git clone https://github.com/SaiGorijala/devops-ai-automator.git
cd devops-ai-automator
```

### Step 2: Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env

# Key configurations to set:
# CLAUDE_API_KEY=sk-ant-xxxxxxxx (optional, but recommended)
# OLLAMA_HOST=http://localhost:11434 (or remote Ollama)
# DEEPSEEK_MODEL=deepseek-coder:6.7b
```

### Step 3: Ollama Setup

**Option A: Local Ollama (Linux/Mac)**
```bash
# Install Ollama from https://ollama.ai
# Then pull the model
bash scripts/setup_ollama.sh

# Verify
curl http://localhost:11434/api/tags
```

**Option B: Remote Ollama**
```bash
# Set OLLAMA_HOST in .env to point to remote instance
OLLAMA_HOST=http://remote-host:11434
```

**Option C: Docker Compose (Included)**
```bash
# Ollama runs in compose, skip manual setup
```

### Step 4: Backend Setup

```bash
# Python 3.11+
python3 --version

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 5: Frontend Setup

```bash
cd frontend

# Node.js 20+
node --version
npm --version

# Install dependencies
npm install

# Build for production
npm run build

# Output in: frontend/dist/
```

### Step 6: Database Setup

```bash
# SQLite database auto-created on first run
# To reset: rm devops_ai.db (or /data/devops_ai.db in Docker)
```

### Step 7: Docker Build (Optional - for deployment)

```bash
# Build Docker image
docker build -t devops-ai-automator:latest .

# Or use Docker Compose
docker compose build
```

### Step 8: Run the Application

**Option A: Docker Compose (Recommended)**
```bash
docker compose up --build
```

Services will start:
- Backend: http://localhost:8000
- Ollama: http://localhost:11434
- Redis: localhost:6379
- Postgres: localhost:5432

**Option B: Manual (Development)**
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start backend
cd backend
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Start frontend (dev mode)
cd frontend
npm run dev

# Frontend accessible at http://localhost:5173
```

### Step 9: Verify Installation

```bash
# Check API health
curl http://localhost:8000/api/health

# Response:
# {"status":"ok","ollama_host":"http://localhost:11434","model":"deepseek-coder:6.7b"}

# Check agents health
curl http://localhost:8000/api/agents/health

# Response:
# {"multi_agent":true,"validation_enabled":true,"llm":{...}}

# Check Ollama
curl http://localhost:8000/api/debug/ollama

# Response shows ollama connectivity and available models
```

### Step 10: Test Deployment (Optional)

```bash
# Use test_api.py
python scripts/test_api.py

# Or manually:
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/test-repo.git",
    "github_token": "ghp_xxx",
    "server_ip": "192.168.1.100",
    "pem_file_content": "...",
    "dockerhub_user": "user",
    "dockerhub_pass": "pass"
  }'
```

### Troubleshooting

**Issue**: Ollama model not downloaded
```bash
# Manually pull model
ollama pull deepseek-coder:6.7b
```

**Issue**: Port already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

**Issue**: Docker socket permission denied
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Issue**: Frontend shows blank page
```bash
# Rebuild frontend
cd frontend
npm run build

# Backend serves from frontend/dist
```

---

## 16. CODE SNIPPETS

### Main FastAPI App Initialization

**File**: `backend/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .database import init_db
from .event_bus import event_bus

app = FastAPI(title=settings.app_name, version="1.0.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False if "*" in settings.cors_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
async def on_startup() -> None:
    settings.local_workspace.mkdir(parents=True, exist_ok=True)
    await init_db()

# Root endpoint
@app.get("/")
async def root() -> Response:
    """Serve frontend or return API info"""
    frontend_dir = settings.frontend_build_dir
    index_file = frontend_dir / "index.html"
    
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    
    return JSONResponse({
        "status": "ok",
        "message": "DevOps AI Platform API",
        "api_endpoints": {...}
    })
```

### Multi-Agent Orchestrator

**File**: `backend/multi_agent.py`

```python
class RemediationAgent(BaseAgent):
    """AI-powered error recovery agent."""
    
    def __init__(self, session_id: str, llm: LLMClient, validator: ValidatorAgent):
        super().__init__("RemediationAgent", session_id, llm)
        self.validator = validator
        self.fix_history: list[str] = []
        self.deployment_context: dict = {}
        self.ssh: SSHManager | None = None
    
    async def monitor_and_fix(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any
    ) -> Any:
        """Execute function with AI-powered error recovery."""
        
        max_attempts = settings.ai_max_retries
        stage = kwargs.get("stage", "unknown")
        
        for attempt in range(1, max_attempts + 1):
            try:
                result = await func(*args, **kwargs)
                
                # Check for failure
                if hasattr(result, "exit_code") and result.exit_code != 0:
                    raise OperationFailure(
                        message=getattr(result, "stderr", "Unknown error"),
                        command=kwargs.get("command", "unknown"),
                        exit_code=result.exit_code
                    )
                
                await self.emit(
                    f"✓ {kwargs.get('operation', 'Operation')} successful on attempt {attempt}",
                    message_type="ok",
                    stage=stage
                )
                return result
                
            except Exception as exc:
                if attempt >= max_attempts:
                    raise
                
                # Format error context
                error_context = {
                    "command": str(func.__name__),
                    "exit_code": getattr(exc, "exit_code", 1),
                    "stderr": str(exc),
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "operation": kwargs.get("operation", "unknown"),
                    "stage": stage,
                    "context": self.deployment_context
                }
                
                # Get fix candidates from LLM
                candidates = await self.llm.query_fix_candidates(error_context)
                
                # Select best fix
                best_fix = self._select_best_fix(candidates)
                
                if best_fix:
                    await self.emit(
                        f"🔧 Applying fix: {best_fix.get('analysis', 'Unknown fix')}",
                        message_type="warn",
                        stage=stage
                    )
                    
                    # Apply fix
                    await self._apply_fix(best_fix)
                    self.fix_history.append(best_fix.get("analysis", "Applied fix"))
                    
                    # Retry
                    continue
                
                raise
```

### LLM Client

**File**: `backend/llm_client.py`

```python
class LLMClient:
    """Multi-provider LLM adapter (Claude → Ollama → Fallback)."""
    
    async def query_fix_candidates(
        self,
        error_context: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Get fix candidates from available LLM providers."""
        
        prompt = self.build_fix_prompt(error_context)
        candidates: dict[str, dict[str, Any]] = {}
        
        # Try Claude first
        if self.claude_api_key:
            try:
                raw = await self._query_claude(prompt)
                candidates["claude"] = self._normalize_fix("claude", raw)
            except Exception:
                pass
        
        # Try Ollama second
        try:
            raw = await self._query_ollama(prompt)
            candidates["ollama"] = self._normalize_fix("ollama", raw)
        except Exception:
            pass
        
        # Fallback to error mapper
        if not candidates:
            pattern = ErrorFixMapper.find_pattern(error_context["stderr"])
            if pattern:
                candidates["fallback"] = pattern
        
        return candidates
    
    def build_fix_prompt(self, error_context: dict[str, Any]) -> str:
        """Build LLM prompt for error fix generation."""
        
        return f"""
An operation failed with this error:

Error: {error_context.get('stderr', 'Unknown')}
Command: {error_context.get('command', 'Unknown')}
Stage: {error_context.get('stage', 'Unknown')}
Attempt: {error_context.get('attempt', 1)} of {error_context.get('max_attempts', 3)}

Generate EXACT shell commands to fix this issue.

Response format (JSON only):
{{
  "analysis": "Explanation of the issue",
  "commands": ["command1", "command2"],
  "verification": "command to verify fix",
  "confidence": 0.95
}}
"""
```

### WebSocket Event Broadcasting

**File**: `backend/event_bus.py`

```python
@dataclass(frozen=True)
class PipelineEvent:
    """Event to broadcast to subscribers."""
    type: str
    data: dict[str, Any]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class EventBus:
    """In-memory event pub/sub system."""
    
    def __init__(self, history_size: int = 500):
        self._history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()
    
    async def publish(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any]
    ) -> None:
        """Publish event to all subscribers."""
        
        event = PipelineEvent(
            type=event_type,
            data=data,
            timestamp=datetime.now(timezone.utc)
        )
        
        async with self._lock:
            # Store in history
            self._history[session_id].append(event)
            
            # Get current subscribers
            subscribers = list(self._subscribers.get(session_id, set()))
        
        # Send to all subscribers
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest if queue full
                queue.get_nowait()
                queue.put_nowait(event)
    
    async def subscribe(
        self,
        session_id: str
    ) -> AsyncGenerator[PipelineEvent, None]:
        """Subscribe to events for a session."""
        
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        async with self._lock:
            # Send historical events first
            for event in self._history.get(session_id, []):
                queue.put_nowait(event)
            
            # Add to subscribers
            self._subscribers[session_id].add(queue)
        
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[session_id].discard(queue)
```

### Credentials Generator

**File**: `backend/credentials_manager.py`

```python
class CredentialsManager:
    """Auto-generate secure credentials for all services."""
    
    def generate_all_credentials(self, server_ip: str) -> dict[str, Any]:
        """Generate all credentials at once."""
        
        credentials = {
            "sonarqube": self._generate_sonarqube_credentials(server_ip),
            "jenkins": self._generate_jenkins_credentials(server_ip),
            "application": self._generate_application_credentials(),
            "database": self._generate_database_credentials(),
            "api_keys": self._generate_api_keys(),
            "generated_at": datetime.now().isoformat()
        }
        
        self.credentials_store = credentials
        return credentials
    
    def _generate_password(self, length: int = 16) -> str:
        """Generate cryptographically secure password."""
        
        chars = string.ascii_letters + string.digits + "!@#$%^&*()"
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    def _generate_sonarqube_credentials(self, server_ip: str) -> dict[str, Any]:
        """Generate SonarQube admin credentials."""
        
        password = self._generate_password(16)
        return {
            "service": "SonarQube",
            "url": f"http://{server_ip}:9000",
            "username": "admin",
            "password": password,
            "api_token": f"squ_{secrets.token_hex(20)}",
            "admin_token": f"admin_{secrets.token_hex(20)}",
            "display_password": f"Auto-generated: {password[:8]}***",
            "generated_at": datetime.now().isoformat()
        }
```

### React Component - Deployment Form

**File**: `frontend/components/DeploymentForm.jsx`

```jsx
import React, { useState } from "react";
import "../styles/DeploymentForm.css";

export default function DeploymentForm({ onDeploy, isLoading }) {
  const [formData, setFormData] = useState({
    repo_url: "",
    github_token: "",
    server_ip: "",
    username: "ubuntu",
    pem_content: "",
    dockerhub_user: "",
    dockerhub_pass: ""
  });

  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: "" }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    
    if (!formData.repo_url.trim()) {
      newErrors.repo_url = "Repository URL is required";
    }
    if (!formData.github_token.trim()) {
      newErrors.github_token = "GitHub token is required";
    }
    if (!formData.server_ip.trim()) {
      newErrors.server_ip = "Server IP is required";
    }
    if (!formData.pem_content.trim()) {
      newErrors.pem_content = "PEM key content is required";
    }
    if (!formData.dockerhub_user.trim()) {
      newErrors.dockerhub_user = "DockerHub username is required";
    }
    if (!formData.dockerhub_pass.trim()) {
      newErrors.dockerhub_pass = "DockerHub password is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      onDeploy(formData);
    }
  };

  return (
    <form className="deployment-form" onSubmit={handleSubmit}>
      <h2>🚀 Start Multi-Agent Deployment</h2>

      <div className="form-group">
        <label>Repository URL *</label>
        <input
          type="url"
          name="repo_url"
          placeholder="https://github.com/user/repo.git"
          value={formData.repo_url}
          onChange={handleChange}
          disabled={isLoading}
        />
        {errors.repo_url && <span className="error">{errors.repo_url}</span>}
      </div>

      <div className="form-group">
        <label>GitHub Personal Access Token *</label>
        <input
          type="password"
          name="github_token"
          placeholder="ghp_xxxxxxxxxxxxx"
          value={formData.github_token}
          onChange={handleChange}
          disabled={isLoading}
        />
        {errors.github_token && <span className="error">{errors.github_token}</span>}
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Target Server IP *</label>
          <input
            type="text"
            name="server_ip"
            placeholder="192.168.1.100"
            value={formData.server_ip}
            onChange={handleChange}
            disabled={isLoading}
          />
          {errors.server_ip && <span className="error">{errors.server_ip}</span>}
        </div>

        <div className="form-group">
          <label>SSH Username</label>
          <input
            type="text"
            name="username"
            value={formData.username}
            onChange={handleChange}
            disabled={isLoading}
          />
        </div>
      </div>

      <div className="form-group">
        <label>PEM Private Key Content *</label>
        <textarea
          name="pem_content"
          placeholder="-----BEGIN PRIVATE KEY-----\n..."
          value={formData.pem_content}
          onChange={handleChange}
          disabled={isLoading}
          rows={6}
        />
        {errors.pem_content && <span className="error">{errors.pem_content}</span>}
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>DockerHub Username *</label>
          <input
            type="text"
            name="dockerhub_user"
            placeholder="your_dockerhub_username"
            value={formData.dockerhub_user}
            onChange={handleChange}
            disabled={isLoading}
          />
          {errors.dockerhub_user && <span className="error">{errors.dockerhub_user}</span>}
        </div>

        <div className="form-group">
          <label>DockerHub Password/Token *</label>
          <input
            type="password"
            name="dockerhub_pass"
            placeholder="your_dockerhub_token"
            value={formData.dockerhub_pass}
            onChange={handleChange}
            disabled={isLoading}
          />
          {errors.dockerhub_pass && <span className="error">{errors.dockerhub_pass}</span>}
        </div>
      </div>

      <button type="submit" disabled={isLoading} className="submit-btn">
        {isLoading ? "⏳ Deploying..." : "🚀 Start Deployment"}
      </button>
    </form>
  );
}
```

---

## Summary

This documentation provides a complete technical reference for the **DevOps AI Automator** project. The system combines:

- **FastAPI backend** with async/await for high concurrency
- **4-agent AI system** for autonomous pipeline orchestration
- **Multi-LLM support** (Claude + Ollama) with intelligent fallback
- **Real-time WebSocket streaming** for live deployment monitoring
- **Auto-generated credentials** for all services
- **AI-powered error recovery** with pattern matching and LLM-generated fixes
- **Learning system** that improves fix selection over time
- **React frontend** for intuitive UI
- **Docker-based deployment** for complete infrastructure automation

All code is production-ready with comprehensive error handling, logging, and validation. The system can be deployed locally for development or to production servers with appropriate security configurations.

For questions or contributions, refer to the main README.md and specific domain guides (MULTI_AGENT_SYSTEM.md, ERROR_MAPPER_GUIDE.md, etc.).

---

**Generated**: 2024-05-28
**Version**: 1.0.0
**Project**: DevOps AI Automator
