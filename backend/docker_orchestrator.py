from __future__ import annotations

import json
import secrets
import shlex
import string
import time
from dataclasses import dataclass

from .config import settings
from .ssh_manager import SSHManager


def _password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _stack_name(session_id: str) -> str:
    safe = "".join(ch for ch in session_id.lower() if ch.isalnum() or ch == "-")
    return f"devops-ai-{safe[:18]}"


@dataclass
class SonarInfo:
    url: str
    username: str
    password: str
    token: str
    port: int


@dataclass
class JenkinsInfo:
    url: str
    username: str
    password: str
    port: int


class DockerOrchestrator:
    def __init__(self, ssh: SSHManager, session_id: str) -> None:
        self.ssh = ssh
        self.session_id = session_id
        self.stack = _stack_name(session_id)
        self.remote_root = f"{settings.remote_workspace}/{self.stack}"

    def deploy_sonarqube(self, server_ip: str) -> SonarInfo:
        port = self.ssh.first_available_port(9000)
        admin_password = _password()
        token_name = f"devops-ai-{self.session_id[:8]}"
        remote_dir = f"{self.remote_root}/sonarqube"
        compose = self._sonarqube_compose(port)
        self.ssh.transfer_file(compose, f"{remote_dir}/docker-compose.yml")
        setup_cmd = (
            "set -e; "
            "sudo sysctl -w vm.max_map_count=524288; "
            "sudo sysctl -w fs.file-max=131072; "
            "sudo apt-get update -y >/dev/null; "
            "sudo apt-get install -y curl >/dev/null; "
            f"cd {shlex.quote(remote_dir)}; "
            "sudo docker compose up -d"
        )
        self.ssh.execute_command(setup_cmd, timeout=900, get_pty=True).raise_for_error()
        self.sonarqube_health_check(port=port, timeout=180)
        self._set_sonar_admin_password(port, admin_password)
        token = self._create_sonar_token(port, admin_password, token_name)
        return SonarInfo(
            url=f"http://{server_ip}:{port}",
            username="admin",
            password=admin_password,
            token=token,
            port=port,
        )

    def deploy_jenkins(self, server_ip: str) -> JenkinsInfo:
        port = self.ssh.first_available_port(8080)
        remote_dir = f"{self.remote_root}/jenkins"
        container_name = f"{self.stack}-jenkins"
        self.ssh.transfer_file(self._jenkins_compose(port, container_name), f"{remote_dir}/docker-compose.yml")
        cmd = (
            f"cd {shlex.quote(remote_dir)}; "
            "sudo docker compose up -d"
        )
        self.ssh.execute_command(cmd, timeout=600, get_pty=True).raise_for_error()
        self.jenkins_wait_for_startup(port=port, timeout=240)
        self._install_jenkins_plugins(container_name, port)
        password = self._read_jenkins_initial_password(container_name)
        return JenkinsInfo(
            url=f"http://{server_ip}:{port}",
            username="admin",
            password=password,
            port=port,
        )

    def sonarqube_health_check(self, port: int = 9000, timeout: int = 120) -> str:
        deadline = time.time() + timeout
        last_output = ""
        while time.time() < deadline:
            result = self.ssh.execute_command(
                f"curl -sf http://127.0.0.1:{port}/api/system/status || true",
                timeout=20,
            )
            last_output = result.stdout.strip()
            if '"status":"UP"' in last_output or '"status":"GREEN"' in last_output:
                return last_output
            time.sleep(5)
        raise TimeoutError(f"SonarQube did not become healthy within {timeout}s. Last response: {last_output}")

    def jenkins_wait_for_startup(self, port: int = 8080, timeout: int = 180) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            result = self.ssh.execute_command(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/login || true",
                timeout=20,
            )
            if result.stdout.strip() in {"200", "403"}:
                return True
            time.sleep(5)
        raise TimeoutError(f"Jenkins did not become ready within {timeout}s")

    def _set_sonar_admin_password(self, port: int, new_password: str) -> None:
        result = self.ssh.execute_command(
            "curl -sf -u admin:admin "
            "-X POST "
            f"-d login=admin -d previousPassword=admin -d password={shlex.quote(new_password)} "
            f"http://127.0.0.1:{port}/api/users/change_password",
            timeout=60,
        )
        if not result.ok:
            # A previous retry may already have changed the password. Verify generated credentials work.
            verify = self.ssh.execute_command(
                f"curl -sf -u admin:{shlex.quote(new_password)} http://127.0.0.1:{port}/api/authentication/validate",
                timeout=30,
            )
            verify.raise_for_error()

    def _create_sonar_token(self, port: int, admin_password: str, token_name: str) -> str:
        result = self.ssh.execute_command(
            f"curl -sf -u admin:{shlex.quote(admin_password)} "
            "-X POST "
            f"-d name={shlex.quote(token_name)} "
            f"http://127.0.0.1:{port}/api/user_tokens/generate",
            timeout=60,
        ).raise_for_error()
        try:
            payload = json.loads(result.stdout)
            token = payload["token"]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Unable to parse SonarQube token response: {result.stdout}") from exc
        return token

    def _read_jenkins_initial_password(self, container_name: str) -> str:
        result = self.ssh.execute_command(
            f"sudo docker exec {shlex.quote(container_name)} "
            "cat /var/jenkins_home/secrets/initialAdminPassword",
            timeout=30,
        ).raise_for_error()
        return result.stdout.strip()

    def _install_jenkins_plugins(self, container_name: str, port: int) -> None:
        plugins = "git workflow-aggregator sonar docker-workflow github configuration-as-code"
        result = self.ssh.execute_command(
            f"sudo docker exec -u jenkins {shlex.quote(container_name)} "
            f"jenkins-plugin-cli --plugins {shlex.quote(plugins)}",
            timeout=900,
            get_pty=True,
        )
        if result.ok:
            self.ssh.execute_command(f"sudo docker restart {shlex.quote(container_name)}", timeout=60)
            self.jenkins_wait_for_startup(port=port, timeout=240)

    def _sonarqube_compose(self, port: int) -> str:
        return f"""services:
  sonar-db:
    image: postgres:15-alpine
    container_name: {self.stack}-sonar-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: sonar
      POSTGRES_PASSWORD: sonar
      POSTGRES_DB: sonar
    volumes:
      - sonar_db_data:/var/lib/postgresql/data

  sonarqube:
    image: sonarqube:lts-community
    container_name: {self.stack}-sonarqube
    depends_on:
      - sonar-db
    restart: unless-stopped
    ports:
      - "{port}:9000"
    environment:
      SONAR_JDBC_URL: jdbc:postgresql://sonar-db:5432/sonar
      SONAR_JDBC_USERNAME: sonar
      SONAR_JDBC_PASSWORD: sonar
    volumes:
      - sonar_data:/opt/sonarqube/data
      - sonar_extensions:/opt/sonarqube/extensions
      - sonar_logs:/opt/sonarqube/logs

volumes:
  sonar_db_data:
  sonar_data:
  sonar_extensions:
  sonar_logs:
"""

    def _jenkins_compose(self, port: int, container_name: str) -> str:
        return f"""services:
  jenkins:
    image: jenkins/jenkins:lts-jdk17
    container_name: {container_name}
    user: root
    restart: unless-stopped
    ports:
      - "{port}:8080"
      - "50000:50000"
    environment:
      JAVA_OPTS: "-Djenkins.install.runSetupWizard=true"
    volumes:
      - jenkins_home:/var/jenkins_home
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  jenkins_home:
"""
