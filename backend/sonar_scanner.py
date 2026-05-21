from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .process import run_command
from .ssh_manager import SSHManager


@dataclass
class Vulnerability:
    key: str
    type: str
    severity: str
    component: str
    file: str | None
    line: int | None
    message: str
    rule: str | None = None


@dataclass
class ScanResult:
    scan_id: str
    project_key: str
    passed: bool
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    raw_output: str = ""


class SonarScanner:
    def __init__(self) -> None:
        self._scan_context: dict[str, dict[str, str]] = {}

    def install_scanner(self, ssh: SSHManager) -> bool:
        if ssh.execute_command("command -v sonar-scanner", timeout=10).ok:
            return True
        cmd = (
            "set -e; "
            "sudo apt-get update -y; "
            "sudo apt-get install -y unzip curl openjdk-17-jre-headless; "
            "cd /tmp; "
            "curl -fsSLo sonar-scanner.zip "
            "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/"
            "sonar-scanner-cli-5.0.1.3006-linux.zip; "
            "sudo rm -rf /opt/sonar-scanner; "
            "sudo unzip -q sonar-scanner.zip -d /opt; "
            "sudo mv /opt/sonar-scanner-* /opt/sonar-scanner; "
            "sudo ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner; "
            "sonar-scanner --version"
        )
        ssh.execute_command(cmd, timeout=300, get_pty=True).raise_for_error()
        return True

    def run_scan(
        self,
        project_path: str | Path,
        sonar_host: str,
        sonar_token: str,
        project_key: str | None = None,
    ) -> ScanResult:
        path = Path(project_path).resolve()
        key = self._project_key(project_key or path.name)
        if shutil.which("sonar-scanner"):
            cli_result = run_command(
                [
                    "sonar-scanner",
                    f"-Dsonar.host.url={sonar_host}",
                    f"-Dsonar.token={sonar_token}",
                    f"-Dsonar.projectKey={key}",
                    "-Dsonar.sources=.",
                    "-Dsonar.sourceEncoding=UTF-8",
                ],
                cwd=path,
                timeout=900,
            )
            cli_result.raise_for_error()
            output = cli_result.stdout + cli_result.stderr
        else:
            docker_result = run_command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-e",
                    f"SONAR_HOST_URL={sonar_host}",
                    "-e",
                    f"SONAR_TOKEN={sonar_token}",
                    "-v",
                    f"{path}:/usr/src",
                    "sonarsource/sonar-scanner-cli:latest",
                    f"-Dsonar.projectKey={key}",
                    "-Dsonar.sources=.",
                    "-Dsonar.sourceEncoding=UTF-8",
                ],
                timeout=900,
            )
            docker_result.raise_for_error()
            output = docker_result.stdout + docker_result.stderr

        scan_id = self._extract_task_id(path, output)
        self._scan_context[scan_id] = {
            "sonar_host": sonar_host,
            "sonar_token": sonar_token,
            "project_key": key,
        }
        gate = self.wait_for_quality_gate(scan_id, timeout=300)
        vulnerabilities = self._fetch_vulnerabilities(sonar_host, sonar_token, key)
        return ScanResult(
            scan_id=scan_id,
            project_key=key,
            passed=gate["passed"],
            vulnerabilities=vulnerabilities,
            raw_output=output,
        )

    def wait_for_quality_gate(self, scan_id: str, timeout: int = 300) -> dict[str, Any]:
        context = self._scan_context.get(scan_id)
        if not context:
            raise KeyError(f"Unknown Sonar scan id: {scan_id}")
        host = context["sonar_host"]
        token = context["sonar_token"]
        deadline = time.time() + timeout
        analysis_id: str | None = None
        with httpx.Client(auth=(token, ""), timeout=30) as client:
            while time.time() < deadline:
                response = client.get(f"{host}/api/ce/task", params={"id": scan_id})
                response.raise_for_status()
                task = response.json()["task"]
                status = task["status"]
                if status == "SUCCESS":
                    analysis_id = task.get("analysisId")
                    break
                if status in {"FAILED", "CANCELED"}:
                    raise RuntimeError(f"SonarQube analysis task ended with status {status}")
                time.sleep(5)
            if not analysis_id:
                raise TimeoutError(f"Timed out waiting for Sonar quality gate task {scan_id}")
            gate = client.get(
                f"{host}/api/qualitygates/project_status",
                params={"analysisId": analysis_id},
            )
            gate.raise_for_status()
            status = gate.json()["projectStatus"]["status"]
            return {"passed": status == "OK", "status": status, "analysis_id": analysis_id}

    def parse_vulnerabilities(self, scan_output: str) -> list[Vulnerability]:
        vulnerabilities: list[Vulnerability] = []
        for line in scan_output.splitlines():
            if "vulnerab" in line.lower() or "security" in line.lower():
                vulnerabilities.append(
                    Vulnerability(
                        key=f"log-{len(vulnerabilities)}",
                        type="VULNERABILITY",
                        severity="UNKNOWN",
                        component="scanner-output",
                        file=None,
                        line=None,
                        message=line.strip(),
                    )
                )
        return vulnerabilities

    def _fetch_vulnerabilities(self, host: str, token: str, project_key: str) -> list[Vulnerability]:
        issues: list[Vulnerability] = []
        with httpx.Client(auth=(token, ""), timeout=30) as client:
            response = client.get(
                f"{host}/api/issues/search",
                params={
                    "projectKeys": project_key,
                    "types": "VULNERABILITY,BUG",
                    "severities": "BLOCKER,CRITICAL,MAJOR",
                    "ps": 100,
                },
            )
            response.raise_for_status()
            for item in response.json().get("issues", []):
                component = item.get("component", "")
                file_name = component.split(":", 1)[-1] if ":" in component else component
                issues.append(
                    Vulnerability(
                        key=item.get("key", ""),
                        type=item.get("type", "ISSUE"),
                        severity=item.get("severity", "UNKNOWN"),
                        component=component,
                        file=file_name or None,
                        line=item.get("line"),
                        message=item.get("message", ""),
                        rule=item.get("rule"),
                    )
                )
        return issues

    @staticmethod
    def _extract_task_id(path: Path, output: str) -> str:
        report = path / ".scannerwork" / "report-task.txt"
        if report.exists():
            for line in report.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("ceTaskId="):
                    return line.split("=", 1)[1].strip()
        match = re.search(r"ceTaskId=([A-Za-z0-9_-]+)", output)
        if match:
            return match.group(1)
        raise RuntimeError("Unable to locate SonarQube ceTaskId in scanner output")

    @staticmethod
    def _project_key(value: str) -> str:
        key = re.sub(r"[^A-Za-z0-9_.:-]", "-", value).strip("-")
        return key or "devops-ai-project"
