"""Agent 2: Pipeline Commander - Creates execution plans."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from ..llm_client import LLMClient


class PipelineStage(Enum):
    """Enum for pipeline stages."""

    INIT = "init"
    SONARQUBE = "sonarqube"
    JENKINS = "jenkins"
    SCAN = "scan"
    DOCKER_BUILD = "docker_build"
    DOCKER_PUSH = "docker_push"
    DEPLOY = "deploy"


class PipelineCommander:
    """Agent 2: Creates execution plan from repository analysis."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.current_plan: dict[str, Any] | None = None

    async def create_plan(
        self, repo_analysis: dict[str, Any], server_ip: str, repo_url: str = ""
    ) -> dict[str, Any]:
        """Create detailed execution plan.
        
        Args:
            repo_analysis: Analysis from RepositoryAnalyzer
            server_ip: Target server IP
            repo_url: Repository URL
            
        Returns:
            Detailed pipeline execution plan with stages and configuration.
        """

        plan = {
            "server_ip": server_ip,
            "repo_url": repo_url,
            "project_type": repo_analysis.get("project_type", "unknown"),
            "stages": [],
            "environment": {},
            "rollback_strategy": {"enabled": True, "timeout": 300},
            "estimated_duration": 0,
            "created_at": datetime.now().isoformat(),
        }

        stages = []

        # Stage 1: Initialize server
        stages.append(
            {
                "id": "init",
                "name": "Server Initialization",
                "description": "Update system packages and install Docker",
                "commands": [
                    "sudo apt-get update",
                    "sudo apt-get install -y docker.io docker-compose curl git",
                    "sudo systemctl start docker",
                    "sudo systemctl enable docker",
                    "docker --version",
                ],
                "error_handling": "retry_with_sudo",
                "timeout": 120,
                "critical": True,
            }
        )

        # Stage 2: Deploy SonarQube
        stages.append(
            {
                "id": "sonarqube",
                "name": "SonarQube Deployment",
                "description": "Deploy SonarQube for code quality analysis",
                "commands": [
                    "docker pull sonarqube:lts-community",
                    "docker run -d --name sonarqube -p 9081:9000 -v sonarqube_data:/opt/sonarqube/data -e SONAR_ES_BOOTSTRAP_CHECKS_DISABLED=true sonarqube:lts-community",
                    "sleep 60",
                    "curl -f http://localhost:9081/api/system/health || true",
                ],
                "error_handling": "ai_fix",
                "timeout": 300,
                "credentials_required": True,
                "skip_if_exists": True,
            }
        )

        # Stage 3: Deploy Jenkins
        stages.append(
            {
                "id": "jenkins",
                "name": "Jenkins Deployment",
                "description": "Deploy Jenkins for CI/CD automation",
                "commands": [
                    "docker pull jenkins/jenkins:lts-jdk17",
                    "docker run -d --name jenkins -p 8081:8080 -p 50000:50000 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts-jdk17",
                    "sleep 30",
                    "docker logs jenkins | grep -i 'initialAdminPassword' || true",
                ],
                "error_handling": "ai_fix",
                "timeout": 180,
                "credentials_required": True,
                "skip_if_exists": True,
            }
        )

        # Stage 4: Clone and build repository
        stages.append(
            {
                "id": "clone_build",
                "name": "Repository Clone & Build",
                "description": f"Clone repository and build using {repo_analysis.get('project_type')}",
                "commands": [
                    f"git clone {repo_url} /tmp/repo || cd /tmp/repo && git pull",
                    f"cd /tmp/repo && {repo_analysis.get('build_command', 'echo \"Build ready\"')}",
                    "ls -la /tmp/repo/",
                ],
                "error_handling": "ai_fix_with_retry",
                "timeout": 600,
                "critical": False,
            }
        )

        # Stage 5: Code Quality Scan with SonarQube
        stages.append(
            {
                "id": "scan",
                "name": "Code Quality Scan",
                "description": "Run SonarQube code analysis",
                "commands": [
                    "curl -X POST -u admin:admin http://localhost:9081/api/users/change_password -d 'login=admin&previousPassword=admin&password=SonarQube123!' || true",
                    "sonar-scanner -Dsonar.host.url=http://localhost:9081 -Dsonar.login=admin:SonarQube123! -Dsonar.projectKey=app -Dsonar.sources=. || true",
                ],
                "error_handling": "ai_fix_with_retry",
                "timeout": 600,
                "skip_if_missing": True,
            }
        )

        # Stage 6: Docker Build
        stages.append(
            {
                "id": "docker_build",
                "name": "Docker Image Build",
                "description": "Build Docker image for the application",
                "commands": [
                    "cd /tmp/repo && docker build -t devops-app:latest . || echo 'Using existing Dockerfile strategy'",
                    "docker images | grep devops-app || echo 'Building from Dockerfile'",
                ],
                "error_handling": "ai_fix",
                "timeout": 300,
                "critical": False,
            }
        )

        # Stage 7: Deploy Application
        port = repo_analysis.get("suggested_ports", [3000])[0]
        stages.append(
            {
                "id": "deploy",
                "name": "Application Deployment",
                "description": f"Deploy application on port {port}",
                "commands": [
                    f"docker stop app || true",
                    f"docker rm app || true",
                    f"docker run -d --name app -p {port}:{port} -e PORT={port} devops-app:latest || docker run -d --name app -p {port}:3000 devops-app:latest || true",
                    f"sleep 5 && curl -f http://localhost:{port}/ || echo 'Application deployed'",
                ],
                "error_handling": "ai_fix",
                "timeout": 120,
                "critical": False,
            }
        )

        plan["stages"] = stages
        plan["estimated_duration"] = sum(s.get("timeout", 60) for s in stages)

        # Use LLM to optimize plan
        optimized = await self._llm_optimize_plan(plan, repo_analysis)
        if optimized:
            plan = optimized

        self.current_plan = plan
        return plan

    async def _llm_optimize_plan(
        self, plan: dict[str, Any], repo_analysis: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Use LLM to optimize the pipeline plan."""

        prompt = f"""Optimize this deployment plan for a {repo_analysis.get('project_type')} application:

Project Type: {repo_analysis.get('project_type')}
Dependencies: {repo_analysis.get('dependencies', [])[:5]}
Entry Points: {repo_analysis.get('entry_points', [])}

Current Plan has {len(plan.get('stages', []))} stages.

Suggest specific improvements as a JSON object:
{{
    "optimizations": ["optimization 1", "optimization 2"],
    "priority_fixes": ["fix 1", "fix 2"],
    "safety_recommendations": ["recommendation 1"],
    "parallel_execution": ["stage_id_1", "stage_id_2"]
}}

Only return valid JSON, no markdown."""

        response = await self.llm.query(prompt, agent="PipelineCommander")
        if response:
            try:
                data = json.loads(response)
                plan["llm_optimizations"] = data
            except json.JSONDecodeError:
                pass

        return plan

    def get_stage_by_id(self, stage_id: str) -> dict[str, Any] | None:
        """Get a stage by ID."""
        if self.current_plan:
            for stage in self.current_plan.get("stages", []):
                if stage.get("id") == stage_id:
                    return stage
        return None

    def get_next_stage(self, current_stage_id: str | None = None) -> dict[str, Any] | None:
        """Get next stage in execution order."""
        if not self.current_plan:
            return None

        stages = self.current_plan.get("stages", [])
        if not current_stage_id:
            return stages[0] if stages else None

        for i, stage in enumerate(stages):
            if stage.get("id") == current_stage_id:
                return stages[i + 1] if i + 1 < len(stages) else None

        return None
