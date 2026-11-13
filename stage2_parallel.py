"""Find neighbors and calculate infection from a read-only agent snapshot."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class AgentView:
    """Read-only data passed to neighbor and event workers."""

    agent_id: int
    kind: str
    x: float
    y: float
    infection: float = 0.0
    health: float = 100.0


@dataclass(frozen=True, slots=True)
class NeighborPair:
    """Two agents that are within the configured interaction radius."""

    left_id: int
    right_id: int
    distance: float


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    """One contact from a source agent to a target agent."""

    event_type: str
    source_id: int
    target_id: int
    amount: float


def _split_chunks(values: Sequence, workers: int) -> list[Sequence]:
    if not values:
        return []
    count = max(1, min(workers, len(values)))
    chunk_size = math.ceil(len(values) / count)
    return [values[index : index + chunk_size] for index in range(0, len(values), chunk_size)]


def _neighbor_chunk(
    agent_ids: Sequence[int],
    positions: Mapping[int, tuple[float, float]],
    grid: Mapping[tuple[int, int], Sequence[int]],
    cell_size: float,
    radius: float,
) -> list[NeighborPair]:
    radius_squared = radius * radius
    result: list[NeighborPair] = []
    cell_radius = max(1, math.ceil(radius / cell_size))
    for agent_id in agent_ids:
        x, y = positions[agent_id]
        cell_x = int(x // cell_size)
        cell_y = int(y // cell_size)
        for offset_x in range(-cell_radius, cell_radius + 1):
            for offset_y in range(-cell_radius, cell_radius + 1):
                for other_id in grid.get((cell_x + offset_x, cell_y + offset_y), ()):
                    if other_id <= agent_id:
                        continue
                    other_x, other_y = positions[other_id]
                    delta_x = x - other_x
                    delta_y = y - other_y
                    distance_squared = delta_x * delta_x + delta_y * delta_y
                    if 0 < distance_squared <= radius_squared:
                        result.append(
                            NeighborPair(agent_id, other_id, math.sqrt(distance_squared))
                        )
    return result


class SpatialHashNeighborFinder:
    """Find nearby agents using a spatial hash instead of all-pairs checks.

    A grid cell is roughly the size of the interaction radius. Each agent only
    checks its own cell and nearby cells. Independent chunks of agents can be
    checked concurrently with a thread pool. The workers read the same
    immutable snapshot and return separate result lists, so they do not race.
    """

    def __init__(self, radius: float = 28.0, workers: int = 1, parallel: bool = True) -> None:
        self.radius = radius
        self.cell_size = radius
        self.workers = max(1, workers)
        self.parallel = parallel and self.workers > 1

    def find_pairs(self, agents: Iterable[AgentView]) -> list[NeighborPair]:
        views = tuple(agents)
        if not views:
            return []
        positions = {agent.agent_id: (agent.x, agent.y) for agent in views}
        grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        for agent in views:
            grid[(int(agent.x // self.cell_size), int(agent.y // self.cell_size))].append(agent.agent_id)

        ids = tuple(sorted(positions))
        chunks = _split_chunks(ids, self.workers if self.parallel else 1)
        if self.parallel and len(chunks) > 1:
            with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="neighbors") as pool:
                futures = [
                    pool.submit(
                        _neighbor_chunk,
                        chunk,
                        positions,
                        grid,
                        self.cell_size,
                        self.radius,
                    )
                    for chunk in chunks
                ]
                parts = [future.result() for future in futures]
        else:
            parts = [
                _neighbor_chunk(chunk, positions, grid, self.cell_size, self.radius)
                for chunk in chunks
            ]

        pairs = [pair for part in parts for pair in part]
        pairs.sort(key=lambda pair: (pair.left_id, pair.right_id))
        return pairs


def _event_chunk(
    pairs: Sequence[NeighborPair],
    agents: Mapping[int, AgentView],
    infection_radius: float,
) -> list[SimulationEvent]:
    events: list[SimulationEvent] = []
    for pair in pairs:
        left = agents[pair.left_id]
        right = agents[pair.right_id]
        if left.kind == right.kind:
            continue
        human, zombie = (left, right) if left.kind == "human" else (right, left)
        intensity = max(0.0, 1.0 - pair.distance / infection_radius)
        events.append(
            SimulationEvent(
                event_type="infection",
                source_id=zombie.agent_id,
                target_id=human.agent_id,
                amount=0.12 * intensity,
            )
        )
    return events


def _event_delta_chunk(events: Sequence[SimulationEvent]) -> dict[int, float]:
    deltas: dict[int, float] = defaultdict(float)
    for event in events:
        if event.event_type == "infection":
            deltas[event.target_id] += event.amount
    return dict(deltas)


class ParallelEventProcessor:
    """Build and reduce interaction events with independent worker chunks."""

    def __init__(self, workers: int = 1, parallel: bool = True) -> None:
        self.workers = max(1, workers)
        self.parallel = parallel and self.workers > 1

    def build_events(
        self,
        agents: Iterable[AgentView],
        pairs: Sequence[NeighborPair],
        infection_radius: float = 28.0,
    ) -> list[SimulationEvent]:
        agent_map = {agent.agent_id: agent for agent in agents}
        chunks = _split_chunks(pairs, self.workers if self.parallel else 1)
        if self.parallel and len(chunks) > 1:
            with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="events") as pool:
                futures = [pool.submit(_event_chunk, chunk, agent_map, infection_radius) for chunk in chunks]
                parts = [future.result() for future in futures]
        else:
            parts = [_event_chunk(chunk, agent_map, infection_radius) for chunk in chunks]
        events = [event for part in parts for event in part]
        events.sort(key=lambda event: (event.target_id, event.source_id, event.event_type))
        return events

    def apply_events(
        self,
        agents: Mapping[int, object],
        events: Sequence[SimulationEvent],
    ) -> int:
        """Apply event deltas in one deterministic commit on the main thread.

        Workers only calculate per-target deltas. The final mutation happens
        here, preventing two workers from racing while updating one human.
        The return value is the number of humans converted by this batch.
        """

        chunks = _split_chunks(events, self.workers if self.parallel else 1)
        if self.parallel and len(chunks) > 1:
            with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="event-reduce") as pool:
                futures = [pool.submit(_event_delta_chunk, chunk) for chunk in chunks]
                partials = [future.result() for future in futures]
        else:
            partials = [_event_delta_chunk(chunk) for chunk in chunks]

        deltas: dict[int, float] = defaultdict(float)
        for partial in partials:
            for agent_id, delta in partial.items():
                deltas[agent_id] += delta

        conversions = 0
        for agent_id in sorted(deltas):
            agent = agents.get(agent_id)
            if agent is None or getattr(agent, "kind", None) != "human":
                continue
            agent.infection = min(1.0, agent.infection + deltas[agent_id])
            if agent.infection >= 1.0:
                agent.kind = "zombie"
                agent.infection = 0.0
                conversions += 1
        return conversions


__all__ = [
    "AgentView",
    "NeighborPair",
    "ParallelEventProcessor",
    "SimulationEvent",
    "SpatialHashNeighborFinder",
]
