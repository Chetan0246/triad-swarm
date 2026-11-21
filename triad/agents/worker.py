"""Worker Agent: Minimalist, context-isolated implementation agent."""

from __future__ import annotations

import json
import re
import time
from typing import Dict, Optional

from triad.agents.base import BaseAgent
from triad.core.llm import BaseLLMProvider
from triad.core.models import ExecutionResult, TaskSlice
from triad.core.sandbox import IsolatedSandbox
from triad.core.token_tracker import TokenTracker

WORKER_SYSTEM_PROMPT = """You are an expert, minimalist Worker Agent.
Your objective is to implement the specified TaskSlice to fulfill its InterfaceContract and pass all acceptance tests.

Requirements:
1. CONTRACT COMPLIANCE: Implement all exported symbols with exact signatures, types, and invariants specified.
2. TOKEN EFFICIENCY: Generate production-ready code with minimal token overhead.
3. CONTEXT ISOLATION: Focus strictly on your assigned target files.

Output Format:
You MUST return a valid JSON object containing the code for each target file:
{
  "files": {
    "relative/path/to/file.py": "complete source code here"
  },
  "summary": "Brief note on implementation"
}
"""


class WorkerAgent(BaseAgent):
    """Homogeneous worker instance executing a single TaskSlice in a sandbox."""

    def __init__(self, worker_id: str, llm: BaseLLMProvider, tracker: TokenTracker):
        super().__init__(agent_id=worker_id, role="worker", llm=llm, tracker=tracker)

    async def execute_slice(
        self,
        task_slice: TaskSlice,
        sandbox: IsolatedSandbox,
        previous_error: Optional[str] = None,
        iteration: int = 1,
    ) -> ExecutionResult:
        """Implement code for the assigned slice inside the isolated sandbox."""
        t0 = time.perf_counter()

        # Build concise, high-density prompt
        contract_info = {
            "module_path": task_slice.contract.module_path,
            "exported_symbols": task_slice.contract.exported_symbols,
            "signatures": task_slice.contract.signatures,
            "invariants": task_slice.contract.invariants,
        }
        if task_slice.contract.type_hints:
            contract_info["type_hints"] = task_slice.contract.type_hints
        if task_slice.contract.required_classes:
            contract_info["required_classes"] = task_slice.contract.required_classes
        if task_slice.contract.forbidden_imports:
            contract_info["forbidden_imports"] = task_slice.contract.forbidden_imports

        prompt_parts = [
            f"Task Slice: {task_slice.slice_id} - {task_slice.title}",
            f"Description: {task_slice.description}",
            f"Target Files: {task_slice.target_files}",
            f"Interface Contract:\n{json.dumps(contract_info, indent=2)}",
        ]

        if task_slice.acceptance_tests:
            test_info = {k: v for k, v in task_slice.acceptance_tests.items()}
            prompt_parts.append(f"Acceptance Tests:\n{json.dumps(test_info, indent=2)}")

        if previous_error:
            prompt_parts.append(
                f"ATTENTION: Previous attempt failed with verification error:\n"
                f"```\n{previous_error}\n```\n"
                f"Analyze the error and fix the implementation to strictly fulfill the contract and pass tests."
            )

        prompt = "\n\n".join(prompt_parts)
        phase_name = f"worker_{task_slice.slice_id}" if iteration == 1 else f"healing_{task_slice.slice_id}"

        # Adaptive temperature: use lower temperature (0.1) on healing retries for targeted precision
        temperature = 0.1 if iteration > 1 else 0.2

        resp = await self.prompt_llm(
            prompt=prompt,
            system_prompt=WORKER_SYSTEM_PROMPT,
            json_mode=True,
            phase=phase_name,
            temperature=temperature,
        )

        # Parse generated files
        try:
            files_written = self._parse_worker_files(resp.content)
            for file_path, content in files_written.items():
                sandbox.write_file(file_path, content)

            status = "success"
            err_msg = None
        except Exception as e:
            status = "error"
            files_written = {}
            err_msg = str(e)

        duration = time.perf_counter() - t0

        return ExecutionResult(
            slice_id=task_slice.slice_id,
            worker_id=self.agent_id,
            status=status,
            files_written=files_written,
            duration_seconds=duration,
            prompt_tokens=resp.prompt_tokens,
            completion_tokens=resp.completion_tokens,
            cached_tokens=resp.cached_tokens,
            total_tokens=resp.total_tokens,
            iterations=iteration,
            error_message=err_msg,
        )

    def _parse_worker_files(self, content: str) -> Dict[str, str]:
        """Extract written files from LLM JSON response."""
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        clean = json_match.group(1).strip() if json_match else content.strip()

        if clean.startswith("```"):
            clean = re.sub(r"^```[a-zA-Z]*\n", "", clean)
            clean = re.sub(r"\n```$", "", clean)

        data = json.loads(clean)
        files = data.get("files", {})
        if not files and "code" in data and "path" in data:
            files = {data["path"]: data["code"]}
        return files
