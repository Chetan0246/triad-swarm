"""Triad Swarm: Minimal-Agent, Maximum-Speed, Minimum-Token Swarm Framework."""

__version__ = "0.3.0"

from triad.agents.polyglot import PolyglotVerifier
from triad.agents.spec_generator import SpecGeneratorAgent
from triad.core.cache import PromptCacheManager
from triad.core.contracts import ASTContractValidator, ContractViolation, TracebackPruner
from triad.core.llm import (
    BaseLLMProvider,
    CachedLLMProvider,
    GeminiProvider,
    MockLLMProvider,
    OpenAICompatibleProvider,
    OpenAIProvider,
    get_llm_provider,
)
from triad.core.models import (
    ExecutionResult,
    InterfaceContract,
    SwarmMetrics,
    TaskSlice,
    VerificationResult,
    WorkloadSpec,
)
from triad.core.repomap import RepoMapGenerator
from triad.core.router import ModelRouter
from triad.core.sandbox import IsolatedSandbox
from triad.core.telemetry import SwarmTracer, TraceSpan
from triad.core.token_tracker import TokenRecord, TokenTracker
from triad.core.web import FreeWebEngine, TinyFishClient
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
    "GeminiProvider",
    "OpenAIProvider",
    "OpenAICompatibleProvider",
    "ModelRouter",
    "RepoMapGenerator",
    "TinyFishClient",
    "FreeWebEngine",
    "SpecGeneratorAgent",
    "PolyglotVerifier",
    "TriadEngine",
]
