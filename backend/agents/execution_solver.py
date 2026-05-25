"""Agent 3: Execution & Error Solver - Executes commands with AI-powered error recovery."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any

from ..llm_client import LLMClient


class LLMInteraction:
    """Represents a single LLM interaction for observability."""

    def __init__(
        self, direction: str, agent: str, data: dict[str, Any], response: dict[str, Any] | None = None
    ):
        self.timestamp = datetime.now().isoformat()
        self.direction = direction  # "query" or "response"
        self.agent = agent
        self.data = data
        self.response = response

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "agent": self.agent,
            "prompt": self.data.get("prompt", self.data.get("stage_name", ""))[:500],
            "full_prompt": self.data,
            "response": self.response,
        }


class ExecutionSolver:
    """Agent 3: Executes commands with AI-powered error recovery."""

    def __init__(self, ssh_manager: Any, llm_client: LLMClient, credentials_manager: Any):
        self.ssh = ssh_manager
        self.llm = llm_client
        self.creds = credentials_manager
        self.fix_history: list[dict[str, Any]] = []
        self.llm_conversations: list[LLMInteraction] = []
        self.execution_log: list[dict[str, Any]] = []

    async def execute_with_ai_fix(
        self, stage: dict[str, Any], context: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        """Execute a stage with automatic AI error fixing.
        
        Args:
            stage: Stage configuration with commands
            context: Execution context including repo analysis
            
        Returns:
            (success: bool, result: dict with execution details)
        """

        stage_id = stage.get("id", "unknown")
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "stage_id": stage_id,
                "stage_name": stage.get("name", "Unknown"),
                "attempt": attempt,
                "action": f"Executing {stage.get('name')} (Attempt {attempt}/{max_retries})",
            }
            self.execution_log.append(log_entry)
            self._log_agent_action(
                f"🚀 Executing {stage.get('name')} (Attempt {attempt}/{max_retries})"
            )

            try:
                results = []
                for cmd in stage.get("commands", []):
                    # Substitute variables
                    cmd = self._substitute_vars(cmd, context)

                    self._log_agent_action(f"   ▶ {cmd[:80]}...")

                    # Execute command
                    result = self.ssh.execute(cmd)

                    results.append(
                        {
                            "command": cmd,
                            "exit_code": result.exit_code if hasattr(result, "exit_code") else 0,
                            "stdout": result.stdout[-500:] if hasattr(result, "stdout") else "",
                            "stderr": result.stderr[-500:] if hasattr(result, "stderr") else "",
                        }
                    )

                    if hasattr(result, "exit_code") and result.exit_code != 0:
                        error_msg = (
                            result.stderr[-200:]
                            if hasattr(result, "stderr")
                            else "Command execution failed"
                        )
                        raise Exception(f"Command failed: {error_msg}")

                # All commands succeeded
                self._log_agent_action(
                    f"✅ {stage.get('name')} completed successfully in attempt {attempt}"
                )
                return True, {"results": results, "attempts": attempt, "timestamp": datetime.now().isoformat()}

            except Exception as e:
                error_msg = str(e)
                self._log_agent_action(f"❌ {stage.get('name')} failed: {error_msg[:80]}")

                # Build comprehensive error context for LLM
                error_context = {
                    "stage": stage_id,
                    "stage_name": stage.get("name", "Unknown"),
                    "attempt": attempt,
                    "error": error_msg,
                    "command_output": results[-1] if results else {},
                    "error_handling_strategy": stage.get("error_handling", "ai_fix"),
                    "project_type": context.get("repo_analysis", {}).get("project_type", "unknown"),
                }

                # Query LLM for fix
                self._log_agent_action(f"🤖 Querying LLM for fix strategy...")
                fix = await self._query_llm_for_fix(error_context)

                if fix and fix.get("commands"):
                    self._log_agent_action(f"💡 AI suggests: {fix.get('analysis', 'Fix available')}")

                    # Execute fix commands
                    fix_successful = True
                    for fix_cmd in fix.get("commands", []):
                        self._log_agent_action(f"   🔧 Applying: {fix_cmd[:80]}...")
                        try:
                            fix_result = self.ssh.execute(fix_cmd)
                            if hasattr(fix_result, "exit_code") and fix_result.exit_code != 0:
                                fix_successful = False
                                self._log_agent_action(
                                    f"   ⚠️ Fix result: {fix_result.stderr[:100] if hasattr(fix_result, 'stderr') else 'Error'}"
                                )
                        except Exception as fix_e:
                            fix_successful = False
                            self._log_agent_action(f"   ❌ Fix failed: {str(fix_e)[:80]}")

                    # Store fix history
                    self.fix_history.append(
                        {
                            "stage": stage_id,
                            "attempt": attempt,
                            "error": error_msg,
                            "fix_analysis": fix.get("analysis"),
                            "fix_commands": fix.get("commands"),
                            "fix_successful": fix_successful,
                            "confidence": fix.get("confidence", 0.5),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                    if fix_successful:
                        self._log_agent_action(f"✅ Fix applied successfully, retrying stage...")
                        time.sleep(2 * attempt)  # Wait before retry
                        continue

                else:
                    self._log_agent_action(f"⚠️ No AI fix available for this error")

                # Exponential backoff before retry
                if attempt < max_retries:
                    time.sleep(5 * attempt)

        self._log_agent_action(f"❌ {stage.get('name')} failed after {max_retries} attempts")
        return False, {
            "error": error_msg,
            "attempts": max_retries,
            "fixes_applied": len(self.fix_history),
            "timestamp": datetime.now().isoformat(),
        }

    async def _query_llm_for_fix(self, error_context: dict[str, Any]) -> dict[str, Any] | None:
        """Query LLM for error fix."""
        try:
            fix = await self.llm.query_for_fix(error_context, "ai_fix")

            # Log the LLM interaction
            interaction = LLMInteraction(
                direction="query",
                agent="ExecutionSolver",
                data=error_context,
                response=fix,
            )
            self.llm_conversations.append(interaction)

            return fix
        except Exception as e:
            self._log_agent_action(f"❌ LLM query failed: {str(e)[:80]}")
            return None

    def _log_agent_action(self, message: str) -> None:
        """Log agent action for UI display."""
        print(f"[AGENT_3] {message}")

    def _log_llm_interaction(self, direction: str, data: dict[str, Any]) -> None:
        """Log LLM interaction for observability."""
        log_entry = {
            "direction": direction,
            "timestamp": datetime.now().isoformat(),
            "agent": "ExecutionSolver",
            "data": data,
        }
        print(f"[LLM_{direction}] {json.dumps(data, indent=2)[:500]}")

    def _substitute_vars(self, cmd: str, context: dict[str, Any]) -> str:
        """Substitute variables in command."""
        # Add context variables
        cmd = cmd.replace("{sonar_token}", "admin:SonarQube123!")
        cmd = cmd.replace("{jenkins_password}", self.creds.get_credentials().get("jenkins", {}).get("password", ""))
        cmd = cmd.replace("{dockerhub_user}", "devops")
        cmd = cmd.replace("{app_image}", "devops-app:latest")
        return cmd

    def get_llm_conversations(self) -> list[dict[str, Any]]:
        """Get all LLM conversations for UI display."""
        return [conv.to_dict() for conv in self.llm_conversations]

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Get execution log."""
        return self.execution_log

    def get_fix_history(self) -> list[dict[str, Any]]:
        """Get fix history."""
        return self.fix_history
