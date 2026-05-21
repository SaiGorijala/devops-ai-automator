from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DeploymentInputs(BaseModel):
    repo_url: str
    github_token: str | None = None
    server_ip: str
    pem_file_content: str
    dockerhub_user: str
    dockerhub_pass: str
    branch: str = "main"
    ssh_user: str | None = None


class DeployRequest(BaseModel):
    repo_url: str | None = None
    github_token: str | None = None
    server_ip: str | None = None
    pem_file_content: str | None = None
    dockerhub_user: str | None = None
    dockerhub_pass: str | None = None
    branch: str = "main"
    ssh_user: str | None = None

    # Compatibility with the supplied React component's field names.
    repo: str | None = None
    token: str | None = None
    ip: str | None = None
    pem: str | None = None
    dhUser: str | None = None
    dhPass: str | None = None

    def to_inputs(self) -> DeploymentInputs:
        repo_url = self.repo_url or self.repo
        server_ip = self.server_ip or self.ip
        pem_file_content = self.pem_file_content or self.pem
        dockerhub_user = self.dockerhub_user or self.dhUser
        dockerhub_pass = self.dockerhub_pass or self.dhPass
        missing = [
            name
            for name, value in {
                "repo_url": repo_url,
                "server_ip": server_ip,
                "pem_file_content": pem_file_content,
                "dockerhub_user": dockerhub_user,
                "dockerhub_pass": dockerhub_pass,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        return DeploymentInputs(
            repo_url=repo_url or "",
            github_token=self.github_token or self.token,
            server_ip=server_ip or "",
            pem_file_content=pem_file_content or "",
            dockerhub_user=dockerhub_user or "",
            dockerhub_pass=dockerhub_pass or "",
            branch=self.branch or "main",
            ssh_user=self.ssh_user,
        )


class DeployResponse(BaseModel):
    session_id: str


class PipelineEventPayload(BaseModel):
    type: Literal["log", "ai_action", "stage_update", "progress", "credentials", "error", "status"]
    data: dict[str, Any]
    timestamp: datetime


class StatusResponse(BaseModel):
    session_id: str = Field(alias="id")
    status: str
    progress: int
    current_stage: str | None
    stages: dict[str, str]
    logs: list[dict[str, Any]]
    ai_interventions: list[dict[str, Any]]
    outputs: dict[str, Any]
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

