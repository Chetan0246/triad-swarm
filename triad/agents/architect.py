"""Architect Agent: Decomposes workloads into contract-first disjoint task slices."""

from __future__ import annotations

import json
import re
from typing import List
from triad.agents.base import BaseAgent
from triad.core.llm import BaseLLMProvider
from triad.core.models import InterfaceContract, TaskSlice, WorkloadSpec
from triad.core.token_tracker import TokenTracker

ARCHITECT_SYSTEM_PROMPT = """You are the Architect Agent in the Triad Swarm.
Your sole job is to analyze the user's workload specification and decompose it into a set of disjoint, highly decoupled, parallelizable TaskSlices.

Rules:
1. CONTRACT-FIRST: Every task slice must declare an explicit InterfaceContract (module path, exported symbols, function signatures, invariants).
2. PARALLEL DECOUPLING: Slices must be independent and disjoint whenever possible so workers can build them concurrently without waiting.
3. TEST-DRIVEN: Every task slice must include executable acceptance tests that deterministically verify the implementation.
4. TOKEN MINIMALISM: Provide precise, unambiguous specifications. Do not generate conversational filler.

Output Format:
You MUST respond with a valid JSON object matching this schema:
{
  "slices": [
    {
      "slice_id": "slice_unique_id",
      "title": "Slice Title",
      "description": "Clear implementation instructions",
      "target_files": ["relative/path/to/file.py"],
      "contract": {
        "module_path": "relative/path/to/file.py",
        "exported_symbols": ["symbol1", "symbol2"],
        "signatures": {"symbol1": "def symbol1(arg1: str) -> bool"},
        "invariants": ["Invariants list"]
      },
      "acceptance_tests": {
        "tests/test_slice.py": "def test_symbol1():\\n    assert True"
      },
      "dependencies": []
    }
  ]
}
"""


class ArchitectAgent(BaseAgent):
    """The single Architect instance in the Triad Swarm."""

    def __init__(self, llm: BaseLLMProvider, tracker: TokenTracker):
        super().__init__(agent_id="architect_01", role="architect", llm=llm, tracker=tracker)

    async def decompose_workload(self, spec: WorkloadSpec) -> List[TaskSlice]:
        """Analyze workload and produce decoupled TaskSlices."""
        prompt = (
            f"Workload Name: {spec.name}\n"
            f"Description: {spec.description}\n"
            f"Acceptance Criteria:\n"
            + "\n".join(f"- {c}" for c in spec.acceptance_criteria)
            + "\n\nInitial Files:\n"
            + "\n".join(f"File `{k}`:\n```\n{v}\n```" for k, v in spec.initial_files.items())
            + "\n\nDecompose this workload into parallel, contract-first TaskSlices in JSON format."
        )

        resp = await self.prompt_llm(
            prompt=prompt,
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            json_mode=True,
            phase="architect",
        )

        slices = self._parse_slices(resp.content)
        return slices

    def _parse_slices(self, content: str) -> List[TaskSlice]:
        """Safely extract and validate TaskSlice models from LLM JSON response."""
        clean = content.strip()
        # Handle markdown fenced code blocks if present
        if clean.startswith("```"):
            clean = re.sub(r"^```[a-zA-Z]*\n", "", clean)
            clean = re.sub(r"\n```$", "", clean)

        data = json.loads(clean)
        slice_dicts = data.get("slices", [])
        if not slice_dicts and isinstance(data, list):
            slice_dicts = data

        parsed: List[TaskSlice] = []
        for s in slice_dicts:
            contract_data = s.get("contract", {})
            contract = InterfaceContract(
                module_path=contract_data.get("module_path", s.get("target_files", [""])[0]),
                exported_symbols=contract_data.get("exported_symbols", []),
                signatures=contract_data.get("signatures", {}),
                contract_schema=contract_data.get("contract_schema", contract_data.get("schema_json")),
                invariants=contract_data.get("invariants", []),
            )
            parsed.append(
                TaskSlice(
                    slice_id=s["slice_id"],
                    title=s["title"],
                    description=s["description"],
                    target_files=s.get("target_files", []),
                    contract=contract,
                    acceptance_tests=s.get("acceptance_tests", {}),
                    dependencies=s.get("dependencies", []),
                )
            )

        return parsed
