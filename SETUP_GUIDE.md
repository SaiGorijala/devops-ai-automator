# FastAPI DevOps AI Multi-Agent Platform - Setup Guide

## 📋 Overview

This is a complete working FastAPI application for a DevOps AI Multi-Agent Platform that orchestrates deployment pipelines with AI-powered agents.

### Key Features
- ✅ Multi-agent orchestration (Repository Analysis, Pipeline Planning, Execution, Validation)
- ✅ Real-time WebSocket updates
- ✅ Automatic credential generation for services
- ✅ LLM integration with Ollama (with fallback support)
- ✅ Session management and activity tracking
- ✅ Health checks and monitoring
- ✅ CORS enabled for frontend integration

## 🚀 Quick Start

### Option 1: Local Python Environment

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the server:**
```bash
python main.py
```

The API will be available at `http://localhost:8000`

3. **Test the API:**
```bash
python test_api.py
```

### Option 2: Docker Compose

1. **Start all services:**
```bash
docker-compose up -d
```

This will start:
- FastAPI backend (port 8000)
- Ollama service (port 11434)
- Redis (for caching)
- PostgreSQL (for database)

2. **Stop services:**
```bash
docker-compose down
```

## 📡 API Endpoints

### Health & Status
```bash
GET /              # Root endpoint with API info
GET /health        # Health check with service status
```

### Deployment
```bash
POST /api/deploy   # Start deployment pipeline
```

**Request body:**
```json
{
  "repo_url": "https://github.com/user/repo.git",
  "github_token": "optional-token",
  "server_ip": "13.60.21.79",
  "pem_content": "ssh-key-content",
  "dockerhub_user": "username",
  "dockerhub_pass": "password"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "status": "started",
  "credentials": { ... },
  "message": "Pipeline started successfully"
}
```

### Session Management
```bash
GET /api/status/{session_id}              # Get pipeline status
GET /api/credentials/{session_id}         # Get generated credentials
GET /api/agent-activity/{session_id}      # Get all agent activities
POST /api/credentials/regenerate/{service} # Regenerate service credentials
```

### LLM & Monitoring
```bash
GET /api/llm-conversations                # Get all LLM conversation history
WS /ws/{session_id}                       # WebSocket for real-time updates
```

## 🧪 Testing

### Test All Endpoints
```bash
python test_api.py
```

### Test Individual Endpoints

**1. Root endpoint:**
```bash
curl http://localhost:8000/
```

**2. Health check:**
```bash
curl http://localhost:8000/health
```

**3. Start deployment:**
```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/SaiGorijala/task-tracker.git",
    "github_token": "",
    "server_ip": "13.60.21.79",
    "pem_content": "fake-pem-content",
    "dockerhub_user": "testuser",
    "dockerhub_pass": "testpass"
  }'
```

**4. Check session status** (use session_id from deploy response):
```bash
curl http://localhost:8000/api/status/{session_id}
```

**5. Get credentials:**
```bash
curl http://localhost:8000/api/credentials/{session_id}
```

**6. Get agent activities:**
```bash
curl http://localhost:8000/api/agent-activity/{session_id}
```

**7. Get LLM conversations:**
```bash
curl http://localhost:8000/api/llm-conversations
```

**8. Test WebSocket** (using websocat or similar):
```bash
websocat ws://localhost:8000/ws/{session_id}
```

## 🏗️ Architecture

### Agent Components

1. **RepositoryAnalyzer**
   - Analyzes GitHub repository
   - Detects project type, dependencies, entry points
   - Returns build and start commands

2. **PipelineCommander**
   - Creates deployment plan with stages
   - Stages: Server Init, SonarQube, Jenkins, Code Scan, Docker Build, Docker Push, Deploy

3. **ExecutionSolver**
   - Executes commands on remote server
   - Implements AI-powered error recovery
   - Handles SSH connections and command execution

4. **ValidatorSelector**
   - Validates deployment success
   - Verifies service health
   - Returns validation score

### Data Flow

```
Client Request
    ↓
Deploy Endpoint → Generate Session + Credentials
    ↓
Background Task: Run Pipeline
    ├→ Repository Analysis (Agent 1)
    ├→ Plan Creation (Agent 2)
    ├→ Execution with AI Fixes (Agent 3)
    └→ Validation (Agent 4)
    ↓
WebSocket Broadcasts + Activity Logging
    ↓
Session Complete
```

## 🔧 Configuration

### Environment Variables

```bash
# LLM Configuration
OLLAMA_HOST=http://localhost:11434
DEEPSEEK_MODEL=deepseek-coder:6.7b

# Server Configuration
APP_ENV=production
APP_SECRET_KEY=your-secret-key

# Database
DATABASE_URL=sqlite+aiosqlite:///devops_ai.db

# Redis
REDIS_URL=redis://localhost:6379

# Timeouts
LLM_TIMEOUT=90
SSH_TIMEOUT=30
MAX_PIPELINE_DURATION=1800
```

## 📊 Data Models

### DeployRequest
```python
{
    "repo_url": str,
    "github_token": Optional[str],
    "server_ip": str,
    "pem_content": str,
    "dockerhub_user": str,
    "dockerhub_pass": str
}
```

### PipelineStatus
```python
{
    "session_id": str,
    "status": str,  # pending, running, completed, failed
    "current_stage": Optional[str],
    "progress": int,  # 0-100
    "started_at": Optional[str],
    "completed_at": Optional[str]
}
```

## 🐛 Troubleshooting

### Issue: "Not Found" error
**Solution:** Ensure you're using the correct endpoint paths as listed above.

### Issue: Ollama not available
**Solution:** The system has built-in fallback mode when Ollama is unavailable. It will provide basic diagnostic commands and SSH fixes.

### Issue: Connection timeout
**Solution:** 
- Check if the server is running: `curl http://localhost:8000/`
- Verify port 8000 is not in use
- Check firewall settings

### Issue: WebSocket connection failed
**Solution:**
- Ensure session_id is valid
- WebSocket endpoint is `/ws/{session_id}` not `/api/ws/`

## 📁 Project Structure

```
.
├── main.py                    # Complete FastAPI application
├── test_api.py               # Test suite
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Multi-service setup
├── setup_guide.md            # This file
└── README.md                 # Project overview
```

## 🔒 Security Notes

- SSH keys are not actually stored; use PEM content directly
- Credentials are generated in-memory (replace with secure storage)
- CORS is open to all origins (restrict in production)
- No authentication required (add JWT in production)

## 🚀 Production Deployment

For production deployment:

1. **Replace in-memory storage:**
   - Use Redis for sessions
   - Use PostgreSQL for persistence
   - Implement caching strategies

2. **Add authentication:**
   - Implement JWT tokens
   - Add role-based access control
   - Secure credential storage

3. **Security hardening:**
   - Restrict CORS origins
   - Add rate limiting
   - Implement request validation
   - Use HTTPS/TLS

4. **Monitoring:**
   - Add structured logging
   - Implement metrics collection
   - Set up alerting

## 📚 API Response Examples

### Deploy Response
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "credentials": {
    "sonarqube": {
      "service": "SonarQube",
      "url": "http://13.60.21.79:9081",
      "username": "admin",
      "password": "generated-password",
      "api_token": "squ_...",
      "generated_at": "2024-01-01T12:00:00"
    },
    "jenkins": { ... },
    "application": { ... }
  },
  "message": "Pipeline started successfully"
}
```

### Status Response
```json
{
  "status": "running",
  "started_at": "2024-01-01T12:00:00",
  "completed_at": null,
  "current_stage": "Docker Build",
  "progress": 65,
  "request": { ... },
  "credentials": { ... }
}
```

### Agent Activity Response
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "activities": [
    {
      "timestamp": "2024-01-01T12:00:01",
      "agent": "RepositoryAnalyzer",
      "action": "started",
      "data": { "repo": "https://github.com/..." }
    },
    {
      "timestamp": "2024-01-01T12:00:05",
      "agent": "RepositoryAnalyzer",
      "action": "completed",
      "data": { "project_type": "python", ... }
    }
  ]
}
```

## 🤝 Contributing

To extend the platform:

1. Add new agents by creating classes inheriting agent patterns
2. Add endpoints for new functionality
3. Update WebSocket messages for real-time updates
4. Add tests for new features

## 📝 License

MIT License - Feel free to use and modify as needed.

## 💬 Support

For issues or questions, check the troubleshooting section or review the endpoint documentation above.
