"""Scalable, database-friendly population simulation for Zombie Game Stage 2."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Iterable

from stage2_parallel import (
    AgentView,
    NeighborPair,
    ParallelEventProcessor,
    SimulationEvent,
    SpatialHashNeighborFinder,
)


WORLD_WIDTH = 2_000.0
WORLD_HEIGHT = 2_000.0


@dataclass(slots=True)
class ScalableAgent:
    """Mutable live state for one Stage 2 agent."""

    agent_id: int
    kind: str
    x: float
    y: float
    vx: float
    vy: float
    infection: float = 0.0
    health: float = 100.0

    def update_position(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x < 0 or self.x > WORLD_WIDTH:
            self.vx *= -1
            self.x = min(WORLD_WIDTH, max(0.0, self.x))
        if self.y < 0 or self.y > WORLD_HEIGHT:
            self.vy *= -1
            self.y = min(WORLD_HEIGHT, max(0.0, self.y))

    def view(self) -> AgentView:
        return AgentView(
            agent_id=self.agent_id,
            kind=self.kind,
            x=self.x,
            y=self.y,
            infection=self.infection,
            health=self.health,
        )


@dataclass(frozen=True, slots=True)
class Stage2StepMetrics:
    """Measurements for one simulation step."""

    step: int
    simulated_seconds: float
    active_agents: int
    humans: int
    zombies: int
    neighbor_pairs: int
    events_processed: int
    conversions: int
    step_time_ms: float
    neighbor_time_ms: float
    event_time_ms: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "step": self.step,
            "simulated_seconds": self.simulated_seconds,
            "active_agents": self.active_agents,
            "humans": self.humans,
            "zombies": self.zombies,
            "neighbor_pairs": self.neighbor_pairs,
            "events_processed": self.events_processed,
            "conversions": self.conversions,
            "step_time_ms": self.step_time_ms,
            "neighbor_time_ms": self.neighbor_time_ms,
            "event_time_ms": self.event_time_ms,
        }


class ScalableSimulation:
    """A deterministic many-agent simulation with pluggable parallel stages.

    The engine keeps live objects in memory for fast updates. A database store
    can receive snapshots after each step, so persistence is separate from
    neighbor finding and event processing. Both parallel stages consume an
    immutable ``AgentView`` snapshot and commit changes centrally.
    """

    def __init__(
        self,
        agent_count: int = 5_000,
        zombie_ratio: float = 0.20,
        seed: int = 7,
        workers: int = 4,
        parallel: bool = True,
        neighbor_radius: float = 28.0,
    ) -> None:
        if agent_count < 1:
            raise ValueError("agent_count must be positive")
        if not 0.0 <= zombie_ratio <= 1.0:
            raise ValueError("zombie_ratio must be between 0 and 1")
        self.agent_count = agent_count
        self.zombie_ratio = zombie_ratio
        self.seed = seed
        self.workers = max(1, workers)
        self.parallel = parallel
        self.rng = random.Random(seed)
        self.neighbor_finder = SpatialHashNeighborFinder(
            radius=neighbor_radius,
            workers=self.workers,
            parallel=parallel,
        )
        self.event_processor = ParallelEventProcessor(
            workers=self.workers,
            parallel=parallel,
        )
        self.agents: dict[int, ScalableAgent] = {}
        self.step_number = 0
        self.simulated_seconds = 0.0
        self.last_pairs: list[NeighborPair] = []
        self.last_events: list[SimulationEvent] = []
        self.reset()

    def reset(self) -> None:
        self.rng = random.Random(self.seed)
        self.agents = {}
        zombie_count = max(1, round(self.agent_count * self.zombie_ratio))
        for agent_id in range(self.agent_count):
            kind = "zombie" if agent_id < zombie_count else "human"
            speed = self.rng.uniform(18.0, 40.0) if kind == "zombie" else self.rng.uniform(24.0, 52.0)
            angle = self.rng.uniform(0.0, math.tau)
            self.agents[agent_id] = ScalableAgent(
                agent_id=agent_id,
                kind=kind,
                x=self.rng.uniform(0.0, WORLD_WIDTH),
                y=self.rng.uniform(0.0, WORLD_HEIGHT),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
            )
        self.step_number = 0
        self.simulated_seconds = 0.0
        self.last_pairs = []
        self.last_events = []

    def snapshot(self) -> tuple[AgentView, ...]:
        return tuple(self.agents[agent_id].view() for agent_id in sorted(self.agents))

    def step(self, dt: float = 0.05) -> Stage2StepMetrics:
        """Advance one fixed step and return measurements for that step."""

        import time

        dt = max(0.0, min(0.25, dt))
        step_started = time.perf_counter()
        for agent in self.agents.values():
            agent.update_position(dt)
        views = self.snapshot()

        neighbor_started = time.perf_counter()
        pairs = self.neighbor_finder.find_pairs(views)
        neighbor_time_ms = (time.perf_counter() - neighbor_started) * 1_000

        event_started = time.perf_counter()
        events, conversions = self._process_events(views, pairs)
        event_time_ms = (time.perf_counter() - event_started) * 1_000

        self.last_pairs = pairs
        self.last_events = events
        self.step_number += 1
        self.simulated_seconds += dt
        humans = sum(agent.kind == "human" for agent in self.agents.values())
        zombies = len(self.agents) - humans
        return Stage2StepMetrics(
            step=self.step_number,
            simulated_seconds=self.simulated_seconds,
            active_agents=len(self.agents),
            humans=humans,
            zombies=zombies,
            neighbor_pairs=len(pairs),
            events_processed=len(events),
            conversions=conversions,
            step_time_ms=(time.perf_counter() - step_started) * 1_000,
            neighbor_time_ms=neighbor_time_ms,
            event_time_ms=event_time_ms,
        )

    def _process_events(
        self, views: tuple[AgentView, ...], pairs: list[NeighborPair]
    ) -> tuple[list[SimulationEvent], int]:
        events = self.event_processor.build_events(views, pairs)
        return events, self.event_processor.apply_events(self.agents, events)

    def run(self, steps: int, dt: float = 0.05) -> list[Stage2StepMetrics]:
        if steps < 0:
            raise ValueError("steps must not be negative")
        return [self.step(dt) for _ in range(steps)]

    def agent_rows(self) -> Iterable[ScalableAgent]:
        return (self.agents[agent_id] for agent_id in sorted(self.agents))


__all__ = [
    "ScalableAgent",
    "ScalableSimulation",
    "Stage2StepMetrics",
    "WORLD_HEIGHT",
    "WORLD_WIDTH",
]
