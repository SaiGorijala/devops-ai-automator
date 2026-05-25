from __future__ import annotations

import re
from typing import Any


class ErrorContextFormatter:
    """Format errors for optimal LLM understanding"""

    @staticmethod
    def format_for_ollama(error: str, context: dict[str, Any], attempt: int) -> str:
        """Create a prompt that forces Ollama to return commands"""

        clean_error = ErrorContextFormatter._clean_error_message(error)

        prompt = f"""You are a DevOps AI. Fix this error IMMEDIATELY.

ACTUAL ERROR: {clean_error}
ATTEMPT: {attempt}/3
COMMAND THAT FAILED: {context.get('command', 'unknown')}

REQUIRED ACTION: Return 3-5 bash commands to fix this specific error.

EXAMPLE FOR "Timeout opening channel":
```json
{{
    "analysis": "SSH channel timeout - increase timeout values",
    "commands": [
        "sed -i 's/^#ClientAliveInterval.*/ClientAliveInterval 60/' /etc/ssh/sshd_config",
        "sed -i 's/^#ClientAliveCountMax.*/ClientAliveCountMax 3/' /etc/ssh/sshd_config",
        "systemctl restart sshd",
        "echo 'SSH timeout increased'"
    ],
    "verification": "ssh -o ConnectTimeout=30 ubuntu@host 'echo OK'",
    "confidence": 0.85
}}
```

EXAMPLE FOR "docker-compose not found":
```json
{{
    "analysis": "Docker Compose missing",
    "commands": [
        "curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose",
        "chmod +x /usr/local/bin/docker-compose",
        "docker-compose --version"
    ],
    "verification": "docker-compose --version",
    "confidence": 0.9
}}
```

NOW FIX THIS EXACT ERROR: {clean_error}

Return ONLY valid JSON with commands. NO explanations outside JSON.
Your JSON response:"""

        return prompt

    @staticmethod
    def _clean_error_message(error: str) -> str:
        """Extract the most relevant part of the error"""
        lines = error.split('\n')
        error_lines = []

        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in
                   ['error', 'failed', 'timeout', 'cannot', 'unable', 'permission', 'not found']):
                error_lines.append(line)

        if error_lines:
            return '; '.join(error_lines[:3])
        return error[:500]
