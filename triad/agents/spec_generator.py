"""Spec Generator Agent: Converts natural language feature prompts into typed WorkloadSpecs.

Empowers users to execute `triad new "<feature>"` without writing raw JSON specs.
Synthesizes acceptance criteria, required module boundaries, and interface contracts.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from triad.agents.base import BaseAgent
from triad.core.llm import BaseLLMProvider, MockLLMProvider
from triad.core.models import WorkloadSpec
from triad.core.token_tracker import TokenTracker

SPEC_GENERATOR_SYSTEM_PROMPT = """You are the Lead Requirements Architect in Triad Swarm.
Your task is to convert a user's natural language feature request into a formal, structured WorkloadSpec.

You handle all practical software engineering and developer tasks:
- Full-Stack Applications: Database layer, REST/GraphQL API layer, Frontend UI/dashboard (HTML/Tailwind/React/Vue).
- Backend Services: APIs, endpoints, authentication, CRUD operations, database migrations, caching.
- Frontend & UI: Interactive interfaces, responsive styling, forms, dashboards, client-side logic.
- Everyday Tools & Automation: Web scrapers, CLI utilities, data ingestion/ETL scripts, report generators.

Rules:
1. CONTRACT RIGOR: Clearly outline the necessary architectural components and acceptance criteria across all layers.
2. DISJOINT DECOUPLING: Structure criteria so the workload can be decomposed into parallel task slices.
3. OUTPUT FORMAT: Respond ONLY with a valid JSON object matching this schema:
{
  "name": "concise-feature-slug",
  "description": "Comprehensive technical description of the feature or full-stack application to be built",
  "acceptance_criteria": [
    "Criterion 1: Concrete requirement (e.g., database models, schema)",
    "Criterion 2: API routes or backend endpoints",
    "Criterion 3: Frontend UI components or user interface"
  ],
  "initial_files": {}
}
"""


class SpecGeneratorAgent(BaseAgent):
    """Generates structured WorkloadSpec objects from plain natural language prompts."""

    def __init__(self, llm: BaseLLMProvider, tracker: Optional[TokenTracker] = None):
        super().__init__(
            agent_id="spec_generator_01",
            role="spec_generator",
            llm=llm,
            tracker=tracker or TokenTracker(),
        )

    async def generate_spec(
        self,
        prompt: str,
        repo_map: Optional[str] = None,
        suggested_name: Optional[str] = None,
    ) -> WorkloadSpec:
        """Synthesize a complete WorkloadSpec from natural language and codebase context."""
        user_prompt_parts = [
            f"User Feature Request:\n{prompt}",
        ]

        if repo_map:
            user_prompt_parts.append(
                f"\nExisting Codebase Context (AST Map):\n```\n{repo_map}\n```\n"
                f"Ensure the new feature integrates cleanly with the existing classes and modules above."
            )

        if suggested_name:
            user_prompt_parts.append(f"Suggested Workload Name: {suggested_name}")

        user_prompt_parts.append("\nGenerate the formal WorkloadSpec JSON now.")

        full_prompt = "\n".join(user_prompt_parts)

        # Handle mock provider offline fallback
        actual_provider = getattr(self.llm, "provider", self.llm)
        if isinstance(actual_provider, MockLLMProvider):
            slug = suggested_name or re.sub(r"[^a-zA-Z0-9]+", "-", prompt.lower()).strip("-")[:30] or "custom-feature"
            return WorkloadSpec(
                name=slug,
                description=prompt,
                acceptance_criteria=[
                    f"Implement functionality matching: {prompt}",
                    "Fulfill all interface contracts and pass deterministic unit tests",
                    "Maintain context isolation and zero-token verifications",
                ],
                initial_files={},
            )

        resp = await self.prompt_llm(
            prompt=full_prompt,
            system_prompt=SPEC_GENERATOR_SYSTEM_PROMPT,
            json_mode=True,
            phase="spec_generation",
        )

        return self._parse_spec(resp.content, fallback_prompt=prompt, suggested_name=suggested_name)

    def _parse_spec(self, content: str, fallback_prompt: str, suggested_name: Optional[str] = None) -> WorkloadSpec:
        """Safely parse LLM JSON into WorkloadSpec."""
        # Extract JSON from code fences if present anywhere in content
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        clean = json_match.group(1).strip() if json_match else content.strip()

        try:
            data = json.loads(clean)
            criteria = data.get("acceptance_criteria")
            if not criteria or not isinstance(criteria, list):
                criteria = ["Feature implemented and verified"]
            return WorkloadSpec(
                name=data.get("name") or suggested_name or "generated-feature",
                description=data.get("description", fallback_prompt),
                acceptance_criteria=criteria,
                initial_files=data.get("initial_files", {}),
            )
        except Exception:
            slug = suggested_name or re.sub(r"[^a-zA-Z0-9]+", "-", fallback_prompt.lower()).strip("-")[:30] or "feature"
            return WorkloadSpec(
                name=slug,
                description=fallback_prompt,
                acceptance_criteria=["Feature implemented and verified"],
                initial_files={},
            )
