# DevOps AI Automator

FastAPI backend plus React UI for an autonomous DevOps deployment pipeline. A user supplies a GitHub repository, SSH target, PEM key, and DockerHub credentials; the backend provisions Docker, SonarQube, Jenkins, scans the repo, builds and pushes an image, deploys the app, and streams all events to the UI.

## What Is Included

- FastAPI API:
  - `POST /api/deploy`
  - `GET /api/status/{session_id}`
  - `GET /api/credentials/{session_id}`
  - `WS /ws/{session_id}`
- Real SSH execution with PEM authentication through Paramiko.
- Remote Docker and Docker Compose installation.
- Remote SonarQube plus PostgreSQL deployment with generated admin password and API token.
- Remote Jenkins deployment with plugin install attempt and initial admin password retrieval.
- Git clone, project type detection, Dockerfile generation, Docker build, DockerHub login/push.
- SonarQube scanner integration using the scanner Docker image.
- Ollama DeepSeek recovery agent with retry logic, fallback patterns, command history, and WebSocket AI events.
- SQLite session persistence with encrypted submitted inputs.
- Vite wrapper around the existing React component.

## Requirements

- Docker Desktop or Docker Engine on the machine running the backend.
- Docker socket mounted into the backend container for image builds and pushes.
- A reachable Ubuntu/Debian-like SSH target with sudo access for the SSH user.
- Inbound target-server ports available, or the pipeline will pick the next open port from:
  - SonarQube: `9000+`
  - Jenkins: `8080+`
  - App: `3000+`
- DockerHub username and access token/password.
- GitHub token for private repositories.

## Quick Start With Compose

```bash
cp .env.example .env
docker compose up --build
```

Open:

```text
http://localhost:8000
```

The compose stack starts Ollama, Redis, Postgres, and the backend. The backend uses SQLite by default at `/data/devops_ai.db`; Postgres is included for teams that want to move persistence later.

## Pull DeepSeek Manually

If the `ollama-init` service is slow or you run Ollama outside Compose:

```bash
bash scripts/setup_ollama.sh
```

On Windows PowerShell:

```powershell
.\scripts\setup_ollama.ps1
```

Default model:

```text
deepseek-coder:6.7b
```

## Local Development

Backend:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The Vite config proxies `/api` and `/ws` to `localhost:8000`. To build the frontend and let FastAPI serve it:

```bash
cd frontend
npm run build
cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## API Example

```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/user/app",
    "github_token": "ghp_optional",
    "server_ip": "ubuntu@203.0.113.10",
    "pem_file_content": "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----",
    "dockerhub_user": "dockerhub-user",
    "dockerhub_pass": "dockerhub-token"
  }'
```

Response:

```json
{ "session_id": "..." }
```

Stream events:

```text
ws://localhost:8000/ws/{session_id}
```

## AI Recovery Safety

The agent asks Ollama for executable bash commands and retries failed operations. It also has deterministic fallback commands for common failures like Docker permission errors, port conflicts, SonarQube timeouts, DNS issues, and disk pressure.

By default, obviously destructive commands are blocked. To allow unrestricted model-proposed commands:

```env
AI_ALLOW_DANGEROUS_COMMANDS=true
```

For review-only mode:

```env
AI_AUTO_EXECUTE=false
```

## Important Operational Notes

- Submitted inputs are encrypted in SQLite using `APP_SECRET_KEY`; replace the default before use.
- Generated service credentials are returned in `/api/credentials/{session_id}` and stored as session outputs.
- Jenkins plugin installation depends on Jenkins update-center availability and can take several minutes.
- Sonar vulnerability auto-fixes are best-effort LLM shell patches. Complex application fixes may still require human review.
- The backend builds Docker images locally, so it needs access to Docker.
- The target server pulls and runs the pushed DockerHub image.
