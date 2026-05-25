from __future__ import annotations

import asyncio
import shlex
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .config import settings
from .docker_builder import DockerBuilder
from .docker_orchestrator import DockerOrchestrator, JenkinsInfo, SonarInfo
from .github_manager import GitHubManager
from .llm_client import LLMClient
from .multi_agent import PipelineCommanderAgent, RemediationAgent, RepositoryAnalyzerAgent, ValidatorAgent
from .schemas import DeploymentInputs
from .session_store import session_store
from .sonar_scanner import ScanResult, SonarScanner, Vulnerability
from .ssh_manager import SSHManager


STAGE_PROGRESS = {
    "init": (2, 14),
    "sonar": (15, 29),
    "jenkins": (30, 42),
    "scan": (43, 60),
    "docker": (61, 74),
    "push": (75, 86),
    "deploy": (87, 98),
}


class PipelineOrchestrator:
    async def execute_pipeline(self, session_id: str, inputs: DeploymentInputs) -> None:
        llm = LLMClient()
        validator = ValidatorAgent(session_id=session_id, llm=llm)
        ai = RemediationAgent(session_id=session_id, llm=llm, validator=validator)
        try:
            await asyncio.wait_for(
                self._execute(session_id, inputs, ai, validator, llm),
                timeout=settings.max_pipeline_duration,
            )
        except Exception as exc:  # noqa: BLE001
            await session_store.append_log(session_id, f"Pipeline failed: {exc}", "error")
            await session_store.fail(session_id, str(exc))
        finally:
            if ai.ssh:
                ai.ssh.close()

    async def _execute(
        self,
        session_id: str,
        inputs: DeploymentInputs,
        ai: RemediationAgent,
        validator: ValidatorAgent,
        llm: LLMClient,
    ) -> None:
        await session_store.append_log(session_id, f"Pipeline started for {inputs.repo_url}", "info")
        await session_store.add_ai_intervention(
            session_id,
            f"Multi-agent system online: Claude={bool(settings.claude_api_key)} Ollama={settings.deepseek_model} @ {settings.ollama_host}",
            intervention_type="ok",
        )
        await ai.ensure_llm_available()

        github = GitHubManager(session_id)
        analyzer = RepositoryAnalyzerAgent(session_id=session_id, llm=llm)
        commander = PipelineCommanderAgent(session_id=session_id, llm=llm)
        repo_analysis = await analyzer.analyze_repository(github, inputs, ai)
        deployment_plan = await commander.create_plan(repo_analysis)
        ai.deployment_context = {
            "repo_analysis": {
                key: value
                for key, value in repo_analysis.items()
                if key not in {"repo_path"}
            },
            "deployment_plan": deployment_plan,
        }
        repo_path = Path(repo_analysis["repo_path"])
        project_type = str(deployment_plan.get("project_type") or repo_analysis.get("project_type") or "unknown")

        await self._start_stage(session_id, "init")
        ssh: SSHManager = await ai.monitor_and_fix(
            SSHManager.connect,
            inputs.server_ip,
            inputs.pem_file_content,
            inputs.ssh_user,
            settings.ssh_timeout,
            stage="init",
            fix_location="local",
            context={
                "server_ip": inputs.server_ip,
                "ssh_user": inputs.ssh_user or settings.ssh_user,
                "error_type": "SSH_connection_failure",
            },
        )
        ai.ssh = ssh
        server_host = ssh.server_ip
        await session_store.append_log(session_id, f"SSH connected to {server_host} as {ssh.username}", "ok", stage="init")
        await ai.monitor_and_fix(ssh.install_docker, stage="init", fix_location="remote")
        await session_store.append_log(session_id, "Docker is installed and running", "ok", stage="init")
        await ai.monitor_and_fix(ssh.install_docker_compose, stage="init", fix_location="remote")
        await session_store.append_log(session_id, "Docker Compose is available", "ok", stage="init")
        await self._finish_stage(session_id, "init")

        docker_ops = DockerOrchestrator(ssh, session_id)

        await self._start_stage(session_id, "sonar")
        sonar_info: SonarInfo = await ai.monitor_and_fix(
            docker_ops.deploy_sonarqube,
            server_host,
            stage="sonar",
            fix_location="remote",
        )
        await session_store.append_log(session_id, f"SonarQube ready at {sonar_info.url}", "ok", stage="sonar")
        await self._finish_stage(session_id, "sonar")

        await self._start_stage(session_id, "jenkins")
        jenkins_info: JenkinsInfo = await ai.monitor_and_fix(
            docker_ops.deploy_jenkins,
            server_host,
            stage="jenkins",
            fix_location="remote",
        )
        await session_store.append_log(session_id, f"Jenkins ready at {jenkins_info.url}", "ok", stage="jenkins")
        await self._finish_stage(session_id, "jenkins")

        await self._start_stage(session_id, "scan")
        await session_store.append_log(
            session_id,
            f"Repository analysis ready; detected project type: {project_type}",
            "ok",
            stage="scan",
        )
        scanner = SonarScanner()
        scan_result = await self._run_sonar_scan(ai, scanner, repo_path, sonar_info, session_id)
        if scan_result.vulnerabilities:
            await self._fix_vulnerabilities(ai, scan_result.vulnerabilities, repo_path, session_id)
            await session_store.append_log(session_id, "Re-running SonarQube scan after AI fixes", "info", stage="scan")
            scan_result = await self._run_sonar_scan(ai, scanner, repo_path, sonar_info, session_id)
        if not scan_result.passed:
            raise RuntimeError("SonarQube quality gate failed after AI remediation")
        await session_store.append_log(session_id, "SonarQube quality gate passed", "ok", stage="scan")
        await self._finish_stage(session_id, "scan")

        builder = DockerBuilder()
        commit_sha = github.commit_sha(repo_path)
        image_base = f"{inputs.dockerhub_user}/{settings.dockerhub_repo_name}"
        image_tag = f"{image_base}:{commit_sha}"
        latest_tag = f"{image_base}:latest"

        await self._start_stage(session_id, "docker")
        await ai.monitor_and_fix(
            builder.detect_or_generate_dockerfile,
            repo_path,
            project_type,
            deployment_plan,
            stage="docker",
            fix_location="local",
            cwd=repo_path,
        )
        await session_store.append_log(session_id, "Dockerfile ready", "ok", stage="docker")
        image_id = await ai.monitor_and_fix(
            builder.build_image,
            repo_path,
            image_tag,
            stage="docker",
            fix_location="local",
            cwd=repo_path,
        )
        await session_store.append_log(session_id, f"Docker image built: {image_id[:24]}", "ok", stage="docker")
        await self._finish_stage(session_id, "docker")

        await self._start_stage(session_id, "push")
        await ai.monitor_and_fix(
            builder.login_dockerhub,
            inputs.dockerhub_user,
            inputs.dockerhub_pass,
            stage="push",
            fix_location="local",
        )
        await session_store.append_log(session_id, "DockerHub login succeeded", "ok", stage="push")
        pushed_tags = await ai.monitor_and_fix(
            builder.multi_tag_push,
            image_tag,
            [image_tag, latest_tag],
            stage="push",
            fix_location="local",
        )
        await session_store.append_log(session_id, f"Pushed image tags: {', '.join(pushed_tags)}", "ok", stage="push")
        await self._finish_stage(session_id, "push")

        await self._start_stage(session_id, "deploy")
        container_port = builder.infer_container_port(repo_path, project_type, deployment_plan)
        app_url = await ai.monitor_and_fix(
            self.deploy_application,
            ssh,
            server_host,
            image_tag,
            inputs.dockerhub_user,
            inputs.dockerhub_pass,
            container_port,
            session_id,
            stage="deploy",
            fix_location="remote",
        )
        validation = await validator.validate_deployment(ssh, app_url, stage="deploy")
        if settings.agent_validation_enabled and not validation.get("success"):
            raise RuntimeError(f"Deployment validation failed: {validation.get('output') or validation.get('reason')}")
        await session_store.append_log(session_id, f"Application live at {app_url}", "ok", stage="deploy")
        await self._finish_stage(session_id, "deploy")

        outputs = {
            "sonar": asdict(sonar_info),
            "jenkins": asdict(jenkins_info),
            "app": {"url": app_url},
            "docker": {
                "image": image_tag,
                "latest": latest_tag,
                "pull": f"docker pull {image_tag}",
            },
            "scan": {
                "project_key": scan_result.project_key,
                "quality_gate_passed": scan_result.passed,
                "vulnerabilities_remaining": len(scan_result.vulnerabilities),
            },
            "repo_analysis": {
                key: value
                for key, value in repo_analysis.items()
                if key not in {"repo_path"}
            },
            "deployment_plan": deployment_plan,
            "validation": validation,
            "ai_interventions": ai.intervention_count,
            "ai_fix_history": ai.fix_history,
        }
        await session_store.complete(session_id, outputs)
        await session_store.append_log(session_id, "Pipeline completed successfully", "success")
        await session_store.add_ai_intervention(
            session_id,
            f"Pipeline complete; {ai.intervention_count} AI fix command(s) executed",
            intervention_type="ok",
        )

    async def _run_sonar_scan(
        self,
        ai: RemediationAgent,
        scanner: SonarScanner,
        repo_path: Path,
        sonar_info: SonarInfo,
        session_id: str,
    ) -> ScanResult:
        result: ScanResult = await ai.monitor_and_fix(
            scanner.run_scan,
            repo_path,
            sonar_info.url,
            sonar_info.token,
            f"devops-ai-{session_id[:8]}",
            stage="scan",
            fix_location="local",
            cwd=repo_path,
        )
        if result.vulnerabilities:
            await session_store.append_log(
                session_id,
                f"SonarQube found {len(result.vulnerabilities)} high-priority issue(s)",
                "warn",
                stage="scan",
            )
        return result

    async def _fix_vulnerabilities(
        self,
        ai: RemediationAgent,
        vulnerabilities: list[Vulnerability],
        repo_path: Path,
        session_id: str,
    ) -> None:
        for index, vuln in enumerate(vulnerabilities[:5], start=1):
            target = f"{vuln.file or vuln.component}:{vuln.line or '?'}"
            await session_store.add_ai_intervention(
                session_id,
                f"Fixing vulnerability {index}/{min(len(vulnerabilities), 5)}: {vuln.severity} {vuln.message} at {target}",
                intervention_type="action",
                stage="scan",
            )
            commands = await ai.query_llm_for_fix(
                error=(
                    f"Fix {vuln.type} vulnerability in repository {repo_path}. "
                    f"File: {target}. Rule: {vuln.rule}. Message: {vuln.message}. "
                    "Patch the code in-place using shell commands."
                ),
                context="vulnerability_patch",
                system_info=await ai.get_system_context(fix_location="local", cwd=repo_path),
                stage="scan",
            )
            for command in commands:
                await ai.execute_local_fix(command, cwd=repo_path, stage="scan")

    def deploy_application(
        self,
        ssh: SSHManager,
        server_ip: str,
        image_tag: str,
        dockerhub_user: str,
        dockerhub_pass: str,
        container_port: int,
        session_id: str,
    ) -> str:
        host_port = ssh.first_available_port(settings.default_app_port)
        stack = f"devops-app-{session_id[:12]}"
        remote_dir = f"{settings.remote_workspace}/{stack}"
        compose = f"""services:
  app:
    image: {image_tag}
    container_name: {stack}
    restart: unless-stopped
    ports:
      - "{host_port}:{container_port}"
    environment:
      PORT: "{container_port}"
"""
        ssh.transfer_file(compose, f"{remote_dir}/docker-compose.yml")
        password_file = f"/tmp/devops-ai-docker-pass-{session_id[:12]}"
        ssh.transfer_file(dockerhub_pass, password_file, mode="0600")
        login_cmd = (
            f"sudo docker login -u {shlex.quote(dockerhub_user)} --password-stdin < {shlex.quote(password_file)}; "
            "status=$?; "
            f"rm -f {shlex.quote(password_file)}; "
            "exit $status"
        )
        ssh.execute_command(login_cmd, timeout=120, get_pty=True).raise_for_error()
        ssh.execute_command(
            f"cd {shlex.quote(remote_dir)}; sudo docker compose pull; sudo docker compose up -d",
            timeout=900,
            get_pty=True,
        ).raise_for_error()
        deadline = time.time() + 120
        last = ""
        while time.time() < deadline:
            result = ssh.execute_command(
                f"curl -fsS http://127.0.0.1:{host_port}/health "
                f"|| curl -fsS http://127.0.0.1:{host_port}/ "
                f"|| sudo docker ps --filter name={shlex.quote(stack)} --filter status=running --format '{{{{.Names}}}}'",
                timeout=15,
            )
            last = result.stdout.strip() + result.stderr.strip()
            if result.ok and last:
                return f"http://{server_ip}:{host_port}"
            time.sleep(5)
        raise TimeoutError(f"Application did not become healthy on port {host_port}. Last output: {last}")

    async def _start_stage(self, session_id: str, stage: str) -> None:
        start, _ = STAGE_PROGRESS[stage]
        await session_store.set_stage(session_id, stage, "running", start)
        await session_store.append_log(session_id, f"Stage started: {stage}", "stage", stage=stage)

    async def _finish_stage(self, session_id: str, stage: str) -> None:
        _, end = STAGE_PROGRESS[stage]
        await session_store.set_stage(session_id, stage, "done", end)


pipeline_orchestrator = PipelineOrchestrator()
