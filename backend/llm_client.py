from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings


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
            raw = await self._query_ollama(prompt)
            candidates["ollama"] = self._normalize_fix("ollama", raw)
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

REQUIREMENTS
1. Return exact bash commands that are safe and idempotent.
2. Include a verification command when possible.
3. Do not print secrets.
4. Do not delete source code, wipe disks, reboot, or change passwords.
5. Prefer fixing the root cause over sleeping, unless a service is still starting.
6. For port conflicts, choose an available alternate port or free only the precise blocked service.

Return ONLY valid JSON:
{{
  "analysis": "brief explanation",
  "commands": ["command1", "command2"],
  "verification": "command that proves the fix worked",
  "confidence": 0.0
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

    def _normalize_fix(self, provider: str, raw: str) -> dict[str, Any]:
        data = self._parse_json_object(raw)
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
