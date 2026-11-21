"""DAGScheduler: Directed Acyclic Graph dependency resolution, topological wave planning, and artifact cascading."""

from __future__ import annotations

import collections
from typing import Dict, List

from triad.core.models import TaskSlice


class CircularDependencyError(Exception):
    """Raised when task slices form a cyclic dependency loop."""
    pass


class MissingDependencyError(Exception):
    """Raised when a task slice depends on an unknown slice ID."""
    pass


class DAGScheduler:
    """
    Constructs, validates, and schedules a Directed Acyclic Graph of TaskSlices.
    Organizes slices into parallel execution waves and manages artifact cascading.
    """

    def __init__(self, slices: List[TaskSlice]):
        self.slices: Dict[str, TaskSlice] = {}
        for s in slices:
            if s.slice_id in self.slices:
                raise ValueError(
                    f"Duplicate task slice_id in workload: '{s.slice_id}'"
                )
            self.slices[s.slice_id] = s
        self._validate_dependencies()
        self.waves: List[List[TaskSlice]] = self._compute_topological_waves()

    def _validate_dependencies(self) -> None:
        """Verify that all referenced dependencies exist and graph has no cycles."""
        # 1. Existence check
        for slice_id, s in self.slices.items():
            for dep in s.dependencies:
                if dep not in self.slices:
                    raise MissingDependencyError(
                        f"Task slice '{slice_id}' depends on '{dep}', which does not exist in workload."
                    )

        # 2. Cycle detection via Kahn's algorithm / in-degree
        in_degree: Dict[str, int] = {sid: 0 for sid in self.slices}
        adj: Dict[str, List[str]] = {sid: [] for sid in self.slices}

        for sid, s in self.slices.items():
            for dep in s.dependencies:
                adj[dep].append(sid)
                in_degree[sid] += 1

        queue = collections.deque([sid for sid, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            node = queue.popleft()
            visited_count += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(self.slices):
            # Find remaining cycles for detailed error diagnostic
            cycle_nodes = [sid for sid, deg in in_degree.items() if deg > 0]
            raise CircularDependencyError(
                f"Circular dependency detected among task slices: {cycle_nodes}"
            )

    def _compute_topological_waves(self) -> List[List[TaskSlice]]:
        """
        Partition slices into sequential waves where each wave contains slices
        whose dependencies were satisfied by previous waves.
        Slices in the same wave can run completely in parallel!
        """
        # Node depth in DAG (longest path from any root)
        depths: Dict[str, int] = {sid: 0 for sid in self.slices}

        # Topological traversal
        in_degree = {sid: len(s.dependencies) for sid, s in self.slices.items()}
        adj: Dict[str, List[str]] = {sid: [] for sid in self.slices}
        for sid, s in self.slices.items():
            for dep in s.dependencies:
                adj[dep].append(sid)

        queue = collections.deque([sid for sid, deg in in_degree.items() if deg == 0])

        while queue:
            curr = queue.popleft()
            curr_depth = depths[curr]
            for neighbor in adj[curr]:
                depths[neighbor] = max(depths[neighbor], curr_depth + 1)
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        max_depth = max(depths.values()) if depths else 0
        waves: List[List[TaskSlice]] = [[] for _ in range(max_depth + 1)]

        for sid, s in self.slices.items():
            d = depths[sid]
            waves[d].append(s)

        # Sort within each wave by priority or slice_id
        for w in waves:
            w.sort(key=lambda s: (-getattr(s, "priority", 1), s.slice_id))

        return waves

    def get_upstream_dependencies(self, slice_id: str) -> List[TaskSlice]:
        """Get direct TaskSlice objects this slice depends upon."""
        s = self.slices[slice_id]
        return [self.slices[dep] for dep in s.dependencies]

    def to_mermaid(self) -> str:
        """Render the DAG in Mermaid flowchart syntax."""
        lines = [
            "flowchart TD",
            "    classDef waveStyle fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;",
        ]

        # Draw waves as subgraphs
        for wave_idx, wave in enumerate(self.waves):
            lines.append(f'    subgraph Wave_{wave_idx} ["Wave {wave_idx + 1} (Parallel Fan-Out)"]')
            for s in wave:
                safe_title = s.title.replace('"', "'")
                lines.append(f'        {s.slice_id}["{s.slice_id}<br><b>{safe_title}</b>"]')
            lines.append("    end")

        # Draw dependency arrows
        for sid, s in self.slices.items():
            for dep in s.dependencies:
                lines.append(f"    {dep} --> {sid}")

        return "\n".join(lines)

    def to_ascii(self) -> str:
        """Render the execution waves in a human-readable ASCII layout."""
        lines = ["=== Triad Swarm Execution Waves (DAG Topology) ==="]
        for idx, wave in enumerate(self.waves):
            lines.append(f"Wave {idx + 1} [{len(wave)} parallel tasks]:")
            for s in wave:
                deps = f" -> depends on {s.dependencies}" if s.dependencies else " (Root / Independent)"
                lines.append(f"   • {s.slice_id}: {s.title}{deps}")
        return "\n".join(lines)
