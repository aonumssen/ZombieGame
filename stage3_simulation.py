"""Stage 3 entry point for the existing large-agent simulation."""

from dataclasses import replace
from time import perf_counter

from stage2_parallel import AgentView, NeighborPair, SimulationEvent
from stage2_simulation import ScalableSimulation, Stage2StepMetrics
from stage3_events import Backend, TargetEventProcessor


class Stage3Simulation(ScalableSimulation):
    """Use the Stage 2 tick with a different event processor."""

    def __init__(self, *, backend: Backend = "processes", workers: int = 4, **options) -> None:
        # Keep neighbor finding serial so event backends can be compared directly.
        super().__init__(workers=workers, parallel=False, **options)
        self.events = TargetEventProcessor(backend, workers)

    def __enter__(self) -> "Stage3Simulation":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.events.close()

    def step(self, dt: float = 0.05) -> Stage2StepMetrics:
        started = perf_counter()
        motion = [
            (agent, agent.x, agent.y, agent.vx, agent.vy)
            for agent in self.agents.values()
        ]
        try:
            metrics = super().step(dt)
        except Exception:
            # Event changes wait for all workers. Roll back movement too.
            for agent, x, y, vx, vy in motion:
                agent.x, agent.y, agent.vx, agent.vy = x, y, vx, vy
            raise
        return replace(metrics, step_time_ms=(perf_counter() - started) * 1_000)

    def _process_events(
        self, views: tuple[AgentView, ...], pairs: list[NeighborPair]
    ) -> tuple[list[SimulationEvent], int]:
        return self.events.process(views, pairs, self.agents)
