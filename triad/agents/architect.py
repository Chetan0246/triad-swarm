"""Architect Agent: Decomposes workloads into contract-first disjoint task slices."""

from __future__ import annotations

import json
import re
from typing import List, Optional

from triad.agents.base import BaseAgent
from triad.core.llm import BaseLLMProvider
from triad.core.models import InterfaceContract, TaskSlice, WorkloadSpec
from triad.core.token_tracker import TokenTracker

ARCHITECT_SYSTEM_PROMPT = """You are the Architect Agent in the Triad Swarm.
Your job is to analyze the user's workload specification and decompose it into a set of disjoint, highly decoupled, parallelizable TaskSlices.

Triad Swarm supports all software workloads:
- Full-Stack Web Applications (Database schema/ORM + Backend API + Frontend UI components/HTML/Tailwind)
- Backend APIs & Microservices (FastAPI, Express, Django, Flask, SQLite/PostgreSQL, Auth)
- Frontend Applications & Dashboards (HTML5, Tailwind CSS, React, Vue, TypeScript, JS)
- Everyday Tools & Automation (Web scrapers, ETL data pipelines, CLI utilities, report generators, bots)

Rules:
1. CONTRACT-FIRST: Every task slice must declare an explicit InterfaceContract (module path, exported symbols, function/class signatures, language, invariants).
   Supported languages: "python", "typescript", "javascript", "html", "css", "web", "json_schema", "shell".
2. PARALLEL DECOUPLING: Slices must be independent and disjoint whenever possible so workers can build them concurrently without waiting. For full-stack apps, separate into layers (e.g. database/models -> backend api -> frontend UI -> integration).
3. TEST-DRIVEN: Every task slice must include executable acceptance tests that deterministically verify the implementation. Tests must be self-contained and runnable via pytest.
4. FOCUSED SLICES: Aim for 2 to 4 high-leverage functional slices. Target 1 primary file per slice (matching contract module_path). Do NOT create trivial slices for README or docs.
5. TOKEN MINIMALISM: Provide precise, unambiguous specifications. Do not generate conversational filler.

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
        "invariants": ["Invariants list"],
        "language": "python"
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

    async def decompose_workload(
        self,
        spec: WorkloadSpec,
        repo_map: Optional[str] = None,
    ) -> List[TaskSlice]:
        """Analyze workload and produce decoupled TaskSlices."""
        prompt_parts = [
            f"Workload Name: {spec.name}",
            f"Description: {spec.description}",
            "Acceptance Criteria:\n" + "\n".join(f"- {c}" for c in spec.acceptance_criteria),
        ]

        if spec.initial_files:
            prompt_parts.append(
                "Initial Files:\n" + "\n".join(f"File `{k}`:\n```\n{v}\n```" for k, v in spec.initial_files.items())
            )

        if repo_map:
            prompt_parts.append(
                f"Existing Codebase AST Map:\n```\n{repo_map}\n```\n"
                f"Ensure planned slices interface cleanly with existing modules and classes."
            )

        prompt_parts.append("Decompose this workload into parallel, contract-first TaskSlices in JSON format.")
        prompt = "\n\n".join(prompt_parts)

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
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        clean = json_match.group(1).strip() if json_match else content.strip()

        if clean.startswith("```"):
            clean = re.sub(r"^```[a-zA-Z]*\n", "", clean)
            clean = re.sub(r"\n```$", "", clean)

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            raise ValueError(f"Architect produced unparseable JSON for TaskSlices: {e}") from e

        if isinstance(data, dict):
            slice_dicts = data.get("slices", [])
        elif isinstance(data, list):
            slice_dicts = data
        else:
            raise ValueError(f"Architect response is not a JSON object or list of slices: {type(data).__name__}")

        parsed: List[TaskSlice] = []
        for s in slice_dicts:
            if not isinstance(s, dict):
                raise ValueError(f"Architect slice entry is not a JSON object: {s!r}")
            for field in ("slice_id", "title", "description"):
                if not s.get(field):
                    raise ValueError(f"Architect slice entry is missing required field '{field}': {s!r}")

            contract_data = s.get("contract") or {}
            if not isinstance(contract_data, dict):
                raise ValueError(f"Architect slice '{s.get('slice_id')}' has a non-object contract.")
            target_files = s.get("target_files") or []
            contract = InterfaceContract(
                module_path=contract_data.get("module_path", target_files[0] if target_files else ""),
                exported_symbols=contract_data.get("exported_symbols", []),
                signatures=contract_data.get("signatures", {}),
                type_hints=contract_data.get("type_hints", {}),
                required_classes=contract_data.get("required_classes", {}),
                forbidden_imports=contract_data.get("forbidden_imports", []),
                contract_schema=contract_data.get("contract_schema", contract_data.get("schema_json")),
                invariants=contract_data.get("invariants", []),
                language=contract_data.get("language", "python"),
            )
            parsed.append(
                TaskSlice(
                    slice_id=s["slice_id"],
                    title=s["title"],
                    description=s["description"],
                    target_files=target_files,
                    contract=contract,
                    acceptance_tests=s.get("acceptance_tests") or {},
                    dependencies=s.get("dependencies") or [],
                )
            )

        return parsed
