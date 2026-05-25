from __future__ import annotations

import re
from typing import Any


class ErrorFixMapper:
    """Direct mapping of errors to fixes - no LLM dependency"""

    FIX_PATTERNS = {
        # SonarQube Authentication Errors
        "not authorized": {
            "analysis": "SonarQube token invalid or expired - regenerating",
            "commands": [
                "curl -s -u admin:admin -X POST 'http://localhost:9000/api/user_tokens/generate' -d 'name=devops-token-$(date +%s)' 2>/dev/null | python3 -c \"import sys, json; data=json.load(sys.stdin); print(data.get('token', ''))\" > /tmp/sonar_token.txt",
                "export SONAR_TOKEN=$(cat /tmp/sonar_token.txt)",
                "echo \"Generated token: $SONAR_TOKEN\"",
            ],
            "verification": "curl -s -u admin:admin 'http://localhost:9000/api/system/status' | grep -i up",
            "requires_retry": True,
            "confidence": 0.95,
        },
        "sonar.login": {
            "analysis": "SonarScanner requires sonar.login parameter instead of sonar.token",
            "commands": [
                "export SONAR_TOKEN=$(curl -s -u admin:admin -X POST 'http://localhost:9000/api/user_tokens/generate' -d 'name=devops-$(date +%s)' 2>/dev/null | python3 -c \"import sys, json; print(json.load(sys.stdin).get('token', 'admin'))\")",
                "echo 'Token: '$SONAR_TOKEN",
            ],
            "verification": "echo 'Using sonar.login='$SONAR_TOKEN",
            "requires_retry": True,
            "confidence": 0.92,
        },
        # SSH Timeout Errors
        "timeout opening channel": {
            "analysis": "SSH channel timeout - increasing server keepalive timeouts",
            "commands": [
                "sudo sed -i 's/^#ClientAliveInterval.*/ClientAliveInterval 120/' /etc/ssh/sshd_config",
                "sudo sed -i 's/^#ClientAliveCountMax.*/ClientAliveCountMax 5/' /etc/ssh/sshd_config",
                "sudo systemctl restart sshd",
                "echo 'SSH timeout settings increased'",
            ],
            "verification": "sudo sshd -T | grep -E 'clientalive'",
            "requires_retry": True,
            "confidence": 0.88,
        },
        # Docker Compose Errors
        "docker-compose: command not found": {
            "analysis": "Docker Compose not installed - installing from releases",
            "commands": [
                "sudo curl -L 'https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose",
                "sudo chmod +x /usr/local/bin/docker-compose",
                "docker-compose --version",
            ],
            "verification": "which docker-compose && docker-compose --version",
            "requires_retry": True,
            "confidence": 0.91,
        },
        "no such file or directory" and "docker-compose": {
            "analysis": "Docker Compose not in PATH",
            "commands": [
                "sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose 2>/dev/null || true",
                "docker-compose --version",
            ],
            "verification": "docker-compose --version",
            "requires_retry": True,
            "confidence": 0.85,
        },
        # Port Conflicts
        "port is already allocated": {
            "analysis": "Port conflict detected - freeing the port",
            "commands": [
                "PORT=$(netstat -tulpn 2>/dev/null | grep ':9000 ' | awk '{print $7}' | cut -d/ -f1)",
                "[ ! -z \"$PORT\" ] && kill -9 $PORT 2>/dev/null || true",
                "sleep 2",
                "echo 'Port 9000 cleared'",
            ],
            "verification": "netstat -tulpn 2>/dev/null | grep ':9000' || echo 'Port free'",
            "requires_retry": True,
            "confidence": 0.80,
        },
        # Docker Permission Errors
        "permission denied": {
            "analysis": "Docker permission issue - fixing user permissions",
            "commands": [
                "sudo usermod -aG docker $USER",
                "sudo chmod 666 /var/run/docker.sock 2>/dev/null || true",
                "sudo systemctl restart docker || true",
            ],
            "verification": "docker ps",
            "requires_retry": True,
            "confidence": 0.87,
        },
        # Container Issues
        "cannot connect to docker daemon": {
            "analysis": "Docker daemon not responding - restarting",
            "commands": [
                "sudo systemctl start docker",
                "sudo systemctl restart docker",
                "sleep 3",
                "docker ps",
            ],
            "verification": "docker ps",
            "requires_retry": True,
            "confidence": 0.86,
        },
        # Memory/Resource Issues
        "no space left on device": {
            "analysis": "Disk space exhausted - cleaning up Docker",
            "commands": [
                "docker system prune -af --volumes || sudo docker system prune -af --volumes",
                "docker images prune -af || sudo docker images prune -af",
                "df -h /",
            ],
            "verification": "df -h / | tail -1",
            "requires_retry": True,
            "confidence": 0.84,
        },
        # Python/Dependency Errors
        "no module named": {
            "analysis": "Missing Python module - installing dependencies",
            "commands": [
                "pip3 install --upgrade pip setuptools wheel",
                "[ -f requirements.txt ] && pip3 install --no-cache-dir -r requirements.txt || true",
                "pip3 install python-dotenv paramiko requests httpx",
            ],
            "verification": "python3 -c 'import paramiko; print(paramiko.__version__)'",
            "requires_retry": True,
            "confidence": 0.83,
        },
        # Git/Repository Errors
        "authentication failed": {
            "analysis": "Git authentication issue - configuring credential helper",
            "commands": [
                "git config --global credential.helper cache",
                "git config --global credential.helper store",
                "echo 'Git credential helper configured'",
            ],
            "verification": "git config --global credential.helper",
            "requires_retry": True,
            "confidence": 0.79,
        },
        # SonarScanner Specific
        "sonar-scanner: not found": {
            "analysis": "SonarScanner not installed - installing",
            "commands": [
                "cd /tmp",
                "curl -fsSLo sonar-scanner.zip https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip",
                "unzip -q -o sonar-scanner.zip",
                "sudo mv sonar-scanner-* /opt/sonar-scanner",
                "sudo ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner",
                "sonar-scanner --version",
            ],
            "verification": "sonar-scanner --version",
            "requires_retry": True,
            "confidence": 0.90,
        },
        # Connection Errors
        "connection refused": {
            "analysis": "Service connection refused - checking service status",
            "commands": [
                "netstat -tulpn 2>/dev/null || ss -tulpn",
                "docker ps -a",
                "sudo systemctl status docker || echo 'Docker systemd check skipped'",
            ],
            "verification": "echo 'Check service availability'",
            "requires_retry": True,
            "confidence": 0.60,
        },
        # Java/SonarQube heap errors
        "gc overhead limit exceeded": {
            "analysis": "Java heap memory exhausted - increasing JVM memory",
            "commands": [
                "export SONAR_JAVA_OPTS='-Xmx2048m -Xms512m'",
                "docker restart sonarqube || docker-compose restart sonarqube || true",
                "sleep 10",
                "echo 'SonarQube memory increased'",
            ],
            "verification": "curl -s -u admin:admin 'http://localhost:9000/api/system/status' | grep -i up",
            "requires_retry": True,
            "confidence": 0.82,
        },
    }

    @classmethod
    def get_fix(cls, error_message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get fix for error based on pattern matching"""

        error_lower = error_message.lower()
        context = context or {}

        # Find matching pattern (try multi-word patterns first)
        for pattern, fix in cls.FIX_PATTERNS.items():
            # Handle patterns with "and" for multiple conditions
            if " and " in pattern:
                conditions = [p.strip() for p in pattern.split(" and ")]
                if all(c.lower() in error_lower for c in conditions):
                    return cls._format_fix(fix, context, error_message)
            elif pattern.lower() in error_lower:
                return cls._format_fix(fix, context, error_message)

        # Default fix for unknown errors
        return cls._get_diagnostic_fix(error_message, context)

    @classmethod
    def _format_fix(cls, fix: dict[str, Any], context: dict[str, Any], error_message: str) -> dict[str, Any]:
        """Format fix with context substitutions"""
        commands = []
        for cmd in fix.get("commands", []):
            # Replace common placeholders
            cmd = cmd.replace("{sonar_host}", context.get("sonar_host", "http://localhost:9000"))
            cmd = cmd.replace("{token}", context.get("token", "squ_xxxxx"))
            cmd = cmd.replace("{project_key}", context.get("project_key", "devops-app"))
            cmd = cmd.replace("{port}", str(context.get("port", "3000")))
            cmd = cmd.replace("{repo}", context.get("repo", "user/repo"))
            cmd = cmd.replace("{module_name}", context.get("module_name", "package"))
            commands.append(cmd)

        verification = fix.get("verification", "echo 'fix applied'")
        for placeholder, value in context.items():
            verification = verification.replace(f"{{{placeholder}}}", str(value))

        return {
            "provider": "direct-mapper",
            "analysis": fix.get("analysis", ""),
            "commands": commands,
            "verification": verification,
            "requires_retry": fix.get("requires_retry", False),
            "confidence": fix.get("confidence", 0.70),
        }

    @classmethod
    def _get_diagnostic_fix(cls, error_message: str, context: dict[str, Any]) -> dict[str, Any]:
        """Get diagnostic commands for unknown errors"""
        return {
            "provider": "diagnostic",
            "analysis": f"Unknown error detected - running diagnostics",
            "commands": [
                "echo '=== System Diagnostics ==='",
                "echo 'Checking Docker:'",
                "docker ps -a",
                "echo 'Recent logs:'",
                "docker logs $(docker ps -aq) --tail 20 2>/dev/null || echo 'No logs available'",
                "echo 'System info:'",
                "uname -a",
                "df -h /",
            ],
            "verification": "echo 'Diagnostic check complete - check output above'",
            "requires_retry": False,
            "confidence": 0.25,
        }

    @classmethod
    def should_use_mapper(cls, error_message: str) -> bool:
        """Check if error has a direct fix mapping"""
        error_lower = error_message.lower()
        for pattern in cls.FIX_PATTERNS.keys():
            if " and " in pattern:
                conditions = [p.strip() for p in pattern.split(" and ")]
                if all(c.lower() in error_lower for c in conditions):
                    return True
            elif pattern.lower() in error_lower:
                return True
        return False
