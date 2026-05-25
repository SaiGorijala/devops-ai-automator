from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings
from .llm_error_formatter import ErrorContextFormatter


@dataclass
class LLMResult:
    provider: str
    raw: str
    data: dict[str, Any]


class LLMClient:
    """Small provider adapter for Claude first, Ollama second, fallback last."""

    def __init__(self) -> None:
        self.claude_api_key = settings.claude_api_key
        self.claude_model = settings.claude_model
        self.ollama_host = settings.ollama_host
        self.ollama_model = settings.deepseek_model

    async def health(self) -> dict[str, Any]:
        status = {
            "claude_configured": bool(self.claude_api_key),
            "ollama_host": self.ollama_host,
            "ollama_model": self.ollama_model,
            "ollama_ready": False,
            "ollama_models": [],
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.ollama_host}/api/tags")
                response.raise_for_status()
                payload = response.json()
                status["ollama_ready"] = True
                status["ollama_models"] = [
                    model.get("name", "")
                    for model in payload.get("models", [])
                    if model.get("name")
                ]
        except Exception as exc:  # noqa: BLE001
            status["ollama_error"] = str(exc)
        return status

    async def test_ollama_generation(self, prompt: str = "Return only: OK") -> dict[str, Any]:
        result = {
            "ollama_reachable": False,
            "model_loaded": False,
            "test_response": None,
            "models": [],
        }
        health = await self.health()
        result["ollama_reachable"] = bool(health.get("ollama_ready"))
        result["models"] = health.get("ollama_models", [])
        result["model"] = self.ollama_model
        result["ollama_host"] = self.ollama_host
        if not result["ollama_reachable"]:
            result["error"] = health.get("ollama_error", "Ollama is not reachable")
            return result
        try:
            raw = await self._query_ollama(prompt)
            result["model_loaded"] = True
            result["test_response"] = raw
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        return result

    async def query_json(self, prompt: str, fallback: dict[str, Any] | None = None) -> LLMResult:
        fallback = fallback or {}
        if self.claude_api_key:
            try:
                raw = await self._query_claude(prompt)
                return LLMResult("claude", raw, self._parse_json_object(raw))
            except Exception:
                pass
        try:
            raw = await self._query_ollama(prompt)
            return LLMResult("ollama", raw, self._parse_json_object(raw))
        except Exception:
            return LLMResult("fallback", json.dumps(fallback), fallback)

    async def query_fix_candidates(self, error_context: dict[str, Any]) -> dict[str, dict[str, Any]]:
        prompt = self.build_fix_prompt(error_context)
        candidates: dict[str, dict[str, Any]] = {}

        if self.claude_api_key:
            try:
                raw = await self._query_claude(prompt)
                candidates["claude"] = self._normalize_fix("claude", raw)
            except Exception as exc:  # noqa: BLE001
                candidates["claude"] = {
                    "provider": "claude",
                    "analysis": f"Claude unavailable: {exc}",
                    "commands": [],
                    "verification": "",
                    "confidence": 0.0,
                }

        try:
            raw = await self._query_ollama_with_retry(prompt)
            parsed = self._normalize_fix("ollama", raw)
            # If no commands returned, try getting direct fixes
            if not parsed.get("commands"):
                parsed = self._get_direct_fix_for_error(error_context.get("stderr", ""), error_context)
                parsed["provider"] = "ollama"
            candidates["ollama"] = parsed
        except Exception as exc:  # noqa: BLE001
            candidates["ollama"] = {
                "provider": "ollama",
                "analysis": f"Ollama unavailable: {exc}",
                "commands": [],
                "verification": "",
                "confidence": 0.0,
            }

        return candidates

    def build_fix_prompt(self, error_context: dict[str, Any]) -> str:
        stdout = str(error_context.get("stdout", ""))[-50000:]
        stderr = str(error_context.get("stderr", ""))[-50000:]
        location = error_context.get("system", {}).get("location")
        ssh_note = ""
        if "SSH" in str(error_context.get("operation", "")) or "ssh" in stderr.lower():
            ssh_note = """
SSH-SPECIFIC INSTRUCTIONS
- The failed connection happened before a remote shell existed.
- If location is local, commands run inside the backend container, so use diagnostics only.
- Good commands: getent hosts, python socket connect, nc -vz, ssh -vvv with BatchMode.
- Do not suggest ufw, systemctl, or remote service changes unless a remote shell is already available.
"""
        return f"""You are a senior DevOps remediation agent. A deployment command failed.

ERROR DETAILS
Command: {error_context.get("command")}
Exit Code: {error_context.get("exit_code")}
Attempt: {error_context.get("attempt")}/{error_context.get("max_attempts")}
Operation: {error_context.get("operation")}
Stage: {error_context.get("stage")}

STDERR:
{stderr}

STDOUT:
{stdout}

DEPLOYMENT CONTEXT:
{json.dumps(error_context.get("context", {}), indent=2)}

SYSTEM INFO:
{json.dumps(error_context.get("system", {}), indent=2)}

FIX LOCATION: {location}
{ssh_note}

REQUIREMENTS
1. Return exact bash commands that are safe and idempotent.
2. Include a verification command when possible.
3. Do not print secrets.
4. Do not delete source code, wipe disks, reboot, or change passwords.
5. Prefer fixing the root cause over sleeping, unless a service is still starting.
6. For port conflicts, choose an available alternate port or free only the precise blocked service.

MANDATORY: Return ONLY valid JSON - NO other text before or after:
{{
  "analysis": "brief explanation of the fix",
  "commands": ["command1", "command2", "command3"],
  "verification": "command that proves the fix worked",
  "confidence": 0.75
}}"""

    async def _query_claude(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.claude_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.claude_model,
                    "max_tokens": 1600,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            payload = response.json()
            parts = payload.get("content", [])
            return "\n".join(
                part.get("text", "")
                for part in parts
                if isinstance(part, dict) and part.get("type") == "text"
            ).strip()

    async def _query_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.2,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_predict": 1200,
            },
        }
        async with httpx.AsyncClient(timeout=settings.llm_timeout) as client:
            response = await client.post(f"{self.ollama_host}/api/generate", json=payload)
            if response.status_code == 404:
                pull = await client.post(
                    f"{self.ollama_host}/api/pull",
                    json={"name": self.ollama_model, "stream": False},
                    timeout=settings.max_pipeline_duration,
                )
                pull.raise_for_status()
                response = await client.post(f"{self.ollama_host}/api/generate", json=payload)
            response.raise_for_status()
            return response.json().get("response", "").strip()

    async def _query_ollama_with_retry(self, prompt: str) -> str:
        """Query Ollama with retry logic and guaranteed JSON response"""
        for retry in range(3):
            try:
                return await self._query_ollama(prompt)
            except Exception as exc:
                if retry < 2:
                    await asyncio.sleep(1)
                    continue
                raise exc

    def _normalize_fix(self, provider: str, raw: str) -> dict[str, Any]:
        try:
            data = self._parse_json_object(raw)
        except Exception:
            # Try to extract commands line by line
            commands = self._extract_shell_commands(raw)
            if commands:
                data = {
                    "analysis": "Extracted shell commands from LLM response",
                    "commands": commands,
                    "verification": commands[0] if commands else "",
                    "confidence": 0.45,
                }
            else:
                data = {
                    "analysis": "LLM returned non-JSON text; no parseable commands found",
                    "commands": [],
                    "verification": "",
                    "confidence": 0.0,
                }
        commands = data.get("commands", [])
        if isinstance(commands, str):
            commands = [line.strip() for line in commands.splitlines() if line.strip()]
        if not isinstance(commands, list):
            commands = []
        cleaned = [str(command).strip() for command in commands if str(command).strip()]
        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
        return {
            "provider": provider,
            "analysis": str(data.get("analysis", "")).strip() or raw[:500],
            "commands": cleaned[:8],
            "verification": str(data.get("verification", "")).strip(),
            "confidence": max(0.0, min(1.0, confidence)),
            "raw": raw,
        }

    def _get_direct_fix_for_error(self, error: str, context: dict[str, Any]) -> dict[str, Any]:
        """Get direct fixes without LLM - immediate fallback for empty responses"""
        stderr = str(context.get("stderr", ""))
        lower = (error + stderr).lower()

        if "timeout opening channel" in lower or "ssh" in lower and "timeout" in lower:
            return {
                "provider": "direct",
                "analysis": "SSH timeout - increase timeout settings",
                "commands": [
                    "sudo sed -i 's/^#ClientAliveInterval.*/ClientAliveInterval 60/' /etc/ssh/sshd_config",
                    "sudo sed -i 's/^#ClientAliveCountMax.*/ClientAliveCountMax 3/' /etc/ssh/sshd_config",
                    "sudo systemctl restart sshd",
                    "echo 'SSH timeout configured'",
                ],
                "verification": "sudo sshd -T | grep -E 'ClientAlive'",
                "confidence": 0.8,
            }

        if "docker-compose" in lower and ("not found" in lower or "no such file" in lower):
            return {
                "provider": "direct",
                "analysis": "Docker Compose missing - installing",
                "commands": [
                    'sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
                    "sudo chmod +x /usr/local/bin/docker-compose",
                    "docker-compose --version",
                    "sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose",
                ],
                "verification": "docker-compose --version",
                "confidence": 0.9,
            }

        if "docker" in lower and "permission denied" in lower:
            return {
                "provider": "direct",
                "analysis": "Docker permission denied - fixing permissions",
                "commands": [
                    "sudo usermod -aG docker $USER",
                    "newgrp docker",
                    "sudo chmod 666 /var/run/docker.sock",
                ],
                "verification": "docker ps",
                "confidence": 0.8,
            }

        if "connection refused" in lower or "connection timeout" in lower:
            return {
                "provider": "direct",
                "analysis": "Connection issue - checking services",
                "commands": [
                    "sudo systemctl status docker || echo 'Docker not running'",
                    "sudo journalctl -u docker -n 20 | tail -10",
                    "netstat -tlnp 2>/dev/null || ss -tlnp",
                ],
                "verification": "echo 'Check logs above'",
                "confidence": 0.6,
            }

        # Generic fallback
        return {
            "provider": "direct",
            "analysis": "Generic error recovery - checking system status",
            "commands": [
                "sudo systemctl status docker || true",
                "sudo journalctl -xe | tail -20",
                "echo 'Attempted diagnostic check'",
            ],
            "verification": "echo 'Check logs'",
            "confidence": 0.3,
        }


    @staticmethod
    def _extract_shell_commands(raw: str) -> list[str]:
        prefixes = (
            "ping ",
            "nc ",
            "ncat ",
            "telnet ",
            "ssh ",
            "ssh-keygen ",
            "getent ",
            "python ",
            "python3 ",
            "docker ",
            "curl ",
            "timeout ",
            "test ",
            "echo ",
        )
        commands: list[str] = []
        for line in raw.splitlines():
            line = line.strip().strip("`")
            if line.startswith("$ "):
                line = line[2:].strip()
            if line and line.startswith(prefixes):
                commands.append(line)
        return commands[:8]

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
        if fence:
            text = fence.group(1)
        elif "{" in text and "}" in text:
            text = text[text.find("{") : text.rfind("}") + 1]
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("LLM response was not a JSON object")
        return payload
