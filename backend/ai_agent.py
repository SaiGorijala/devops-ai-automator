from __future__ import annotations

import asyncio
import inspect
import platform
import re
import shlex
import shutil
from pathlib import Path
from typing import Any, Callable

import httpx

from .config import settings
from .process import LocalCommandResult, run_command
from .session_store import SessionStore, session_store
from .ssh_manager import CommandResult, SSHManager


class AIAgent:
    def __init__(
        self,
        ssh: SSHManager | None = None,
        session_id: str | None = None,
        store: SessionStore = session_store,
    ) -> None:
        self.ssh = ssh
        self.session_id = session_id
        self.store = store
        self.ollama_host = settings.ollama_host
        self.model = settings.deepseek_model
        self.intervention_count = 0
        self.fix_history: list[dict[str, Any]] = []

    async def monitor_and_fix(
        self,
        command_func: Callable[..., Any],
        *args: Any,
        stage: str | None = None,
        fix_location: str = "remote",
        cwd: str | Path | None = None,
        **kwargs: Any,
    ) -> Any:
        max_retries = settings.ai_max_retries
        context = getattr(command_func, "__qualname__", getattr(command_func, "__name__", "operation"))
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                return await self._call(command_func, *args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - the AI wrapper intentionally catches all operation failures.
                last_error = exc
                error_msg = str(exc)
                await self.log_error(error_msg, context, stage=stage, attempt=attempt)
                system_info = await self._safe_system_context(fix_location=fix_location, cwd=cwd)
                commands = await self.query_llm_for_fix(
                    error=error_msg,
                    context=context,
                    system_info=system_info,
                    stage=stage,
                )
                if not commands:
                    commands = self.dynamic_error_patterns(error_msg)
                if not commands:
                    await self.log_ai_action(
                        f"No AI fix commands were produced for {context}; retrying after delay",
                        stage=stage,
                        intervention_type="warn",
                    )
                for command in commands:
                    if fix_location == "local":
                        await self.execute_local_fix(command, cwd=cwd, stage=stage)
                    else:
                        await self.execute_fix(command, stage=stage)
                if attempt < max_retries:
                    await asyncio.sleep(5)
        raise RuntimeError(f"AI unable to resolve error after {max_retries} attempts: {last_error}")

    async def query_llm_for_fix(
        self,
        error: str,
        context: str,
        system_info: str,
        stage: str | None = None,
    ) -> list[str]:
        prompt = f"""You are a DevOps AI. Fix this error.

Error: {error}
Operation: {context}
System: {system_info}

Return ONLY executable bash commands, one per line, no markdown and no explanations.
Commands must be idempotent and safe to retry.
Do not print secrets. Do not delete application source code.

Your fix commands:"""
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await self._generate_with_model_recovery(client, prompt, stage)
                raw = response.json().get("response", "")
        except Exception as exc:  # noqa: BLE001
            await self.log_ai_action(
                f"Ollama unavailable, using fallback recovery patterns: {exc}",
                stage=stage,
                intervention_type="warn",
            )
            return []

        commands = self._clean_commands(raw)
        if commands:
            await self.log_ai_action(
                f"DeepSeek proposed {len(commands)} fix command(s) for {context}",
                stage=stage,
                intervention_type="action",
            )
        return commands

    async def _generate_with_model_recovery(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        stage: str | None,
    ) -> httpx.Response:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.3,
        }
        response = await client.post(f"{self.ollama_host}/api/generate", json=payload)
        if response.status_code != 404:
            response.raise_for_status()
            return response

        detail = response.text[:300]
        await self.log_ai_action(
            f"Ollama returned 404 for model '{self.model}'. Pulling model before retry. Detail: {detail}",
            stage=stage,
            intervention_type="warn",
        )
        pull_response = await client.post(
            f"{self.ollama_host}/api/pull",
            json={"name": self.model, "stream": False},
            timeout=settings.max_pipeline_duration,
        )
        pull_response.raise_for_status()
        retry = await client.post(f"{self.ollama_host}/api/generate", json=payload)
        retry.raise_for_status()
        return retry

    async def execute_fix(self, command: str, stage: str | None = None) -> CommandResult | None:
        original = command
        command = self._validate_command(command)
        if not command:
            await self.log_ai_action(f"Blocked unsafe AI command: {original}", stage=stage, intervention_type="warn")
            return None
        if not self.ssh:
            raise RuntimeError("Remote AI fix requested, but no SSH manager is attached")
        await self.log_ai_action(f"Executing remote fix: {command}", stage=stage)
        if not settings.ai_auto_execute:
            await self.log_ai_action("AI_AUTO_EXECUTE is disabled; command skipped", stage=stage, intervention_type="warn")
            return None
        result = await asyncio.to_thread(self.ssh.execute_command, command, 180, True)
        await self.log_ai_result(result.stdout, result.stderr, result.exit_code, stage=stage)
        self._record_fix(command, result.exit_code, "remote")
        return result

    async def execute_local_fix(
        self,
        command: str,
        cwd: str | Path | None = None,
        stage: str | None = None,
    ) -> LocalCommandResult | None:
        original = command
        command = self._validate_command(command)
        if not command:
            await self.log_ai_action(f"Blocked unsafe AI command: {original}", stage=stage, intervention_type="warn")
            return None
        await self.log_ai_action(f"Executing local fix: {command}", stage=stage)
        if not settings.ai_auto_execute:
            await self.log_ai_action("AI_AUTO_EXECUTE is disabled; command skipped", stage=stage, intervention_type="warn")
            return None
        shell = self._shell_command(command)
        result = await asyncio.to_thread(run_command, shell, cwd, 300)
        await self.log_ai_result(result.stdout, result.stderr, result.exit_code, stage=stage)
        self._record_fix(command, result.exit_code, "local")
        return result

    async def get_system_context(
        self,
        fix_location: str = "remote",
        cwd: str | Path | None = None,
    ) -> str:
        if fix_location == "remote" and self.ssh:
            result = await asyncio.to_thread(
                self.ssh.execute_command,
                "set +e; uname -a; docker --version 2>&1; df -h /; free -m 2>/dev/null; sudo ss -ltnp 2>/dev/null | head -50",
                30,
            )
            return (result.stdout + result.stderr)[-4000:]
        cwd_text = str(Path(cwd).resolve()) if cwd else str(Path.cwd())
        return f"local_os={platform.platform()}\npython={platform.python_version()}\ncwd={cwd_text}"

    async def _safe_system_context(
        self,
        fix_location: str = "remote",
        cwd: str | Path | None = None,
    ) -> str:
        try:
            return await self.get_system_context(fix_location=fix_location, cwd=cwd)
        except Exception as exc:  # noqa: BLE001
            return f"system_context_unavailable={exc}"

    def fallback_for_error(self, error: str) -> list[str]:
        return self.dynamic_error_patterns(error)

    def dynamic_error_patterns(self, error: str = "") -> list[str]:
        lower = error.lower()
        if "docker" in lower and "permission denied" in lower:
            user = self.ssh.username if self.ssh else "$USER"
            return [
                "sudo systemctl restart docker || true",
                f"sudo usermod -aG docker {shlex.quote(user)} || true",
            ]
        if "no such file or directory" in lower and "'docker'" in lower:
            return [
                "if command -v apt-get >/dev/null; then apt-get update && apt-get install -y docker.io; elif command -v apk >/dev/null; then apk add --no-cache docker-cli; fi",
                "docker --version",
            ]
        if "no such file or directory" in lower and "'sonar-scanner'" in lower:
            return [self._install_sonar_scanner_command()]
        if "sonar-scanner" in lower and ("not found" in lower or "command not found" in lower):
            return [self._install_sonar_scanner_command()]
        if "port" in lower and ("already in use" in lower or "bind" in lower or "allocated" in lower):
            match = re.search(r":(\d{2,5})", error)
            port = match.group(1) if match else "3000"
            return [f"sudo fuser -k {port}/tcp || true"]
        if "npm: command not found" in lower or "node: command not found" in lower:
            return [
                "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -",
                "sudo apt-get install -y nodejs",
            ]
        if "sonarqube" in lower and ("timeout" in lower or "timed out" in lower):
            return [
                "sudo docker ps --format '{{.Names}}' | grep sonarqube | xargs -r sudo docker restart",
                "sleep 30",
            ]
        if "api/system/status" in lower and ("timeout" in lower or "timed out" in lower):
            return [
                "sudo docker ps --format '{{.Names}}' | grep sonarqube | xargs -r sudo docker restart",
                "sleep 30",
            ]
        if "timeout opening channel" in lower:
            return ["sleep 15"]
        if "authentication failed" in lower and "git" in lower:
            return ["git config --global --unset credential.helper || true"]
        if "no space left" in lower:
            return ["docker system prune -af || sudo docker system prune -af"]
        if "temporary failure resolving" in lower or "could not resolve" in lower:
            return ["sudo systemctl restart systemd-resolved || true"]
        return []

    @staticmethod
    def _install_sonar_scanner_command() -> str:
        return (
            "if command -v apt-get >/dev/null; then "
            "apt-get update && apt-get install -y curl unzip openjdk-17-jre-headless; "
            "fi; "
            "cd /tmp && "
            "curl -fsSLo sonar-scanner.zip "
            "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/"
            "sonar-scanner-cli-5.0.1.3006-linux.zip && "
            "rm -rf /opt/sonar-scanner && "
            "unzip -q -o sonar-scanner.zip -d /opt && "
            "mv /opt/sonar-scanner-* /opt/sonar-scanner && "
            "ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner && "
            "sonar-scanner --version"
        )

    async def log_error(
        self,
        error_msg: str,
        context: str,
        stage: str | None = None,
        attempt: int | None = None,
    ) -> None:
        prefix = f"Attempt {attempt}: " if attempt else ""
        if self.session_id:
            await self.store.append_log(
                self.session_id,
                f"{prefix}{context} failed: {error_msg}",
                "error",
                stage=stage,
            )
        await self.log_ai_action(
            f"{context} failed; analyzing recovery path",
            stage=stage,
            intervention_type="warn",
        )

    async def log_ai_action(
        self,
        message: str,
        stage: str | None = None,
        intervention_type: str = "action",
        **extra: Any,
    ) -> None:
        if self.session_id:
            await self.store.add_ai_intervention(
                self.session_id,
                message,
                intervention_type=intervention_type,
                stage=stage,
                **extra,
            )

    async def log_ai_result(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        stage: str | None = None,
    ) -> None:
        summary = (stderr.strip() or stdout.strip() or "command produced no output")[-800:]
        level = "ok" if exit_code == 0 else "warn"
        if self.session_id:
            await self.store.add_ai_intervention(
                self.session_id,
                f"Fix command exited {exit_code}: {summary}",
                intervention_type=level,
                stage=stage,
            )

    async def _call(self, command_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if inspect.iscoroutinefunction(command_func):
            return await command_func(*args, **kwargs)
        result = await asyncio.to_thread(command_func, *args, **kwargs)
        if isinstance(result, CommandResult):
            result.raise_for_error()
        if isinstance(result, LocalCommandResult):
            result.raise_for_error()
        return result

    def _record_fix(self, command: str, exit_code: int, location: str) -> None:
        self.intervention_count += 1
        self.fix_history.append(
            {
                "command": command,
                "exit_code": exit_code,
                "location": location,
            }
        )

    def _clean_commands(self, response: str) -> list[str]:
        commands: list[str] = []
        in_code_fence = False
        for raw_line in response.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("```"):
                in_code_fence = not in_code_fence
                continue
            if line.startswith("#"):
                continue
            if line.startswith("$ "):
                line = line[2:].strip()
            if re.match(r"(?i)^(here|explanation|note|these|the following)\b", line):
                continue
            if self._is_safe_command(line):
                commands.append(line)
            elif self.session_id:
                # This is intentionally not awaited; _clean_commands is sync.
                pass
        return commands[:8]

    def _validate_command(self, command: str) -> str | None:
        command = command.strip()
        if not command:
            return None
        if not self._is_safe_command(command):
            if settings.ai_allow_dangerous_commands:
                return command
            return None
        return command

    @staticmethod
    def _is_safe_command(command: str) -> bool:
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

    @staticmethod
    def _shell_command(command: str) -> list[str]:
        if shutil.which("bash"):
            return ["bash", "-lc", command]
        if shutil.which("sh"):
            return ["sh", "-lc", command]
        return ["powershell", "-NoProfile", "-Command", command]
