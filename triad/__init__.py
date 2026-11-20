"""Triad Swarm: Minimal-Agent, Maximum-Speed, Minimum-Token Swarm Framework."""

__version__ = "0.1.0"

from triad.core.models import (
    InterfaceContract,
    TaskSlice,
    WorkloadSpec,
    ExecutionResult,
    VerificationResult,
    SwarmMetrics,
)
from triad.core.token_tracker import TokenTracker
from triad.core.llm import get_llm_provider, BaseLLMProvider
from triad.orchestrator.engine import TriadEngine

__all__ = [
    "InterfaceContract",
    "TaskSlice",
    "WorkloadSpec",
    "ExecutionResult",
    "VerificationResult",
    "SwarmMetrics",
    "TokenTracker",
    "get_llm_provider",
    "BaseLLMProvider",
    "TriadEngine",
]
