"""Triad Swarm: Minimal-Agent, Maximum-Speed, Minimum-Token Swarm Framework."""

__version__ = "0.2.0"

from triad.core.cache import PromptCacheManager
from triad.core.contracts import ASTContractValidator, TracebackPruner, ContractViolation
from triad.core.llm import BaseLLMProvider, CachedLLMProvider, MockLLMProvider, get_llm_provider
from triad.core.models import (
    ExecutionResult,
    InterfaceContract,
    SwarmMetrics,
    TaskSlice,
    VerificationResult,
    WorkloadSpec,
)
from triad.core.sandbox import IsolatedSandbox
from triad.core.telemetry import SwarmTracer, TraceSpan
from triad.core.token_tracker import TokenRecord, TokenTracker
from triad.orchestrator.engine import TriadEngine
from triad.orchestrator.scheduler import CircularDependencyError, DAGScheduler, MissingDependencyError

__all__ = [
    "InterfaceContract",
    "TaskSlice",
    "WorkloadSpec",
    "ExecutionResult",
    "VerificationResult",
    "SwarmMetrics",
    "TokenTracker",
    "TokenRecord",
    "PromptCacheManager",
    "SwarmTracer",
    "TraceSpan",
    "ASTContractValidator",
    "TracebackPruner",
    "ContractViolation",
    "IsolatedSandbox",
    "DAGScheduler",
    "CircularDependencyError",
    "MissingDependencyError",
    "get_llm_provider",
    "BaseLLMProvider",
    "CachedLLMProvider",
    "MockLLMProvider",
    "TriadEngine",
]
