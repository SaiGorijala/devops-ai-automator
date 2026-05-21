from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _sqlite_async_url(url: str) -> str:
    if url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "DevOps AI Automator")
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = _sqlite_async_url(os.getenv("DATABASE_URL", "sqlite:///./devops_ai.db"))
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-coder:6.7b")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    max_pipeline_duration: int = _int("MAX_PIPELINE_DURATION", 1800)
    ssh_timeout: int = _int("SSH_TIMEOUT", 30)
    ssh_user: str = os.getenv("SSH_USER", "ubuntu")
    remote_workspace: str = os.getenv("REMOTE_WORKSPACE", "/opt/devops-ai-automator")
    local_workspace: Path = Path(os.getenv("LOCAL_WORKSPACE", "./workspace")).resolve()
    frontend_build_dir: Path = Path(os.getenv("FRONTEND_BUILD_DIR", "./frontend/dist")).resolve()
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    )
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "change-me-before-production")
    encryption_key: str | None = os.getenv("ENCRYPTION_KEY")
    ai_auto_execute: bool = _bool("AI_AUTO_EXECUTE", True)
    ai_allow_dangerous_commands: bool = _bool("AI_ALLOW_DANGEROUS_COMMANDS", False)
    ai_max_retries: int = _int("AI_MAX_RETRIES", 3)
    default_app_port: int = _int("DEFAULT_APP_PORT", 3000)
    dockerhub_repo_name: str = os.getenv("DOCKERHUB_REPO_NAME", "devops-ai-app")


settings = Settings()

