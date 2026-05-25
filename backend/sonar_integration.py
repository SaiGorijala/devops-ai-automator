from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from .ssh_manager import SSHManager


class SonarQubeAuthManager:
    """Manage SonarQube authentication and token generation"""

    def __init__(self, ssh: SSHManager | None = None, sonar_host: str = "http://localhost:9000"):
        self.ssh = ssh
        self.sonar_host = sonar_host
        self.admin_user = "admin"
        self.admin_pass = "admin"

    async def ensure_token_exists(self) -> str | None:
        """Ensure a valid SonarQube token exists, generate if needed"""
        if not self.ssh:
            return None

        # Check if SonarQube is accessible
        status = await self._check_sonarqube_status()
        if not status:
            return None

        # Try to get existing token
        token = await self._get_existing_token()
        if token:
            return token

        # Generate new token
        return await self._generate_token()

    async def _check_sonarqube_status(self) -> bool:
        """Check if SonarQube is up and responding"""
        if not self.ssh:
            return False

        cmd = f"curl -s -u {self.admin_user}:{self.admin_pass} '{self.sonar_host}/api/system/status' | grep -i 'UP'"

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, cmd, 10)
            return result.exit_code == 0
        except Exception:
            return False

    async def _get_existing_token(self) -> str | None:
        """Retrieve an existing valid token"""
        if not self.ssh:
            return None

        cmd = f"""
        curl -s -u {self.admin_user}:{self.admin_pass} \
            '{self.sonar_host}/api/user_tokens/search' 2>/dev/null | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tokens = data.get('userTokens', [])
    if tokens:
        print(tokens[0].get('token', '').strip())
except:
    pass
"
        """

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, cmd, 10)
            token = result.stdout.strip()
            if token and token.startswith("squ_"):
                return token
        except Exception:
            pass

        return None

    async def _generate_token(self) -> str | None:
        """Generate a new SonarQube token"""
        if not self.ssh:
            return None

        cmd = f"""
        curl -s -u {self.admin_user}:{self.admin_pass} -X POST \
            '{self.sonar_host}/api/user_tokens/generate' \
            -d 'name=devops-token-$(date +%s)' 2>/dev/null | \
        python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    token = data.get('token', '').strip()
    if token:
        print(token)
except:
    print('admin')
"
        """

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, cmd, 15)
            token = result.stdout.strip()
            if token:
                return token
        except Exception:
            pass

        return "admin"  # Fallback

    async def test_token(self, token: str) -> bool:
        """Test if a token is valid"""
        if not self.ssh:
            return False

        cmd = f"curl -s -u {token}: '{self.sonar_host}/api/system/status' | grep -i UP"

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, cmd, 10)
            return result.exit_code == 0
        except Exception:
            return False


class SonarScannerRunner:
    """Run SonarScanner with automatic authentication and retry"""

    def __init__(self, ssh: SSHManager, sonar_host: str = "http://localhost:9000"):
        self.ssh = ssh
        self.sonar_host = sonar_host
        self.auth_manager = SonarQubeAuthManager(ssh, sonar_host)

    async def run_scan(
        self,
        project_path: str,
        project_key: str = "devops-app",
        max_retries: int = 3,
    ) -> tuple[bool, str]:
        """
        Run SonarScanner with automatic auth fixes

        Returns: (success: bool, message: str)
        """

        # Ensure we have a valid token
        token = await self.auth_manager.ensure_token_exists()
        if not token:
            return False, "Could not generate SonarQube token"

        for attempt in range(1, max_retries + 1):
            # Try scan with token parameter
            success, message = await self._run_scan_attempt(project_path, project_key, token, attempt)

            if success:
                return True, message

            # Check if it's an auth error
            if "not authorized" in message.lower() or "sonar.login" in message.lower():
                # Try with login parameter instead
                success2, message2 = await self._run_scan_with_login(project_path, project_key, token, attempt)
                if success2:
                    return True, message2

                # Try generating a fresh token
                token = await self.auth_manager._generate_token()
                if not token:
                    return False, f"Failed to generate new token on attempt {attempt}"

            # Wait before retry
            if attempt < max_retries:
                wait_time = 5 * attempt
                print(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(5)

        return False, f"Failed after {max_retries} attempts"

    async def _run_scan_attempt(
        self,
        project_path: str,
        project_key: str,
        token: str,
        attempt: int,
    ) -> tuple[bool, str]:
        """Run a single scan attempt with token parameter"""

        cmd = f"""
        cd {project_path} && \
        sonar-scanner \
            -Dsonar.host.url={self.sonar_host} \
            -Dsonar.token={token} \
            -Dsonar.projectKey={project_key} \
            -Dsonar.sources=. \
            -Dsonar.sourceEncoding=UTF-8
        """

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, cmd, 300)

            if result.exit_code == 0:
                return True, f"Scan completed successfully on attempt {attempt}"

            error_msg = (result.stderr + result.stdout)[-1000:]
            return False, error_msg

        except Exception as e:
            return False, str(e)

    async def _run_scan_with_login(
        self,
        project_path: str,
        project_key: str,
        token: str,
        attempt: int,
    ) -> tuple[bool, str]:
        """Run scan with sonar.login parameter (legacy format)"""

        cmd = f"""
        cd {project_path} && \
        sonar-scanner \
            -Dsonar.host.url={self.sonar_host} \
            -Dsonar.login={token} \
            -Dsonar.projectKey={project_key} \
            -Dsonar.sources=. \
            -Dsonar.sourceEncoding=UTF-8
        """

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, cmd, 300)

            if result.exit_code == 0:
                return True, f"Scan completed with sonar.login on attempt {attempt}"

            error_msg = (result.stderr + result.stdout)[-1000:]
            return False, error_msg

        except Exception as e:
            return False, str(e)

    async def ensure_sonarscanner_installed(self) -> bool:
        """Ensure sonar-scanner is installed"""

        # Check if already installed
        cmd = "which sonar-scanner"
        result = await asyncio.to_thread(self.ssh.execute_command, cmd, 5)

        if result.exit_code == 0:
            return True

        # Install sonar-scanner
        install_cmd = """
        cd /tmp && \
        curl -fsSLo sonar-scanner.zip \
            'https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip' && \
        unzip -q -o sonar-scanner.zip && \
        sudo mv sonar-scanner-* /opt/sonar-scanner 2>/dev/null || \
            mv sonar-scanner-* /opt/sonar-scanner && \
        sudo ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner && \
        sonar-scanner --version
        """

        try:
            result = await asyncio.to_thread(self.ssh.execute_command, install_cmd, 120)
            return result.exit_code == 0
        except Exception:
            return False

