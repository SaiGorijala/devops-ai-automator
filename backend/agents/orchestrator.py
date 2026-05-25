from __future__ import annotations

from ..pipeline import PipelineOrchestrator


class MultiAgentOrchestrator(PipelineOrchestrator):
    """Compatibility entry point for the multi-agent pipeline coordinator."""


multi_agent_orchestrator = MultiAgentOrchestrator()
