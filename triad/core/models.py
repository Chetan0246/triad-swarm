"""Data models and schemas for Triad Swarm."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class InterfaceContract(BaseModel):
    """Formal interface contract defining expected symbols, types, invariants, and security rules."""
    module_path: str = Field(description="Relative path of the module (e.g. storage/db.py)")
    exported_symbols: List[str] = Field(default_factory=list, description="Exported classes, functions, or variables")
    signatures: Dict[str, str] = Field(default_factory=dict, description="Symbol name -> Type signature / specification")
    type_hints: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Detailed type hint map: symbol -> {arg_name: type_str, 'return': type_str}"
    )
    required_classes: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Class name -> List of required method names that must exist"
    )
    forbidden_imports: List[str] = Field(
        default_factory=list,
        description="Modules strictly forbidden from being imported (e.g., subprocess, pickle)"
    )
    contract_schema: Optional[Dict[str, Any]] = Field(default=None, description="Optional JSON Schema / type contract")
    invariants: List[str] = Field(default_factory=list, description="Logical invariants that must hold true")
    language: Literal["python", "typescript", "javascript", "json_schema"] = Field(
        default="python",
        description="Target language for contract verification"
    )


class TaskSlice(BaseModel):
    """An independent or DAG-dependent task slice assigned to an isolated worker."""
    slice_id: str = Field(description="Unique identifier for the slice (e.g. slice_db_layer)")
    title: str = Field(description="Short descriptive title")
    description: str = Field(description="Actionable, clear requirements for the slice")
    target_files: List[str] = Field(default_factory=list, description="Files this slice is allowed to create or modify")
    contract: InterfaceContract = Field(description="Interface contract this slice must fulfill")
    acceptance_tests: Dict[str, str] = Field(
        default_factory=dict,
        description="Path -> Test code content to deterministically verify fulfillment"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="IDs of slices this slice depends on in the workload DAG"
    )
    priority: int = Field(default=1, description="Execution priority (higher executes earlier in wave)")
    timeout_seconds: int = Field(default=30, description="Max execution timeout in seconds")


class WorkloadSpec(BaseModel):
    """Specification of an entire software project or workload to be completed."""
    name: str
    description: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    initial_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional seed files or config files (e.g., pyproject.toml)"
    )


class ExecutionResult(BaseModel):
    """Outcome of a Worker Agent running a TaskSlice in an isolated sandbox."""
    slice_id: str
    worker_id: str
    status: Literal["success", "failure", "timeout", "error"]
    files_written: Dict[str, str] = Field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    iterations: int = 1
    error_message: Optional[str] = None


class VerificationResult(BaseModel):
    """Outcome of the Deterministic Verifier executing tests against a slice."""
    slice_id: str
    passed: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    failure_trace: Optional[str] = None
    pruned_traceback: Optional[str] = None
    ast_errors: List[str] = Field(default_factory=list)
    security_violations: List[str] = Field(default_factory=list)
    verification_phase: str = "pass"
    tokens_used: int = 0  # Crucial: 0 tokens if passed deterministically!


class SwarmMetrics(BaseModel):
    """Consolidated token, time, and success metrics for the entire swarm run."""
    workload_name: str
    total_agents_invoked: int
    active_worker_concurrency: int
    wall_clock_seconds: float
    cumulative_worker_seconds: float
    parallel_speedup: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int
    zero_token_verifications: int
    llm_verifications: int
    tasks_total: int
    tasks_succeeded: int
    success_rate: float
    estimated_cost_usd: float = 0.0
    cache_hits: int = 0
    cache_tokens_saved: int = 0
    execution_waves: int = 1
    traceback_tokens_saved: int = 0
    trace_events: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
