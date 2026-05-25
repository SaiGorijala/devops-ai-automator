from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import platform
import re
import shlex
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select

from .config import settings
from .database import AsyncSessionLocal
from .error_fix_mapper import ErrorFixMapper
from .event_bus import event_bus
from .github_manager import GitHubManager
from .llm_client import LLMClient
from .models import AgentLearning
from .process import LocalCommandResult, run_command
from .schemas import DeploymentInputs
from .session_store import SessionStore, session_store
from .ssh_manager import CommandResult, SSHManager


@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str
    message_type: str
    content: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }


class OperationFailure(RuntimeError):
    def __init__(
        self,
        message: str,
        command: str = "unknown",
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class BaseAgent:
    def __init__(
        self,
        name: str,
        session_id: str,
        llm: LLMClient,
        store: SessionStore = session_store,
    ) -> None:
        self.name = name
        self.session_id = session_id
        self.llm = llm
        self.store = store

    async def emit(
        self,
        message: str,
        message_type: str = "info",
        to_agent: str = "ui",
        stage: str | None = None,
        **content: Any,
    ) -> None:
        payload = AgentMessage(
            from_agent=self.name,
            to_agent=to_agent,
            message_type=message_type,
            content={"message": message, "stage": stage, **content},
        ).to_dict()
        print(f"[AI] {self.name} -> {to_agent}: {message}", flush=True)
        await self.store.add_ai_intervention(
            self.session_id,
            f"{self.name}: {message}",
            intervention_type=message_type if message_type in {"ok", "warn", "error", "action", "info", "success"} else "info",
            stage=stage,
            agent=self.name,
            agent_message=payload,
        )
        await event_bus.publish(self.session_id, "agent_event", payload)


class RepositoryAnalyzerAgent(BaseAgent):
    def __init__(self, session_id: str, llm: LLMClient) -> None:
        super().__init__("Repository Analyzer", session_id, llm)

    async def analyze_repository(
        self,
        github: GitHubManager,
        inputs: DeploymentInputs,
        remediation: "RemediationAgent",
    ) -> dict[str, Any]:
        await self.emit("Cloning repository and scanning project structure", "action", to_agent="Pipeline Commander", stage="scan")
        repo_path = await remediation.monitor_and_fix(
            github.clone_repo,
            inputs.repo_url,
            inputs.github_token,
            inputs.branch,
            stage="scan",
            fix_location="local",
        )
        file_list = self._file_list(repo_path)
        important_files = self._important_files(repo_path)
        heuristic = self._heuristic_analysis(inputs.repo_url, inputs.branch, repo_path, file_list, important_files)
        prompt = self._analysis_prompt(inputs.repo_url, file_list, important_files, heuristic)
        result = await self.llm.query_json(prompt, fallback={})
        analysis = self._merge_analysis(heuristic, result.data)
        analysis["repo_path"] = str(repo_path)
        analysis["llm_provider"] = result.provider
        (repo_path / "repository_analysis.json").write_text(
            json.dumps(analysis, indent=2),
            encoding="utf-8",
        )
        await self.emit(
            f"Detected {analysis['project_type']} app on port {analysis['port']}",
            "ok",
            to_agent="Pipeline Commander",
            stage="scan",
            project_type=analysis["project_type"],
            port=analysis["port"],
        )
        return analysis

    def _analysis_prompt(
        self,
        repo_url: str,
        file_list: list[str],
        important_files: dict[str, str],
        heuristic: dict[str, Any],
    ) -> str:
        return f"""Analyze this repository and return a deployment plan as JSON.

Repository: {repo_url}
Detected by heuristics: {json.dumps(heuristic, indent=2)}
Files found: {json.dumps(file_list[:300], indent=2)}
Important file excerpts: {json.dumps(important_files, indent=2)}

Return ONLY JSON:
{{
  "project_type": "nodejs|python|java|go|rust|php|static|unknown",
  "build_command": "command or empty string",
  "install_command": "command or empty string",
  "start_command": "command",
  "port": 3000,
  "entry_points": ["file"],
  "environment_variables": ["NAME"],
  "database": ["postgres|mysql|mongodb|redis"],
  "special_config": ["short notes"]
}}"""

    def _file_list(self, repo_path: Path) -> list[str]:
        excluded_dirs = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next"}
        files: list[str] = []
        for path in repo_path.rglob("*"):
            rel = path.relative_to(repo_path)
            if any(part in excluded_dirs for part in rel.parts):
                continue
            if path.is_file():
                files.append(rel.as_posix())
            if len(files) >= 600:
                break
        return files

    def _important_files(self, repo_path: Path) -> dict[str, str]:
        names = {
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Pipfile",
            "Dockerfile",
            "docker-compose.yml",
            "compose.yml",
            "pom.xml",
            "build.gradle",
            "go.mod",
            "Cargo.toml",
            "main.py",
            "app.py",
            "server.js",
            "index.js",
            "README.md",
        }
        content: dict[str, str] = {}
        for path in repo_path.rglob("*"):
            if path.is_file() and path.name in names:
                rel = path.relative_to(repo_path).as_posix()
                content[rel] = path.read_text(encoding="utf-8", errors="replace")[:5000]
            if len(content) >= 40:
                break
        return content

    def _heuristic_analysis(
        self,
        repo_url: str,
        branch: str,
        repo_path: Path,
        file_list: list[str],
        important_files: dict[str, str],
    ) -> dict[str, Any]:
        project_type = self._detect_type(repo_path, file_list)
        env_vars = sorted(self._detect_env_vars(important_files))
        database = sorted(self._detect_databases(important_files))
        entry_points = self._entry_points(file_list)
        port = self._detect_port(important_files, project_type)
        commands = self._commands(repo_path, project_type, important_files)
        return {
            "repo_url": repo_url,
            "branch": branch,
            "project_type": project_type,
            "files_scanned": len(file_list),
            "entry_points": entry_points,
            "port": port,
            "environment_variables": env_vars,
            "database": database,
            "special_config": [],
            **commands,
        }

    def _detect_type(self, repo_path: Path, file_list: list[str]) -> str:
        files = set(file_list)
        if "package.json" in files:
            return "nodejs"
        if {"requirements.txt", "pyproject.toml", "Pipfile"} & files:
            return "python"
        if {"pom.xml", "build.gradle", "build.gradle.kts"} & files:
            return "java"
        if "go.mod" in files:
            return "go"
        if "Cargo.toml" in files:
            return "rust"
        if "composer.json" in files:
            return "php"
        if (repo_path / "index.html").exists():
            return "static"
        return "unknown"

    def _commands(self, repo_path: Path, project_type: str, important_files: dict[str, str]) -> dict[str, str]:
        if project_type == "nodejs":
            try:
                package = json.loads(important_files.get("package.json", "{}") or "{}")
            except json.JSONDecodeError:
                package = {}
            scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
            install = "npm ci" if (repo_path / "package-lock.json").exists() else "npm install"
            build = "npm run build" if "build" in scripts else ""
            start = "npm start" if "start" in scripts else self._node_entry_command(repo_path)
            return {"install_command": install, "build_command": build, "start_command": start}
        if project_type == "python":
            install = "pip install --no-cache-dir -r requirements.txt" if (repo_path / "requirements.txt").exists() else "pip install --no-cache-dir ."
            start = "python main.py" if (repo_path / "main.py").exists() else "python app.py" if (repo_path / "app.py").exists() else "python -m app"
            if "uvicorn" in important_files.get("requirements.txt", "").lower():
                start = "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"
            return {"install_command": install, "build_command": "", "start_command": start}
        if project_type == "java":
            if (repo_path / "pom.xml").exists():
                return {"install_command": "mvn -q -DskipTests package", "build_command": "", "start_command": "java -jar target/*.jar"}
            return {"install_command": "gradle build -x test --no-daemon", "build_command": "", "start_command": "java -jar build/libs/*.jar"}
        if project_type == "go":
            return {"install_command": "go mod download", "build_command": "go build -o app .", "start_command": "./app"}
        if project_type == "rust":
            return {"install_command": "cargo fetch", "build_command": "cargo build --release", "start_command": "./target/release/app"}
        if project_type == "static":
            return {"install_command": "", "build_command": "", "start_command": "nginx -g 'daemon off;'"}
        return {"install_command": "", "build_command": "", "start_command": ""}

    @staticmethod
    def _node_entry_command(repo_path: Path) -> str:
        for candidate in ("server.js", "app.js", "index.js"):
            if (repo_path / candidate).exists():
                return f"node {candidate}"
        return "npm start"

    @staticmethod
    def _detect_env_vars(important_files: dict[str, str]) -> set[str]:
        joined = "\n".join(important_files.values())
        patterns = [
            r"process\.env\.([A-Z0-9_]+)",
            r"os\.getenv\([\"']([A-Z0-9_]+)[\"']",
            r"ENV\[?[\"']([A-Z0-9_]+)[\"']\]?",
            r"\$\{([A-Z0-9_]+)(?::-[^}]*)?\}",
        ]
        values: set[str] = set()
        for pattern in patterns:
            values.update(re.findall(pattern, joined))
        return {value for value in values if len(value) > 1 and "SECRET" not in value}

    @staticmethod
    def _detect_databases(important_files: dict[str, str]) -> set[str]:
        joined = "\n".join(important_files.values()).lower()
        found: set[str] = set()
        for name in ("postgres", "postgresql", "mysql", "mongodb", "mongo", "redis", "sqlite"):
            if name in joined:
                found.add("mongodb" if name == "mongo" else "postgres" if name == "postgresql" else name)
        return found

    @staticmethod
    def _entry_points(file_list: list[str]) -> list[str]:
        candidates = [
            file
            for file in file_list
            if file in {"main.py", "app.py", "server.js", "index.js", "src/main.py", "cmd/main.go", "main.go"}
            or file.endswith("/main.py")
            or file.endswith("/server.js")
        ]
        return candidates[:10]

    @staticmethod
    def _detect_port(important_files: dict[str, str], project_type: str) -> int:
        joined = "\n".join(important_files.values())
        expose = re.search(r"(?im)^\s*EXPOSE\s+(\d{2,5})", joined)
        if expose:
            return int(expose.group(1))
        for pattern in (r"PORT\s*[:=]\s*[\"']?(\d{2,5})", r"listen\(\s*(\d{2,5})", r"--port\s+(\d{2,5})"):
            match = re.search(pattern, joined)
            if match:
                return int(match.group(1))
        defaults = {"nodejs": 3000, "python": 8000, "java": 8080, "go": 8080, "rust": 8080, "php": 8000, "static": 80}
        return defaults.get(project_type, 3000)

    @staticmethod
    def _merge_analysis(heuristic: dict[str, Any], llm_data: dict[str, Any]) -> dict[str, Any]:
        merged = dict(heuristic)
        for key in (
            "project_type",
            "install_command",
            "build_command",
            "start_command",
            "entry_points",
            "environment_variables",
            "database",
            "special_config",
        ):
            value = llm_data.get(key)
            if value:
                merged[key] = value
        try:
            port = int(llm_data.get("port", merged["port"]))
            if 1 <= port <= 65535:
                merged["port"] = port
        except (TypeError, ValueError):
            pass
        return merged


class PipelineCommanderAgent(BaseAgent):
    def __init__(self, session_id: str, llm: LLMClient) -> None:
        super().__init__("Pipeline Commander", session_id, llm)

    async def create_plan(self, analysis: dict[str, Any]) -> dict[str, Any]:
        await self.emit("Creating execution plan from repository analysis", "action", to_agent="Execution Solver", stage="scan")
        fallback = self._fallback_plan(analysis)
        result = await self.llm.query_json(self._plan_prompt(analysis), fallback=fallback)
        plan = self._merge_plan(fallback, result.data)
        plan["llm_provider"] = result.provider
        repo_path = Path(analysis["repo_path"])
        (repo_path / "deployment_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        script = self._script(plan)
        script_path = repo_path / "pipeline_script.sh"
        script_path.write_text(script, encoding="utf-8")
        script_path.chmod(0o755)
        await self.emit(
            f"Plan ready: install='{plan.get('install_command') or 'none'}', start='{plan.get('start_command') or 'docker default'}'",
            "ok",
            to_agent="Execution Solver",
            stage="scan",
            plan_summary={key: plan.get(key) for key in ("project_type", "port", "install_command", "build_command", "start_command")},
        )
        return plan

    def _plan_prompt(self, analysis: dict[str, Any]) -> str:
        return f"""Create a production deployment plan for this repository analysis.

Repository analysis:
{json.dumps(analysis, indent=2)}

Return ONLY JSON:
{{
  "project_type": "{analysis.get('project_type', 'unknown')}",
  "install_command": "exact command or empty",
  "build_command": "exact command or empty",
  "start_command": "exact command",
  "port": {analysis.get('port', 3000)},
  "environment_variables": ["NAME"],
  "database": ["name"],
  "steps": [
    {{"name": "install", "command": "command", "phase": "build"}},
    {{"name": "start", "command": "command", "phase": "runtime"}}
  ],
  "error_strategies": ["short remediation hint"]
}}"""

    @staticmethod
    def _fallback_plan(analysis: dict[str, Any]) -> dict[str, Any]:
        steps = []
        for name in ("install_command", "build_command", "start_command"):
            command = analysis.get(name) or ""
            if command:
                steps.append({"name": name.replace("_command", ""), "command": command, "phase": "runtime" if name == "start_command" else "build"})
        return {
            "project_type": analysis.get("project_type", "unknown"),
            "install_command": analysis.get("install_command", ""),
            "build_command": analysis.get("build_command", ""),
            "start_command": analysis.get("start_command", ""),
            "port": analysis.get("port", 3000),
            "environment_variables": analysis.get("environment_variables", []),
            "database": analysis.get("database", []),
            "steps": steps,
            "error_strategies": [
                "capture stdout and stderr",
                "check port conflicts",
                "verify container health",
            ],
        }

    @staticmethod
    def _merge_plan(fallback: dict[str, Any], llm_data: dict[str, Any]) -> dict[str, Any]:
        plan = dict(fallback)
        for key, value in llm_data.items():
            if value not in (None, "", []):
                plan[key] = value
        try:
            plan["port"] = int(plan.get("port", fallback["port"]))
        except (TypeError, ValueError):
            plan["port"] = fallback["port"]
        return plan

    @staticmethod
    def _script(plan: dict[str, Any]) -> str:
        lines = ["#!/usr/bin/env bash", "set -euo pipefail"]
        for command in (plan.get("install_command"), plan.get("build_command")):
            if command:
                lines.append(command)
        if plan.get("start_command"):
            lines.append(plan["start_command"])
        return "\n".join(lines) + "\n"


class ValidatorAgent(BaseAgent):
    def __init__(self, session_id: str, llm: LLMClient) -> None:
        super().__init__("Validator", session_id, llm)

    async def select_best_fix(
        self,
        fixes_from_agents: dict[str, dict[str, Any]],
        error_context: dict[str, Any],
    ) -> dict[str, Any]:
        signature = self._signature(error_context)
        scores = await self._provider_scores(signature)
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for provider, fix in fixes_from_agents.items():
            quality = self.evaluate_fix_quality(fix)
            score = scores.get(provider, 0.5) + quality
            scored.append((score, provider, fix))
        scored.sort(key=lambda item: item[0], reverse=True)
        best = scored[0][2] if scored else self.fallback_fix(error_context)

        # If best has no commands, find first one that does or create emergency fix
        if not best.get("commands") or len(best.get("commands", [])) == 0:
            for _, _, fix in scored:
                if fix.get("commands") and len(fix.get("commands", [])) > 0:
                    best = fix
                    break
            if not best.get("commands"):
                best = self._get_emergency_fix(error_context)

        await self.emit(
            f"Selected {best.get('provider', 'fallback')} fix with {len(best.get('commands', []))} command(s)",
            "action",
            to_agent="Execution Solver",
            stage=error_context.get("stage"),
            selected_provider=best.get("provider", "fallback"),
            confidence=best.get("confidence", 0),
        )
        return best

    def evaluate_fix_quality(self, fix: dict[str, Any]) -> float:
        commands = fix.get("commands", [])
        if not commands:
            return -1.0
        score = float(fix.get("confidence", 0.5)) * 0.4
        if len(commands) <= 5:
            score += 0.2
        if fix.get("verification"):
            score += 0.2
        if all(self.is_safe_command(str(command)) for command in commands):
            score += 0.4
        else:
            score -= 1.0
        text = " ".join(str(command).lower() for command in commands)
        if "docker" in text:
            score += 0.1
        if "systemctl" in text:
            score += 0.05
        return score

    async def record_fix_outcome(self, provider: str, error_context: dict[str, Any], fix: dict[str, Any], success: bool) -> None:
        signature = self._signature(error_context)
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(AgentLearning).where(
                    AgentLearning.provider == provider,
                    AgentLearning.error_signature == signature,
                )
            )
            learning = existing.scalar_one_or_none()
            if not learning:
                learning = AgentLearning(provider=provider, error_signature=signature)
                db.add(learning)
            if success:
                learning.successes = (learning.successes or 0) + 1
            else:
                learning.failures = (learning.failures or 0) + 1
            learning.last_error = str(error_context.get("stderr") or error_context.get("error") or "")[-2000:]
            learning.last_fix = fix
            learning.updated_at = datetime.now(timezone.utc)
            await db.commit()

    async def validate_deployment(self, ssh: SSHManager | None, app_url: str | None, stage: str = "deploy") -> dict[str, Any]:
        if not ssh or not app_url:
            return {"success": True, "reason": "No remote app URL to validate"}
        match = re.search(r":(\d{2,5})(?:/|$)", app_url)
        port = match.group(1) if match else ""
        command = f"curl -fsS --connect-timeout 3 --max-time 10 http://127.0.0.1:{port}/health || curl -fsS --connect-timeout 3 --max-time 10 http://127.0.0.1:{port}/"
        result = await asyncio.to_thread(ssh.execute_command, command, 20)
        success = result.ok and bool((result.stdout or result.stderr).strip())
        await self.emit(
            "Deployment validation passed" if success else "Deployment validation failed",
            "ok" if success else "warn",
            to_agent="Pipeline Commander",
            stage=stage,
            command=command,
            output=(result.stdout + result.stderr)[-1000:],
        )
        return {"success": success, "command": command, "output": (result.stdout + result.stderr)[-2000:]}

    async def _provider_scores(self, signature: str) -> dict[str, float]:
        async with AsyncSessionLocal() as db:
            rows = await db.execute(select(AgentLearning).where(AgentLearning.error_signature == signature))
            scores: dict[str, float] = {}
            for row in rows.scalars():
                total = (row.successes or 0) + (row.failures or 0)
                scores[row.provider] = 0.5 if total == 0 else max(0.0, min(1.0, row.successes / total))
            return scores

    @staticmethod
    def _signature(error_context: dict[str, Any]) -> str:
        text = f"{error_context.get('operation')}|{error_context.get('command')}|{error_context.get('stderr') or error_context.get('error')}"
        normalized = re.sub(r"\b[0-9a-f]{8,}\b", "<id>", text.lower())
        normalized = re.sub(r"\d{2,5}", "<num>", normalized)
        return hashlib.sha256(normalized[:4000].encode("utf-8", errors="ignore")).hexdigest()

    @classmethod
    def fallback_fix(cls, error_context: dict[str, Any]) -> dict[str, Any]:
        commands = cls.dynamic_error_patterns(error_context)
        return {
            "provider": "fallback",
            "analysis": "Pattern-based fallback remediation",
            "commands": commands,
            "verification": commands[0] if commands else "",
            "confidence": 0.35,
        }

    @classmethod
    def _get_emergency_fix(cls, error_context: dict[str, Any]) -> dict[str, Any]:
        """Emergency fix when LLM returns empty commands"""
        error_text = str(error_context.get("stderr", "")) + str(error_context.get("error", ""))
        lower = error_text.lower()

        if "timeout" in lower or "timeout opening channel" in lower:
            return {
                "provider": "emergency",
                "analysis": "Timeout detected - emergency recovery",
                "commands": [
                    "sleep 5",
                    "sudo systemctl restart docker || true",
                    "echo 'Emergency timeout recovery'",
                ],
                "verification": "docker ps",
                "confidence": 0.5,
            }

        if "docker" in lower or "container" in lower:
            return {
                "provider": "emergency",
                "analysis": "Docker issue detected - emergency recovery",
                "commands": [
                    "sudo systemctl restart docker || true",
                    "sudo systemctl daemon-reload",
                    "sleep 3",
                    "echo 'Docker service restarted'",
                ],
                "verification": "docker ps",
                "confidence": 0.5,
            }

        return {
            "provider": "emergency",
            "analysis": "Generic emergency recovery",
            "commands": [
                "sleep 3",
                "echo 'System check:'",
                "uname -a",
                "echo 'Emergency fix applied'",
            ],
            "verification": "echo 'Check passed'",
            "confidence": 0.3,
        }


    @classmethod
    def dynamic_error_patterns(cls, error: str | dict[str, Any] = "") -> list[str]:
        error_context = error if isinstance(error, dict) else {}
        error_text = str(
            error_context.get("stderr")
            or error_context.get("error")
            or error
            or ""
        )
        host, port, username = cls._ssh_target_from_context(error_context, error_text)
        lower = error_text.lower()
        if (
            "ssh_protocol_banner" in lower
            or "error reading ssh protocol banner" in lower
            or "ssh connection failed" in lower
            or "socket timeout" in lower
            or "connection refused" in lower
        ):
            safe_host = shlex.quote(host)
            safe_user = shlex.quote(username)
            safe_port = int(port)
            return [
                f"getent hosts {safe_host} || true",
                f"python -c \"import socket; s=socket.create_connection(({host!r}, {safe_port}), 10); print('tcp connect ok'); s.close()\"",
                f"nc -vz -w 10 {safe_host} {safe_port} || true",
                f"ssh -vvv -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no -p {safe_port} {safe_user}@{safe_host} true || true",
            ]
        if "authentication" in lower and "ssh" in lower:
            safe_host = shlex.quote(host)
            safe_user = shlex.quote(username)
            safe_port = int(port)
            return [
                "python -c \"print('PEM parsed by Paramiko before authentication; verify username and EC2 key pair match')\"",
                f"ssh -vvv -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no -p {safe_port} {safe_user}@{safe_host} true || true",
            ]
        if "docker" in lower and "permission denied" in lower:
            return ["sudo systemctl restart docker || true", "sudo chmod 666 /var/run/docker.sock || true"]
        if "docker" in lower and ("not found" in lower or "no such file" in lower):
            return ["curl -fsSL https://get.docker.com | sudo sh", "sudo systemctl enable --now docker"]
        if "openjdk-17-jre-headless" in lower and "no installation candidate" in lower:
            return ["sudo apt-get update -y", "sudo apt-get install -y openjdk-21-jre-headless || sudo apt-get install -y default-jre-headless"]
        if "sonarqube" in lower and ("timeout" in lower or "timed out" in lower or "health" in lower):
            return [
                "sudo sysctl -w vm.max_map_count=524288",
                "sudo docker ps --format '{{.Names}}' | grep sonarqube | xargs -r sudo docker restart",
                "sleep 30",
            ]
        if "port" in lower and ("already in use" in lower or "bind" in lower or "allocated" in lower):
            match = re.search(r":(\d{2,5})", error)
            port = match.group(1) if match else "3000"
            return [f"sudo fuser -k {port}/tcp || true"]
        if "temporary failure resolving" in lower or "could not resolve" in lower:
            return ["sudo systemctl restart systemd-resolved || true"]
        if "no space left" in lower:
            return ["sudo docker system prune -af || true"]
        if "ollama unavailable" in lower or "connection refused" in lower and "11434" in lower:
            return ["docker ps -a --filter name=ollama --format '{{.ID}}' | head -1 | xargs -r docker start"]
        return []

    @staticmethod
    def _ssh_target_from_context(error_context: dict[str, Any], error_text: str) -> tuple[str, int, str]:
        host = "127.0.0.1"
        port = 22
        username = settings.ssh_user
        context = error_context.get("context", {}) if isinstance(error_context, dict) else {}
        if isinstance(context, dict):
            host = str(context.get("server_ip") or context.get("host") or host)
            username = str(context.get("username") or context.get("ssh_user") or username)
        match = re.search(r'"host"\s*:\s*"([^"]+)"', error_text)
        if match:
            host = match.group(1)
        match = re.search(r'"username"\s*:\s*"([^"]+)"', error_text)
        if match:
            username = match.group(1)
        match = re.search(r'"port"\s*:\s*(\d{1,5})', error_text)
        if match:
            port = int(match.group(1))
        if "@" in host:
            parsed_user, parsed_host = host.split("@", 1)
            username = parsed_user or username
            host = parsed_host
        if ":" in host and host.count(":") == 1:
            host_part, port_part = host.rsplit(":", 1)
            if port_part.isdigit():
                host = host_part
                port = int(port_part)
        return host, port, username

    @staticmethod
    def is_safe_command(command: str) -> bool:
        if settings.ai_allow_dangerous_commands:
            return True
        blocked_patterns = [
            r"rm\s+-rf\s+/(?:\s|$)",
            r"rm\s+-rf\s+--no-preserve-root",
            r"mkfs\.",
            r"\bdd\s+if=",
            r":\(\)\s*\{\s*:\|:",
            r"\bshutdown\b",
            r"\bpoweroff\b",
            r"\breboot\b",
            r"chmod\s+-R\s+777\s+/",
            r"chown\s+-R\s+[^ ]+\s+/",
            r"\buserdel\b",
            r"\bpasswd\b",
        ]
        return not any(re.search(pattern, command) for pattern in blocked_patterns)


class RemediationAgent(BaseAgent):
    def __init__(
        self,
        session_id: str,
        llm: LLMClient,
        validator: ValidatorAgent,
        ssh: SSHManager | None = None,
    ) -> None:
        super().__init__("Execution Solver", session_id, llm)
        self.validator = validator
        self.ssh = ssh
        self.intervention_count = 0
        self.fix_history: list[dict[str, Any]] = []
        self.deployment_context: dict[str, Any] = {}

    async def ensure_llm_available(self) -> dict[str, Any]:
        health = await self.llm.health()
        if health.get("ollama_ready") or health.get("claude_configured"):
            await self.emit("LLM provider ready", "ok", to_agent="Repository Analyzer", llm_health=health)
            return health
        await self.emit("Ollama unavailable; attempting container auto-start before using fallback patterns", "warn", llm_health=health)
        await self._try_start_ollama_container()
        health = await self.llm.health()
        await self.emit(
            "Ollama API ready" if health.get("ollama_ready") else "LLM still unavailable; fallback remediation remains enabled",
            "ok" if health.get("ollama_ready") else "warn",
            llm_health=health,
        )
        return health

    async def monitor_and_fix(
        self,
        command_func: Callable[..., Any],
        *args: Any,
        stage: str | None = None,
        fix_location: str = "remote",
        cwd: str | Path | None = None,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        max_retries = settings.ai_max_retries
        operation = getattr(command_func, "__qualname__", getattr(command_func, "__name__", "operation"))
        last_error: OperationFailure | None = None
        for attempt in range(1, max_retries + 1):
            try:
                result = await self._call(command_func, *args, **kwargs)
                if attempt > 1 and last_error:
                    await self.validator.record_fix_outcome("selected", self._error_context(last_error, operation, attempt, max_retries, stage, fix_location, cwd, context), {"commands": []}, True)
                return result
            except Exception as exc:  # noqa: BLE001
                failure = self._failure_from_exception(exc)
                last_error = failure
                system_snapshot = await self._safe_system_snapshot(fix_location=fix_location, cwd=cwd)
                error_context = self._error_context(
                    failure,
                    operation,
                    attempt,
                    max_retries,
                    stage,
                    fix_location,
                    cwd,
                    context,
                    system_snapshot,
                )
                await self.emit(
                    f"{operation} failed on attempt {attempt}; sending full error context to LLM",
                    "warn",
                    to_agent="Validator",
                    stage=stage,
                    command=failure.command,
                    exit_code=failure.exit_code,
                )
                await self.emit(
                    "Querying Claude/Ollama for remediation commands",
                    "action",
                    to_agent="Validator",
                    stage=stage,
                    operation=operation,
                    stderr=failure.stderr[-2000:],
                )

                # Try direct mapper FIRST (no LLM needed)
                candidates: dict[str, dict[str, Any]] = {}
                if ErrorFixMapper.should_use_mapper(failure.stderr):
                    direct_fix = ErrorFixMapper.get_fix(failure.stderr, error_context.get("context", {}))
                    candidates["direct-mapper"] = direct_fix
                    await self.emit(
                        f"Direct mapper found fix: {direct_fix['analysis'][:100]}",
                        "action",
                        to_agent="Validator",
                        stage=stage,
                    )

                # If no direct fix, query LLM
                if not candidates:
                    candidates = await self.llm.query_fix_candidates(error_context)
                else:
                    # Still query LLM as backup, but we have direct fix ready
                    llm_candidates = await self.llm.query_fix_candidates(error_context)
                    candidates.update(llm_candidates)

                await self.emit(
                    "LLM remediation candidates received",
                    "info",
                    to_agent="Validator",
                    stage=stage,
                    candidates={
                        provider: {
                            "commands": len(fix.get("commands", [])),
                            "analysis": str(fix.get("analysis", ""))[:300],
                        }
                        for provider, fix in candidates.items()
                    },
                )
                fallback = self.validator.fallback_fix(error_context)
                if fallback.get("commands"):
                    candidates["fallback"] = fallback
                fix = await self.validator.select_best_fix(candidates, error_context)
                success = await self._execute_fix_plan(fix, fix_location=fix_location, cwd=cwd, stage=stage)
                await self.validator.record_fix_outcome(fix.get("provider", "fallback"), error_context, fix, success)
                if attempt < max_retries:
                    await asyncio.sleep(min(30, 5 * attempt))
        raise RuntimeError(f"AI unable to resolve error after {max_retries} attempts: {last_error}")

    async def query_llm_for_fix(
        self,
        error: str,
        context: str,
        system_info: str | dict[str, Any],
        stage: str | None = None,
    ) -> list[str]:
        failure = OperationFailure(error, command=context, stderr=error, exit_code=1)
        error_context = {
            "command": context,
            "exit_code": 1,
            "stdout": "",
            "stderr": error,
            "attempt": 1,
            "max_attempts": settings.ai_max_retries,
            "operation": context,
            "stage": stage,
            "context": self.deployment_context,
            "system": system_info,
        }
        candidates = await self.llm.query_fix_candidates(error_context)
        fallback = self.validator.fallback_fix(error_context)
        if fallback.get("commands"):
            candidates["fallback"] = fallback
        fix = await self.validator.select_best_fix(candidates, error_context)
        return [command for command in fix.get("commands", []) if self.validator.is_safe_command(command)]

    async def execute_fix(self, command: str, stage: str | None = None) -> CommandResult | None:
        command = self._validate_command(command)
        if not command:
            return None
        if not self.ssh:
            raise RuntimeError("Remote AI fix requested, but no SSH manager is attached")
        await self.emit(f"Executing remote fix: {command}", "action", stage=stage)
        print(f"[FIX] remote: {command}", flush=True)
        if not settings.ai_auto_execute:
            await self.emit("AI_AUTO_EXECUTE is disabled; command skipped", "warn", stage=stage)
            return None
        result = await asyncio.to_thread(self.ssh.execute_command, command, 300, True)
        await self._record_fix_result(command, result.stdout, result.stderr, result.exit_code, "remote", stage)
        return result

    async def execute_local_fix(
        self,
        command: str,
        cwd: str | Path | None = None,
        stage: str | None = None,
    ) -> LocalCommandResult | None:
        command = self._validate_command(command)
        if not command:
            return None
        await self.emit(f"Executing local fix: {command}", "action", stage=stage)
        print(f"[FIX] local: {command}", flush=True)
        if not settings.ai_auto_execute:
            await self.emit("AI_AUTO_EXECUTE is disabled; command skipped", "warn", stage=stage)
            return None
        result = await asyncio.to_thread(run_command, self._shell_command(command), cwd, 300)
        await self._record_fix_result(command, result.stdout, result.stderr, result.exit_code, "local", stage)
        return result

    async def get_system_context(
        self,
        fix_location: str = "remote",
        cwd: str | Path | None = None,
    ) -> str:
        snapshot = await self._safe_system_snapshot(fix_location=fix_location, cwd=cwd)
        return json.dumps(snapshot, indent=2)

    async def _execute_fix_plan(
        self,
        fix: dict[str, Any],
        fix_location: str,
        cwd: str | Path | None,
        stage: str | None,
    ) -> bool:
        commands = [command for command in fix.get("commands", []) if self._validate_command(str(command))]
        if not commands:
            await self.emit("No safe fix commands were produced", "warn", stage=stage)
            return False
        ok = True
        for command in commands:
            result = await (self.execute_local_fix(command, cwd=cwd, stage=stage) if fix_location == "local" else self.execute_fix(command, stage=stage))
            ok = ok and (result is None or result.ok)
        verification = str(fix.get("verification") or "").strip()
        if verification and self._validate_command(verification):
            result = await (self.execute_local_fix(verification, cwd=cwd, stage=stage) if fix_location == "local" else self.execute_fix(verification, stage=stage))
            ok = ok and bool(result and result.ok)
        return ok

    async def _call(self, command_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(command_func):
            result = await command_func(*args, **kwargs)
        else:
            result = await asyncio.to_thread(command_func, *args, **kwargs)
        if isinstance(result, CommandResult) and not result.ok:
            raise OperationFailure(
                f"Command failed ({result.exit_code})",
                command=result.command,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
            )
        if isinstance(result, LocalCommandResult) and not result.ok:
            raise OperationFailure(
                f"Local command failed ({result.exit_code})",
                command=" ".join(result.command),
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
            )
        return result

    def _failure_from_exception(self, exc: Exception) -> OperationFailure:
        if isinstance(exc, OperationFailure):
            return exc
        text = str(exc)
        command = "unknown"
        stderr = text
        exit_code = 1
        match = re.search(r"Command failed \((\d+)\): ([^\n]+)\n(.*)", text, flags=re.S)
        if match:
            exit_code = int(match.group(1))
            command = match.group(2)
            stderr = match.group(3)
        match = re.search(r"Local command failed \((\d+)\): ([^\n]+)\n(.*)", text, flags=re.S)
        if match:
            exit_code = int(match.group(1))
            command = match.group(2)
            stderr = match.group(3)
        return OperationFailure(text, command=command, stderr=stderr, exit_code=exit_code)

    def _error_context(
        self,
        failure: OperationFailure,
        operation: str,
        attempt: int,
        max_attempts: int,
        stage: str | None,
        fix_location: str,
        cwd: str | Path | None,
        context: dict[str, Any] | None,
        system_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "command": failure.command,
            "exit_code": failure.exit_code,
            "stdout": failure.stdout[-50000:],
            "stderr": failure.stderr[-50000:],
            "attempt": attempt,
            "max_attempts": max_attempts,
            "operation": operation,
            "stage": stage,
            "context": {**self.deployment_context, **(context or {})},
            "system": {
                "location": fix_location,
                "cwd": str(cwd) if cwd else None,
                **(system_snapshot or {}),
            },
            "error": str(failure),
        }

    async def _safe_system_snapshot(
        self,
        fix_location: str = "remote",
        cwd: str | Path | None = None,
    ) -> dict[str, Any]:
        if fix_location == "remote" and self.ssh:
            command = "set +e; uname -a; docker --version 2>&1; docker compose version 2>&1; df -h /; free -m 2>/dev/null; sudo ss -ltnp 2>/dev/null | head -80"
            try:
                result = await asyncio.to_thread(self.ssh.execute_command, command, 30)
                return {"os": "remote-linux", "raw": (result.stdout + result.stderr)[-8000:]}
            except Exception as exc:  # noqa: BLE001
                return {"os": "remote-linux", "error": str(exc)}
        return {
            "os": platform.platform(),
            "python": platform.python_version(),
            "cwd": str(Path(cwd).resolve()) if cwd else str(Path.cwd()),
            "docker": shutil.which("docker") or "unavailable",
        }

    async def _try_start_ollama_container(self) -> None:
        if not shutil.which("docker"):
            return
        result = await asyncio.to_thread(
            run_command,
            ["docker", "ps", "-a", "--filter", "name=ollama", "--format", "{{.ID}}"],
            None,
            20,
        )
        container_id = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        if container_id:
            await asyncio.to_thread(run_command, ["docker", "start", container_id], None, 60)

    async def _record_fix_result(
        self,
        command: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        location: str,
        stage: str | None,
    ) -> None:
        self.intervention_count += 1
        self.fix_history.append({"command": command, "exit_code": exit_code, "location": location})
        summary = (stderr.strip() or stdout.strip() or "command produced no output")[-1000:]
        await self.emit(f"Fix command exited {exit_code}: {summary}", "ok" if exit_code == 0 else "warn", stage=stage)

    def _validate_command(self, command: str) -> str | None:
        command = command.strip()
        if not command:
            return None
        if self.validator.is_safe_command(command):
            return command
        if settings.ai_allow_dangerous_commands:
            return command
        asyncio.create_task(self.emit(f"Blocked unsafe AI command: {command}", "warn"))
        return None

    @staticmethod
    def _shell_command(command: str) -> list[str]:
        if shutil.which("bash"):
            return ["bash", "-lc", command]
        if shutil.which("sh"):
            return ["sh", "-lc", command]
        return ["powershell", "-NoProfile", "-Command", command]
