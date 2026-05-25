"""Agent 4: Validator & Selector - Validates deployment and learns from results."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from ..llm_client import LLMClient


class ValidatorSelector:
    """Agent 4: Validates fixes and selects best strategies."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm = llm_client
        self.agent_scores: dict[str, float] = defaultdict(float)
        self.successful_fixes: list[dict[str, Any]] = []
        self.failed_fixes: list[dict[str, Any]] = []
        self.validation_history: list[dict[str, Any]] = []

    async def validate_deployment(self, ssh_manager: Any, server_ip: str) -> dict[str, Any]:
        """Validate if deployment was successful.
        
        Args:
            ssh_manager: SSH manager for running validation commands
            server_ip: Target server IP
            
        Returns:
            Validation results with success status and score.
        """

        validation_results = {
            "success": True,
            "checks": [],
            "issues": [],
            "score": 0.0,
            "timestamp": datetime.now().isoformat(),
        }

        checks = []

        # Check 1: Docker is running
        try:
            result = ssh_manager.execute("docker ps -q")
            docker_check = {
                "name": "Docker Status",
                "passed": result.exit_code == 0 if hasattr(result, "exit_code") else True,
                "details": "Docker daemon is running",
            }
            checks.append(docker_check)
            if not docker_check["passed"]:
                validation_results["issues"].append("Docker daemon not running")
                validation_results["success"] = False
        except Exception as e:
            checks.append(
                {
                    "name": "Docker Status",
                    "passed": False,
                    "error": str(e)[:100],
                }
            )
            validation_results["success"] = False

        # Check 2: Required containers running
        containers_to_check = ["sonarqube", "jenkins", "app"]
        running_containers = []
        try:
            result = ssh_manager.execute("docker ps --format {{.Names}}")
            if hasattr(result, "stdout"):
                running_containers = result.stdout.strip().split("\n")

            containers_check = {
                "name": "Container Status",
                "passed": len([c for c in containers_to_check if c in str(running_containers)]) > 0,
                "containers": running_containers,
                "details": f"Found {len(running_containers)} running containers",
            }
            checks.append(containers_check)
            if not containers_check["passed"]:
                validation_results["issues"].append("Expected containers not running")
        except Exception as e:
            checks.append(
                {
                    "name": "Container Status",
                    "passed": False,
                    "error": str(e)[:100],
                }
            )

        # Check 3: Ports are accessible
        ports_to_check = {"3000": "Application", "9081": "SonarQube", "8081": "Jenkins"}
        accessible_ports = []
        for port, service in ports_to_check.items():
            try:
                result = ssh_manager.execute(f"curl -f -s http://localhost:{port}/ -o /dev/null")
                is_accessible = result.exit_code == 0 if hasattr(result, "exit_code") else False
                accessible_ports.append(
                    {
                        "port": port,
                        "service": service,
                        "accessible": is_accessible,
                    }
                )
            except Exception:
                accessible_ports.append(
                    {
                        "port": port,
                        "service": service,
                        "accessible": False,
                    }
                )

        ports_check = {
            "name": "Port Accessibility",
            "passed": any(p["accessible"] for p in accessible_ports),
            "ports": accessible_ports,
        }
        checks.append(ports_check)
        if not ports_check["passed"]:
            validation_results["issues"].append("Key ports are not accessible")
            validation_results["success"] = False

        validation_results["checks"] = checks

        # Calculate overall score
        passed_checks = sum(1 for c in checks if c.get("passed", False))
        validation_results["score"] = passed_checks / len(checks) if checks else 0.0

        self.validation_history.append(validation_results)
        return validation_results

    def select_best_fix(self, fixes: list[dict[str, Any]]) -> dict[str, Any]:
        """Select the best fix from multiple candidates.
        
        Args:
            fixes: List of candidate fixes
            
        Returns:
            Best fix with highest score.
        """

        scored_fixes = []

        for fix in fixes:
            score = 0.0

            # Prefer fixes with commands
            if fix.get("commands"):
                score += len(fix.get("commands", [])) * 0.1
                score += 0.3

            # Prefer fixes with high confidence
            score += fix.get("confidence", 0.0) * 0.3

            # Check safety - penalize dangerous commands
            commands_str = str(fix.get("commands", []))
            if "rm -rf" in commands_str or "sudo rm" in commands_str:
                score -= 0.5
            if "passwd" in commands_str or "password" in commands_str.lower():
                score += 0.1  # Credential management is good

            # Track score for learning
            pattern = fix.get("analysis", "unknown")[:20]
            if score > 0.5:
                self.agent_scores[pattern] += 0.1

            scored_fixes.append((score, fix))

        scored_fixes.sort(reverse=True, key=lambda x: x[0])

        if scored_fixes:
            best = scored_fixes[0][1]
            self._log_selection(best, scored_fixes[0][0])
            return best

        return {"commands": [], "analysis": "No valid fixes found", "confidence": 0.0}

    def learn_from_fix(self, fix: dict[str, Any], was_successful: bool) -> None:
        """Learn from fix outcomes for future improvements.
        
        Args:
            fix: Fix that was applied
            was_successful: Whether the fix resolved the issue
        """

        if was_successful:
            self.successful_fixes.append(fix)
            # Increase score for patterns that worked
            for cmd in fix.get("commands", []):
                pattern = cmd.split()[0] if cmd.split() else cmd
                self.agent_scores[pattern] += 0.15

            print(f"[AGENT_4] ✅ Learned successful pattern: {pattern}")
        else:
            self.failed_fixes.append(fix)
            # Decrease score for patterns that failed
            for cmd in fix.get("commands", []):
                pattern = cmd.split()[0] if cmd.split() else cmd
                self.agent_scores[pattern] = max(0, self.agent_scores[pattern] - 0.1)

            print(f"[AGENT_4] ❌ Marked pattern as failed: {pattern}")

    def get_agent_score_report(self) -> dict[str, Any]:
        """Get report of learned patterns and their scores."""
        return {
            "successful_fixes": len(self.successful_fixes),
            "failed_fixes": len(self.failed_fixes),
            "top_patterns": sorted(
                self.agent_scores.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "confidence": (
                len(self.successful_fixes)
                / (len(self.successful_fixes) + len(self.failed_fixes))
                if (len(self.successful_fixes) + len(self.failed_fixes)) > 0
                else 0.0
            ),
        }

    def _log_selection(self, fix: dict[str, Any], score: float) -> None:
        """Log fix selection for observability."""
        print(
            f"[AGENT_4] 🎯 Selected fix with score {score:.2f}: {fix.get('analysis', 'No analysis')[:60]}"
        )

    def get_validation_history(self) -> list[dict[str, Any]]:
        """Get validation history."""
        return self.validation_history
